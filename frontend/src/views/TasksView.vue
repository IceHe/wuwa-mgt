<template>
  <section class="panel" style="margin-bottom: 12px">
    <h2>任务模板</h2>
    <div class="form-grid">
      <label>
        名称
        <input v-model="templateForm.name" placeholder="例：清体力" />
      </label>
      <label>
        类型
        <select v-model="templateForm.task_type">
          <option value="daily">每日</option>
          <option value="weekly">每周</option>
          <option value="version">版本</option>
          <option value="half_version">半版本</option>
          <option value="special">特定周期</option>
        </select>
      </label>
      <label>
        默认优先级
        <input v-model.number="templateForm.default_priority" type="number" min="1" max="9" />
      </label>
    </div>
    <label>
      描述
      <input v-model="templateForm.description" placeholder="选填" />
    </label>
    <div class="actions" style="margin-top: 8px">
      <button class="primary" @click="createTemplate">新增模板</button>
      <span class="meta">模板总数：{{ templates.length }}</span>
    </div>
  </section>

  <section class="panel" style="margin-bottom: 12px">
    <h2>批量生成当期任务</h2>
    <div class="form-grid">
      <label>
        period_key
        <input v-model="generator.period_key" placeholder="例：2026-03-28 或 2026-W13" />
      </label>
      <label>
        开始时间
        <input v-model="generator.start_at" type="datetime-local" />
      </label>
      <label>
        截止时间
        <input v-model="generator.deadline_at" type="datetime-local" />
      </label>
      <label>
        类型过滤
        <select v-model="generator.task_type">
          <option value="">全部</option>
          <option value="daily">每日</option>
          <option value="weekly">每周</option>
          <option value="version">版本</option>
          <option value="half_version">半版本</option>
          <option value="special">特定周期</option>
        </select>
      </label>
    </div>
    <div class="actions" style="margin-top: 8px">
      <button class="primary" @click="generate">一键生成</button>
      <span v-if="lastCreatedCount !== null" class="meta">本次新增：{{ lastCreatedCount }}</span>
    </div>
  </section>

  <section class="panel">
    <h2>周期任务实例</h2>
    <div class="actions" style="margin-bottom: 10px">
      <label style="max-width: 180px">
        账号ID
        <input v-model.number="accountId" type="number" min="1" placeholder="可选" />
      </label>
      <label style="max-width: 240px">
        period_key
        <input v-model="periodKey" placeholder="例: 2026-03-28" />
      </label>
      <button class="primary" @click="refresh">查询</button>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>账号</th>
          <th>模板</th>
          <th>period_key</th>
          <th>优先级</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.id }}</td>
          <td>{{ row.account_id }}</td>
          <td>{{ row.template_id }}</td>
          <td>{{ row.period_key }}</td>
          <td>{{ row.priority }}</td>
          <td>
            <select :value="row.status" @change="setStatus(row.id, $event.target.value)">
              <option value="todo">待办</option>
              <option value="done">已完成</option>
              <option value="skipped">跳过</option>
            </select>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const rows = ref([])
const templates = ref([])
const accountId = ref(null)
const periodKey = ref('')
const lastCreatedCount = ref(null)

const templateForm = reactive({
  name: '',
  task_type: 'daily',
  default_priority: 3,
  description: '',
  is_active: true,
})

const nowLocal = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
  .toISOString()
  .slice(0, 16)
const generator = reactive({
  period_key: new Date().toISOString().slice(0, 10),
  start_at: nowLocal,
  deadline_at: '',
  task_type: '',
})

async function refreshTemplates() {
  templates.value = await api.listTaskTemplates()
}

async function refresh() {
  rows.value = await api.listTaskInstances(accountId.value, periodKey.value.trim())
}

async function createTemplate() {
  if (!templateForm.name.trim()) return
  await api.createTaskTemplate({
    ...templateForm,
    name: templateForm.name.trim(),
    description: templateForm.description.trim() || null,
  })
  templateForm.name = ''
  templateForm.description = ''
  await refreshTemplates()
}

async function generate() {
  if (!generator.period_key.trim() || !generator.start_at) return
  const payload = {
    period_key: generator.period_key.trim(),
    start_at: new Date(generator.start_at).toISOString(),
    deadline_at: generator.deadline_at ? new Date(generator.deadline_at).toISOString() : null,
    task_type: generator.task_type || null,
  }
  const result = await api.generateTaskInstances(payload)
  lastCreatedCount.value = result.created
  periodKey.value = payload.period_key
  await refresh()
}

async function setStatus(id, status) {
  await api.updateTaskInstance(id, { status })
  await refresh()
}

onMounted(async () => {
  await refreshTemplates()
  await refresh()
})
</script>
