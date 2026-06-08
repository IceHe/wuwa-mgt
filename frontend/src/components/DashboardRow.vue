<template>
  <tr
    :class="[
      liveEnergy.warn_level,
      {
        edited: highlighted,
        'all-done-row': allDoneRow,
      },
    ]"
    @click="$emit('toggle-highlight', account.id)"
  >
    <td>
      <div class="account-cell">
        <div class="account-main">
          <strong><span class="abbr-mark">{{ account.abbr }}</span>: <span class="id-text">{{ account.id }}</span></strong>
        </div>
        <div class="account-sub meta">
          <span class="phone-tail-text">{{ phoneTail(account.phone_number) }}</span>
          <span class="account-divider">/</span>
          <span class="nickname-text">{{ account.nickname }}</span>
          <span v-if="allDoneRow" class="all-done-badge">✓</span>
        </div>
      </div>
    </td>
    <td>
      <button
        type="button"
        class="remark-chip"
        :class="{ empty: !account.remark, long: isLongRemark(account.remark) }"
        :title="account.remark || ''"
        @click.stop="$emit('open-remark-editor', account)"
      >
        {{ remarkPreview(account.remark) }}
      </button>
    </td>
    <td>
      <select
        :value="tacet"
        :class="['tacet-select', tacetClass(tacet)]"
        :title="tacet || '未设置无音区'"
        @click.stop
        @change="$emit('update-tacet', account.id, $event.target.value)"
      >
        <option value=""></option>
        <option v-for="option in tacetOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </td>
    <td>
      <button
        type="button"
        class="energy-summary-card"
        :class="energySummaryClass(liveEnergy)"
        :title="`当前体力 ${liveEnergy.current_waveplate}，当前体力结晶 ${liveEnergy.current_waveplate_crystal}`"
        @click.stop="$emit('open-energy-editor', liveAccount)"
      >
        <span class="energy-summary-inline">
          <span class="energy-summary-main">{{ liveEnergy.current_waveplate }}</span>
          <span class="energy-summary-sub">+{{ liveEnergy.current_waveplate_crystal }}</span>
        </span>
      </button>
    </td>
    <td class="eta-cell">
      <div class="eta-inline">
        <button type="button" class="eta-trigger eta-chip" @click.stop="$emit('open-energy-editor', liveAccount)">
          {{ formatFullTime(account.eta_waveplate_full) }}
        </button>
        <span class="eta-next meta eta-next-chip">{{ formatNextWaveplateCountdown() }}</span>
      </div>
    </td>
    <td>
      <div class="quick-row overview-quick-row compact-quick-row">
        <template v-if="!quickMenuOpen">
          <button class="btn-gain" @click.stop="$emit('gain', account.id, 60)">+60</button>
          <button class="btn-spend" @click.stop="$emit('spend', account.id, 60)">-60</button>
          <button
            type="button"
            class="quick-more-btn"
            @click.stop="toggleQuickMenu"
          >
            更多
          </button>
        </template>
        <template v-else>
          <button class="btn-gain" @click.stop="runQuickAction('gain', 40)">+40</button>
          <button class="btn-spend" @click.stop="runQuickAction('spend', 40)">-40</button>
          <button type="button" class="quick-more-btn quick-more-back-btn" @click.stop="toggleQuickMenu">
            返回
          </button>
        </template>
      </div>
    </td>
    <td>
      <label :class="['status-item', 'flag-daily-task', statusClass(statuses.daily_task), { 'flag-all-done': allDoneFlags.daily_task }]">
        <button
          type="button"
          class="status-toggle"
          :title="statusLabel(statuses.daily_task)"
          @click.stop="$emit('cycle-flag', account.id, 'daily_task')"
        >
          {{ statusChipLabel(statuses.daily_task) }}
        </button>
      </label>
    </td>
    <td>
      <label :class="['status-item', 'flag-daily-nest', statusClass(statuses.daily_nest), { 'flag-all-done': allDoneFlags.daily_nest }]">
        <button
          type="button"
          class="status-toggle"
          :title="statusLabel(statuses.daily_nest)"
          @click.stop="$emit('cycle-flag', account.id, 'daily_nest')"
        >
          {{ statusChipLabel(statuses.daily_nest) }}
        </button>
      </label>
    </td>
    <td>
      <label :class="['status-item', 'flag-weekly-door', statusClass(statuses.weekly_door), { 'flag-all-done': allDoneFlags.weekly_door }]">
        <button
          type="button"
          class="status-toggle"
          :title="statusLabel(statuses.weekly_door)"
          @click.stop="$emit('cycle-flag', account.id, 'weekly_door')"
        >
          {{ statusChipLabel(statuses.weekly_door) }}
        </button>
      </label>
    </td>
    <td>
      <label :class="['status-item', 'flag-weekly-boss', statusClass(statuses.weekly_boss), { 'flag-all-done': allDoneFlags.weekly_boss }]">
        <button
          type="button"
          class="status-toggle"
          :title="statusLabel(statuses.weekly_boss)"
          @click.stop="$emit('cycle-flag', account.id, 'weekly_boss')"
        >
          {{ statusChipLabel(statuses.weekly_boss) }}
        </button>
      </label>
    </td>
    <td>
      <label :class="['status-item', 'flag-weekly-synthesis', statusClass(statuses.weekly_synthesis), { 'flag-all-done': allDoneFlags.weekly_synthesis }]">
        <button
          type="button"
          class="status-toggle"
          :title="statusLabel(statuses.weekly_synthesis)"
          @click.stop="$emit('cycle-flag', account.id, 'weekly_synthesis')"
        >
          {{ statusChipLabel(statuses.weekly_synthesis) }}
        </button>
      </label>
    </td>
    <td>
      <button
        type="button"
        class="periodic-row-open-btn"
        @click.stop="$emit('open-periodic', account)"
      >
        活动
      </button>
    </td>
  </tr>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  WAVEPLATE_CAP,
  WAVEPLATE_CRYSTAL_CAP,
  WAVEPLATE_CRYSTAL_RECOVERY_SECONDS,
  WAVEPLATE_RECOVERY_SECONDS,
  deriveEnergySnapshot,
} from '../utils/energy'

