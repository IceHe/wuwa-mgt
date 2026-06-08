<template>
  <div v-if="visible" class="fulltime-modal-mask" @click="$emit('close')">
    <div class="fulltime-modal periodic-account-modal" @click.stop>
      <div class="energy-editor-header">
        <div>
          <h3 style="margin: 0 0 4px">周期活动</h3>
          <p class="meta" style="margin: 0">{{ accountLabel }}</p>
        </div>
        <button type="button" class="energy-editor-close" @click="$emit('close')">关闭</button>
      </div>

      <div v-if="loading" class="periodic-account-modal-state">加载中...</div>
      <div v-else-if="error" class="periodic-account-modal-state error">
        <span>{{ error }}</span>
        <button type="button" @click="$emit('retry')">重试</button>
      </div>
      <div v-else-if="account" class="table-wrap">
        <table class="periodic-table periodic-account-table">
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
              <th colspan="5" class="group-fv">每版本</th>
              <th colspan="1" class="group-temp">临时活动</th>
              <th colspan="1" class="group-hv">每半版本</th>
              <th colspan="1" class="group-monthly">每月</th>
              <th colspan="2" class="group-fourweek">每四周</th>
            </tr>
            <tr>
              <th class="col-version-matrix">终焉矩阵</th>
              <th class="col-version-coral">小珊瑚兑换</th>
              <th class="col-version-hologram">全息挑战</th>
              <th class="col-version-template">声骸模板</th>
              <th class="col-version-mainline">主线</th>
              <th class="col-temp-roguelike">肉鸽</th>
              <th class="col-hv-trial">角色试用</th>
              <th class="col-monthly-tower">深塔兑换所</th>
              <th class="col-fw-tower">深塔</th>
              <th class="col-fw-ruins">海墟</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <div class="account-main">
                  <strong><span class="abbr-mark">{{ account.abbr }}</span>: <span class="id-text">{{ account.id }}</span></strong>
                </div>
                <div class="account-sub meta">
                  <span class="phone-tail-text">{{ phoneTail(account.phone_number) }}</span>
                  <span> / </span>
                  <span class="nickname-text">{{ account.nickname }}</span>
                </div>
              </td>
              <td v-for="activity in activities" :key="activity.key" :class="activity.cellClass">
                <label :class="['status-item', activity.flagClass, statusClass(activity)]">
                  <button
                    type="button"
                    class="status-toggle"
                    :title="statusTitle(activity)"
                    :disabled="savingKey === activity.key"
                    @click.stop="$emit('cycle', activity.key)"
                  >
                    {{ statusChipLabel(activity) }}
                  </button>
                </label>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="periodic-account-modal-state">未找到账号</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const STATUS_FLOW = ['todo', 'done', 'skipped']

const activities = [
  {
    key: 'version_matrix_soldier',
    statusField: 'version_matrix_soldier_status',
    boolField: 'version_matrix_soldier',
    flagClass: 'flag-version-matrix',
    cellClass: 'cell-version-matrix',
  },
  {
    key: 'version_small_coral_exchange',
    statusField: 'version_small_coral_exchange_status',
    boolField: 'version_small_coral_exchange',
    flagClass: 'flag-version-coral',
    cellClass: 'cell-version-coral',
  },
  {
    key: 'version_hologram_challenge',
    statusField: 'version_hologram_challenge_status',
    boolField: 'version_hologram_challenge',
    flagClass: 'flag-version-hologram',
    cellClass: 'cell-version-hologram',
  },
  {
    key: 'version_echo_template_adjust',
    statusField: 'version_echo_template_adjust_status',
    boolField: 'version_echo_template_adjust',
    flagClass: 'flag-version-template',
    cellClass: 'cell-version-template',
  },
  {
    key: 'version_mainline',
    statusField: 'version_mainline_status',
    boolField: 'version_mainline',
    flagClass: 'flag-version-mainline',
    cellClass: 'cell-version-mainline',
  },
  {
    key: 'temp_roguelike',
    statusField: 'temp_roguelike_status',
    boolField: 'temp_roguelike',
    flagClass: 'flag-temp-roguelike',
    cellClass: 'cell-temp-roguelike',
  },
  {
    key: 'hv_trial_character',
    statusField: 'hv_trial_character_status',
    boolField: 'hv_trial_character',
    flagClass: 'flag-hv-trial',
    cellClass: 'cell-hv-trial',
  },
  {
    key: 'monthly_tower_exchange',
    statusField: 'monthly_tower_exchange_status',
    boolField: 'monthly_tower_exchange',
    flagClass: 'flag-monthly-tower',
    cellClass: 'cell-monthly-tower',
  },
  {
    key: 'four_week_tower',
    statusField: 'four_week_tower_status',
    boolField: 'four_week_tower',
    flagClass: 'flag-fw-tower',
    cellClass: 'cell-fw-tower',
  },
  {
    key: 'four_week_ruins',
    statusField: 'four_week_ruins_status',
    boolField: 'four_week_ruins',
    flagClass: 'flag-fw-ruins',
    cellClass: 'cell-fw-ruins',
  },
]

const props = defineProps({
  visible: { type: Boolean, default: false },
  account: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  savingKey: { type: String, default: '' },
})

defineEmits(['close', 'retry', 'cycle'])

const accountLabel = computed(() => {
  if (!props.account) return '-'
  return `${props.account.abbr} / ${props.account.id} / ${props.account.nickname}`
})

function normalizeStatus(status, boolFallback = false) {
  if (typeof status === 'string' && STATUS_FLOW.includes(status)) return status
  return boolFallback ? 'done' : 'todo'
}

function activityStatus(activity) {
  if (!props.account) return 'todo'
  return normalizeStatus(props.account[activity.statusField], props.account[activity.boolField])
}

function statusClass(activity) {
  return `status-${activityStatus(activity)}`
}

function statusTitle(activity) {
  const normalized = activityStatus(activity)
  if (normalized === 'done') return '已完成'
  if (normalized === 'skipped') return '已跳过'
  return '待处理'
}

function statusChipLabel(activity) {
  const normalized = activityStatus(activity)
  if (normalized === 'done') return '完成'
  if (normalized === 'skipped') return '跳过'
  return '待办'
}

function phoneTail(phoneNumber) {
  const raw = String(phoneNumber || '').trim()
  if (!raw) return '-'
  return raw.slice(-4)
}
</script>
