<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">每日每周总览</h2>
      <div class="actions" style="align-items: center">
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
        <label style="max-width: 220px">
          排序方式
          <select v-model="sortMode">
            <option value="eta">最近满体</option>
            <option value="recent_edit">最近修改</option>
            <option value="oldest_edit">最久未修改</option>
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
          <th>体力 / 溢出</th>
          <th>满体力</th>
          <th>体力快捷操作</th>
          <th>每日清单</th>
          <th>每周清单</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="acc in sortedAccounts"
          :key="acc.id"
          :class="[acc.warn_level, { edited: isHighlighted(acc.id) }]"
          @click="pinRow(acc.id)"
        >
          <td>
            <div class="account-main">
              <strong><span class="abbr-mark">{{ acc.abbr }}</span>: <span class="id-text">{{ acc.id }}</span></strong>
            </div>
            <div class="account-sub meta">
              <span class="phone-tail-text">{{ phoneTail(acc.phone_number) }}</span>
              <span> / </span>
              <span class="nickname-text">{{ acc.nickname }}</span>
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
            <div class="energy-stack">
              <input
                v-model.number="manualInput[acc.id]"
                class="waveplate-input"
                type="number"
                min="0"
                max="240"
                placeholder="体力"
                style="max-width: 84px"
                @keyup.enter="submitWaveplate(acc.id)"
                @blur="submitWaveplate(acc.id)"
              />
              <input
                v-model.number="manualCrystalInput[acc.id]"
                class="crystal-input"
                type="number"
                min="0"
                max="480"
                placeholder="结晶"
                style="max-width: 84px"
                @keyup.enter="submitWaveplate(acc.id)"
                @blur="submitWaveplate(acc.id)"
              />
            </div>
          </td>
          <td class="eta-cell">{{ formatFullTime(acc.eta_waveplate_full) }}</td>
          <td>
            <div class="actions">
              <div class="quick-row">
                <button class="btn-gain" @click="gain(acc.id, 60)">+60</button>
                <button class="btn-gain" @click="gain(acc.id, 40)">+40</button>
              </div>
              <div class="quick-row quick-spend-row">
                <button class="btn-spend" v-for="cost in [40, 60, 80, 120]" :key="cost" @click="spend(acc.id, cost)">-{{ cost }}</button>
              </div>
            </div>
          </td>
          <td>
            <div class="status-wrap">
              <label :class="['status-item', 'flag-daily-task', { 'flag-all-done': allDoneFlags.daily_task }]">
                <input
                  type="checkbox"
                  v-model="dailyDoneInput[acc.id]"
                  @change="updateDailyFlag(acc.id, 'daily_task', !!dailyDoneInput[acc.id])"
                />
                <span>日常</span>
              </label>
              <label :class="['status-item', 'flag-daily-nest', { 'flag-all-done': allDoneFlags.daily_nest }]">
                <input
                  type="checkbox"
                  v-model="nestClearedInput[acc.id]"
                  @change="updateDailyFlag(acc.id, 'daily_nest', !!nestClearedInput[acc.id])"
                />
                <span>聚落</span>
              </label>
            </div>
          </td>
          <td>
            <div class="status-wrap">
              <label :class="['status-item', 'flag-weekly-door', { 'flag-all-done': allDoneFlags.weekly_door }]">
                <input
                  type="checkbox"
                  v-model="weeklyDoorInput[acc.id]"
                  @change="updateDailyFlag(acc.id, 'weekly_door', !!weeklyDoorInput[acc.id])"
                />
                <span>门扉</span>
              </label>
              <label :class="['status-item', 'flag-weekly-boss', { 'flag-all-done': allDoneFlags.weekly_boss }]">
                <input
                  type="checkbox"
                  v-model="weeklyBossInput[acc.id]"
                  @change="updateDailyFlag(acc.id, 'weekly_boss', !!weeklyBossInput[acc.id])"
                />
                <span>周本</span>
              </label>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'

const REFRESH_INTERVAL_SECONDS = 60
const LAST_EDIT_STORAGE_KEY = 'wuwa_dashboard_last_edit_map_v1'
const accounts = ref([])
const sortMode = ref('eta')
const manualInput = ref({})
const manualCrystalInput = ref({})
const tacetInput = ref({})
const dailyDoneInput = ref({})
const nestClearedInput = ref({})
const weeklyDoorInput = ref({})
const weeklyBossInput = ref({})
const highlightedAccountId = ref(null)
const countdownSeconds = ref(REFRESH_INTERVAL_SECONDS)
const savedWaveplate = ref({})
const savedCrystal = ref({})
const lastEditedMap = ref({})
const savingIds = new Set()
let fetchTimer = null
let countdownTimer = null

