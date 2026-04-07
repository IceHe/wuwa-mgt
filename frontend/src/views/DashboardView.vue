<template>
  <section class="panel">
    <div class="actions dashboard-toolbar">
      <div class="actions dashboard-toolbar-main">
        <h2 style="margin: 0">每日每周总览</h2>
        <div class="refresh-indicator" title="每 60 秒自动刷新">
          <div
            class="refresh-pie"
            :class="{ urgent: countdownSeconds <= 8 }"
            :style="{
              background: `conic-gradient(${countdownSeconds <= 8 ? '#c62026' : '#1664d9'} ${countdownRemainProgress * 360}deg, #dce3f1 ${countdownRemainProgress * 360}deg 360deg)`,
            }"
            aria-hidden="true"
          ></div>
          <span class="refresh-text">{{ countdownSeconds }}s</span>
        </div>
        <div class="cleanup-total-indicator" title="当前所有账号清日常总时长">
          <span class="meta">当前清日常总时长</span>
          <strong class="cleanup-total-indicator-text">{{ formatDurationMmSs(currentCleanupTotalSeconds) }}</strong>
        </div>
      </div>
      <div class="actions dashboard-toolbar-side">
        <label style="max-width: 220px">
          排序方式
          <select v-model="sortMode">
            <option value="eta">最近满体</option>
            <option value="recent_edit">最近修改</option>
            <option value="oldest_edit">最久未修改</option>
            <option value="abbr">账号缩写</option>
          </select>
        </label>
      </div>
    </div>

    <div class="table-wrap">
      <table class="overview-table">
        <thead>
          <tr>
            <th>账号</th>
            <th>备忘</th>
            <th>无音区</th>
            <th>体力</th>
            <th>满体力时间</th>
            <th>体力快捷操作</th>
            <th>清日常时长</th>
            <th>日常</th>
            <th>聚落</th>
            <th>门扉</th>
            <th>周本</th>
            <th>定向合成</th>
          </tr>
        </thead>
        <tbody>
          <DashboardRow
            v-for="acc in sortedAccounts"
            :key="acc.id"
            :account="acc"
            :tacet="tacetInput[acc.id] || ''"
            :statuses="{
              daily_task: dailyTaskStatusInput[acc.id],
              daily_nest: dailyNestStatusInput[acc.id],
              weekly_door: weeklyDoorStatusInput[acc.id],
              weekly_boss: weeklyBossStatusInput[acc.id],
              weekly_synthesis: weeklySynthesisStatusInput[acc.id],
            }"
            :all-done-flags="allDoneFlags"
            :all-done-row="isAllChecklistCompleted(acc.id)"
            :highlighted="isHighlighted(acc.id)"
            :cleanup-busy="!!cleanupBusyMap[acc.id]"
            :clock-now-ms="clockNowMs"
            @toggle-highlight="toggleHighlight"
            @update-tacet="updateTacet"
            @open-energy-editor="openEnergyEditor"
            @open-remark-editor="openRemarkEditor"
            @gain="gain"
            @spend="spend"
            @toggle-cleanup="toggleCleanupTimer"
            @cycle-flag="cycleDailyFlag"
          />
        </tbody>
      </table>
    </div>

    <EnergyEditorModal
      :visible="energyEditor.visible"
      :account="selectedEnergyAccount"
      :state="energyEditor"
      :saving="energyEditor.saving"
      @close="closeEnergyEditor"
      @save="submitEnergyEditor"
      @set-mode="setEnergyEditorMode"
      @update-field="updateEnergyEditorField"
    />

    <RemarkEditorModal
      :visible="remarkEditor.visible"
      :account="selectedRemarkAccount"
      :value="remarkEditor.value"
      :saving="remarkEditor.saving"
      @close="closeRemarkEditor"
      @save="submitRemarkEditor"
      @update:value="updateRemarkEditorValue"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import DashboardRow from '../components/DashboardRow.vue'
