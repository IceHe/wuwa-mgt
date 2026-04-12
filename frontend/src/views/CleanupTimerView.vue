<template>
  <section class="panel">
    <div class="actions" style="justify-content: space-between; margin-bottom: 8px; align-items: center">
      <h2 style="margin: 0">清日常计时明细</h2>
      <div class="actions" style="align-items: center">
        <label>
          范围
          <select v-model.number="days" @change="refreshAll">
            <option :value="7">近 7 天</option>
            <option :value="14">近 14 天</option>
            <option :value="30">近 30 天</option>
          </select>
        </label>
        <button type="button" @click="refreshAll">刷新</button>
      </div>
    </div>

    <div class="cleanup-summary-grid">
      <div class="cleanup-summary-card">
        <div class="meta">统计区间</div>
        <div><strong>{{ weeklySummary.range_start || '-' }}</strong> ~ <strong>{{ weeklySummary.range_end || '-' }}</strong></div>
      </div>
      <div class="cleanup-summary-card">
        <div class="meta">总时长</div>
        <div class="cleanup-total-text">{{ formatDurationMmSs(weeklySummary.total_duration_sec || 0) }}</div>
      </div>
    </div>

    <div class="cleanup-summary-card" style="margin-top: 10px">
      <div class="meta" style="margin-bottom: 6px">手动补录</div>
      <div v-if="manualSuccess.message" class="cleanup-manual-success">
        <strong>补录成功</strong>
        <span>{{ manualSuccess.message }}</span>
      </div>
      <div class="cleanup-manual-form">
        <label>
          指定用户
          <select v-model="manual.accountId">
            <option value="">请选择账号</option>
            <option v-for="acc in accounts" :key="acc.account_id" :value="String(acc.account_id)">
              {{ acc.abbr }} / {{ acc.id }} / {{ acc.nickname }}
            </option>
          </select>
        </label>
        <label>
          录入方式
          <select v-model="manual.mode">
            <option value="duration">按时长</option>
            <option value="period">按时段</option>
          </select>
        </label>
        <template v-if="manual.mode === 'duration'">
          <label>
            业务日
            <input v-model="manual.bizDate" type="date" />
          </label>
          <label>
            小时
            <input v-model.number="manual.hours" type="number" min="0" max="24" />
          </label>
          <label>
            分钟
            <input v-model.number="manual.minutes" type="number" min="0" max="59" />
          </label>
          <label>
            秒
            <input v-model.number="manual.seconds" type="number" min="0" max="59" />
          </label>
        </template>
        <template v-else>
          <label>
            开始时间
            <input v-model="manual.periodStart" type="datetime-local" step="1" />
          </label>
          <label>
            结束时间
            <input v-model="manual.periodEnd" type="datetime-local" step="1" />
          </label>
        </template>
        <button type="button" class="primary" :disabled="manual.saving" @click="submitManualSession">
          补录
        </button>
      </div>
    </div>

    <div class="table-wrap" style="margin-top: 10px">
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>时长</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in weeklySummary.daily || []" :key="item.biz_date">
            <td>{{ item.biz_date }}</td>
            <td>{{ formatDurationMmSs(item.duration_sec) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="table-wrap" style="margin-top: 10px">
      <table>
        <thead>
          <tr>
            <th>账号</th>
            <th>一周时长</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in weeklySummary.by_account || []" :key="item.account_id">
            <td>{{ item.abbr }} / {{ item.id }} / {{ item.nickname }}</td>
            <td>{{ formatDurationMmSs(item.duration_sec) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="table-wrap" style="margin-top: 10px">
      <table>
        <thead>
          <tr>
            <th>业务日</th>
            <th>账号</th>
            <th>开始</th>
            <th>结束</th>
            <th>时长</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sessions" :key="row.id">
            <td>{{ row.biz_date }}</td>
            <td>{{ row.account_abbr }} / {{ row.account_game_id }}</td>
            <td>{{ formatDateTime(row.started_at) }}</td>
            <td>{{ row.ended_at ? formatDateTime(row.ended_at) : '-' }}</td>
            <td>{{ formatDurationMmSs(row.status === 'running' ? runningDurationSec(row.started_at) : row.duration_sec) }}</td>
            <td>{{ row.status === 'running' ? '进行中' : '已暂停' }}</td>
            <td>
              <button
                type="button"
                class="warn"
                :disabled="deletingSessionId === row.id"
                @click="deleteSession(row)"
              >
                {{ deletingSessionId === row.id ? '删除中...' : '删除' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'

const days = ref(7)
const accounts = ref([])
const weeklySummary = ref({
  range_start: '',
  range_end: '',
  total_duration_sec: 0,
  daily: [],
  by_account: [],
})
const sessions = ref([])
const clockNowMs = ref(Date.now())
const deletingSessionId = ref(null)
const manualSuccess = ref({
  message: '',
  ts: 0,
})
const manual = ref({
  mode: 'duration',
  accountId: '',
  bizDate: getTodayDateKey(),
  hours: 0,
  minutes: 30,
  seconds: 0,
  periodStart: getNowDateTimeLocalText(),
  periodEnd: getLaterDateTimeLocalText(30 * 60),
  saving: false,
})
let timer = null

function getTodayDateKey() {
  const dt = new Date()
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function getNowDateTimeLocalText() {
  const dt = new Date()
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  const hh = String(dt.getHours()).padStart(2, '0')
  const mm = String(dt.getMinutes()).padStart(2, '0')
  const ss = String(dt.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d}T${hh}:${mm}:${ss}`
}

function getLaterDateTimeLocalText(deltaSeconds) {
  const dt = new Date(Date.now() + deltaSeconds * 1000)
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  const hh = String(dt.getHours()).padStart(2, '0')
  const mm = String(dt.getMinutes()).padStart(2, '0')
  const ss = String(dt.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d}T${hh}:${mm}:${ss}`
}

function formatDurationMmSs(totalSeconds) {
  const sec = Math.max(0, Number(totalSeconds) || 0)
  const mm = String(Math.floor(sec / 60)).padStart(2, '0')
  const ss = String(sec % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function formatDateTime(v) {
  const dt = new Date(v)
  if (Number.isNaN(dt.getTime())) return '-'
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  const hh = String(dt.getHours()).padStart(2, '0')
  const mm = String(dt.getMinutes()).padStart(2, '0')
  const ss = String(dt.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

function runningDurationSec(startedAt) {
  const started = new Date(startedAt).getTime()
  if (Number.isNaN(started)) return 0
  return Math.max(0, Math.floor((clockNowMs.value - started) / 1000))
}

async function refreshAll() {
  const [summary, detail] = await Promise.all([
    api.getCleanupWeeklySummary(days.value),
    api.listCleanupSessions(days.value),
  ])
  weeklySummary.value = summary
  sessions.value = detail
}

async function refreshAccounts() {
  const rows = await api.listAccounts()
  accounts.value = rows.filter((item) => item.is_active).sort((a, b) => String(a.abbr || '').localeCompare(String(b.abbr || '')))
  if (!manual.value.accountId && accounts.value.length) {
    manual.value.accountId = String(accounts.value[0].account_id)
  }
}

async function submitManualSession() {
  const accountId = Number(manual.value.accountId)
  if (!accountId) {
    alert('请选择账号')
    return
  }
  manualSuccess.value = { message: '', ts: 0 }
  manual.value.saving = true
  try {
    let successMessage = ''
    if (manual.value.mode === 'duration') {
      const hours = Number(manual.value.hours)
      const minutes = Number(manual.value.minutes)
      const seconds = Number(manual.value.seconds)
      const bizDate = String(manual.value.bizDate || '').trim()
      if (!/^\d{4}-\d{2}-\d{2}$/.test(bizDate)) {
        alert('业务日格式无效')
        return
      }
      if (!Number.isInteger(hours) || hours < 0 || hours > 24) {
        alert('小时范围应为 0~24')
        return
      }
      if (!Number.isInteger(minutes) || minutes < 0 || minutes > 59) {
        alert('分钟范围应为 0~59')
        return
      }
      if (!Number.isInteger(seconds) || seconds < 0 || seconds > 59) {
        alert('秒范围应为 0~59')
        return
      }
      const durationSec = hours * 3600 + minutes * 60 + seconds
      if (durationSec <= 0) {
        alert('补录时长必须大于 0 秒')
        return
      }
      if (durationSec > 86400) {
        alert('补录时长不能超过 24 小时')
        return
      }
      await api.createCleanupSessionManual({
        account_id: accountId,
        biz_date: bizDate,
        duration_sec: durationSec,
      })
      successMessage = `${bizDate} 已补录 ${formatDurationMmSs(durationSec)}`
    } else {
      const startRaw = String(manual.value.periodStart || '').trim()
      const endRaw = String(manual.value.periodEnd || '').trim()
      if (!startRaw || !endRaw) {
        alert('请填写开始时间和结束时间')
        return
      }
      const start = new Date(startRaw)
      const end = new Date(endRaw)
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        alert('时段格式无效')
        return
      }
      if (end.getTime() <= start.getTime()) {
        alert('结束时间必须晚于开始时间')
        return
      }
      const durationSec = Math.floor((end.getTime() - start.getTime()) / 1000)
      if (durationSec > 86400) {
        alert('补录时段不能超过 24 小时')
        return
      }
      await api.createCleanupSessionManual({
        account_id: accountId,
        started_at: start.toISOString(),
        ended_at: end.toISOString(),
      })
      successMessage = `${formatDateTime(start)} ~ ${formatDateTime(end)} 已补录`
    }
    await refreshAll()
    manualSuccess.value = {
      message: successMessage,
      ts: Date.now(),
    }
  } catch (err) {
    alert(`补录失败：${err.message || '请稍后重试'}`)
  } finally {
    manual.value.saving = false
  }
}

async function deleteSession(row) {
  const ok = confirm(`确认删除该记录吗？\n账号: ${row.account_abbr} / ${row.account_game_id}\n开始: ${formatDateTime(row.started_at)}`)
  if (!ok) return
  deletingSessionId.value = row.id
  try {
    await api.deleteCleanupSession(row.id)
    await refreshAll()
  } catch (err) {
    alert(`删除失败：${err.message || '请稍后重试'}`)
  } finally {
    deletingSessionId.value = null
  }
}

onMounted(async () => {
  await Promise.all([refreshAccounts(), refreshAll()])
  timer = setInterval(() => {
    clockNowMs.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
