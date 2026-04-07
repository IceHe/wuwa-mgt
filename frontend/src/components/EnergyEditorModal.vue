<template>
  <div v-if="visible" class="fulltime-modal-mask" @click="$emit('close')">
    <div class="fulltime-modal energy-editor-modal" @click.stop>
      <div class="energy-editor-header">
        <div>
          <h3 style="margin: 0 0 4px">编辑体力</h3>
          <p class="meta" style="margin: 0">{{ accountLabel }}</p>
        </div>
        <button type="button" class="energy-editor-close" @click="$emit('close')">关闭</button>
      </div>

      <div class="energy-editor-summary">
        <div class="energy-editor-summary-card">
          <span class="meta">当前体力</span>
          <strong>{{ currentWaveplateLabel }}</strong>
        </div>
        <div class="energy-editor-summary-card">
          <span class="meta">当前结晶</span>
          <strong>+{{ currentCrystalLabel }}</strong>
        </div>
        <div class="energy-editor-summary-card">
          <span class="meta">满体时间</span>
          <strong>{{ etaLabel }}</strong>
        </div>
      </div>

      <div class="energy-editor-mode-tabs">
        <button
          v-for="item in modeOptions"
          :key="item.value"
          type="button"
          :class="['energy-editor-mode-tab', { active: state.mode === item.value }]"
          @click="$emit('set-mode', item.value)"
        >
          {{ item.label }}
        </button>
      </div>

      <div v-if="state.mode === 'current'" class="energy-editor-section">
        <div class="fulltime-form">
          <label>
            当前体力
            <input
              :value="state.currentWaveplate"
              type="number"
              min="0"
              max="240"
              @input="$emit('update-field', 'currentWaveplate', $event.target.value)"
            />
          </label>
          <label>
            当前结晶
            <input
              :value="state.currentCrystal"
              type="number"
              min="0"
              max="480"
              @input="$emit('update-field', 'currentCrystal', $event.target.value)"
            />
          </label>
        </div>
      </div>

      <div v-else-if="state.mode === 'absolute'" class="energy-editor-section">
        <div class="fulltime-form">
          <label>
            日期
            <select :value="state.dayOffset" @change="$emit('update-field', 'dayOffset', $event.target.value)">
              <option value="0">今天</option>
              <option value="1">明天</option>
            </select>
          </label>
          <label>
            时间
            <input
              :value="state.time"
              type="time"
              step="1"
              @input="$emit('update-field', 'time', $event.target.value)"
            />
          </label>
        </div>
      </div>

      <div v-else class="energy-editor-section">
        <div class="fulltime-form fulltime-duration">
          <label>
            小时
            <input
              :value="state.durationHours"
              type="number"
              min="0"
              max="24"
              @input="$emit('update-field', 'durationHours', $event.target.value)"
            />
          </label>
          <label>
            分钟
            <input
              :value="state.durationMinutes"
              type="number"
              min="0"
              max="59"
              @input="$emit('update-field', 'durationMinutes', $event.target.value)"
            />
          </label>
          <label>
            秒
            <input
              :value="state.durationSeconds"
              type="number"
              min="0"
              max="59"
              @input="$emit('update-field', 'durationSeconds', $event.target.value)"
            />
          </label>
        </div>
      </div>

      <div class="actions" style="justify-content: flex-end; margin-top: 12px">
        <button type="button" @click="$emit('close')">取消</button>
        <button type="button" class="primary" :disabled="saving" @click="$emit('save')">
          {{ saving ? '保存中...' : '确认' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  account: { type: Object, default: null },
  state: { type: Object, required: true },
  saving: { type: Boolean, default: false },
})

defineEmits(['close', 'save', 'set-mode', 'update-field'])

const modeOptions = [
  { value: 'current', label: '当前数值' },
  { value: 'absolute', label: '满体时间' },
  { value: 'duration', label: '剩余时长' },
]

const accountLabel = computed(() => {
  if (!props.account) return '-'
  return `${props.account.abbr} / ${props.account.id} / ${props.account.nickname}`
})

const currentWaveplateLabel = computed(() => props.account?.current_waveplate ?? 0)
const currentCrystalLabel = computed(() => props.account?.current_waveplate_crystal ?? 0)

const etaLabel = computed(() => {
  if (!props.account?.eta_waveplate_full) return '-'
  const dt = new Date(props.account.eta_waveplate_full)
  if (Number.isNaN(dt.getTime())) return '-'
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(dt)
  const values = {}
  for (const part of parts) {
    if (part.type !== 'literal') values[part.type] = part.value
  }
  return `${values.month}-${values.day} ${values.hour}:${values.minute}`
})
</script>
