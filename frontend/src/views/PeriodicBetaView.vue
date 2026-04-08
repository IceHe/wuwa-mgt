<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">周期活动beta</h2>
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
      <table class="periodic-beta-table">
        <thead>
          <tr>
            <th class="beta-activity-col">活动 / 用户</th>
            <th
              v-for="acc in sortedAccounts"
              :key="acc.id"
              :class="['beta-account-col', { 'beta-account-highlight': isHighlighted(acc.id) }]"
            >
              <div class="beta-account-main beta-account-main-compact">
                <span class="abbr-mark">{{ acc.abbr }}</span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="activity in activityRows" :key="activity.key">
            <th :class="['beta-activity-col', activity.headerClass]">
              <div class="beta-activity-main">{{ activity.label }}</div>
              <div class="beta-activity-sub">{{ activity.periodLabel }} · {{ activityDateLabel(activity.key) }}</div>
            </th>
            <td
              v-for="acc in sortedAccounts"
              :key="`${activity.key}-${acc.id}`"
              :class="['beta-status-cell', activity.cellClass, { 'beta-account-highlight': isHighlighted(acc.id) }]"
            >
              <label :class="['status-item', activity.flagClass, statusClass(statusValue(activity.key, acc.id)), { 'flag-all-done': activity.allDone }]">
                <button
                  type="button"
                  class="status-toggle"
                  :title="statusLabel(statusValue(activity.key, acc.id))"
                  @click.stop="cycleCheckin(acc.id, activity.key)"
                >
                  {{ statusLabel(statusValue(activity.key, acc.id)) }}
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

const LAST_EDIT_STORAGE_KEY = 'wuwa_periodic_beta_last_edit_map_v1'
const SORT_MODE_STORAGE_KEY = 'wuwa_periodic_beta_sort_mode_v1'
const SORT_MODE_OPTIONS = ['abbr', 'created_desc', 'recent_edit']
const STATUS_FLOW = ['todo', 'done', 'skipped']
const ACTIVITY_DEFS = [
  {
    key: 'version_matrix_soldier',
    label: '终焉矩阵',
    periodLabel: '每版本',
    statusField: 'version_matrix_soldier_status',
    boolField: 'version_matrix_soldier',
    flagClass: 'flag-version-matrix',
    headerClass: 'beta-header-version-matrix',
    cellClass: 'beta-cell-version-matrix',
  },
  {
    key: 'version_small_coral_exchange',
    label: '小珊瑚兑换',
    periodLabel: '每版本',
    statusField: 'version_small_coral_exchange_status',
    boolField: 'version_small_coral_exchange',
    flagClass: 'flag-version-coral',
    headerClass: 'beta-header-version-coral',
    cellClass: 'beta-cell-version-coral',
  },
  {
    key: 'version_hologram_challenge',
    label: '全息挑战',
    periodLabel: '每版本',
    statusField: 'version_hologram_challenge_status',
    boolField: 'version_hologram_challenge',
    flagClass: 'flag-version-hologram',
    headerClass: 'beta-header-version-hologram',
    cellClass: 'beta-cell-version-hologram',
  },
  {
    key: 'version_echo_template_adjust',
    label: '声骸模板',
    periodLabel: '每版本',
    statusField: 'version_echo_template_adjust_status',
    boolField: 'version_echo_template_adjust',
    flagClass: 'flag-version-template',
    headerClass: 'beta-header-version-template',
    cellClass: 'beta-cell-version-template',
  },
  {
    key: 'hv_trial_character',
    label: '角色试用',
    periodLabel: '每半版本',
    statusField: 'hv_trial_character_status',
    boolField: 'hv_trial_character',
    flagClass: 'flag-hv-trial',
    headerClass: 'beta-header-hv-trial',
    cellClass: 'beta-cell-hv-trial',
  },
  {
    key: 'monthly_tower_exchange',
    label: '深塔兑换所',
    periodLabel: '每月',
    statusField: 'monthly_tower_exchange_status',
    boolField: 'monthly_tower_exchange',
    flagClass: 'flag-monthly-tower',
    headerClass: 'beta-header-monthly-tower',
    cellClass: 'beta-cell-monthly-tower',
  },
  {
    key: 'four_week_tower',
    label: '深塔',
    periodLabel: '每四周',
    statusField: 'four_week_tower_status',
    boolField: 'four_week_tower',
    flagClass: 'flag-fw-tower',
    headerClass: 'beta-header-fw-tower',
    cellClass: 'beta-cell-fw-tower',
  },
  {
    key: 'four_week_ruins',
    label: '海墟',
    periodLabel: '每四周',
    statusField: 'four_week_ruins_status',
    boolField: 'four_week_ruins',
    flagClass: 'flag-fw-ruins',
    headerClass: 'beta-header-fw-ruins',
    cellClass: 'beta-cell-fw-ruins',
  },
  {
    key: 'range_plate',
    label: '餐盘',
    periodLabel: '限时',
    statusField: 'range_plate_status',
    boolField: 'range_plate',
    flagClass: 'flag-range-plate',
    headerClass: 'beta-header-range-plate',
    cellClass: 'beta-cell-range-plate',
  },
  {
    key: 'range_music_game',
    label: '音游',
    periodLabel: '限时',
    statusField: 'range_music_game_status',
    boolField: 'range_music_game',
    flagClass: 'flag-range-music',
    headerClass: 'beta-header-range-music',
    cellClass: 'beta-cell-range-music',
  },
]

