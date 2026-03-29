const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const AUTH_TOKEN_KEY = 'wuwa_auth_token'

export function getAuthToken() {
  try {
    return (localStorage.getItem(AUTH_TOKEN_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function setAuthToken(token) {
  try {
    const normalized = (token || '').trim()
    if (normalized) {
      localStorage.setItem(AUTH_TOKEN_KEY, normalized)
    } else {
      localStorage.removeItem(AUTH_TOKEN_KEY)
    }
  } catch {
    // Ignore storage failures.
  }
}

export function clearAuthToken() {
  setAuthToken('')
}

async function request(path, options = {}) {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Token': token } : {}),
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
  listPeriodicAccounts: () => request('/periodic/accounts'),
  listAccounts: () => request('/accounts'),
  getAccountById: (id) => request(`/accounts/by-id/${encodeURIComponent(id)}`),
  createAccount: (payload) => request('/accounts', { method: 'POST', body: JSON.stringify(payload) }),
  updateAccount: (id, payload) =>
    request(`/accounts/by-id/${encodeURIComponent(id)}/update`, { method: 'POST', body: JSON.stringify(payload) }),
  deleteAccount: (id) => request(`/accounts/by-id/${encodeURIComponent(id)}/delete`, { method: 'POST' }),
  setWaveplate: (id, currentWaveplate, currentWaveplateCrystal = null) => {
    const payload = { current_waveplate: currentWaveplate }
    if (currentWaveplateCrystal !== null && currentWaveplateCrystal !== undefined) {
      payload.current_waveplate_crystal = currentWaveplateCrystal
    }
    return request(`/accounts/by-id/${encodeURIComponent(id)}/energy/set`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  spendWaveplate: (id, cost) =>
    request(`/accounts/by-id/${encodeURIComponent(id)}/energy/spend`, {
      method: 'POST',
      body: JSON.stringify({ cost }),
    }),
  gainWaveplate: (id, amount = 60) =>
    request(`/accounts/by-id/${encodeURIComponent(id)}/energy/gain`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    }),
  setDailyFlag: (id, flagKey, statusOrDone) => {
    const payload = { flag_key: flagKey }
    if (typeof statusOrDone === 'string') payload.status = statusOrDone
    else payload.is_done = !!statusOrDone
    return request(`/accounts/by-id/${encodeURIComponent(id)}/daily-flags`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  setCheckin: (id, flagKey, statusOrDone) => {
    const payload = { flag_key: flagKey }
    if (typeof statusOrDone === 'string') payload.status = statusOrDone
    else payload.is_done = !!statusOrDone
    return request(`/accounts/by-id/${encodeURIComponent(id)}/checkins`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  setTacet: (id, tacet) =>
    request(`/accounts/by-id/${encodeURIComponent(id)}/tacet`, {
      method: 'POST',
      body: JSON.stringify({ tacet }),
    }),
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
