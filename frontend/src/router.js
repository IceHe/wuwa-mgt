import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import AccountsManageView from './views/AccountsManageView.vue'
import AccountEditView from './views/AccountEditView.vue'
import TasksView from './views/TasksView.vue'

const routes = [
  { path: '/', component: DashboardView },
  { path: '/tasks', component: TasksView },
  { path: '/manage/accounts', component: AccountsManageView },
  { path: '/manage/accounts/:playerId', component: AccountEditView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
