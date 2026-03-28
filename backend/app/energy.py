from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ENERGY_SOFT_CAP = 240
ENERGY_HARD_CAP = 480


def clamp_energy(value: int) -> int:
    return max(0, min(ENERGY_HARD_CAP, int(value)))


def previous_4am(now: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    pivot = local_now.replace(hour=4, minute=0, second=0, microsecond=0)
    if local_now < pivot:
        pivot -= timedelta(days=1)
    return pivot.astimezone(now.tzinfo)


def calc_energy_from_elapsed(base_energy: int, elapsed_minutes: int) -> int:
    energy = clamp_energy(base_energy)
    elapsed = max(0, elapsed_minutes)

    if energy < ENERGY_SOFT_CAP:
        mins_to_soft = (ENERGY_SOFT_CAP - energy) * 6
        if elapsed <= mins_to_soft:
            return clamp_energy(energy + elapsed // 6)
        elapsed -= mins_to_soft
        energy = ENERGY_SOFT_CAP

    # Above soft cap: recovery speed halves.
    energy += elapsed // 12
    return clamp_energy(energy)


def current_energy(base_energy: int, base_at: datetime, now: datetime) -> int:
    elapsed = int((now - base_at).total_seconds() // 60)
    return calc_energy_from_elapsed(base_energy, elapsed)


def infer_base_energy_from_current(target_energy: int, base_at: datetime, now: datetime) -> int:
    elapsed = int((now - base_at).total_seconds() // 60)
    target = clamp_energy(target_energy)

    lo, hi = 0, ENERGY_HARD_CAP
    while lo < hi:
        mid = (lo + hi) // 2
        got = calc_energy_from_elapsed(mid, elapsed)
        if got < target:
            lo = mid + 1
        else:
            hi = mid

    best = lo
    if calc_energy_from_elapsed(best, elapsed) != target:
        # Fallback for unreachable target due to step granularity.
        return max(0, best - 1)
    return best


def minutes_to_target(now_energy: int, target: int) -> int | None:
    current = clamp_energy(now_energy)
    tgt = clamp_energy(target)
    if current >= tgt:
        return 0

    if current < ENERGY_SOFT_CAP and tgt <= ENERGY_SOFT_CAP:
        return (tgt - current) * 6

    minutes = 0
    if current < ENERGY_SOFT_CAP:
        minutes += (ENERGY_SOFT_CAP - current) * 6
        current = ENERGY_SOFT_CAP
    minutes += (tgt - current) * 12
    return minutes


def warn_level(now_energy: int) -> str:
    if now_energy >= 240:
        return "danger"
    if now_energy >= 235:
        return "danger"
    if now_energy >= 220:
        return "warning"
    return "normal"
