<template>
  <div class="app-shell">
    <header class="topbar">
      <h1>鸣潮账号体力管理系统</h1>
      <nav>
        <RouterLink to="/">每日每周</RouterLink>
        <RouterLink to="/periodic">周期活动</RouterLink>
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
