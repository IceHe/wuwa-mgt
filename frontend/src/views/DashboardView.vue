<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <div class="actions" style="align-items: center">
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
      </div>
      <div class="actions" style="align-items: center">
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
          <th>ID / 尾号 / 昵称</th>
          <th>无音区</th>
          <th>体力</th>
          <th>溢出</th>
          <th>满体力</th>
          <th>体力快捷操作</th>
          <th>日常</th>
          <th>聚落</th>
          <th>门扉</th>
          <th>周本</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="acc in sortedAccounts"
          :key="acc.id"
          @click="toggleHighlight(acc.id)"
          :class="[
            acc.warn_level,
            {
              edited: isHighlighted(acc.id),
              'all-done-row': isAllChecklistCompleted(acc.id),
            },
          ]"
        >
          <td>
            <div class="account-main">
              <strong><span class="abbr-mark">{{ acc.abbr }}</span>: <span class="id-text">{{ acc.id }}</span></strong>
            </div>
            <div class="account-sub meta">
              <span class="phone-tail-text">{{ phoneTail(acc.phone_number) }}</span>
              <span> / </span>
              <span class="nickname-text">{{ acc.nickname }}</span>
              <span v-if="isAllChecklistCompleted(acc.id)" class="all-done-badge">✓</span>
            </div>
          </td>
          <td>
            <select
              v-model="tacetInput[acc.id]"
              :class="['tacet-select', tacetClass(tacetInput[acc.id])]"
              @change="updateTacet(acc.id, tacetInput[acc.id])"
              style="min-width: 88px"
            >
              <option value=""></option>
              <option>爱弥斯</option>
              <option>西格莉卡</option>
              <option>旧暗</option>
              <option>旧雷</option>
              <option>达妮娅</option>
            </select>
          </td>
          <td>
              <input
                v-model.number="manualInput[acc.id]"
                :class="['waveplate-input', { 'input-flash': flashWaveplateInput[acc.id] }]"
                type="number"
                min="0"
                max="240"
              placeholder="体力"
              style="max-width: 72px"
              @keyup.enter="submitWaveplate(acc.id)"
              @blur="submitWaveplate(acc.id, $event)"
            />
          </td>
          <td>
            <input
              v-model.number="manualCrystalInput[acc.id]"
              :class="['crystal-input', { 'input-flash': flashCrystalInput[acc.id] }]"
              type="number"
              min="0"
              max="480"
              placeholder="溢出"
              style="max-width: 72px"
              @keyup.enter="submitWaveplate(acc.id)"
              @blur="submitWaveplate(acc.id, $event)"
            />
          </td>
          <td class="eta-cell">
            <button
              type="button"
              class="eta-trigger"
              @mousedown.prevent.stop="prepareOpenFullWaveplatePicker(acc.id)"
              @click.stop="openFullWaveplatePicker(acc)"
            >
              {{ formatFullTime(acc.eta_waveplate_full) }}
            </button>
          </td>
          <td>
            <div class="quick-row overview-quick-row">
              <button class="btn-gain" @click="gain(acc.id, 60)">+60</button>
              <button class="btn-gain" @click="gain(acc.id, 40)">+40</button>
              <button class="btn-spend" @click="spend(acc.id, 40)">-40</button>
              <button class="btn-spend" @click="spend(acc.id, 60)">-60</button>
            </div>
          </td>
          <td>
            <label :class="['status-item', 'flag-daily-task', statusClass(dailyTaskStatusInput[acc.id]), { 'flag-all-done': allDoneFlags.daily_task }]">
              <button
                type="button"
                class="status-toggle"
                @click="cycleDailyFlag(acc.id, 'daily_task')"
              >
                {{ statusLabel(dailyTaskStatusInput[acc.id]) }}
              </button>
            </label>
          </td>
          <td>
            <label :class="['status-item', 'flag-daily-nest', statusClass(dailyNestStatusInput[acc.id]), { 'flag-all-done': allDoneFlags.daily_nest }]">
              <button
                type="button"
                class="status-toggle"
                @click="cycleDailyFlag(acc.id, 'daily_nest')"
              >
                {{ statusLabel(dailyNestStatusInput[acc.id]) }}
              </button>
            </label>
          </td>
          <td>
            <label :class="['status-item', 'flag-weekly-door', statusClass(weeklyDoorStatusInput[acc.id]), { 'flag-all-done': allDoneFlags.weekly_door }]">
              <button
                type="button"
                class="status-toggle"
                @click="cycleDailyFlag(acc.id, 'weekly_door')"
              >
                {{ statusLabel(weeklyDoorStatusInput[acc.id]) }}
              </button>
            </label>
          </td>
          <td>
            <label :class="['status-item', 'flag-weekly-boss', statusClass(weeklyBossStatusInput[acc.id]), { 'flag-all-done': allDoneFlags.weekly_boss }]">
              <button
                type="button"
                class="status-toggle"
                @click="cycleDailyFlag(acc.id, 'weekly_boss')"
              >
                {{ statusLabel(weeklyBossStatusInput[acc.id]) }}
              </button>
            </label>
          </td>
        </tr>
      </tbody>
    </table>
    </div>

    <div v-if="fullWaveplatePicker.visible" class="fulltime-modal-mask" @click="closeFullWaveplatePicker">
      <div class="fulltime-modal" @click.stop>
        <h3 style="margin: 0 0 8px">设置满体力时间</h3>
        <p class="meta" style="margin: 0 0 8px">账号：{{ fullWaveplatePicker.targetId }}</p>
        <div class="meta" style="margin: 0 0 6px">满体力时间</div>
        <div class="fulltime-form">
          <label>
            日期
            <select v-model="fullWaveplatePicker.dayOffset" @change="onAbsoluteInputChange">
              <option value="0">今天</option>
              <option value="1">明天</option>
            </select>
          </label>
          <label>
            时间
            <input v-model="fullWaveplatePicker.time" type="time" step="1" @input="onAbsoluteInputChange" />
          </label>
        </div>
        <div class="meta" style="margin: 10px 0 6px">还有多久满体力</div>
        <div class="fulltime-form fulltime-duration">
          <label>
            小时
            <input
              v-model.number="fullWaveplatePicker.durationHours"
              type="number"
              min="0"
              max="24"
              @input="onDurationInputChange"
            />
          </label>
          <label>
            分钟
            <input
              v-model.number="fullWaveplatePicker.durationMinutes"
              type="number"
              min="0"
              max="59"
              @input="onDurationInputChange"
            />
          </label>
          <label>
            秒
            <input
              v-model.number="fullWaveplatePicker.durationSeconds"
              type="number"
              min="0"
              max="59"
              @input="onDurationInputChange"
            />
          </label>
        </div>
        <div class="actions" style="justify-content: flex-end; margin-top: 10px">
          <button @click="closeFullWaveplatePicker">取消</button>
          <button class="primary" :disabled="fullWaveplatePicker.saving" @click="submitFullWaveplatePicker">
            确认
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '../api'