const accounts = ref([])
const sortMode = ref(loadStoredValue(SORT_MODE_STORAGE_KEY, 'abbr', SORT_MODE_OPTIONS))
const highlightedAccountId = ref(null)
const lastEditedMap = ref({})
const statusMaps = ref(Object.fromEntries(ACTIVITY_DEFS.map((item) => [item.key, {}])))

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

const activityRows = computed(() =>
  ACTIVITY_DEFS.map((activity) => ({
    ...activity,
    allDone: isAllCompleted(statusMaps.value[activity.key] || {}),
  })),
)

const periodWindows = computed(() => accounts.value[0]?.period_windows || {})

function normalizedId(id) {
  if (id === null || id === undefined) return ''
  return String(id)
}

function isHighlighted(id) {
  return normalizedId(id) === normalizedId(highlightedAccountId.value)
}

function normalizeStatus(status, boolFallback = false) {
  if (typeof status === 'string' && STATUS_FLOW.includes(status)) return status
  return boolFallback ? 'done' : 'todo'
}

function isCompletedStatus(status) {
  const normalized = normalizeStatus(status)
  return normalized === 'done' || normalized === 'skipped'
}

function isAllCompleted(map) {
  const ids = accounts.value.map((acc) => normalizedId(acc.id))
  if (!ids.length) return false
  return ids.every((id) => isCompletedStatus(map[id]))
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

function formatShortDate(value) {
  const raw = String(value || '').trim()
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return ''
  return `${Number(match[2])}/${Number(match[3])}`
}

function activityDateLabel(flagKey) {
  const window = periodWindows.value?.[flagKey]
  if (!window) return ''
  const start = formatShortDate(window.start)
  const end = formatShortDate(window.end)
  if (!start && !end) return ''
  if (!end || start === end) return `${start}${end && !start ? end : ''}`
  if (!start) return end
  return `${start}-${end}`
}

function statusValue(flagKey, id) {
  return statusMaps.value[flagKey]?.[id] || 'todo'
}

async function refresh() {
  accounts.value = await api.listPeriodicAccounts()
  const nextMaps = Object.fromEntries(ACTIVITY_DEFS.map((item) => [item.key, {}]))
  for (const acc of accounts.value) {
    for (const activity of ACTIVITY_DEFS) {
      nextMaps[activity.key][acc.id] = normalizeStatus(acc[activity.statusField], acc[activity.boolField])
    }
  }
  statusMaps.value = nextMaps
  syncHighlightedAccountId()
}

async function cycleCheckin(id, flagKey) {
  const current = statusValue(flagKey, id)
  const next = nextStatus(current)
  statusMaps.value[flagKey][id] = next
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
