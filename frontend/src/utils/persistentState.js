export function loadStoredValue(storageKey, fallbackValue, validValues = []) {
  if (typeof window === 'undefined') return fallbackValue
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (raw === null) return fallbackValue
    if (Array.isArray(validValues) && validValues.length > 0 && !validValues.includes(raw)) {
      return fallbackValue
    }
    return raw
  } catch {
    return fallbackValue
  }
}

export function saveStoredValue(storageKey, value) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(storageKey, value)
  } catch {
    // Ignore storage failures.
  }
}
