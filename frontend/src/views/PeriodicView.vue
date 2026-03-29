<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">周期活动</h2>
      <button type="button" @click="refresh">刷新</button>
    </div>
    <div class="table-wrap">
      <table class="periodic-table">
        <thead>
          <tr>
            <th>ID / 尾号 / 昵称</th>
            <th>每版本</th>
            <th>每半版本</th>
            <th>每月</th>
            <th>每四周</th>
            <th>限时</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="acc in sortedAccounts"
            :key="acc.id"
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
              <div class="status-wrap">
                <label :class="['status-item', 'flag-version-matrix', { 'flag-all-done': allDoneFlags.version_matrix_soldier }]">
                  <input
                    type="checkbox"
                    v-model="versionMatrixSoldierInput[acc.id]"
                    @change="updateCheckin(acc.id, 'version_matrix_soldier', !!versionMatrixSoldierInput[acc.id])"
                  />
                  <span>矩阵叠兵</span>
                </label>
                <label :class="['status-item', 'flag-version-coral', { 'flag-all-done': allDoneFlags.version_small_coral_exchange }]">
                  <input
                    type="checkbox"
                    v-model="versionSmallCoralInput[acc.id]"
                    @change="updateCheckin(acc.id, 'version_small_coral_exchange', !!versionSmallCoralInput[acc.id])"
                  />
                  <span>小珊瑚兑换</span>
                </label>
                <label :class="['status-item', 'flag-version-hologram', { 'flag-all-done': allDoneFlags.version_hologram_challenge }]">
                  <input
                    type="checkbox"
                    v-model="versionHologramInput[acc.id]"
                    @change="updateCheckin(acc.id, 'version_hologram_challenge', !!versionHologramInput[acc.id])"
                  />
                  <span>全息挑战</span>
                </label>
                <label :class="['status-item', 'flag-version-template', { 'flag-all-done': allDoneFlags.version_echo_template_adjust }]">
                  <input
                    type="checkbox"
                    v-model="versionEchoTemplateInput[acc.id]"
                    @change="updateCheckin(acc.id, 'version_echo_template_adjust', !!versionEchoTemplateInput[acc.id])"
                  />
                  <span>声骸模板调整</span>
                </label>
              </div>
            </td>
            <td>
              <div class="status-wrap">
                <label :class="['status-item', 'flag-hv-trial', { 'flag-all-done': allDoneFlags.hv_trial_character }]">
                  <input
                    type="checkbox"
                    v-model="hvTrialCharacterInput[acc.id]"
                    @change="updateCheckin(acc.id, 'hv_trial_character', !!hvTrialCharacterInput[acc.id])"
                  />
                  <span>角色试用</span>
                </label>
              </div>
            </td>
            <td>
              <div class="status-wrap">
                <label :class="['status-item', 'flag-monthly-tower', { 'flag-all-done': allDoneFlags.monthly_tower_exchange }]">
                  <input
                    type="checkbox"
                    v-model="monthlyTowerExchangeInput[acc.id]"
                    @change="updateCheckin(acc.id, 'monthly_tower_exchange', !!monthlyTowerExchangeInput[acc.id])"
                  />
                  <span>深塔兑换所</span>
                </label>
              </div>
            </td>
            <td>
              <div class="status-wrap">
                <label :class="['status-item', 'flag-fw-tower', { 'flag-all-done': allDoneFlags.four_week_tower }]">
                  <input
                    type="checkbox"
                    v-model="fourWeekTowerInput[acc.id]"
                    @change="updateCheckin(acc.id, 'four_week_tower', !!fourWeekTowerInput[acc.id])"
                  />
                  <span>深塔</span>
                </label>
                <label :class="['status-item', 'flag-fw-ruins', { 'flag-all-done': allDoneFlags.four_week_ruins }]">
                  <input
                    type="checkbox"
                    v-model="fourWeekRuinsInput[acc.id]"
                    @change="updateCheckin(acc.id, 'four_week_ruins', !!fourWeekRuinsInput[acc.id])"
                  />
                  <span>海墟</span>
                </label>
              </div>
            </td>
            <td>
              <div class="status-wrap">
                <label :class="['status-item', 'flag-range-lahailuo', { 'flag-all-done': allDoneFlags.range_lahailuo_cube }]">
                  <input
                    type="checkbox"
                    v-model="rangeLahailuoCubeInput[acc.id]"
                    @change="updateCheckin(acc.id, 'range_lahailuo_cube', !!rangeLahailuoCubeInput[acc.id])"
                  />
                  <span>填方块</span>
                </label>
                <label :class="['status-item', 'flag-range-music', { 'flag-all-done': allDoneFlags.range_music_game }]">
                  <input
                    type="checkbox"
                    v-model="rangeMusicGameInput[acc.id]"
                    @change="updateCheckin(acc.id, 'range_music_game', !!rangeMusicGameInput[acc.id])"
                  />
                  <span>音游</span>
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
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const LAST_EDIT_STORAGE_KEY = 'wuwa_periodic_last_edit_map_v1'
const accounts = ref([])
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
  return [...accounts.value]
})

const allDoneFlags = computed(() => ({
  version_matrix_soldier: isAllChecked(versionMatrixSoldierInput.value),
  version_small_coral_exchange: isAllChecked(versionSmallCoralInput.value),
  version_hologram_challenge: isAllChecked(versionHologramInput.value),
  version_echo_template_adjust: isAllChecked(versionEchoTemplateInput.value),
  hv_trial_character: isAllChecked(hvTrialCharacterInput.value),
  monthly_tower_exchange: isAllChecked(monthlyTowerExchangeInput.value),
  four_week_tower: isAllChecked(fourWeekTowerInput.value),
  four_week_ruins: isAllChecked(fourWeekRuinsInput.value),
  range_lahailuo_cube: isAllChecked(rangeLahailuoCubeInput.value),
  range_music_game: isAllChecked(rangeMusicGameInput.value),
}))

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

function phoneTail(phoneNumber) {
  const raw = String(phoneNumber || '').trim()
  if (!raw) return '-'
  return raw.slice(-4)
}

async function refresh() {
  accounts.value = await api.listPeriodicAccounts()
  for (const acc of accounts.value) {
    versionMatrixSoldierInput.value[acc.id] = !!acc.version_matrix_soldier
    versionSmallCoralInput.value[acc.id] = !!acc.version_small_coral_exchange
    versionHologramInput.value[acc.id] = !!acc.version_hologram_challenge
    versionEchoTemplateInput.value[acc.id] = !!acc.version_echo_template_adjust
    hvTrialCharacterInput.value[acc.id] = !!acc.hv_trial_character
    monthlyTowerExchangeInput.value[acc.id] = !!acc.monthly_tower_exchange
    fourWeekTowerInput.value[acc.id] = !!acc.four_week_tower
    fourWeekRuinsInput.value[acc.id] = !!acc.four_week_ruins
    rangeLahailuoCubeInput.value[acc.id] = !!acc.range_lahailuo_cube
    rangeMusicGameInput.value[acc.id] = !!acc.range_music_game
  }
  syncHighlightedAccountId()
}

async function updateCheckin(id, flagKey, isDone) {
  try {
    await api.setCheckin(id, flagKey, isDone)
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
</script>