const REFRESH_INTERVAL_SECONDS = 60
const LAST_EDIT_STORAGE_KEY = 'wuwa_dashboard_last_edit_map_v1'
const STATUS_FLOW = ['todo', 'done', 'skipped']
const DISPLAY_TIMEZONE = 'Asia/Shanghai'
const accounts = ref([])
const sortMode = ref('eta')
const manualInput = ref({})
const manualCrystalInput = ref({})
const tacetInput = ref({})
const dailyTaskStatusInput = ref({})
const dailyNestStatusInput = ref({})
const weeklyDoorStatusInput = ref({})
const weeklyBossStatusInput = ref({})
const highlightedAccountId = ref(null)
const countdownSeconds = ref(REFRESH_INTERVAL_SECONDS)
const savedWaveplate = ref({})
const savedCrystal = ref({})
const flashWaveplateInput = ref({})
const flashCrystalInput = ref({})
const lastEditedMap = ref({})
const orderFrozen = ref(false)
const frozenOrderIds = ref([])
const fullWaveplatePicker = ref({
  visible: false,
  targetId: '',
  lastEdited: 'absolute',
  dayOffset: '0',
  time: '',
  durationHours: 0,
  durationMinutes: 0,
  durationSeconds: 0,
  saving: false,
})
const suppressBlurSubmitForId = ref('')
const savingIds = new Set()
const flashTimers = new Map()
let fetchTimer = null
let countdownTimer = null

