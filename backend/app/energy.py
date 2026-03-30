from datetime import datetime, timedelta
from math import ceil

WAVEPLATE_CAP = 240
WAVEPLATE_RECOVER_MINUTES = 6
WAVEPLATE_RECOVER_SECONDS = WAVEPLATE_RECOVER_MINUTES * 60
WAVEPLATE_CRYSTAL_CAP = 480
WAVEPLATE_CRYSTAL_RECOVER_MINUTES = 12
WAVEPLATE_CRYSTAL_RECOVER_SECONDS = WAVEPLATE_CRYSTAL_RECOVER_MINUTES * 60


def clamp_waveplate(value: int) -> int:
    return max(0, min(WAVEPLATE_CAP, int(value)))


def clamp_waveplate_crystal(value: int) -> int:
    return max(0, min(WAVEPLATE_CRYSTAL_CAP, int(value)))


def normalize_resources(waveplate: int, waveplate_crystal: int) -> tuple[int, int]:
    wp = max(0, int(waveplate))
    crystal = max(0, int(waveplate_crystal))
    if wp > WAVEPLATE_CAP:
        crystal += wp - WAVEPLATE_CAP
        wp = WAVEPLATE_CAP
    crystal = clamp_waveplate_crystal(crystal)
    return wp, crystal


def seconds_to_waveplate_full_from_current(waveplate: int) -> int:
    wp = clamp_waveplate(waveplate)
    if wp >= WAVEPLATE_CAP:
        return 0
    return (WAVEPLATE_CAP - wp) * WAVEPLATE_RECOVER_SECONDS


def seconds_to_waveplate_full_from_full_time(full_waveplate_at: datetime, now: datetime) -> int:
    return max(0, int((full_waveplate_at - now).total_seconds()))


def current_resources_from_full_time(
    full_waveplate_at: datetime,
    full_waveplate_crystal: int,
    now: datetime,
) -> tuple[int, int]:
    base_crystal = clamp_waveplate_crystal(full_waveplate_crystal)
    delta_seconds = int((full_waveplate_at - now).total_seconds())
    if delta_seconds > 0:
        missing = min(WAVEPLATE_CAP, ceil(delta_seconds / WAVEPLATE_RECOVER_SECONDS))
        current_wp = WAVEPLATE_CAP - missing
        return current_wp, base_crystal

    crystal_gained = max(0, int((now - full_waveplate_at).total_seconds()) // WAVEPLATE_CRYSTAL_RECOVER_SECONDS)
    return WAVEPLATE_CAP, clamp_waveplate_crystal(base_crystal + crystal_gained)


def full_time_from_current_resources(
    waveplate: int,
    current_waveplate_crystal: int,
    now: datetime,
) -> tuple[datetime, int]:
    wp, crystal = normalize_resources(waveplate, current_waveplate_crystal)
    return now + timedelta(seconds=seconds_to_waveplate_full_from_current(wp)), crystal


def full_crystal_from_current_crystal(
    current_waveplate_crystal: int,
    full_waveplate_at: datetime,
    now: datetime,
) -> int:
    current_crystal = clamp_waveplate_crystal(current_waveplate_crystal)
    if full_waveplate_at > now:
        return current_crystal
    crystal_gained = max(0, int((now - full_waveplate_at).total_seconds()) // WAVEPLATE_CRYSTAL_RECOVER_SECONDS)
    base_crystal = current_crystal - crystal_gained
    if base_crystal < 0:
        raise ValueError("current_waveplate_crystal is too small for the selected full_waveplate_at")
    return clamp_waveplate_crystal(base_crystal)


def spend_resources(
    waveplate: int,
    waveplate_crystal: int,
    cost: int,
) -> tuple[int, int]:
    wp, crystal = normalize_resources(waveplate, waveplate_crystal)
    remain = max(0, int(cost))
    use_wp = min(wp, remain)
    wp -= use_wp
    remain -= use_wp
    if remain > 0:
        crystal = max(0, crystal - remain)
    return wp, crystal


def add_resources(
    waveplate: int,
    waveplate_crystal: int,
    amount: int,
) -> tuple[int, int]:
    wp, crystal = normalize_resources(waveplate, waveplate_crystal)
    increase = max(0, int(amount))
    wp += increase
    if wp > WAVEPLATE_CAP:
        crystal = min(WAVEPLATE_CRYSTAL_CAP, crystal + (wp - WAVEPLATE_CAP))
        wp = WAVEPLATE_CAP
    return wp, crystal


def validate_full_waveplate_at(now: datetime, full_waveplate_at: datetime) -> None:
    delta_seconds = int((full_waveplate_at - now).total_seconds())
    max_seconds = seconds_to_waveplate_full_from_current(0)
    if delta_seconds > max_seconds:
        raise ValueError(f"full_waveplate_at too far in future (max {max_seconds} seconds)")


def warn_level(waveplate: int) -> str:
    wp = clamp_waveplate(waveplate)
    if wp >= 235:
        return "danger"
    if wp >= 220:
        return "warning"
    return "normal"
