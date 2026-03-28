const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || 'request failed')
  }

  if (response.status === 204) {
    return null
  }
  return response.json()
}

export const api = {
  listDashboardAccounts: () => request('/dashboard/accounts'),
  listAccounts: () => request('/accounts'),
  getAccountByPlayer: (playerId) => request(`/accounts/by-player/${encodeURIComponent(playerId)}`),
  createAccount: (payload) => request('/accounts', { method: 'POST', body: JSON.stringify(payload) }),
  updateAccount: (playerId, payload) =>
    request(`/accounts/by-player/${encodeURIComponent(playerId)}/update`, { method: 'POST', body: JSON.stringify(payload) }),
  deleteAccount: (playerId) => request(`/accounts/by-player/${encodeURIComponent(playerId)}/delete`, { method: 'POST' }),
  setEnergy: (playerId, currentEnergy) =>
    request(`/accounts/by-player/${encodeURIComponent(playerId)}/energy/set`, {
      method: 'POST',
      body: JSON.stringify({ current_energy: currentEnergy }),
    }),
  spendEnergy: (playerId, cost) =>
    request(`/accounts/by-player/${encodeURIComponent(playerId)}/energy/spend`, { method: 'POST', body: JSON.stringify({ cost }) }),
  listTaskTemplates: () => request('/task-templates'),
  createTaskTemplate: (payload) => request('/task-templates', { method: 'POST', body: JSON.stringify(payload) }),
  generateTaskInstances: (payload) =>
    request('/task-instances/generate', { method: 'POST', body: JSON.stringify(payload) }),
  listTaskInstances: (accountId, periodKey) => {
    const params = new URLSearchParams()
    if (accountId) params.set('account_id', String(accountId))
    if (periodKey) params.set('period_key', periodKey)
    const query = params.toString()
    return request(`/task-instances${query ? `?${query}` : ''}`)
  },
  updateTaskInstance: (id, payload) =>
    request(`/task-instances/${id}/update`, { method: 'POST', body: JSON.stringify(payload) }),
}
