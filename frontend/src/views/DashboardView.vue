<template>
  <section class="panel">
    <h2 style="margin-top: 0">账号体力总览</h2>
    <table>
      <thead>
        <tr>
          <th>玩家ID / 账号</th>
          <th>当前体力</th>
          <th>240回满</th>
          <th>快捷操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="acc in accounts" :key="acc.player_id" :class="acc.warn_level">
          <td>
            <strong>{{ acc.player_id }}</strong>
            <span class="meta"> / {{ acc.account_name }}</span>
          </td>
          <td>
            <strong>{{ acc.current_energy }}</strong>
          </td>
          <td>{{ formatFullTime(acc.eta_240) }}</td>
          <td>
            <div class="actions">
              <button class="primary" @click="addEnergy(acc.player_id, acc.current_energy, 60)">+60</button>
              <button v-for="cost in [40, 60, 80, 120]" :key="cost" @click="spend(acc.player_id, cost)">-{{ cost }}</button>
              <input
                v-model.number="manualInput[acc.player_id]"
                type="number"
                min="0"
                max="480"
                placeholder="体力"
                style="max-width: 84px"
              />
              <button class="primary" @click="setEnergy(acc.player_id)">校准</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'

const accounts = ref([])
const manualInput = ref({})
let fetchTimer = null

async function refresh() {
  accounts.value = await api.listDashboardAccounts()
}

function formatFullTime(v) {
  const dt = new Date(v)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetDay = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate())
  const diffDays = Math.round((targetDay - today) / 86400000)
  const hh = String(dt.getHours()).padStart(2, '0')
  const mm = String(dt.getMinutes()).padStart(2, '0')
  if (diffDays === 0) return `${hh}:${mm}`
  if (diffDays === 1) return `明天 ${hh}:${mm}`
  return `${dt.getMonth() + 1}-${dt.getDate()} ${hh}:${mm}`
}

async function spend(playerId, cost) {
  await api.spendEnergy(playerId, cost)
  await refresh()
}

async function addEnergy(playerId, currentEnergy, amount) {
  const nextEnergy = Math.min(480, Number(currentEnergy) + Number(amount))
  await api.setEnergy(playerId, nextEnergy)
  await refresh()
}

async function setEnergy(playerId) {
  const value = Number(manualInput.value[playerId])
  if (Number.isNaN(value)) return
  await api.setEnergy(playerId, value)
  await refresh()
}

onMounted(async () => {
  await refresh()
  fetchTimer = setInterval(refresh, 60000)
})

onUnmounted(() => {
  if (fetchTimer) clearInterval(fetchTimer)
})
</script>