import EnergyEditorModal from '../components/EnergyEditorModal.vue'
import RemarkEditorModal from '../components/RemarkEditorModal.vue'
import { api } from '../api'
import { loadStoredValue, saveStoredValue } from '../utils/persistentState'

const REFRESH_INTERVAL_SECONDS = 60
const LAST_EDIT_STORAGE_KEY = 'wuwa_dashboard_last_edit_map_v1'
const SORT_MODE_STORAGE_KEY = 'wuwa_dashboard_sort_mode_v1'
const SORT_MODE_OPTIONS = ['eta', 'recent_edit', 'oldest_edit', 'abbr']
const STATUS_FLOW = ['todo', 'done', 'skipped']

const accounts = ref([])
const sortMode = ref(loadStoredValue(SORT_MODE_STORAGE_KEY, 'eta', SORT_MODE_OPTIONS))
const tacetInput = ref({})
const dailyTaskStatusInput = ref({})
const dailyNestStatusInput = ref({})
const weeklyDoorStatusInput = ref({})
const weeklyBossStatusInput = ref({})
const weeklySynthesisStatusInput = ref({})
const highlightedAccountId = ref(null)
const countdownSeconds = ref(REFRESH_INTERVAL_SECONDS)
const cleanupBusyMap = ref({})
const lastEditedMap = ref({})
const orderFrozen = ref(false)
const frozenOrderIds = ref([])
const clockNowMs = ref(Date.now())
const energyEditor = ref({
  visible: false,
  targetId: '',
  mode: 'current',
  currentWaveplate: '',
  currentCrystal: '',
  dayOffset: '0',
  time: '',
  durationHours: '0',
  durationMinutes: '0',
  durationSeconds: '0',
  saving: false,
})
const remarkEditor = ref({
  visible: false,
  targetId: '',
  value: '',
  saving: false,
})

let fetchTimer = null
let countdownTimer = null
let refreshing = false

function getSortedRowsByMode() {
  const rows = [...accounts.value]
  if (sortMode.value === 'recent_edit') {
    rows.sort((a, b) => Number(lastEditedMap.value[a.id] || 0) - Number(lastEditedMap.value[b.id] || 0))
    rows.reverse()
    return rows
  }
  if (sortMode.value === 'oldest_edit') {
    rows.sort((a, b) => Number(lastEditedMap.value[a.id] || 0) - Number(lastEditedMap.value[b.id] || 0))
    return rows
  }
  if (sortMode.value === 'abbr') {
    rows.sort((a, b) => String(a.abbr || '').localeCompare(String(b.abbr || '')))
    return rows
  }
  rows.sort((a, b) => new Date(a.eta_waveplate_full).getTime() - new Date(b.eta_waveplate_full).getTime())
  return rows
}

const sortedAccounts = computed(() => {
  const rows = getSortedRowsByMode()
  if (!orderFrozen.value || !frozenOrderIds.value.length) return rows

  const orderMap = new Map(frozenOrderIds.value.map((id, idx) => [String(id), idx]))
  rows.sort((a, b) => {
    const ia = orderMap.get(String(a.id))
    const ib = orderMap.get(String(b.id))
    if (ia === undefined && ib === undefined) return 0
    if (ia === undefined) return 1
    if (ib === undefined) return -1
    return ia - ib
  })
  return rows
})

const countdownProgress = computed(() => {
  const done = REFRESH_INTERVAL_SECONDS - countdownSeconds.value
  return Math.min(1, Math.max(0, done / REFRESH_INTERVAL_SECONDS))
})

