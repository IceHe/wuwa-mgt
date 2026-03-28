<template>
  <section class="panel" style="margin-bottom: 12px">
    <h2>新建账号</h2>
    <div class="form-grid">
      <label>
        玩家ID
        <input v-model="form.player_id" placeholder="例: 120003177" />
      </label>
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
        前一个4点体力
        <input v-model.number="form.energy_at_prev_4am" type="number" min="0" max="480" />
      </label>
    </div>
    <label>
      备注
      <textarea v-model="form.note" rows="2" />
    </label>
    <div class="actions" style="margin-top: 8px">
      <button class="primary" @click="create">创建</button>
    </div>
  </section>

  <section class="panel">
    <h2>账号列表</h2>
    <table>
      <thead>
        <tr>
          <th>玩家ID</th>
          <th>缩写</th>
          <th>名称</th>
          <th>手机号</th>
          <th>前一个4点体力</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="acc in accounts" :key="acc.player_id">
          <td>{{ acc.player_id }}</td>
          <td>{{ acc.account_code }}</td>
          <td>{{ acc.account_name }}</td>
          <td>{{ acc.phone || '-' }}</td>
          <td>{{ acc.energy_at_prev_4am }}</td>
          <td>
            <button @click="edit(acc.player_id)">编辑</button>
            <button class="warn" @click="remove(acc.player_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const accounts = ref([])
const form = reactive({
  player_id: '',
  account_code: '',
  account_name: '',
  phone: '',
  note: '',
  energy_at_prev_4am: 0,
  is_active: true,
})

async function refresh() {
  accounts.value = await api.listAccounts()
}

async function create() {
  await api.createAccount(form)
  form.player_id = ''
  form.account_code = ''
  form.account_name = ''
  form.phone = ''
  form.note = ''
  form.energy_at_prev_4am = 0
  await refresh()
}

async function remove(playerId) {
  await api.deleteAccount(playerId)
  await refresh()
}

function edit(playerId) {
  router.push(`/manage/accounts/${encodeURIComponent(playerId)}`)
}

onMounted(refresh)
</script>
