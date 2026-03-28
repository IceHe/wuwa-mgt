<template>
  <div class="app-shell">
    <header class="topbar">
      <h1>鸣潮代肝管理</h1>
      <nav>
        <RouterLink to="/">主页面</RouterLink>
        <RouterLink to="/tasks">任务页</RouterLink>
        <RouterLink to="/manage/accounts">账号管理</RouterLink>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>