const sortedAccounts = computed(() => {
  const rows = [...accounts.value]
  const pinEditedRowToTop = (list) => {
    const currentId = normalizedId(highlightedAccountId.value)
    if (!currentId) return list
    const idx = list.findIndex((row) => normalizedId(row.id) === currentId)
    if (idx <= 0) return list
    const [target] = list.splice(idx, 1)
    list.unshift(target)
    return list
  }

  if (sortMode.value === 'recent_edit') {
    rows.sort((a, b) => {
      const ta = Number(lastEditedMap.value[a.id] || 0)
      const tb = Number(lastEditedMap.value[b.id] || 0)
      return tb - ta
    })
    return pinEditedRowToTop(rows)
  }
  if (sortMode.value === 'oldest_edit') {
    rows.sort((a, b) => {
      const ta = Number(lastEditedMap.value[a.id] || 0)
      const tb = Number(lastEditedMap.value[b.id] || 0)
      return ta - tb
    })
    return pinEditedRowToTop(rows)
  }
  rows.sort((a, b) => new Date(a.eta_waveplate_full).getTime() - new Date(b.eta_waveplate_full).getTime())
  return pinEditedRowToTop(rows)
})

const countdownProgress = computed(() => {
  const done = REFRESH_INTERVAL_SECONDS - countdownSeconds.value
  return Math.min(1, Math.max(0, done / REFRESH_INTERVAL_SECONDS))
})

const countdownRemainProgress = computed(() => 1 - countdownProgress.value)

const allDoneFlags = computed(() => ({
  daily_task: isAllChecked(dailyDoneInput.value),
  daily_nest: isAllChecked(nestClearedInput.value),
  weekly_door: isAllChecked(weeklyDoorInput.value),
  weekly_boss: isAllChecked(weeklyBossInput.value),
}))

async function refresh() {
  accounts.value = await api.listDashboardAccounts()
  for (const acc of accounts.value) {
    manualInput.value[acc.id] = acc.current_waveplate
    manualCrystalInput.value[acc.id] = acc.current_waveplate_crystal
    tacetInput.value[acc.id] = acc.tacet || ''
    savedWaveplate.value[acc.id] = acc.current_waveplate
    savedCrystal.value[acc.id] = acc.current_waveplate_crystal
    dailyDoneInput.value[acc.id] = !!(acc.daily_task ?? acc.daily_done)
    nestClearedInput.value[acc.id] = !!(acc.daily_nest ?? acc.nest_cleared)
    weeklyDoorInput.value[acc.id] = !!acc.weekly_door
    weeklyBossInput.value[acc.id] = !!acc.weekly_boss
  }
  syncHighlightedAccountId()
}

function formatFullTime(v) {
  const dt = new Date(v)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetDay = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate())
  const diffDays = Math.round((targetDay - today) / 86400000)
  const hh = String(dt.getHours()).padStart(2, '0')
  const mm = String(dt.getMinutes()).padStart(2, '0')
  if (diffDays === 0) return `${hh}:${mm}`
  if (diffDays === 1) return `明天\n${hh}:${mm}`
  return `${dt.getMonth() + 1}-${dt.getDate()} ${hh}:${mm}`
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

function isAllChecked(map) {
  const ids = accounts.value.map((acc) => normalizedId(acc.id))
  if (!ids.length) return false
  return ids.every((id) => !!map[id])
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

async function submitWaveplate(id) {
  if (savingIds.has(id)) return
  savingIds.add(id)
  try {
    await setWaveplate(id)
  } finally {
    savingIds.delete(id)
  }
}

async function updateDailyFlag(id, flagKey, isDone) {
  try {
    await api.setDailyFlag(id, flagKey, isDone)
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

function markEdited(id) {
  const key = normalizedId(id)
  highlightedAccountId.value = key
  lastEditedMap.value[key] = Date.now()
  saveLastEditedMap()
  scrollToPageTop()
}

function pinRow(id) {
  highlightedAccountId.value = normalizedId(id)
  scrollToPageTop()
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

function scrollToPageTop() {
  if (typeof window === 'undefined') return
  window.scrollTo({ top: 0, behavior: 'smooth' })
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

onUnmounted(() => {
  if (fetchTimer) clearInterval(fetchTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