const countdownRemainProgress = computed(() => 1 - countdownProgress.value)
const currentCleanupTotalSeconds = computed(() => (
  accounts.value.reduce((sum, acc) => sum + getCleanupDisplaySeconds(acc), 0)
))
const allDoneFlags = computed(() => ({
  daily_task: isAllCompleted(dailyTaskStatusInput.value),
  daily_nest: isAllCompleted(dailyNestStatusInput.value),
  weekly_door: isAllCompleted(weeklyDoorStatusInput.value),
  weekly_boss: isAllCompleted(weeklyBossStatusInput.value),
  weekly_synthesis: isAllCompleted(weeklySynthesisStatusInput.value),
}))

const selectedEnergyAccount = computed(() => (
  accounts.value.find((item) => String(item.id) === String(energyEditor.value.targetId)) || null
))
const selectedRemarkAccount = computed(() => (
  accounts.value.find((item) => String(item.id) === String(remarkEditor.value.targetId)) || null
))

const fullDateMin = computed(() => getDateKeyInTZ(new Date()))

async function refresh() {
  if (refreshing) return
  refreshing = true
  try {
    const rows = await api.listDashboardAccounts()
    accounts.value = rows
    for (const acc of rows) {
      tacetInput.value[acc.id] = acc.tacet || ''
      dailyTaskStatusInput.value[acc.id] = normalizeStatus(acc.daily_task_status, acc.daily_task)
      dailyNestStatusInput.value[acc.id] = normalizeStatus(acc.daily_nest_status, acc.daily_nest)
      weeklyDoorStatusInput.value[acc.id] = normalizeStatus(acc.weekly_door_status, acc.weekly_door)
      weeklyBossStatusInput.value[acc.id] = normalizeStatus(acc.weekly_boss_status, acc.weekly_boss)
      weeklySynthesisStatusInput.value[acc.id] = normalizeStatus(acc.weekly_synthesis_status, acc.weekly_synthesis)
      cleanupBusyMap.value[acc.id] = false
    }
    syncHighlightedAccountId()
  } finally {
    refreshing = false
  }
}

function replaceAccountPatch(id, patch) {
  const key = String(id)
  let nextAccount = null
  accounts.value = accounts.value.map((account) => {
    if (String(account.id) !== key) return account
    nextAccount = { ...account, ...patch }
    return nextAccount
  })
  return nextAccount
}

function applyEnergyPayload(id, payload) {
  replaceAccountPatch(id, {
    current_waveplate: payload.current_waveplate,
    current_waveplate_crystal: payload.current_waveplate_crystal,
    full_waveplate_at: payload.full_waveplate_at,
    eta_waveplate_full: payload.eta_waveplate_full,
    waveplate_full_in_minutes: payload.waveplate_full_in_minutes,
    warn_level: payload.warn_level,
  })
}

function applyCleanupState(id, state) {
  replaceAccountPatch(id, {
    cleanup_today_total_sec: state.today_total_sec,
    cleanup_today_paused_sec: state.today_paused_sec,
    cleanup_running: state.running,
    cleanup_running_started_at: state.running_started_at,
  })
}

function getCleanupDisplaySeconds(acc) {
  const paused = Number(acc.cleanup_today_paused_sec || 0)
  if (!acc.cleanup_running || !acc.cleanup_running_started_at) {
    const total = Number(acc.cleanup_today_total_sec || paused)
    return Math.max(paused, total)
  }
  const startedAtMs = new Date(acc.cleanup_running_started_at).getTime()
  if (Number.isNaN(startedAtMs)) return Number(acc.cleanup_today_total_sec || paused)
  const live = Math.max(0, Math.floor((clockNowMs.value - startedAtMs) / 1000))
  return paused + live
}

