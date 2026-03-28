<template>
  <section class="panel" style="margin-bottom: 12px">
    <h2>编辑账号</h2>
    <p class="meta">玩家ID：{{ playerId }}</p>
    <div class="form-grid">
      <label>
        账号缩写
        <input v-model="form.account_code" />
      </label>
      <label>
        账号名称
        <input v-model="form.account_name" />
      </label>
      <label>
        手机号
        <input v-model="form.phone" />
      </label>
      <label>
        启用状态
        <select v-model="form.is_active">
          <option :value="true">启用</option>
          <option :value="false">停用</option>
        </select>
      </label>
      <label>
        前一个4点体力
        <input v-model.number="form.energy_at_prev_4am" type="number" min="0" max="480" />
      </label>
    </div>
    <label>
      备注
      <textarea v-model="form.note" rows="3" />
    </label>
    <div class="actions" style="margin-top: 8px">
      <button class="primary" @click="save">保存</button>
      <button @click="back">返回</button>
      <span v-if="saved" class="meta">已保存</span>
    </div>

    <hr style="border: none; border-top: 1px solid #dce3f1; margin: 14px 0" />
    <h3>当前体力校准</h3>
    <div class="actions">
      <input
        v-model.number="manualCurrentEnergy"
        type="number"
        min="0"
        max="480"
        placeholder="输入当前体力"
        style="max-width: 160px"
      />
      <button class="primary" @click="setCurrentEnergy">校准当前体力</button>
      <span v-if="energySaved" class="meta">已校准</span>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const playerId = route.params.playerId
const saved = ref(false)
const energySaved = ref(false)
const manualCurrentEnergy = ref(0)

const form = reactive({
  account_code: '',
  account_name: '',
  phone: '',
  note: '',
  is_active: true,
  energy_at_prev_4am: 0,
})

async function load() {
  const account = await api.getAccountByPlayer(playerId)
  form.account_code = account.account_code || ''
  form.account_name = account.account_name || ''
  form.phone = account.phone || ''
  form.note = account.note || ''
  form.is_active = !!account.is_active
  form.energy_at_prev_4am = Number(account.energy_at_prev_4am || 0)
  manualCurrentEnergy.value = Number(account.energy_at_prev_4am || 0)
}

async function save() {
  saved.value = false
  await api.updateAccount(playerId, {
    account_code: form.account_code,
    account_name: form.account_name,
    phone: form.phone,
    note: form.note,
    is_active: form.is_active,
    energy_at_prev_4am: form.energy_at_prev_4am,
  })
  saved.value = true
  await load()
}

async function setCurrentEnergy() {
  const value = Number(manualCurrentEnergy.value)
  if (Number.isNaN(value)) return
  energySaved.value = false
  await api.setEnergy(playerId, value)
  energySaved.value = true
  await load()
}

function back() {
  router.push('/manage/accounts')
}

onMounted(load)
</script>