function getSortedRowsByMode() {
  const rows = [...accounts.value]
  if (sortMode.value === 'recent_edit') {
    rows.sort((a, b) => {
      const ta = Number(lastEditedMap.value[a.id] || 0)
      const tb = Number(lastEditedMap.value[b.id] || 0)
      return tb - ta
    })
    return rows
  }
  if (sortMode.value === 'oldest_edit') {
    rows.sort((a, b) => {
      const ta = Number(lastEditedMap.value[a.id] || 0)
      const tb = Number(lastEditedMap.value[b.id] || 0)
      return ta - tb
    })
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

const allDoneFlags = computed(() => ({
  daily_task: isAllCompleted(dailyTaskStatusInput.value),
  daily_nest: isAllCompleted(dailyNestStatusInput.value),
  weekly_door: isAllCompleted(weeklyDoorStatusInput.value),
  weekly_boss: isAllCompleted(weeklyBossStatusInput.value),
}))
const fullDateMin = computed(() => getDateKeyInTZ(new Date()))

async function refresh() {
  accounts.value = await api.listDashboardAccounts()
  for (const acc of accounts.value) {
    const prevWaveplate = savedWaveplate.value[acc.id]
    const prevCrystal = savedCrystal.value[acc.id]
    if (prevWaveplate !== undefined && prevWaveplate !== acc.current_waveplate) {
      triggerInputFlash(acc.id, 'waveplate')
    }
    if (prevCrystal !== undefined && prevCrystal !== acc.current_waveplate_crystal) {
      triggerInputFlash(acc.id, 'crystal')
    }
    manualInput.value[acc.id] = acc.current_waveplate
    manualCrystalInput.value[acc.id] = acc.current_waveplate_crystal
    tacetInput.value[acc.id] = acc.tacet || ''
    savedWaveplate.value[acc.id] = acc.current_waveplate
    savedCrystal.value[acc.id] = acc.current_waveplate_crystal
    dailyTaskStatusInput.value[acc.id] = normalizeStatus(acc.daily_task_status, acc.daily_task)
    dailyNestStatusInput.value[acc.id] = normalizeStatus(acc.daily_nest_status, acc.daily_nest)
    weeklyDoorStatusInput.value[acc.id] = normalizeStatus(acc.weekly_door_status, acc.weekly_door)
    weeklyBossStatusInput.value[acc.id] = normalizeStatus(acc.weekly_boss_status, acc.weekly_boss)
  }
  syncHighlightedAccountId()
}

function triggerInputFlash(id, type) {
  const key = `${type}:${id}`
  const prevTimer = flashTimers.get(key)
  if (prevTimer) clearTimeout(prevTimer)
  if (type === 'waveplate') {
    flashWaveplateInput.value[id] = true
  } else {
    flashCrystalInput.value[id] = true
  }
  const timer = setTimeout(() => {
    if (type === 'waveplate') {
      flashWaveplateInput.value[id] = false
    } else {
      flashCrystalInput.value[id] = false
    }
    flashTimers.delete(key)
  }, 750)
  flashTimers.set(key, timer)
}

function formatFullTime(v) {
  const dt = new Date(v)
  const nowKey = getDateKeyInTZ(new Date())
  const targetParts = getTZParts(dt)
  const targetKey = `${targetParts.year}-${targetParts.month}-${targetParts.day}`
  const diffDays = diffDateKeyDays(targetKey, nowKey)
  const hh = targetParts.hour
  const mm = targetParts.minute
  if (diffDays === 0) return `${hh}:${mm}`
  if (diffDays === 1) return `明天 ${hh}:${mm}`
  return `${Number(targetParts.month)}-${Number(targetParts.day)} ${hh}:${mm}`
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

function getTZParts(dt) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: DISPLAY_TIMEZONE,
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

function diffDateKeyDays(a, b) {
  const [ay, am, ad] = a.split('-').map((v) => Number(v))
  const [by, bm, bd] = b.split('-').map((v) => Number(v))
  const ua = Date.UTC(ay, am - 1, ad)
  const ub = Date.UTC(by, bm - 1, bd)
  return Math.round((ua - ub) / 86400000)
}

function phoneTail(phoneNumber) {
  const raw = String(phoneNumber || '').trim()
  if (!raw) return '-'
  return raw.slice(-4)
}

function tacetClass(tacet) {
  const colorMap = {
    '爱弥斯': 'tacet-aimisi',
    '西格莉卡': 'tacet-xigelika',
    '旧暗': 'tacet-old-dark',
    '旧雷': 'tacet-old-thunder',
    '达妮娅': 'tacet-daniya',
  }
  return colorMap[tacet] || 'tacet-empty'
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

function statusClass(status) {
  return `status-${normalizeStatus(status)}`
}

function statusLabel(status) {
  const normalized = normalizeStatus(status)
  if (normalized === 'done') return 'Done'
  if (normalized === 'skipped') return 'Skip'
  return 'Todo'
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
    isCompletedStatus(weeklyDoorStatusInput.value[id]) &&
    isCompletedStatus(weeklyBossStatusInput.value[id])
  )
}

async function spend(id, cost) {
  try {
    await api.spendWaveplate(id, cost)
    markEdited(id)
    await refresh()
  } catch (err) {
    alert(`扣减失败：${err.message || '体力不足'}`)
  }
}

async function gain(id, amount) {
  await api.gainWaveplate(id, amount)
  markEdited(id)
  await refresh()
}

async function setWaveplate(id) {
  const waveplateRaw = manualInput.value[id]
  const waveplate = waveplateRaw === '' || waveplateRaw === undefined || waveplateRaw === null ? 0 : Number(waveplateRaw)
  const crystalRaw = manualCrystalInput.value[id]
  const crystal = crystalRaw === '' || crystalRaw === undefined || crystalRaw === null ? null : Number(crystalRaw)
  if (Number.isNaN(waveplate) || waveplate < 0 || waveplate > 240) {
    alert('体力范围应为 0~240')
    return
  }
  if (crystal !== null && (Number.isNaN(crystal) || crystal < 0 || crystal > 480)) {
    alert('体力结晶范围应为 0~480')
    return
  }
  if (waveplate === savedWaveplate.value[id] && (crystal ?? savedCrystal.value[id]) === savedCrystal.value[id]) {
    return
  }
  await api.setWaveplate(id, waveplate, crystal)
  savedWaveplate.value[id] = waveplate
  savedCrystal.value[id] = crystal ?? savedCrystal.value[id]
  markEdited(id)
  await refresh()
}

async function submitWaveplate(id, event = null) {
  if (event && suppressBlurSubmitForId.value && String(suppressBlurSubmitForId.value) === String(id)) {
    suppressBlurSubmitForId.value = ''
    return
  }
  if (fullWaveplatePicker.value.visible && String(fullWaveplatePicker.value.targetId) === String(id)) {
    return
  }
  if (savingIds.has(id)) return
  savingIds.add(id)
  try {
    await setWaveplate(id)
  } finally {
    savingIds.delete(id)
  }
}

function statusMapByKey(flagKey) {
  if (flagKey === 'daily_task') return dailyTaskStatusInput.value
  if (flagKey === 'daily_nest') return dailyNestStatusInput.value
  if (flagKey === 'weekly_door') return weeklyDoorStatusInput.value
  return weeklyBossStatusInput.value
}

async function cycleDailyFlag(id, flagKey) {
  const map = statusMapByKey(flagKey)
  const current = map[id]
  const next = nextStatus(current)
  map[id] = next
  await updateDailyFlag(id, flagKey, next)
}

async function updateDailyFlag(id, flagKey, status) {
  try {
    await api.setDailyFlag(id, flagKey, status)
    markEdited(id)
  } catch (err) {
    alert(`保存失败：${err.message || '请稍后重试'}`)
    await refresh()
  }
}

async function updateTacet(id, tacet) {
  try {
    await api.setTacet(id, tacet)
    markEdited(id)
  } catch (err) {
    alert(`保存失败：${err.message || '请稍后重试'}`)
    await refresh()
  }
}

function openFullWaveplatePicker(account) {
  const eta = new Date(account.eta_waveplate_full)
  fullWaveplatePicker.value = {
    visible: true,
    targetId: String(account.id),
    lastEdited: 'absolute',
    dayOffset: '0',
    time: timeToInputValue(eta),
    durationHours: 0,
    durationMinutes: 0,
    durationSeconds: 0,
    saving: false,
  }
  suppressBlurSubmitForId.value = ''
}

function closeFullWaveplatePicker(force = false) {
  if (!force && fullWaveplatePicker.value.saving) return
  fullWaveplatePicker.value.visible = false
}

function prepareOpenFullWaveplatePicker(id) {
  suppressBlurSubmitForId.value = String(id)
}

function onAbsoluteInputChange() {
  const state = fullWaveplatePicker.value
  state.lastEdited = 'absolute'
  state.durationHours = 0
  state.durationMinutes = 0
  state.durationSeconds = 0
}

function onDurationInputChange() {
  const state = fullWaveplatePicker.value
  state.lastEdited = 'duration'
  state.dayOffset = '0'
  state.time = ''
}

async function submitFullWaveplatePicker() {
  const state = fullWaveplatePicker.value
  if (!state.targetId) return
  let deltaSeconds = 0
  if (state.lastEdited === 'duration') {
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
    deltaSeconds = h * 3600 + m * 60 + s
    if (deltaSeconds > 86400) {
      alert('满体力剩余时间不能超过 24 小时')
      return
    }
  } else {
    const dayOffsetNum = Number(state.dayOffset)
    if (!Number.isInteger(dayOffsetNum) || dayOffsetNum < 0 || dayOffsetNum > 1) {
      alert('日期仅支持今天或明天')
      return
    }
    const dateText = addDaysToDateKey(fullDateMin.value, dayOffsetNum)
    const timeText = normalizeTimeValue(state.time)
    const normalizedFullAtBase = `${dateText}T${timeText}`
    const normalizedFullAt = `${normalizedFullAtBase}+08:00`
    if (!timeText) {
      alert('请选择时间')
      return
    }
    const fullAt = new Date(normalizedFullAt)
    if (Number.isNaN(fullAt.getTime())) {
      alert('满体力时间格式无效')
      return
    }
    deltaSeconds = Math.max(0, Math.floor((fullAt.getTime() - Date.now()) / 1000))
  }
  state.saving = true
  try {
    const missing = deltaSeconds <= 0 ? 0 : Math.ceil(deltaSeconds / 360)
    const waveplate = Math.max(0, 240 - missing)
    await api.setWaveplate(state.targetId, waveplate)
    markEdited(state.targetId)
    closeFullWaveplatePicker(true)
    await refresh()
  } catch (err) {
    alert(`设置失败：${err.message || '请稍后重试'}`)
  } finally {
    state.saving = false
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
    if (parsed && typeof parsed === "object") {
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
    if (countdownSeconds.value > 0) countdownSeconds.value -= 1
  }, 1000)
})

watch(sortMode, () => {
  orderFrozen.value = false
  frozenOrderIds.value = []
})

onUnmounted(() => {
  if (fetchTimer) clearInterval(fetchTimer)
  if (countdownTimer) clearInterval(countdownTimer)
  for (const timer of flashTimers.values()) clearTimeout(timer)
  flashTimers.clear()
})
</script>
