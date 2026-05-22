export const WAVEPLATE_CAP = 240
export const WAVEPLATE_RECOVERY_SECONDS = 360
export const WAVEPLATE_CRYSTAL_CAP = 480
export const WAVEPLATE_CRYSTAL_RECOVERY_SECONDS = 720

function clampInt(value, min, max) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return min
  return Math.min(max, Math.max(min, Math.trunc(numeric)))
}

function warnLevel(waveplate) {
  const current = clampInt(waveplate, 0, WAVEPLATE_CAP)
  if (current >= 235) return 'danger'
  if (current >= 220) return 'warning'
  return 'normal'
}

export function deriveEnergySnapshot(account, nowMs = Date.now()) {
  const currentWaveplate = clampInt(account?.current_waveplate, 0, WAVEPLATE_CAP)
  const currentCrystal = clampInt(account?.current_waveplate_crystal, 0, WAVEPLATE_CRYSTAL_CAP)
  const fullAtMs = new Date(account?.eta_waveplate_full || account?.full_waveplate_at || '').getTime()
  if (Number.isNaN(fullAtMs)) {
    return {
      current_waveplate: currentWaveplate,
      current_waveplate_crystal: currentCrystal,
      waveplate_full_in_minutes: 0,
      warn_level: warnLevel(currentWaveplate),
    }
  }

  if (fullAtMs > nowMs) {
    const deltaSeconds = Math.ceil((fullAtMs - nowMs) / 1000)
    const missingWaveplate = Math.min(
      WAVEPLATE_CAP,
      Math.ceil(deltaSeconds / WAVEPLATE_RECOVERY_SECONDS),
    )
    const liveWaveplate = WAVEPLATE_CAP - missingWaveplate
    return {
      current_waveplate: liveWaveplate,
      current_waveplate_crystal: currentCrystal,
      waveplate_full_in_minutes: Math.ceil(deltaSeconds / 60),
      warn_level: warnLevel(liveWaveplate),
    }
  }

  const snapshotMs = Number(account?._energy_snapshot_ms || nowMs)
  const snapshotTicks = Math.max(
    0,
    Math.floor(Math.max(0, snapshotMs - fullAtMs) / 1000 / WAVEPLATE_CRYSTAL_RECOVERY_SECONDS),
  )
  const nowTicks = Math.max(
    0,
    Math.floor(Math.max(0, nowMs - fullAtMs) / 1000 / WAVEPLATE_CRYSTAL_RECOVERY_SECONDS),
  )
  const gainedCrystal = Math.max(0, nowTicks - snapshotTicks)
  const liveCrystal = clampInt(currentCrystal + gainedCrystal, 0, WAVEPLATE_CRYSTAL_CAP)

  return {
    current_waveplate: WAVEPLATE_CAP,
    current_waveplate_crystal: liveCrystal,
    waveplate_full_in_minutes: 0,
    warn_level: warnLevel(WAVEPLATE_CAP),
  }
}