const props = defineProps({
  account: { type: Object, required: true },
  tacet: { type: String, default: '' },
  statuses: { type: Object, required: true },
  allDoneFlags: { type: Object, required: true },
  allDoneRow: { type: Boolean, default: false },
  highlighted: { type: Boolean, default: false },
  clockNowMs: { type: Number, required: true },
})

const emit = defineEmits([
  'toggle-highlight',
  'update-tacet',
  'open-energy-editor',
  'open-remark-editor',
  'gain',
  'spend',
  'cycle-flag',
  'open-periodic',
])

const quickMenuOpen = ref(false)
const liveEnergy = computed(() => deriveEnergySnapshot(props.account, props.clockNowMs))
const liveAccount = computed(() => ({
  ...props.account,
  ...liveEnergy.value,
}))
const tacetOptions = [
  { value: '爱弥斯', label: '爱弥' },
  { value: '西格莉卡', label: '西格' },
  { value: '旧暗', label: '旧暗' },
  { value: '旧雷', label: '旧雷' },
  { value: '达妮娅', label: '达妮' },
  { value: '绯雪', label: '绯雪' },
  { value: '洛瑟拉', label: '洛瑟' },
]

function toggleQuickMenu() {
  quickMenuOpen.value = !quickMenuOpen.value
}

function runQuickAction(type, amount) {
  emit(type, props.account.id, amount)
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
    '绯雪': 'tacet-feixue',
    '洛瑟拉': 'tacet-luosela',
  }
  return colorMap[tacet] || 'tacet-empty'
}

