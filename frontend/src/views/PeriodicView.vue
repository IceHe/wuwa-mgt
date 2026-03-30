<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">周期活动</h2>
      <div class="actions" style="align-items: center">
        <label style="max-width: 220px">
          排序方式
          <select v-model="sortMode">
            <option value="abbr">账户缩写</option>
            <option value="created_desc">最近创建</option>
            <option value="recent_edit">最近修改</option>
          </select>
        </label>
      </div>
    </div>
    <div class="table-wrap">
      <table class="periodic-table">
        <colgroup>
          <col class="col-id" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
          <col class="col-flag" />
        </colgroup>
        <thead>
          <tr class="group-row">
            <th rowspan="2" class="group-id">ID / 尾号 / 昵称</th>
            <th colspan="4" class="group-fv">每版本</th>
            <th colspan="1" class="group-hv">每半版本</th>
            <th colspan="1" class="group-monthly">每月</th>
            <th colspan="2" class="group-fourweek">每四周</th>
            <th colspan="2" class="group-range">限时</th>
          </tr>
          <tr>
            <th class="col-version-matrix">终焉矩阵</th>
            <th class="col-version-coral">小珊瑚兑换</th>
            <th class="col-version-hologram">全息挑战</th>
            <th class="col-version-template">声骸模板</th>
            <th class="col-hv-trial">角色试用</th>
            <th class="col-monthly-tower">深塔兑换所</th>
            <th class="col-fw-tower">深塔</th>
            <th class="col-fw-ruins">海墟</th>
            <th class="col-range-lahailuo">填方块</th>
            <th class="col-range-music">音游</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="acc in sortedAccounts"
            :key="acc.id"
            @click="toggleHighlight(acc.id)"
            :class="{ edited: isHighlighted(acc.id) }"
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
              <label :class="['status-item', 'flag-version-matrix', statusClass(versionMatrixSoldierInput[acc.id]), { 'flag-all-done': allDoneFlags.version_matrix_soldier }]">
                <button type="button" class="status-toggle" :title="statusLabel(versionMatrixSoldierInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'version_matrix_soldier')">
                  {{ statusLabel(versionMatrixSoldierInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-version-coral', statusClass(versionSmallCoralInput[acc.id]), { 'flag-all-done': allDoneFlags.version_small_coral_exchange }]">
                <button type="button" class="status-toggle" :title="statusLabel(versionSmallCoralInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'version_small_coral_exchange')">
                  {{ statusLabel(versionSmallCoralInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-version-hologram', statusClass(versionHologramInput[acc.id]), { 'flag-all-done': allDoneFlags.version_hologram_challenge }]">
                <button type="button" class="status-toggle" :title="statusLabel(versionHologramInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'version_hologram_challenge')">
                  {{ statusLabel(versionHologramInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-version-template', statusClass(versionEchoTemplateInput[acc.id]), { 'flag-all-done': allDoneFlags.version_echo_template_adjust }]">
                <button type="button" class="status-toggle" :title="statusLabel(versionEchoTemplateInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'version_echo_template_adjust')">
                  {{ statusLabel(versionEchoTemplateInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-hv-trial', statusClass(hvTrialCharacterInput[acc.id]), { 'flag-all-done': allDoneFlags.hv_trial_character }]">
                <button type="button" class="status-toggle" :title="statusLabel(hvTrialCharacterInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'hv_trial_character')">
                  {{ statusLabel(hvTrialCharacterInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-monthly-tower', statusClass(monthlyTowerExchangeInput[acc.id]), { 'flag-all-done': allDoneFlags.monthly_tower_exchange }]">
                <button type="button" class="status-toggle" :title="statusLabel(monthlyTowerExchangeInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'monthly_tower_exchange')">
                  {{ statusLabel(monthlyTowerExchangeInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-fw-tower', statusClass(fourWeekTowerInput[acc.id]), { 'flag-all-done': allDoneFlags.four_week_tower }]">
                <button type="button" class="status-toggle" :title="statusLabel(fourWeekTowerInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'four_week_tower')">
                  {{ statusLabel(fourWeekTowerInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-fw-ruins', statusClass(fourWeekRuinsInput[acc.id]), { 'flag-all-done': allDoneFlags.four_week_ruins }]">
                <button type="button" class="status-toggle" :title="statusLabel(fourWeekRuinsInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'four_week_ruins')">
                  {{ statusLabel(fourWeekRuinsInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-range-lahailuo', statusClass(rangeLahailuoCubeInput[acc.id]), { 'flag-all-done': allDoneFlags.range_lahailuo_cube }]">
                <button type="button" class="status-toggle" :title="statusLabel(rangeLahailuoCubeInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'range_lahailuo_cube')">
                  {{ statusLabel(rangeLahailuoCubeInput[acc.id]) }}
                </button>
              </label>
            </td>
            <td>
              <label :class="['status-item', 'flag-range-music', statusClass(rangeMusicGameInput[acc.id]), { 'flag-all-done': allDoneFlags.range_music_game }]">
                <button type="button" class="status-toggle" :title="statusLabel(rangeMusicGameInput[acc.id])" @click.stop="cycleCheckin(acc.id, 'range_music_game')">
                  {{ statusLabel(rangeMusicGameInput[acc.id]) }}
                </button>
              </label>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { loadStoredValue, saveStoredValue } from '../utils/persistentState'

const LAST_EDIT_STORAGE_KEY = 'wuwa_periodic_last_edit_map_v1'
const SORT_MODE_STORAGE_KEY = 'wuwa_periodic_sort_mode_v1'
const SORT_MODE_OPTIONS = ['abbr', 'created_desc', 'recent_edit']
const STATUS_FLOW = ['todo', 'done', 'skipped']
const accounts = ref([])
const sortMode = ref(loadStoredValue(SORT_MODE_STORAGE_KEY, 'abbr', SORT_MODE_OPTIONS))
const highlightedAccountId = ref(null)
const lastEditedMap = ref({})

const versionMatrixSoldierInput = ref({})
const versionSmallCoralInput = ref({})
const versionHologramInput = ref({})
const versionEchoTemplateInput = ref({})
const hvTrialCharacterInput = ref({})
const monthlyTowerExchangeInput = ref({})
const fourWeekTowerInput = ref({})
const fourWeekRuinsInput = ref({})
const rangeLahailuoCubeInput = ref({})
const rangeMusicGameInput = ref({})

const sortedAccounts = computed(() => {
  const rows = [...accounts.value]
  if (sortMode.value === 'created_desc') {
    rows.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    return rows
  }
  if (sortMode.value === 'recent_edit') {
    rows.sort((a, b) => {
      const ta = Number(lastEditedMap.value[normalizedId(a.id)] || 0)
      const tb = Number(lastEditedMap.value[normalizedId(b.id)] || 0)
      return tb - ta
    })
    return rows
  }
  rows.sort((a, b) => String(a.abbr || '').localeCompare(String(b.abbr || '')))
  return rows
})

const allDoneFlags = computed(() => ({
  version_matrix_soldier: isAllCompleted(versionMatrixSoldierInput.value),
  version_small_coral_exchange: isAllCompleted(versionSmallCoralInput.value),
  version_hologram_challenge: isAllCompleted(versionHologramInput.value),
  version_echo_template_adjust: isAllCompleted(versionEchoTemplateInput.value),
  hv_trial_character: isAllCompleted(hvTrialCharacterInput.value),
  monthly_tower_exchange: isAllCompleted(monthlyTowerExchangeInput.value),
  four_week_tower: isAllCompleted(fourWeekTowerInput.value),
  four_week_ruins: isAllCompleted(fourWeekRuinsInput.value),
  range_lahailuo_cube: isAllCompleted(rangeLahailuoCubeInput.value),
  range_music_game: isAllCompleted(rangeMusicGameInput.value),
}))

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

function statusMapByKey(flagKey) {
  if (flagKey === 'version_matrix_soldier') return versionMatrixSoldierInput.value
  if (flagKey === 'version_small_coral_exchange') return versionSmallCoralInput.value
  if (flagKey === 'version_hologram_challenge') return versionHologramInput.value
  if (flagKey === 'version_echo_template_adjust') return versionEchoTemplateInput.value
  if (flagKey === 'hv_trial_character') return hvTrialCharacterInput.value
  if (flagKey === 'monthly_tower_exchange') return monthlyTowerExchangeInput.value
  if (flagKey === 'four_week_tower') return fourWeekTowerInput.value
  if (flagKey === 'four_week_ruins') return fourWeekRuinsInput.value
  if (flagKey === 'range_lahailuo_cube') return rangeLahailuoCubeInput.value
  return rangeMusicGameInput.value
}

function phoneTail(phoneNumber) {
  const raw = String(phoneNumber || '').trim()
  if (!raw) return '-'
  return raw.slice(-4)
}

async function refresh() {
  accounts.value = await api.listPeriodicAccounts()
  for (const acc of accounts.value) {
    versionMatrixSoldierInput.value[acc.id] = normalizeStatus(acc.version_matrix_soldier_status, acc.version_matrix_soldier)
    versionSmallCoralInput.value[acc.id] = normalizeStatus(acc.version_small_coral_exchange_status, acc.version_small_coral_exchange)
    versionHologramInput.value[acc.id] = normalizeStatus(acc.version_hologram_challenge_status, acc.version_hologram_challenge)
    versionEchoTemplateInput.value[acc.id] = normalizeStatus(acc.version_echo_template_adjust_status, acc.version_echo_template_adjust)
    hvTrialCharacterInput.value[acc.id] = normalizeStatus(acc.hv_trial_character_status, acc.hv_trial_character)
    monthlyTowerExchangeInput.value[acc.id] = normalizeStatus(acc.monthly_tower_exchange_status, acc.monthly_tower_exchange)
    fourWeekTowerInput.value[acc.id] = normalizeStatus(acc.four_week_tower_status, acc.four_week_tower)
    fourWeekRuinsInput.value[acc.id] = normalizeStatus(acc.four_week_ruins_status, acc.four_week_ruins)
    rangeLahailuoCubeInput.value[acc.id] = normalizeStatus(acc.range_lahailuo_cube_status, acc.range_lahailuo_cube)
    rangeMusicGameInput.value[acc.id] = normalizeStatus(acc.range_music_game_status, acc.range_music_game)
  }
  syncHighlightedAccountId()
}

async function cycleCheckin(id, flagKey) {
  const map = statusMapByKey(flagKey)
  const current = map[id]
  const next = nextStatus(current)
  map[id] = next
  await updateCheckin(id, flagKey, next)
}

async function updateCheckin(id, flagKey, status) {
  try {
    await api.setCheckin(id, flagKey, status)
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
})

watch(sortMode, (value) => {
  saveStoredValue(SORT_MODE_STORAGE_KEY, value)
})
</script>