function formatDurationMmSs(totalSeconds) {
  const sec = Math.max(0, Number(totalSeconds) || 0)
  const mm = String(Math.floor(sec / 60)).padStart(2, '0')
  const ss = String(sec % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function getTZParts(dt) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(dt)
  const out = {}
  for (const p of parts) {
    if (p.type !== 'literal') out[p.type] = p.value
  }
  return out
}

function getDateKeyInTZ(dt) {
  const p = getTZParts(dt)
  return `${p.year}-${p.month}-${p.day}`
}

function addDaysToDateKey(dateKey, days) {
  const [y, m, d] = dateKey.split('-').map((v) => Number(v))
  const base = new Date(Date.UTC(y, m - 1, d))
  base.setUTCDate(base.getUTCDate() + days)
  const yy = base.getUTCFullYear()
  const mm = String(base.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(base.getUTCDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

function timeToInputValue(dt) {
  const parts = getTZParts(dt)
  return `${parts.hour}:${parts.minute}:${parts.second}`
}

function normalizeTimeValue(timeText) {
  const raw = String(timeText || '').trim()
  if (/^\d{2}:\d{2}$/.test(raw)) return `${raw}:00`
  return raw
}

function normalizedId(id) {
  if (id === null || id === undefined) return ''
  return String(id)
}

function isHighlighted(id) {
  return normalizedId(id) === normalizedId(highlightedAccountId.value)
}

function toggleHighlight(id) {
  const key = normalizedId(id)
  highlightedAccountId.value = normalizedId(highlightedAccountId.value) === key ? null : key
}

function normalizeStatus(status, boolFallback = false) {
  if (typeof status === 'string' && STATUS_FLOW.includes(status)) return status
  return boolFallback ? 'done' : 'todo'
}

function isCompletedStatus(status) {
  const normalized = normalizeStatus(status)
  return normalized === 'done' || normalized === 'skipped'
}

function nextStatus(status) {
  const idx = STATUS_FLOW.indexOf(normalizeStatus(status))
  return STATUS_FLOW[(idx + 1) % STATUS_FLOW.length]
}

function isAllCompleted(map) {
  const ids = accounts.value.map((acc) => normalizedId(acc.id))
  if (!ids.length) return false
  return ids.every((id) => isCompletedStatus(map[id]))
}

function isAllChecklistCompleted(id) {
  return (
    isCompletedStatus(dailyTaskStatusInput.value[id]) &&
    isCompletedStatus(dailyNestStatusInput.value[id]) &&
    isCompletedStatus(weeklySynthesisStatusInput.value[id])
  )
}

async function spend(id, cost) {
  try {
    const payload = await api.spendWaveplate(id, cost)
    applyEnergyPayload(id, payload)
    markEdited(id)
  } catch (err) {
    alert(`扣减失败：${err.message || '体力不足'}`)
  }
}

async function gain(id, amount) {
  try {
    const payload = await api.gainWaveplate(id, amount)
    applyEnergyPayload(id, payload)
    markEdited(id)
  } catch (err) {
    alert(`增加失败：${err.message || '请稍后重试'}`)
  }
}

function openEnergyEditor(account) {
  const eta = new Date(account.eta_waveplate_full)
  energyEditor.value = {
    visible: true,
    targetId: String(account.id),
    mode: 'current',
    currentWaveplate: String(account.current_waveplate),
    currentCrystal: String(account.current_waveplate_crystal),
    dayOffset: '0',
    time: timeToInputValue(eta),
    durationHours: '0',
    durationMinutes: '0',
    durationSeconds: '0',
    saving: false,
  }
}

function closeEnergyEditor(force = false) {
  if (!force && energyEditor.value.saving) return
  energyEditor.value.visible = false
}

function setEnergyEditorMode(mode) {
  energyEditor.value.mode = mode
}

function updateEnergyEditorField(field, value) {
  energyEditor.value[field] = value
}

function openRemarkEditor(account) {
  remarkEditor.value = {
    visible: true,
    targetId: String(account.id),
    value: String(account.remark || ''),
    saving: false,
  }
}

function closeRemarkEditor(force = false) {
  if (!force && remarkEditor.value.saving) return
  remarkEditor.value.visible = false
}

function updateRemarkEditorValue(value) {
  remarkEditor.value.value = value
}

async function submitEnergyEditor() {
  const state = energyEditor.value
  if (!state.targetId) return
  state.saving = true
  try {
    let payload
    if (state.mode === 'current') {
      const waveplate = Number(state.currentWaveplate)
      const crystal = Number(state.currentCrystal)
      if (!Number.isInteger(waveplate) || waveplate < 0 || waveplate > 240) {
        alert('体力范围应为 0~240')
        return
      }
      if (!Number.isInteger(crystal) || crystal < 0 || crystal > 480) {
        alert('体力结晶范围应为 0~480')
        return
      }
      payload = await api.setCurrentEnergy(state.targetId, waveplate, crystal)
    } else if (state.mode === 'absolute') {
      const dayOffsetNum = Number(state.dayOffset)
      if (!Number.isInteger(dayOffsetNum) || dayOffsetNum < 0 || dayOffsetNum > 1) {
        alert('日期仅支持今天或明天')
        return
      }
      const dateText = addDaysToDateKey(fullDateMin.value, dayOffsetNum)
      const timeText = normalizeTimeValue(state.time)
      if (!timeText) {
        alert('请选择时间')
        return
      }
      const fullAt = new Date(`${dateText}T${timeText}+08:00`)
      if (Number.isNaN(fullAt.getTime())) {
        alert('满体力时间格式无效')
        return
      }
      payload = await api.setFullWaveplateTime(state.targetId, fullAt.toISOString())
    } else {
      const h = Number(state.durationHours)
      const m = Number(state.durationMinutes)
      const s = Number(state.durationSeconds)
      if (!Number.isInteger(h) || h < 0 || h > 24) {
        alert('小时范围应为 0~24')
        return
      }
      if (!Number.isInteger(m) || m < 0 || m > 59 || !Number.isInteger(s) || s < 0 || s > 59) {
        alert('分钟和秒范围应为 0~59')
        return
      }
      const deltaSeconds = h * 3600 + m * 60 + s
      if (deltaSeconds > 86400) {
        alert('满体力剩余时间不能超过 24 小时')
        return
      }
      payload = await api.setFullWaveplateTime(state.targetId, new Date(Date.now() + deltaSeconds * 1000).toISOString())
    }
    applyEnergyPayload(state.targetId, payload)
    markEdited(state.targetId)
    closeEnergyEditor(true)
  } catch (err) {
    alert(`设置失败：${err.message || '请稍后重试'}`)
  } finally {
    state.saving = false
  }
}

async function submitRemarkEditor() {
  const state = remarkEditor.value
  if (!state.targetId) return
  state.saving = true
  try {
    const normalized = String(state.value || '').trim()
    await api.updateAccount(state.targetId, { remark: normalized })
    replaceAccountPatch(state.targetId, { remark: normalized })
    markEdited(state.targetId)
    closeRemarkEditor(true)
  } catch (err) {
    alert(`保存失败：${err.message || '请稍后重试'}`)
  } finally {
    state.saving = false
  }
}

function statusMapByKey(flagKey) {
  if (flagKey === 'daily_task') return dailyTaskStatusInput.value
  if (flagKey === 'daily_nest') return dailyNestStatusInput.value
  if (flagKey === 'weekly_door') return weeklyDoorStatusInput.value
  if (flagKey === 'weekly_boss') return weeklyBossStatusInput.value
  return weeklySynthesisStatusInput.value
}

async function cycleDailyFlag(id, flagKey) {
  const map = statusMapByKey(flagKey)
  const current = map[id]
  const next = nextStatus(current)
  map[id] = next
  try {
    await api.setCheckin(id, flagKey, next)
    markEdited(id)
    applyStatusToAccount(id, flagKey, next)
  } catch (err) {
    alert(`保存失败：${err.message || '请稍后重试'}`)
    await refresh()
  }
}

function applyStatusToAccount(id, flagKey, status) {
  const normalized = normalizeStatus(status)
  const boolValue = normalized === 'done' || normalized === 'skipped'
  const patch = {}
  if (flagKey === 'daily_task') {
    patch.daily_task_status = normalized
    patch.daily_task = boolValue
  } else if (flagKey === 'daily_nest') {
    patch.daily_nest_status = normalized
    patch.daily_nest = boolValue
  } else if (flagKey === 'weekly_door') {
    patch.weekly_door_status = normalized
    patch.weekly_door = boolValue
  } else if (flagKey === 'weekly_boss') {
    patch.weekly_boss_status = normalized
    patch.weekly_boss = boolValue
  } else if (flagKey === 'weekly_synthesis') {
    patch.weekly_synthesis_status = normalized
    patch.weekly_synthesis = boolValue
  }
  replaceAccountPatch(id, patch)
}

async function updateTacet(id, tacet) {
  tacetInput.value[id] = tacet
  replaceAccountPatch(id, { tacet })
  try {
    await api.setTacet(id, tacet)
    markEdited(id)
  } catch (err) {
    alert(`保存失败：${err.message || '请稍后重试'}`)
    await refresh()
  }
}

async function toggleCleanupTimer(acc) {
  const id = acc.id
  if (cleanupBusyMap.value[id]) return
  cleanupBusyMap.value[id] = true
  try {
    const payload = acc.cleanup_running
      ? await api.pauseCleanupTimer(id)
      : await api.startCleanupTimer(id)
    applyCleanupState(id, payload)
    markEdited(id)
  } catch (err) {
    alert(`计时操作失败：${err.message || '请稍后重试'}`)
    await refresh()
  } finally {
    cleanupBusyMap.value[id] = false
  }
}

function markEdited(id) {
  if (!orderFrozen.value) {
    frozenOrderIds.value = getSortedRowsByMode().map((row) => row.id)
    orderFrozen.value = true
  }
  const key = normalizedId(id)
  highlightedAccountId.value = key
  lastEditedMap.value[key] = Date.now()
  saveLastEditedMap()
}

function saveLastEditedMap() {
  try {
    localStorage.setItem(LAST_EDIT_STORAGE_KEY, JSON.stringify(lastEditedMap.value))
  } catch {
    // Ignore storage failures.
  }
}

function loadLastEditedMap() {
  try {
    const raw = localStorage.getItem(LAST_EDIT_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      lastEditedMap.value = parsed
    }
  } catch {
    // Ignore malformed data.
  }
}

function syncHighlightedAccountId() {
  const accountIds = new Set(accounts.value.map((acc) => normalizedId(acc.id)))
  const current = normalizedId(highlightedAccountId.value)
  if (current && accountIds.has(current)) return
  let latestId = ''
  let latestTs = 0
  for (const [id, ts] of Object.entries(lastEditedMap.value)) {
    const key = normalizedId(id)
    const n = Number(ts || 0)
    if (!accountIds.has(key)) continue
    if (n > latestTs) {
      latestTs = n
      latestId = key
    }
  }
  highlightedAccountId.value = latestId || null
}

onMounted(async () => {
  loadLastEditedMap()
  await refresh()
  countdownSeconds.value = REFRESH_INTERVAL_SECONDS
  fetchTimer = setInterval(async () => {
    await refresh()
    countdownSeconds.value = REFRESH_INTERVAL_SECONDS
  }, REFRESH_INTERVAL_SECONDS * 1000)
  countdownTimer = setInterval(() => {
    clockNowMs.value = Date.now()
    if (countdownSeconds.value > 0) countdownSeconds.value -= 1
  }, 1000)
})

watch(sortMode, () => {
  saveStoredValue(SORT_MODE_STORAGE_KEY, sortMode.value)
  orderFrozen.value = false
  frozenOrderIds.value = []
})

onUnmounted(() => {
  if (fetchTimer) clearInterval(fetchTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
