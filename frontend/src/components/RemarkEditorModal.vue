<template>
  <div v-if="visible" class="fulltime-modal-mask" @click="$emit('close')">
    <div class="fulltime-modal remark-editor-modal" @click.stop>
      <div class="energy-editor-header">
        <div>
          <h3 style="margin: 0 0 4px">编辑备忘</h3>
          <p class="meta" style="margin: 0">{{ accountLabel }}</p>
        </div>
        <button type="button" class="energy-editor-close" @click="$emit('close')">关闭</button>
      </div>

      <div class="remark-editor-section">
        <label class="remark-editor-field">
          <span class="meta">备忘内容</span>
          <textarea
            :value="value"
            rows="5"
            maxlength="500"
            placeholder="输入备忘内容"
            @input="$emit('update:value', $event.target.value)"
          />
        </label>
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
  value: { type: String, default: '' },
  saving: { type: Boolean, default: false },
})

defineEmits(['close', 'save', 'update:value'])

const accountLabel = computed(() => {
  if (!props.account) return '-'
  return `${props.account.abbr} / ${props.account.id} / ${props.account.nickname}`
})
</script>
