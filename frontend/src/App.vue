<template>
  <div class="app-shell">
    <header class="topbar">
      <h1>鸣潮账号体力管理系统</h1>
      <nav>
        <RouterLink to="/">每日每周</RouterLink>
        <RouterLink to="/periodic">周期活动</RouterLink>
        <RouterLink to="/periodic-beta">周期活动beta</RouterLink>
        <RouterLink to="/cleanup-timer">清日常时长</RouterLink>
        <RouterLink to="/manage/accounts">账号管理</RouterLink>
      </nav>
      <div class="auth-inline">
        <template v-if="!isAuthed">
          <input
            v-model="tokenInput"
            type="password"
            placeholder="请输入 manage Token"
            style="width: 210px"
            @keyup.enter="login"
          />
          <button type="button" class="primary" @click="login">登录</button>
        </template>
        <template v-else>
          <span class="auth-status">已登录（manage）</span>
          <button type="button" @click="logout">退出</button>
        </template>
      </div>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { clearAuthToken, getAuthToken, setAuthToken } from './api'

const tokenInput = ref(getAuthToken())
const isAuthed = ref(false)

async function verifyManageToken(token) {
  const response = await fetch('/api/auth/ping', {
    headers: {
      'Content-Type': 'application/json',
      'X-Token': token,
    },
  })
  return response.ok
}

async function login() {
  const token = (tokenInput.value || '').trim()
  if (!token) {
    alert('请输入 Token')
    return
  }
  const ok = await verifyManageToken(token)
  if (!ok) {
    clearAuthToken()
    isAuthed.value = false
    alert('登录失败：Token 无效或没有 manage 权限')
    return
  }
  setAuthToken(token)
  isAuthed.value = true
  tokenInput.value = ''
}

function logout() {
  isAuthed.value = false
  tokenInput.value = ''
  clearAuthToken()
}

onMounted(async () => {
  const saved = (getAuthToken() || '').trim()
  if (!saved) {
    isAuthed.value = false
    return
  }
  isAuthed.value = await verifyManageToken(saved)
  if (!isAuthed.value) {
    clearAuthToken()
  }
})
</script>
