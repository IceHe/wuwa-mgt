<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">账号列表</h2>
      <div class="actions" style="align-items: center; gap: 12px">
        <label style="max-width: 220px">
          排序方式
          <select v-model="sortMode">
            <option value="abbr">账户缩写</option>
            <option value="created_desc">最近创建</option>
            <option value="updated_desc">最近修改</option>
          </select>
        </label>
        <button class="primary" @click="openCreateModal">创建账号</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="manage-table">
        <thead>
          <tr>
            <th>ID / 尾号 / 昵称</th>
            <th>手机号</th>
            <th>上次体力</th>
            <th>结晶</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="acc in sortedAccounts" :key="acc.id" :class="{ inactive: !acc.is_active }">
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
              <span v-if="acc.phone_number">{{ maskPhone(acc.phone_number) }}</span>
              <span v-else>-</span>
              <button
                v-if="acc.phone_number"
                style="margin-left: 6px; padding: 2px 6px"
                @click="copyPhone(acc)"
              >
                {{ copiedAccountId === acc.account_id ? '已复制' : '复制' }}
              </button>
            </td>
            <td>{{ acc.last_waveplate }}</td>
            <td>{{ acc.waveplate_crystal }}</td>
            <td>
              <button @click="edit(acc.id)">编辑</button>
              <button :class="acc.is_active ? 'warn' : ''" @click="toggleActive(acc)">
                {{ acc.is_active ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <div v-if="showCreateModal" class="modal-mask" @click="closeCreateModal">
    <div class="modal-card panel" @click.stop>
      <h2 style="margin-top: 0">新建账号</h2>
      <div class="form-grid">
        <label>
          账号 ID
          <input v-model="form.id" placeholder="例: 120003177" />
        </label>
        <label>
          账号缩写 (abbr)
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
          上次更新体力
          <input v-model.number="form.last_waveplate" type="number" min="0" max="240" />
        </label>
        <label>
          体力结晶
          <input v-model.number="form.waveplate_crystal" type="number" min="0" max="480" />
        </label>
      </div>
      <label>
        备注
        <textarea v-model="form.remark" rows="2" />
      </label>
      <div class="actions" style="margin-top: 10px; justify-content: flex-end">
        <button @click="closeCreateModal">取消</button>
        <button class="primary" @click="create">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const accounts = ref([])
const sortMode = ref('abbr')
const copiedAccountId = ref(null)
const showCreateModal = ref(false)
const form = reactive({
  id: '',
  phone_number: '',
  nickname: '',
  abbr: '',
  remark: '',
  last_waveplate: 0,
  waveplate_crystal: 0,
  is_active: true,
})

const sortedAccounts = computed(() => {
  const rows = [...accounts.value]
  if (sortMode.value === 'created_desc') {
    rows.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    return rows
  }
  if (sortMode.value === 'updated_desc') {
    rows.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    return rows
  }
  rows.sort((a, b) => String(a.abbr || '').localeCompare(String(b.abbr || '')))
  return rows
})

async function refresh() {
  accounts.value = await api.listAccounts()
}

async function create() {
  await api.createAccount(form)
  resetCreateForm()
  showCreateModal.value = false
  await refresh()
}

function edit(id) {
  router.push(`/manage/accounts/${encodeURIComponent(id)}`)
}

function openCreateModal() {
  showCreateModal.value = true
}

function closeCreateModal() {
  showCreateModal.value = false
}

function resetCreateForm() {
  form.id = ''
  form.phone_number = ''
  form.nickname = ''
  form.abbr = ''
  form.remark = ''
  form.last_waveplate = 0
  form.waveplate_crystal = 0
}

async function toggleActive(acc) {
  const nextActive = !acc.is_active
  const actionText = nextActive ? '启用' : '停用'
  if (!confirm(`确认${actionText}账号 ${acc.id} 吗？`)) return
  await api.updateAccount(acc.id, { is_active: nextActive })
  await refresh()
}

function maskPhone(phone) {
  const raw = String(phone || '').trim()
  if (raw.length < 7) return raw
  return `${raw.slice(0, 3)}****${raw.slice(-4)}`
}

function phoneTail(phone) {
  const raw = String(phone || '').trim()
  if (!raw) return '-'
  return raw.slice(-4)
}

async function copyPhone(acc) {
  const full = String(acc.phone_number || '').trim()
  if (!full) return
  try {
    await navigator.clipboard.writeText(full)
  } catch {
    const input = document.createElement('input')
    input.value = full
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
  }
  copiedAccountId.value = acc.account_id
  setTimeout(() => {
    if (copiedAccountId.value === acc.account_id) copiedAccountId.value = null
  }, 1200)
}

onMounted(refresh)
</script>
