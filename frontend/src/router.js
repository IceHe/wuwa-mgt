import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import AccountsManageView from './views/AccountsManageView.vue'
import AccountEditView from './views/AccountEditView.vue'
import TasksView from './views/TasksView.vue'
import PeriodicView from './views/PeriodicView.vue'
import PeriodicBetaView from './views/PeriodicBetaView.vue'
import CleanupTimerView from './views/CleanupTimerView.vue'

const routes = [
  { path: '/', component: DashboardView },
  { path: '/periodic', component: PeriodicView },
  { path: '/periodic-beta', component: PeriodicBetaView },
  { path: '/cleanup-timer', component: CleanupTimerView },
  { path: '/tasks', component: TasksView },
  { path: '/manage/accounts', component: AccountsManageView },
  { path: '/manage/accounts/:id', component: AccountEditView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
