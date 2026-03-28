from datetime import datetime

WAVEPLATE_CAP = 240
WAVEPLATE_RECOVER_MINUTES = 6
WAVEPLATE_CRYSTAL_CAP = 480
WAVEPLATE_CRYSTAL_RECOVER_MINUTES = 12


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
    elapsed = max(0, int((now - last_updated_at).total_seconds() // 60))

    if wp < WAVEPLATE_CAP:
        add_wp = min((elapsed // WAVEPLATE_RECOVER_MINUTES), WAVEPLATE_CAP - wp)
        wp += add_wp
        elapsed -= add_wp * WAVEPLATE_RECOVER_MINUTES

    if wp >= WAVEPLATE_CAP and crystal < WAVEPLATE_CRYSTAL_CAP:
        crystal = min(WAVEPLATE_CRYSTAL_CAP, crystal + elapsed // WAVEPLATE_CRYSTAL_RECOVER_MINUTES)

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


def warn_level(waveplate: int) -> str:
    wp = clamp_waveplate(waveplate)
    if wp >= 235:
        return "danger"
    if wp >= 220:
        return "warning"
    return "normal"
