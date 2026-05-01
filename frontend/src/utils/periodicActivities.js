const PERIODIC_DISPLAY_TIME_ZONE = 'Asia/Shanghai'

export const V33_TEMP_ACTIVITY_DEFS = [
  {
    key: 'v33_gifts_of_grand_celebration',
    label: '庆典赠礼',
    periodLabel: '3.3 临时活动',
    statusField: 'v33_gifts_of_grand_celebration_status',
    boolField: 'v33_gifts_of_grand_celebration',
    flagClass: 'flag-v33-gifts',
    headerClass: 'beta-header-v33-gifts',
    cellClass: 'beta-cell-v33-gifts',
    tableHeaderClass: 'col-v33-gifts',
    tableCellClass: 'cell-v33-gifts',
    startAt: '2026-04-30T00:00:00+08:00',
  },
  {
    key: 'v33_bountiful_waves',
    label: '福利浪潮',
    periodLabel: '3.3 临时活动',
    statusField: 'v33_bountiful_waves_status',
    boolField: 'v33_bountiful_waves',
    flagClass: 'flag-v33-waves',
    headerClass: 'beta-header-v33-waves',
    cellClass: 'beta-cell-v33-waves',
    tableHeaderClass: 'col-v33-waves',
    tableCellClass: 'cell-v33-waves',
    startAt: '2026-04-30T00:00:00+08:00',
  },
  {
    key: 'v33_star_bouncing',
    label: '星跃庆典',
    periodLabel: '3.3 临时活动',
    statusField: 'v33_star_bouncing_status',
    boolField: 'v33_star_bouncing',
    flagClass: 'flag-v33-star',
    headerClass: 'beta-header-v33-star',
    cellClass: 'beta-cell-v33-star',
    tableHeaderClass: 'col-v33-star',
    tableCellClass: 'cell-v33-star',
    startAt: '2026-05-02T00:00:00+08:00',
  },
  {
    key: 'v33_cubie_derby_championship',
    label: '方块竞速锦标赛',
    periodLabel: '3.3 临时活动',
    statusField: 'v33_cubie_derby_championship_status',
    boolField: 'v33_cubie_derby_championship',
    flagClass: 'flag-v33-cubie',
    headerClass: 'beta-header-v33-cubie',
    cellClass: 'beta-cell-v33-cubie',
    tableHeaderClass: 'col-v33-cubie',
    tableCellClass: 'cell-v33-cubie',
    startAt: '2026-05-09T00:00:00+08:00',
  },
]

function parseTimestamp(value) {
  if (!value) return Number.NaN
  return new Date(value).getTime()
}

function formatMonthDay(value) {
  const timestamp = parseTimestamp(value)
  if (!Number.isFinite(timestamp)) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: PERIODIC_DISPLAY_TIME_ZONE,
    month: 'numeric',
    day: 'numeric',
  }).format(new Date(timestamp))
}

export function isScheduledActivityVisible(activity, nowMs = Date.now()) {
  const startMs = parseTimestamp(activity.startAt)
  if (Number.isFinite(startMs) && nowMs < startMs) return false
  const endMs = parseTimestamp(activity.endAt)
  if (Number.isFinite(endMs) && nowMs > endMs) return false
  return true
}

export function filterVisibleScheduledActivities(activities, nowMs = Date.now()) {
  return activities.filter((activity) => isScheduledActivityVisible(activity, nowMs))
}

export function formatScheduledActivityDateLabel(activity) {
  const start = formatMonthDay(activity.startAt)
  const end = formatMonthDay(activity.endAt)
  if (start && end && start !== end) return `${start}-${end}`
  if (start && end) return start
  if (start) return `${start}起`
  return end
}
