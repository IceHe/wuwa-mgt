from datetime import datetime
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


def recover_resources(
    waveplate: int,
    waveplate_crystal: int,
    last_updated_at: datetime,
    now: datetime,
) -> tuple[int, int]:
    wp, crystal = normalize_resources(waveplate, waveplate_crystal)
    elapsed = max(0, int((now - last_updated_at).total_seconds()))

    if wp < WAVEPLATE_CAP:
        add_wp = min((elapsed // WAVEPLATE_RECOVER_SECONDS), WAVEPLATE_CAP - wp)
        wp += add_wp
        elapsed -= add_wp * WAVEPLATE_RECOVER_SECONDS

    if wp >= WAVEPLATE_CAP and crystal < WAVEPLATE_CRYSTAL_CAP:
        crystal = min(WAVEPLATE_CRYSTAL_CAP, crystal + elapsed // WAVEPLATE_CRYSTAL_RECOVER_SECONDS)

    return wp, crystal


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


def minutes_to_waveplate_full(waveplate: int) -> int:
    wp = clamp_waveplate(waveplate)
    if wp >= WAVEPLATE_CAP:
        return 0
    return (WAVEPLATE_CAP - wp) * WAVEPLATE_RECOVER_MINUTES


def seconds_to_waveplate_full(
    waveplate: int,
    last_updated_at: datetime,
    now: datetime,
) -> int:
    wp = clamp_waveplate(waveplate)
    if wp >= WAVEPLATE_CAP:
        return 0
    elapsed = max(0, int((now - last_updated_at).total_seconds()))
    total = (WAVEPLATE_CAP - wp) * WAVEPLATE_RECOVER_SECONDS
    return max(0, total - elapsed)


def reverse_waveplate_from_full_time(now: datetime, full_waveplate_at: datetime) -> tuple[int, int]:
    delta_seconds = int((full_waveplate_at - now).total_seconds())
    if delta_seconds <= 0:
        return WAVEPLATE_CAP, 0
    max_seconds = WAVEPLATE_CAP * WAVEPLATE_RECOVER_SECONDS
    if delta_seconds > max_seconds:
        raise ValueError(f"full_waveplate_at too far in future (max {max_seconds} seconds)")
    missing = ceil(delta_seconds / WAVEPLATE_RECOVER_SECONDS)
    current_wp = WAVEPLATE_CAP - missing
    progressed_seconds = (missing * WAVEPLATE_RECOVER_SECONDS) - delta_seconds
    return current_wp, progressed_seconds


def warn_level(waveplate: int) -> str:
    wp = clamp_waveplate(waveplate)
    if wp >= 235:
        return "danger"
    if wp >= 220:
        return "warning"
    return "normal"