function energySummaryClass(account) {
  if (Number(account.current_waveplate) >= 240) return 'waveplate-full'
  if (Number(account.current_waveplate) >= 120) return 'waveplate-high'
  if (Number(account.current_waveplate) + Number(account.current_waveplate_crystal) >= 240) return 'combined-alert-240'
  if (Number(account.current_waveplate) + Number(account.current_waveplate_crystal) >= 120) return 'combined-alert-120'
  return 'waveplate-normal'
}

function formatCountdownSeconds(totalSeconds) {
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

function diffDateKeyDays(a, b) {
  const [ay, am, ad] = a.split('-').map((v) => Number(v))
  const [by, bm, bd] = b.split('-').map((v) => Number(v))
  const ua = Date.UTC(ay, am - 1, ad)
  const ub = Date.UTC(by, bm - 1, bd)
  return Math.round((ua - ub) / 86400000)
}

function formatFullTime(v) {
  const dt = new Date(v)
  const nowKey = getDateKeyInTZ(new Date(props.clockNowMs))
  const targetParts = getTZParts(dt)
  const targetKey = `${targetParts.year}-${targetParts.month}-${targetParts.day}`
  const diffDays = diffDateKeyDays(targetKey, nowKey)
  const hh = targetParts.hour
  const mm = targetParts.minute
  if (diffDays === 0) return `${hh}:${mm}`
  if (diffDays === 1) return `明天 ${hh}:${mm}`
  return `${Number(targetParts.month)}-${Number(targetParts.day)} ${hh}:${mm}`
}

function formatNextWaveplateCountdown() {
  const fullAtMs = new Date(props.account.eta_waveplate_full).getTime()
  if (Number.isNaN(fullAtMs)) return '-- +1'
  const currentWaveplate = Number(liveEnergy.value.current_waveplate)
  const currentCrystal = Number(liveEnergy.value.current_waveplate_crystal) || 0

  if (currentWaveplate < WAVEPLATE_CAP) {
    const deltaSeconds = Math.max(0, Math.floor((fullAtMs - props.clockNowMs) / 1000))
    if (deltaSeconds <= 0) return '已满'
    const nextPointSeconds = deltaSeconds % WAVEPLATE_RECOVERY_SECONDS || WAVEPLATE_RECOVERY_SECONDS
    return formatCountdownSeconds(nextPointSeconds)
  }

  if (currentCrystal >= WAVEPLATE_CRYSTAL_CAP) return '已满'

  const elapsedSinceFullSeconds = Math.max(0, Math.floor((props.clockNowMs - fullAtMs) / 1000))
  const elapsedIntoCrystalTick = elapsedSinceFullSeconds % WAVEPLATE_CRYSTAL_RECOVERY_SECONDS
  const nextCrystalSeconds =
    elapsedIntoCrystalTick === 0
      ? WAVEPLATE_CRYSTAL_RECOVERY_SECONDS
      : WAVEPLATE_CRYSTAL_RECOVERY_SECONDS - elapsedIntoCrystalTick
  return `结晶 ${formatCountdownSeconds(nextCrystalSeconds)}`
}

function normalizeStatus(status, boolFallback = false) {
  if (typeof status === 'string' && ['todo', 'done', 'skipped'].includes(status)) return status
  return boolFallback ? 'done' : 'todo'
}

function statusClass(status) {
  return `status-${normalizeStatus(status)}`
}

function statusLabel(status) {
  const normalized = normalizeStatus(status)
  if (normalized === 'done') return '已完成'
  if (normalized === 'skipped') return '已跳过'
  return '待处理'
}

function statusChipLabel(status) {
  const normalized = normalizeStatus(status)
  if (normalized === 'done') return '完成'
  if (normalized === 'skipped') return '跳过'
  return '待办'
}

function remarkPreview(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text
}

function isLongRemark(value) {
  return String(value || '').trim().length > 24
}
</script>
