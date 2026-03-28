<template>
  <section class="panel" style="margin-bottom: 12px">
    <h2>编辑账号</h2>
    <p class="meta">账号 ID：{{ id }}</p>
    <div class="form-grid">
      <label>
        账号缩写
        <input v-model="form.abbr" />
      </label>
      <label>
        账号昵称
        <input v-model="form.nickname" />
      </label>
      <label>
        手机号
        <input v-model="form.phone_number" />
      </label>
      <label>
        启用状态
        <select v-model="form.is_active">
          <option :value="true">启用</option>
          <option :value="false">停用</option>
        </select>
      </label>
      <label>
        体力结晶
        <input v-model.number="form.waveplate_crystal" type="number" min="0" max="480" />
      </label>
    </div>
    <label>
      备注
      <textarea v-model="form.remark" rows="3" />
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
        max="240"
        placeholder="输入当前体力"
        style="max-width: 160px"
      />
      <input
        v-model.number="manualCurrentCrystal"
        type="number"
        min="0"
        max="480"
        placeholder="输入体力结晶(可选)"
        style="max-width: 180px"
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
const id = route.params.id
const saved = ref(false)
const energySaved = ref(false)
const manualCurrentEnergy = ref(0)
const manualCurrentCrystal = ref(null)

const form = reactive({
  phone_number: '',
  nickname: '',
  abbr: '',
  remark: '',
  is_active: true,
  waveplate_crystal: 0,
})

async function load() {
  const account = await api.getAccountById(id)
  form.abbr = account.abbr || ''
  form.nickname = account.nickname || ''
  form.phone_number = account.phone_number || ''
  form.remark = account.remark || ''
  form.is_active = !!account.is_active
  form.waveplate_crystal = Number(account.waveplate_crystal || 0)
  manualCurrentEnergy.value = Number(account.last_waveplate || 0)
  manualCurrentCrystal.value = Number(account.waveplate_crystal || 0)
}

async function save() {
  saved.value = false
  await api.updateAccount(id, {
    abbr: form.abbr,
    nickname: form.nickname,
    phone_number: form.phone_number,
    remark: form.remark,
    is_active: form.is_active,
    waveplate_crystal: form.waveplate_crystal,
  })
  saved.value = true
  await load()
}

async function setCurrentEnergy() {
  const value = Number(manualCurrentEnergy.value ?? 0)
  const crystalRaw = manualCurrentCrystal.value
  const crystal =
    crystalRaw === '' || crystalRaw === undefined || crystalRaw === null ? null : Number(crystalRaw)
  if (Number.isNaN(value) || value < 0 || value > 240) {
    alert('体力范围应为 0~240')
    return
  }
  if (crystal !== null && (Number.isNaN(crystal) || crystal < 0 || crystal > 480)) {
    alert('体力结晶范围应为 0~480')
    return
  }
  energySaved.value = false
  await api.setWaveplate(id, value, crystal)
  energySaved.value = true
  await load()
}

function back() {
  router.push('/manage/accounts')
}

onMounted(load)
</script>
