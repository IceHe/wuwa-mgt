import os
import json
from datetime import date, datetime, timedelta
from urllib import error as urlerror
from urllib import request as urlrequest
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .energy import (
    add_resources,
    clamp_waveplate,
    clamp_waveplate_crystal,
    normalize_resources,
    recover_resources,
    reverse_waveplate_from_full_time,
    seconds_to_waveplate_full,
    spend_resources,
    warn_level,
)
from .models import Account, AccountCheckin, AccountCleanupSession, TaskInstance, TaskStatus, TaskTemplate
from .schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    DailyFlagUpdateIn,
    DashboardAccountOut,
    CleanupSessionOut,
    CleanupSessionManualCreateIn,
    CleanupTimerStateOut,
    CleanupWeeklySummaryOut,
    PeriodicAccountOut,
    TacetUpdateIn,
    EnergyGainIn,
    EnergyOut,
    EnergySetIn,
    EnergySpendIn,
    TaskInstanceCreate,
    TaskInstanceOut,
    TaskInstanceUpdate,
    TaskGenerateIn,
    TaskGenerateOut,
    TaskTemplateCreate,
    TaskTemplateOut,
    TaskTemplateUpdate,
)

load_dotenv()
APP_TZ = os.getenv("APP_TZ", "Asia/Shanghai")
RESET_HOUR = int(os.getenv("RESET_HOUR", "4"))
AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
AUTH_REQUIRED_PERMISSION = os.getenv("AUTH_REQUIRED_PERMISSION", "manage")
AUTH_VALIDATE_TIMEOUT_SECONDS = float(os.getenv("AUTH_VALIDATE_TIMEOUT_SECONDS", "3"))
ALLOWED_FLAG_KEYS = {
    "daily_task",
    "daily_nest",
    "weekly_door",
    "weekly_boss",
    "weekly_synthesis",
    "version_matrix_soldier",
    "version_small_coral_exchange",
    "version_hologram_challenge",
    "version_echo_template_adjust",
    "hv_trial_character",
    "monthly_tower_exchange",
    "four_week_tower",
    "four_week_ruins",
    "range_lahailuo_cube",
    "range_music_game",
}
FLAG_KEY_PERIOD_TYPE = {
    "daily_task": "daily",
    "daily_nest": "daily",
    "weekly_door": "weekly",
    "weekly_boss": "weekly",
    "weekly_synthesis": "weekly",
    "version_matrix_soldier": "fv",
    "version_small_coral_exchange": "fv",
    "version_hologram_challenge": "fv",
    "version_echo_template_adjust": "fv",
    "hv_trial_character": "hv",
    "monthly_tower_exchange": "monthly",
    "four_week_tower": "four_week",
    "four_week_ruins": "four_week",
    "range_lahailuo_cube": "range",
    "range_music_game": "range",
}
LEGACY_FLAG_KEY_MAP = {
    "daily_done": "daily_task",
    "nest_cleared": "daily_nest",
    "door": "weekly_door",
}
FOUR_WEEK_DAYS = 28
FOUR_WEEK_TOWER_ANCHOR = date.fromisoformat(os.getenv("FOUR_WEEK_TOWER_ANCHOR", "2026-03-30"))
FOUR_WEEK_RUINS_ANCHOR = date.fromisoformat(os.getenv("FOUR_WEEK_RUINS_ANCHOR", "2026-03-16"))
CURRENT_FV_START = date.fromisoformat(os.getenv("CURRENT_FV_START", "2026-03-26"))
CURRENT_HV_START = date.fromisoformat(os.getenv("CURRENT_HV_START", "2026-03-26"))
LAHAILUO_RANGE_START = date.fromisoformat("2026-03-26")
LAHAILUO_RANGE_END = date.fromisoformat("2026-04-13")
MUSIC_GAME_RANGE_START = date.fromisoformat("2026-03-19")
MUSIC_GAME_RANGE_END = date.fromisoformat("2026-04-29")
ALLOWED_TACET_VALUES = {"", "爱弥斯", "西格莉卡", "旧暗", "旧雷", "达妮娅"}
DONE_STATUSES = {"done", "skipped"}

app = FastAPI(title="Wuwa Account Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract_token_from_headers(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return request.headers.get("X-Token", "").strip()


def validate_token_by_auth_service(token: str) -> tuple[bool, str]:
    payload = {"token": token, "permission": AUTH_REQUIRED_PERMISSION}
    req = urlrequest.Request(
        url=f"{AUTH_BASE_URL}/api/validate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=AUTH_VALIDATE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except (urlerror.URLError, TimeoutError):
        return False, "auth service unavailable"
    except json.JSONDecodeError:
        return False, "invalid auth response"
    valid = bool(data.get("valid"))
    reason = str(data.get("reason") or "")
    if valid:
        return True, ""
    return False, (reason or "forbidden")


@app.middleware("http")
async def require_manage_permission(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in {"/healthz"}:
        return await call_next(request)

    token = extract_token_from_headers(request)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "missing token"})

    valid, reason = validate_token_by_auth_service(token)
    if not valid:
        status_code = 403 if reason in {"forbidden", "invalid permission"} else 401
        return JSONResponse(status_code=status_code, content={"detail": reason})
    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    ensure_checkins_table_rename()
    Base.metadata.create_all(bind=engine)
    ensure_account_columns()
    ensure_checkin_columns()
    ensure_cleanup_timer_columns()


def ensure_account_columns() -> None:
    ddl = [
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='id'
                AND data_type IN ('bigint', 'integer')
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='account_id'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN id TO account_id;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='account_identifier'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='id'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN account_identifier TO id;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='feature_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='id'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN feature_id TO id;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='account_code'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='abbr'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN account_code TO abbr;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='account_name'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='nickname'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN account_name TO nickname;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='phone'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='phone_number'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN phone TO phone_number;
            END IF;
        END
        $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='note'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='accounts' AND column_name='remark'
            ) THEN
                ALTER TABLE accounts RENAME COLUMN note TO remark;
            END IF;
        END
        $$;
        """,
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_waveplate INTEGER DEFAULT 0",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_waveplate_updated_at TIMESTAMPTZ DEFAULT now()",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS waveplate_crystal INTEGER DEFAULT 0",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS tacet VARCHAR(32) DEFAULT ''",
        "ALTER TABLE accounts DROP COLUMN IF EXISTS energy_at_prev_4am",
        "ALTER TABLE accounts DROP COLUMN IF EXISTS prev_4am_at",
        "ALTER TABLE accounts DROP COLUMN IF EXISTS stamina_at_4am",
        "ALTER TABLE accounts DROP COLUMN IF EXISTS overflow_stamina",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_id ON accounts (id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_abbr ON accounts (abbr)",
        "DROP INDEX IF EXISTS ix_accounts_account_code",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
        conn.execute(
            text(
                "UPDATE accounts SET last_waveplate = COALESCE(last_waveplate, 0), "
                "waveplate_crystal = COALESCE(waveplate_crystal, 0), "
                "last_waveplate_updated_at = COALESCE(last_waveplate_updated_at, now()), "
                "tacet = CASE "
                "WHEN tacet IS NULL THEN '' "
                "WHEN tacet IN ('未选定', '?') THEN '' "
                "ELSE tacet END"
            )
        )


def ensure_checkins_table_rename() -> None:
    ddl = [
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='account_daily_flags'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='account_checkins'
            ) THEN
                ALTER TABLE account_daily_flags RENAME TO account_checkins;
            END IF;
        END
        $$;
        """,
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def ensure_checkin_columns() -> None:
    ddl = [
        "ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS period_type VARCHAR(16) DEFAULT 'daily'",
        "ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS period_key VARCHAR(32) DEFAULT ''",
        "ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'todo'",
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_period_type ON account_checkins (period_type)",
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_period_key ON account_checkins (period_key)",
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_status ON account_checkins (status)",
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_account_period ON account_checkins (account_id, period_type, period_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_account_checkin_compound ON account_checkins (account_id, period_type, period_key, flag_key)",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
        conn.execute(
            text(
                "UPDATE account_checkins SET "
                "period_type = COALESCE(NULLIF(period_type, ''), 'daily'), "
                "period_key = COALESCE(NULLIF(period_key, ''), status_date::text), "
                "status = CASE "
                "WHEN status IN ('done', 'skipped') THEN status "
                "WHEN is_done THEN 'done' "
                "ELSE 'todo' END, "
                "is_done = CASE "
                "WHEN status IN ('done', 'skipped') THEN TRUE "
                "WHEN status = 'todo' THEN FALSE "
                "ELSE is_done END, "
                "flag_key = CASE "
                "WHEN flag_key = 'daily_done' THEN 'daily_task' "
                "WHEN flag_key = 'nest_cleared' THEN 'daily_nest' "
                "WHEN flag_key = 'door' THEN 'weekly_door' "
                "ELSE flag_key END"
            )
        )


def ensure_cleanup_timer_columns() -> None:
    ddl = [
        "CREATE TABLE IF NOT EXISTS account_cleanup_sessions ("
        "id SERIAL PRIMARY KEY, "
        "account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE, "
        "biz_date DATE NOT NULL, "
        "started_at TIMESTAMPTZ NOT NULL, "
        "ended_at TIMESTAMPTZ NULL, "
        "duration_sec INTEGER NOT NULL DEFAULT 0, "
        "status VARCHAR(16) NOT NULL DEFAULT 'running', "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS biz_date DATE",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS duration_sec INTEGER DEFAULT 0",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'running'",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()",
        "ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
        "CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_account_id ON account_cleanup_sessions (account_id)",
        "CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_biz_date ON account_cleanup_sessions (biz_date)",
        "CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_status ON account_cleanup_sessions (status)",
        "CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_started_at ON account_cleanup_sessions (started_at)",
        "CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_ended_at ON account_cleanup_sessions (ended_at)",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
        conn.execute(
            text(
                "UPDATE account_cleanup_sessions SET "
                "status = CASE WHEN ended_at IS NULL THEN 'running' ELSE 'paused' END "
                "WHERE status IS NULL OR status NOT IN ('running', 'paused')"
            )
        )
        conn.execute(
            text(
                "UPDATE account_cleanup_sessions SET "
                "duration_sec = CASE "
                "WHEN ended_at IS NOT NULL THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (ended_at - started_at)))::INT) "
                "ELSE COALESCE(duration_sec, 0) END "
                "WHERE duration_sec IS NULL OR duration_sec < 0"
            )
        )
        conn.execute(
            text(
                "UPDATE account_cleanup_sessions SET "
                "biz_date = COALESCE(biz_date, (started_at AT TIME ZONE :app_tz)::DATE, CURRENT_DATE)"
            ),
            {"app_tz": APP_TZ},
        )


def now_tz() -> datetime:
    return datetime.now(ZoneInfo(APP_TZ))


def today_tz() -> date:
    return now_tz().date()


def reset_day_tz(now: datetime | None = None) -> date:
    current = now or now_tz()
    if not (0 <= RESET_HOUR <= 23):
        raise ValueError("RESET_HOUR must be 0..23")
    if current.hour < RESET_HOUR:
        return (current - timedelta(days=1)).date()
    return current.date()


def to_app_tz(dt: datetime) -> datetime:
    app_zone = ZoneInfo(APP_TZ)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=app_zone)
    return dt.astimezone(app_zone)


def monday_of_week(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_period_key(day: date) -> str:
    return f"{monday_of_week(day).isoformat()}W"


def normalize_flag_key(flag_key: str) -> str:
    return LEGACY_FLAG_KEY_MAP.get(flag_key, flag_key)


def four_week_window(anchor: date, day: date) -> tuple[date, date]:
    delta_days = (day - anchor).days
    window_index = delta_days // FOUR_WEEK_DAYS
    start = anchor + timedelta(days=window_index * FOUR_WEEK_DAYS)
    end = start + timedelta(days=FOUR_WEEK_DAYS - 1)
    return start, end


def range_period_key(start: date, end: date) -> str:
    return f"{start.isoformat()}_{end.isoformat()}"


def resolve_period(flag_key: str, day: date) -> tuple[str, str, date]:
    period_type = FLAG_KEY_PERIOD_TYPE[flag_key]
    if period_type == "daily":
        return period_type, day.isoformat(), day
    if period_type == "weekly":
        monday = monday_of_week(day)
        return period_type, weekly_period_key(day), monday
    if period_type == "monthly":
        month_start = day.replace(day=1)
        return period_type, day.strftime("%Y-%m"), month_start
    if period_type == "fv":
        return period_type, f"fv-{CURRENT_FV_START.isoformat()}", CURRENT_FV_START
    if period_type == "hv":
        return period_type, f"hv-{CURRENT_HV_START.isoformat()}", CURRENT_HV_START
    if period_type == "four_week":
        anchor = FOUR_WEEK_TOWER_ANCHOR if flag_key == "four_week_tower" else FOUR_WEEK_RUINS_ANCHOR
        start, end = four_week_window(anchor, day)
        return period_type, range_period_key(start, end), start
    if period_type == "range":
        if flag_key == "range_music_game":
            return period_type, range_period_key(MUSIC_GAME_RANGE_START, MUSIC_GAME_RANGE_END), MUSIC_GAME_RANGE_START
        return period_type, range_period_key(LAHAILUO_RANGE_START, LAHAILUO_RANGE_END), LAHAILUO_RANGE_START
    raise HTTPException(status_code=400, detail=f"unsupported period type for flag: {flag_key}")


def energy_payload(account: Account, now: datetime) -> EnergyOut:
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    to_full_seconds = seconds_to_waveplate_full(account.last_waveplate, account.last_waveplate_updated_at, now)
    to_full = (to_full_seconds + 59) // 60
    return EnergyOut(
        account_id=account.account_id,
        id=account.id,
        current_waveplate=current_wp,
        current_waveplate_crystal=current_crystal,
        last_waveplate=account.last_waveplate,
        last_waveplate_updated_at=account.last_waveplate_updated_at,
        waveplate_full_in_minutes=to_full,
        eta_waveplate_full=now + timedelta(seconds=to_full_seconds),
        warn_level=warn_level(current_wp),
    )


def snapshot_resources_for_now(account: Account, now: datetime) -> tuple[int, int]:
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    account.last_waveplate = current_wp
    account.waveplate_crystal = current_crystal
    account.last_waveplate_updated_at = now
    return current_wp, current_crystal


def apply_energy_set(account: Account, payload: EnergySetIn, now: datetime) -> None:
    _, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    if payload.full_waveplate_at is not None:
        full_at = to_app_tz(payload.full_waveplate_at)
        try:
            target_wp, progressed_seconds = reverse_waveplate_from_full_time(now, full_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        account.last_waveplate = target_wp
        account.last_waveplate_updated_at = now - timedelta(seconds=progressed_seconds)
    else:
        account.last_waveplate = clamp_waveplate(payload.current_waveplate or 0)
        account.last_waveplate_updated_at = now
    if payload.current_waveplate_crystal is None:
        account.waveplate_crystal = current_crystal
    else:
        account.waveplate_crystal = clamp_waveplate_crystal(payload.current_waveplate_crystal)


def get_account_by_id(db: Session, game_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.id == game_id))
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


def running_duration_seconds(started_at: datetime, now: datetime) -> int:
    return max(0, int((now - started_at).total_seconds()))


def account_cleanup_state(db: Session, account: Account, day: date, now: datetime) -> CleanupTimerStateOut:
    paused_total = db.scalar(
        select(func.coalesce(func.sum(AccountCleanupSession.duration_sec), 0)).where(
            AccountCleanupSession.account_id == account.account_id,
            AccountCleanupSession.biz_date == day,
            AccountCleanupSession.status == "paused",
        )
    )
    running_session = db.scalar(
        select(AccountCleanupSession)
        .where(
            AccountCleanupSession.account_id == account.account_id,
            AccountCleanupSession.status == "running",
        )
        .order_by(AccountCleanupSession.started_at.desc())
    )
    running_seconds = 0
    running_started_at: datetime | None = None
    running_session_id: int | None = None
    if running_session is not None:
        running_seconds = running_duration_seconds(running_session.started_at, now)
        running_started_at = running_session.started_at
        running_session_id = running_session.id
    paused_sec = int(paused_total or 0)
    return CleanupTimerStateOut(
        account_id=account.account_id,
        id=account.id,
        abbr=account.abbr,
        nickname=account.nickname,
        biz_date=day.isoformat(),
        today_total_sec=paused_sec + running_seconds,
        today_paused_sec=paused_sec,
        running=running_session is not None,
        running_started_at=running_started_at,
        running_session_id=running_session_id,
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/accounts", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    now = now_tz()
    if payload.tacet not in ALLOWED_TACET_VALUES:
        raise HTTPException(status_code=400, detail=f"unsupported tacet: {payload.tacet}")
    wp, crystal = normalize_resources(payload.last_waveplate, payload.waveplate_crystal)
    account = Account(
        id=payload.id,
        abbr=payload.abbr,
        nickname=payload.nickname,
        phone_number=payload.phone_number,
        remark=payload.remark,
        tacet=payload.tacet,
        is_active=payload.is_active,
        last_waveplate=wp,
        waveplate_crystal=crystal,
        last_waveplate_updated_at=now,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="id or abbr already exists") from exc
    db.refresh(account)
    return account


@app.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), active_only: bool = False) -> list[Account]:
    stmt = select(Account).order_by(Account.created_at.desc())
    if active_only:
        stmt = stmt.where(Account.is_active.is_(True))
    return db.scalars(stmt).all()


@app.get("/accounts/by-id/{id}", response_model=AccountOut)
def get_account_by_id_api(id: str, db: Session = Depends(get_db)) -> Account:
    return get_account_by_id(db, id)


@app.get("/accounts/by-feature/{feature_id}", response_model=AccountOut)
def get_account_by_feature(feature_id: str, db: Session = Depends(get_db)) -> Account:
    return get_account_by_id(db, feature_id)


@app.get("/accounts/by-player/{player_id}", response_model=AccountOut)
def get_account_by_player(player_id: str, db: Session = Depends(get_db)) -> Account:
    return get_account_by_id(db, player_id)


@app.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    data = payload.model_dump(exclude_unset=True)
    if "tacet" in data and data["tacet"] not in ALLOWED_TACET_VALUES:
        raise HTTPException(status_code=400, detail=f"unsupported tacet: {data['tacet']}")
    if "last_waveplate" in data or "waveplate_crystal" in data:
        wp, crystal = normalize_resources(
            data.get("last_waveplate", account.last_waveplate),
            data.get("waveplate_crystal", account.waveplate_crystal),
        )
        data["last_waveplate"] = wp
        data["waveplate_crystal"] = crystal
        data["last_waveplate_updated_at"] = now_tz()
    for key, value in data.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


@app.post("/accounts/{account_id}/update", response_model=AccountOut)
def update_account_post(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    return update_account(account_id, payload, db)


@app.post("/accounts/by-player/{player_id}/update", response_model=AccountOut)
def update_account_by_player(player_id: str, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    account = get_account_by_id(db, player_id)
    data = payload.model_dump(exclude_unset=True)
    if "tacet" in data and data["tacet"] not in ALLOWED_TACET_VALUES:
        raise HTTPException(status_code=400, detail=f"unsupported tacet: {data['tacet']}")
    if "last_waveplate" in data or "waveplate_crystal" in data:
        wp, crystal = normalize_resources(
            data.get("last_waveplate", account.last_waveplate),
            data.get("waveplate_crystal", account.waveplate_crystal),
        )
        data["last_waveplate"] = wp
        data["waveplate_crystal"] = crystal
        data["last_waveplate_updated_at"] = now_tz()
    for key, value in data.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


@app.post("/accounts/by-id/{id}/update", response_model=AccountOut)
def update_account_by_id(id: str, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    return update_account_by_player(id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/update", response_model=AccountOut)
def update_account_by_feature(feature_id: str, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    return update_account_by_player(feature_id, payload, db)


@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.post("/accounts/{account_id}/delete")
def delete_account_post(account_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    return delete_account(account_id, db)


@app.post("/accounts/by-player/{player_id}/delete")
def delete_account_by_player(player_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    account = get_account_by_id(db, player_id)
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.post("/accounts/by-id/{id}/delete")
def delete_account_by_id(id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    account = get_account_by_id(db, id)
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.post("/accounts/by-feature/{feature_id}/delete")
def delete_account_by_feature(feature_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    account = get_account_by_id(db, feature_id)
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.post("/accounts/by-id/{id}/daily-flags")
def set_daily_flag_by_id(id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)) -> dict[str, bool | str]:
    normalized_key = normalize_flag_key(payload.flag_key)
    if normalized_key not in ALLOWED_FLAG_KEYS:
        raise HTTPException(status_code=400, detail=f"unsupported flag_key: {payload.flag_key}")
    account = get_account_by_id(db, id)
    period_type, period_key, status_date = resolve_period(normalized_key, reset_day_tz())
    item = db.scalar(
        select(AccountCheckin).where(
            AccountCheckin.account_id == account.account_id,
            AccountCheckin.period_type == period_type,
            AccountCheckin.period_key == period_key,
            AccountCheckin.flag_key == normalized_key,
        )
    )
    resolved_status = payload.status if payload.status is not None else ("done" if payload.is_done else "todo")
    is_done = resolved_status in DONE_STATUSES
    if item is None:
        item = AccountCheckin(
            account_id=account.account_id,
            status_date=status_date,
            period_type=period_type,
            period_key=period_key,
            flag_key=normalized_key,
            status=resolved_status,
            is_done=is_done,
        )
        db.add(item)
    else:
        item.status = resolved_status
        item.is_done = is_done
        item.status_date = status_date
        item.period_type = period_type
        item.period_key = period_key
    db.commit()
    return {"ok": True, "flag_key": normalized_key, "status": resolved_status, "is_done": is_done}


@app.post("/accounts/by-player/{player_id}/daily-flags")
def set_daily_flag_by_player(
    player_id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)
) -> dict[str, bool | str]:
    return set_daily_flag_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/daily-flags")
def set_daily_flag_by_feature(
    feature_id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)
) -> dict[str, bool | str]:
    return set_daily_flag_by_id(feature_id, payload, db)


@app.post("/accounts/by-id/{id}/checkins")
def set_checkin_by_id(id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)) -> dict[str, bool | str]:
    return set_daily_flag_by_id(id, payload, db)


@app.post("/accounts/by-player/{player_id}/checkins")
def set_checkin_by_player(
    player_id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)
) -> dict[str, bool | str]:
    return set_daily_flag_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/checkins")
def set_checkin_by_feature(
    feature_id: str, payload: DailyFlagUpdateIn, db: Session = Depends(get_db)
) -> dict[str, bool | str]:
    return set_daily_flag_by_id(feature_id, payload, db)


@app.post("/accounts/by-id/{id}/tacet")
def set_tacet_by_id(id: str, payload: TacetUpdateIn, db: Session = Depends(get_db)) -> dict[str, bool | str]:
    if payload.tacet not in ALLOWED_TACET_VALUES:
        raise HTTPException(status_code=400, detail=f"unsupported tacet: {payload.tacet}")
    account = get_account_by_id(db, id)
    account.tacet = payload.tacet
    db.commit()
    return {"ok": True, "tacet": payload.tacet}


@app.post("/accounts/by-player/{player_id}/tacet")
def set_tacet_by_player(player_id: str, payload: TacetUpdateIn, db: Session = Depends(get_db)) -> dict[str, bool | str]:
    return set_tacet_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/tacet")
def set_tacet_by_feature(
    feature_id: str, payload: TacetUpdateIn, db: Session = Depends(get_db)
) -> dict[str, bool | str]:
    return set_tacet_by_id(feature_id, payload, db)


@app.post("/accounts/by-id/{id}/cleanup-timer/start", response_model=CleanupTimerStateOut)
def start_cleanup_timer_by_id(id: str, db: Session = Depends(get_db)) -> CleanupTimerStateOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    today = reset_day_tz(now)

    running_session = db.scalar(
        select(AccountCleanupSession)
        .where(
            AccountCleanupSession.account_id == account.account_id,
            AccountCleanupSession.status == "running",
        )
        .order_by(AccountCleanupSession.started_at.desc())
    )
    if running_session is None:
        running_session = AccountCleanupSession(
            account_id=account.account_id,
            biz_date=today,
            started_at=now,
            status="running",
            duration_sec=0,
        )
        db.add(running_session)
        db.commit()
    return account_cleanup_state(db, account, today, now)


@app.post("/accounts/by-id/{id}/cleanup-timer/pause", response_model=CleanupTimerStateOut)
def pause_cleanup_timer_by_id(id: str, db: Session = Depends(get_db)) -> CleanupTimerStateOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    today = reset_day_tz(now)

    running_session = db.scalar(
        select(AccountCleanupSession)
        .where(
            AccountCleanupSession.account_id == account.account_id,
            AccountCleanupSession.status == "running",
        )
        .order_by(AccountCleanupSession.started_at.desc())
    )
    if running_session is not None:
        duration_sec = running_duration_seconds(running_session.started_at, now)
        running_session.ended_at = now
        running_session.duration_sec = duration_sec
        running_session.status = "paused"
        db.commit()
    return account_cleanup_state(db, account, today, now)


@app.get("/accounts/by-id/{id}/cleanup-timer/today", response_model=CleanupTimerStateOut)
def get_cleanup_timer_today_by_id(id: str, db: Session = Depends(get_db)) -> CleanupTimerStateOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    today = reset_day_tz(now)
    return account_cleanup_state(db, account, today, now)


@app.get("/cleanup-timer/weekly-summary", response_model=CleanupWeeklySummaryOut)
def cleanup_timer_weekly_summary(
    db: Session = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
) -> CleanupWeeklySummaryOut:
    now = now_tz()
    end_day = reset_day_tz(now)
    start_day = end_day - timedelta(days=days - 1)
    day_keys = [(start_day + timedelta(days=i)).isoformat() for i in range(days)]
    day_duration = {key: 0 for key in day_keys}

    paused_rows = db.execute(
        select(
            AccountCleanupSession.biz_date,
            func.coalesce(func.sum(AccountCleanupSession.duration_sec), 0),
        )
        .where(
            AccountCleanupSession.biz_date >= start_day,
            AccountCleanupSession.biz_date <= end_day,
            AccountCleanupSession.status == "paused",
        )
        .group_by(AccountCleanupSession.biz_date)
    ).all()
    for biz_date, total_sec in paused_rows:
        key = biz_date.isoformat()
        if key in day_duration:
            day_duration[key] += int(total_sec or 0)

    account_duration: dict[int, int] = {}
    account_paused_rows = db.execute(
        select(
            AccountCleanupSession.account_id,
            func.coalesce(func.sum(AccountCleanupSession.duration_sec), 0),
        )
        .where(
            AccountCleanupSession.biz_date >= start_day,
            AccountCleanupSession.biz_date <= end_day,
            AccountCleanupSession.status == "paused",
        )
        .group_by(AccountCleanupSession.account_id)
    ).all()
    for account_id, total_sec in account_paused_rows:
        account_duration[int(account_id)] = int(total_sec or 0)

    running_rows = db.scalars(
        select(AccountCleanupSession).where(
            AccountCleanupSession.status == "running",
            AccountCleanupSession.biz_date >= start_day,
            AccountCleanupSession.biz_date <= end_day,
        )
    ).all()
    for row in running_rows:
        live_sec = running_duration_seconds(row.started_at, now)
        key = row.biz_date.isoformat()
        if key in day_duration:
            day_duration[key] += live_sec
        account_duration[row.account_id] = account_duration.get(row.account_id, 0) + live_sec

    account_meta = {
        acc.account_id: acc
        for acc in db.scalars(select(Account).where(Account.account_id.in_(list(account_duration.keys())))).all()
    } if account_duration else {}

    daily = [{"biz_date": key, "duration_sec": int(day_duration[key])} for key in day_keys]
    by_account = []
    for account_id, duration_sec in sorted(account_duration.items(), key=lambda item: item[1], reverse=True):
        account = account_meta.get(account_id)
        if account is None:
            continue
        by_account.append(
            {
                "account_id": account.account_id,
                "id": account.id,
                "abbr": account.abbr,
                "nickname": account.nickname,
                "duration_sec": int(duration_sec),
            }
        )

    return CleanupWeeklySummaryOut(
        range_start=start_day.isoformat(),
        range_end=end_day.isoformat(),
        total_duration_sec=sum(item["duration_sec"] for item in daily),
        daily=daily,
        by_account=by_account,
    )


@app.get("/cleanup-timer/sessions", response_model=list[CleanupSessionOut])
def list_cleanup_sessions(
    db: Session = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
    account_id: int | None = Query(default=None),
) -> list[CleanupSessionOut]:
    now = now_tz()
    end_day = reset_day_tz(now)
    start_day = end_day - timedelta(days=days - 1)
    stmt = (
        select(AccountCleanupSession, Account)
        .join(Account, Account.account_id == AccountCleanupSession.account_id)
        .where(
            AccountCleanupSession.biz_date >= start_day,
            AccountCleanupSession.biz_date <= end_day,
        )
        .order_by(AccountCleanupSession.started_at.desc())
    )
    if account_id is not None:
        stmt = stmt.where(AccountCleanupSession.account_id == account_id)
    rows = db.execute(stmt).all()
    result: list[CleanupSessionOut] = []
    for session, account in rows:
        duration_sec = int(session.duration_sec or 0)
        if session.status == "running":
            duration_sec = running_duration_seconds(session.started_at, now)
        result.append(
            CleanupSessionOut(
                id=session.id,
                account_id=account.account_id,
                account_game_id=account.id,
                account_abbr=account.abbr,
                account_nickname=account.nickname,
                biz_date=session.biz_date.isoformat(),
                started_at=session.started_at,
                ended_at=session.ended_at,
                duration_sec=duration_sec,
                status=session.status,
            )
        )
    return result


@app.post("/cleanup-timer/sessions/manual", response_model=CleanupSessionOut)
def create_cleanup_session_manual(
    payload: CleanupSessionManualCreateIn,
    db: Session = Depends(get_db),
) -> CleanupSessionOut:
    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    app_zone = ZoneInfo(APP_TZ)
    started_at = datetime.combine(payload.biz_date, datetime.min.time(), tzinfo=app_zone)
    ended_at = started_at + timedelta(seconds=payload.duration_sec)
    session = AccountCleanupSession(
        account_id=account.account_id,
        biz_date=payload.biz_date,
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=payload.duration_sec,
        status="paused",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return CleanupSessionOut(
        id=session.id,
        account_id=account.account_id,
        account_game_id=account.id,
        account_abbr=account.abbr,
        account_nickname=account.nickname,
        biz_date=session.biz_date.isoformat(),
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_sec=session.duration_sec,
        status=session.status,
    )


@app.get("/accounts/{account_id}/energy", response_model=EnergyOut)
def get_account_energy(account_id: int, db: Session = Depends(get_db)) -> EnergyOut:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    now = now_tz()
    snapshot_resources_for_now(account, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.get("/accounts/by-id/{id}/energy", response_model=EnergyOut)
def get_account_energy_by_id(id: str, db: Session = Depends(get_db)) -> EnergyOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    snapshot_resources_for_now(account, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.get("/accounts/by-player/{player_id}/energy", response_model=EnergyOut)
def get_account_energy_by_player(player_id: str, db: Session = Depends(get_db)) -> EnergyOut:
    return get_account_energy_by_id(player_id, db)


@app.get("/accounts/by-feature/{feature_id}/energy", response_model=EnergyOut)
def get_account_energy_by_feature(feature_id: str, db: Session = Depends(get_db)) -> EnergyOut:
    return get_account_energy_by_id(feature_id, db)


@app.post("/accounts/{account_id}/energy/set", response_model=EnergyOut)
def set_current_waveplate(account_id: int, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    now = now_tz()
    apply_energy_set(account, payload, now)

    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-id/{id}/energy/set", response_model=EnergyOut)
def set_current_waveplate_by_id(id: str, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    apply_energy_set(account, payload, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-player/{player_id}/energy/set", response_model=EnergyOut)
def set_current_energy_by_player(player_id: str, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    return set_current_waveplate_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/energy/set", response_model=EnergyOut)
def set_current_waveplate_by_feature(feature_id: str, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    return set_current_waveplate_by_id(feature_id, payload, db)


@app.post("/accounts/{account_id}/energy/spend", response_model=EnergyOut)
def spend_energy(account_id: int, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.cost not in {40, 60, 80, 120}:
        raise HTTPException(status_code=400, detail="cost must be one of 40, 60, 80, 120")

    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    now = now_tz()
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    if (current_wp + current_crystal) < payload.cost:
        raise HTTPException(
            status_code=400,
            detail=f"not enough waveplate: current {current_wp} + crystal {current_crystal} < cost {payload.cost}",
        )
    next_wp, next_crystal = spend_resources(current_wp, current_crystal, payload.cost)
    account.last_waveplate = next_wp
    account.waveplate_crystal = next_crystal
    account.last_waveplate_updated_at = now

    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-id/{id}/energy/spend", response_model=EnergyOut)
def spend_energy_by_id(id: str, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.cost not in {40, 60, 80, 120}:
        raise HTTPException(status_code=400, detail="cost must be one of 40, 60, 80, 120")
    account = get_account_by_id(db, id)
    now = now_tz()
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    if (current_wp + current_crystal) < payload.cost:
        raise HTTPException(
            status_code=400,
            detail=f"not enough waveplate: current {current_wp} + crystal {current_crystal} < cost {payload.cost}",
        )
    next_wp, next_crystal = spend_resources(current_wp, current_crystal, payload.cost)
    account.last_waveplate = next_wp
    account.waveplate_crystal = next_crystal
    account.last_waveplate_updated_at = now
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-player/{player_id}/energy/spend", response_model=EnergyOut)
def spend_energy_by_player(player_id: str, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    return spend_energy_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/energy/spend", response_model=EnergyOut)
def spend_energy_by_feature(feature_id: str, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    return spend_energy_by_id(feature_id, payload, db)


@app.post("/accounts/{account_id}/energy/gain", response_model=EnergyOut)
def gain_energy(account_id: int, payload: EnergyGainIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.amount not in {40, 60}:
        raise HTTPException(status_code=400, detail="amount must be one of 40, 60")
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    now = now_tz()
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    next_wp, next_crystal = add_resources(current_wp, current_crystal, payload.amount)
    account.last_waveplate = next_wp
    account.waveplate_crystal = next_crystal
    account.last_waveplate_updated_at = now
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-id/{id}/energy/gain", response_model=EnergyOut)
def gain_energy_by_id(id: str, payload: EnergyGainIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.amount not in {40, 60}:
        raise HTTPException(status_code=400, detail="amount must be one of 40, 60")
    account = get_account_by_id(db, id)
    now = now_tz()
    current_wp, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    next_wp, next_crystal = add_resources(current_wp, current_crystal, payload.amount)
    account.last_waveplate = next_wp
    account.waveplate_crystal = next_crystal
    account.last_waveplate_updated_at = now
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-player/{player_id}/energy/gain", response_model=EnergyOut)
def gain_energy_by_player(player_id: str, payload: EnergyGainIn, db: Session = Depends(get_db)) -> EnergyOut:
    return gain_energy_by_id(player_id, payload, db)


@app.post("/accounts/by-feature/{feature_id}/energy/gain", response_model=EnergyOut)
def gain_energy_by_feature(feature_id: str, payload: EnergyGainIn, db: Session = Depends(get_db)) -> EnergyOut:
    return gain_energy_by_id(feature_id, payload, db)


@app.get("/dashboard/accounts", response_model=list[DashboardAccountOut])
def dashboard_accounts(db: Session = Depends(get_db)) -> list[DashboardAccountOut]:
    now = now_tz()
    today = reset_day_tz(now)
    week_key = weekly_period_key(today)
    today_key = today.isoformat()
    accounts = db.scalars(select(Account).where(Account.is_active.is_(True)).order_by(Account.abbr)).all()
    rows: list[DashboardAccountOut] = []
    account_ids = [acc.account_id for acc in accounts]
    flags: list[AccountCheckin] = []
    if account_ids:
        flags = db.scalars(
            select(AccountCheckin).where(
                AccountCheckin.account_id.in_(account_ids),
                (
                    (AccountCheckin.period_type == "daily") & (AccountCheckin.period_key == today_key)
                ) | (
                    (AccountCheckin.period_type == "weekly") & (AccountCheckin.period_key == week_key)
                ),
            )
        ).all()
    flags_map: dict[int, dict[str, str]] = {}
    for flag in flags:
        raw_status = (flag.status or "").strip().lower()
        normalized_status = raw_status if raw_status in {"todo", "done", "skipped"} else ("done" if flag.is_done else "todo")
        flags_map.setdefault(flag.account_id, {})[flag.flag_key] = normalized_status

    cleanup_paused_map: dict[int, int] = {}
    cleanup_running_map: dict[int, AccountCleanupSession] = {}
    if account_ids:
        paused_rows = db.execute(
            select(
                AccountCleanupSession.account_id,
                func.coalesce(func.sum(AccountCleanupSession.duration_sec), 0),
            ).where(
                AccountCleanupSession.account_id.in_(account_ids),
                AccountCleanupSession.biz_date == today,
                AccountCleanupSession.status == "paused",
            ).group_by(AccountCleanupSession.account_id)
        ).all()
        cleanup_paused_map = {int(account_id): int(total_sec or 0) for account_id, total_sec in paused_rows}
        running_sessions = db.scalars(
            select(AccountCleanupSession).where(
                AccountCleanupSession.account_id.in_(account_ids),
                AccountCleanupSession.status == "running",
            )
        ).all()
        for session in running_sessions:
            existing = cleanup_running_map.get(session.account_id)
            if existing is None or session.started_at > existing.started_at:
                cleanup_running_map[session.account_id] = session

    for acc in accounts:
        current_wp, current_crystal = recover_resources(
            acc.last_waveplate,
            acc.waveplate_crystal,
            acc.last_waveplate_updated_at,
            now,
        )
        to_full_seconds = seconds_to_waveplate_full(acc.last_waveplate, acc.last_waveplate_updated_at, now)
        to_full = (to_full_seconds + 59) // 60
        acc_flags = flags_map.get(acc.account_id, {})
        daily_task_status = acc_flags.get("daily_task", "todo")
        daily_nest_status = acc_flags.get("daily_nest", "todo")
        weekly_door_status = acc_flags.get("weekly_door", "todo")
        weekly_boss_status = acc_flags.get("weekly_boss", "todo")
        weekly_synthesis_status = acc_flags.get("weekly_synthesis", "todo")
        cleanup_paused_sec = cleanup_paused_map.get(acc.account_id, 0)
        running_session = cleanup_running_map.get(acc.account_id)
        cleanup_running = running_session is not None
        cleanup_running_started_at = running_session.started_at if running_session else None
        cleanup_total_sec = cleanup_paused_sec
        if running_session:
            cleanup_total_sec += running_duration_seconds(running_session.started_at, now)

        todo_count = db.scalar(
            select(func.count(TaskInstance.id)).where(
                TaskInstance.account_id == acc.account_id,
                TaskInstance.status == TaskStatus.todo,
            )
        )
        done_count = db.scalar(
            select(func.count(TaskInstance.id)).where(
                TaskInstance.account_id == acc.account_id,
                TaskInstance.status == TaskStatus.done,
            )
        )

        rows.append(
            DashboardAccountOut(
                account_id=acc.account_id,
                id=acc.id,
                abbr=acc.abbr,
                nickname=acc.nickname,
                phone_number=acc.phone_number,
                remark=acc.remark,
                tacet=acc.tacet,
                current_waveplate=current_wp,
                current_waveplate_crystal=current_crystal,
                warn_level=warn_level(current_wp),
                daily_task=daily_task_status in DONE_STATUSES,
                daily_nest=daily_nest_status in DONE_STATUSES,
                weekly_door=weekly_door_status in DONE_STATUSES,
                weekly_boss=weekly_boss_status in DONE_STATUSES,
                weekly_synthesis=weekly_synthesis_status in DONE_STATUSES,
                daily_task_status=daily_task_status,
                daily_nest_status=daily_nest_status,
                weekly_door_status=weekly_door_status,
                weekly_boss_status=weekly_boss_status,
                weekly_synthesis_status=weekly_synthesis_status,
                cleanup_today_total_sec=cleanup_total_sec,
                cleanup_today_paused_sec=cleanup_paused_sec,
                cleanup_running=cleanup_running,
                cleanup_running_started_at=cleanup_running_started_at,
                waveplate_full_in_minutes=to_full,
                eta_waveplate_full=now + timedelta(seconds=to_full_seconds),
                todo_count=todo_count or 0,
                done_count=done_count or 0,
            )
        )

    rows.sort(key=lambda item: item.eta_waveplate_full)
    return rows


@app.get("/periodic/accounts", response_model=list[PeriodicAccountOut])
def periodic_accounts(db: Session = Depends(get_db)) -> list[PeriodicAccountOut]:
    today = today_tz()
    accounts = db.scalars(select(Account).where(Account.is_active.is_(True)).order_by(Account.abbr)).all()
    account_ids = [acc.account_id for acc in accounts]
    if not account_ids:
        return []

    tracked_keys = [
        "version_matrix_soldier",
        "version_small_coral_exchange",
        "version_hologram_challenge",
        "version_echo_template_adjust",
        "hv_trial_character",
        "monthly_tower_exchange",
        "four_week_tower",
        "four_week_ruins",
        "range_lahailuo_cube",
        "range_music_game",
    ]
    expected_pairs = [resolve_period(flag_key, today)[:2] for flag_key in tracked_keys]
    expected_set = {(period_type, period_key) for period_type, period_key in expected_pairs}

    checkins = db.scalars(
        select(AccountCheckin).where(
            AccountCheckin.account_id.in_(account_ids),
            AccountCheckin.flag_key.in_(tracked_keys),
        )
    ).all()

    flags_map: dict[int, dict[str, str]] = {}
    for item in checkins:
        if (item.period_type, item.period_key) not in expected_set:
            continue
        raw_status = (item.status or "").strip().lower()
        normalized_status = raw_status if raw_status in {"todo", "done", "skipped"} else ("done" if item.is_done else "todo")
        flags_map.setdefault(item.account_id, {})[item.flag_key] = normalized_status

    rows: list[PeriodicAccountOut] = []
    for acc in accounts:
        acc_flags = flags_map.get(acc.account_id, {})
        version_matrix_soldier_status = acc_flags.get("version_matrix_soldier", "todo")
        version_small_coral_exchange_status = acc_flags.get("version_small_coral_exchange", "todo")
        version_hologram_challenge_status = acc_flags.get("version_hologram_challenge", "todo")
        version_echo_template_adjust_status = acc_flags.get("version_echo_template_adjust", "todo")
        hv_trial_character_status = acc_flags.get("hv_trial_character", "todo")
        monthly_tower_exchange_status = acc_flags.get("monthly_tower_exchange", "todo")
        four_week_tower_status = acc_flags.get("four_week_tower", "todo")
        four_week_ruins_status = acc_flags.get("four_week_ruins", "todo")
        range_lahailuo_cube_status = acc_flags.get("range_lahailuo_cube", "todo")
        range_music_game_status = acc_flags.get("range_music_game", "todo")
        rows.append(
            PeriodicAccountOut(
                account_id=acc.account_id,
                id=acc.id,
                abbr=acc.abbr,
                nickname=acc.nickname,
                phone_number=acc.phone_number,
                created_at=acc.created_at,
                updated_at=acc.updated_at,
                version_matrix_soldier=version_matrix_soldier_status in DONE_STATUSES,
                version_matrix_soldier_status=version_matrix_soldier_status,
                version_small_coral_exchange=version_small_coral_exchange_status in DONE_STATUSES,
                version_small_coral_exchange_status=version_small_coral_exchange_status,
                version_hologram_challenge=version_hologram_challenge_status in DONE_STATUSES,
                version_hologram_challenge_status=version_hologram_challenge_status,
                version_echo_template_adjust=version_echo_template_adjust_status in DONE_STATUSES,
                version_echo_template_adjust_status=version_echo_template_adjust_status,
                hv_trial_character=hv_trial_character_status in DONE_STATUSES,
                hv_trial_character_status=hv_trial_character_status,
                monthly_tower_exchange=monthly_tower_exchange_status in DONE_STATUSES,
                monthly_tower_exchange_status=monthly_tower_exchange_status,
                four_week_tower=four_week_tower_status in DONE_STATUSES,
                four_week_tower_status=four_week_tower_status,
                four_week_ruins=four_week_ruins_status in DONE_STATUSES,
                four_week_ruins_status=four_week_ruins_status,
                range_lahailuo_cube=range_lahailuo_cube_status in DONE_STATUSES,
                range_lahailuo_cube_status=range_lahailuo_cube_status,
                range_music_game=range_music_game_status in DONE_STATUSES,
                range_music_game_status=range_music_game_status,
            )
        )

    return rows


@app.post("/task-templates", response_model=TaskTemplateOut)
def create_task_template(payload: TaskTemplateCreate, db: Session = Depends(get_db)) -> TaskTemplate:
    model = TaskTemplate(**payload.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@app.get("/task-templates", response_model=list[TaskTemplateOut])
def list_task_templates(db: Session = Depends(get_db)) -> list[TaskTemplate]:
    return db.scalars(select(TaskTemplate).order_by(TaskTemplate.task_type, TaskTemplate.default_priority)).all()


@app.patch("/task-templates/{template_id}", response_model=TaskTemplateOut)
def update_task_template(template_id: int, payload: TaskTemplateUpdate, db: Session = Depends(get_db)) -> TaskTemplate:
    model = db.get(TaskTemplate, template_id)
    if not model:
        raise HTTPException(status_code=404, detail="template not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(model, key, value)
    db.commit()
    db.refresh(model)
    return model


@app.post("/task-instances", response_model=TaskInstanceOut)
def create_task_instance(payload: TaskInstanceCreate, db: Session = Depends(get_db)) -> TaskInstance:
    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    template = db.get(TaskTemplate, payload.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")

    model = TaskInstance(**payload.model_dump())
    if model.status == TaskStatus.done:
        model.completed_at = now_tz()

    db.add(model)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="task instance already exists for this period") from exc
    db.refresh(model)
    return model


@app.get("/task-instances", response_model=list[TaskInstanceOut])
def list_task_instances(
    db: Session = Depends(get_db),
    account_id: int | None = Query(default=None),
    period_key: str | None = Query(default=None),
) -> list[TaskInstance]:
    stmt = select(TaskInstance).order_by(TaskInstance.priority, TaskInstance.deadline_at)
    if account_id is not None:
        stmt = stmt.where(TaskInstance.account_id == account_id)
    if period_key:
        stmt = stmt.where(TaskInstance.period_key == period_key)
    return db.scalars(stmt).all()


@app.patch("/task-instances/{instance_id}", response_model=TaskInstanceOut)
def update_task_instance(instance_id: int, payload: TaskInstanceUpdate, db: Session = Depends(get_db)) -> TaskInstance:
    model = db.get(TaskInstance, instance_id)
    if not model:
        raise HTTPException(status_code=404, detail="instance not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(model, key, value)

    if "status" in updates:
        if updates["status"] == TaskStatus.done:
            model.completed_at = now_tz()
        elif updates["status"] in {TaskStatus.todo, TaskStatus.skipped}:
            model.completed_at = None

    db.commit()
    db.refresh(model)
    return model


@app.post("/task-instances/{instance_id}/update", response_model=TaskInstanceOut)
def update_task_instance_post(instance_id: int, payload: TaskInstanceUpdate, db: Session = Depends(get_db)) -> TaskInstance:
    return update_task_instance(instance_id, payload, db)


@app.post("/task-instances/generate", response_model=TaskGenerateOut)
def generate_task_instances(payload: TaskGenerateIn, db: Session = Depends(get_db)) -> TaskGenerateOut:
    accounts = db.scalars(select(Account).where(Account.is_active.is_(True))).all()
    templates_stmt = select(TaskTemplate).where(TaskTemplate.is_active.is_(True))
    if payload.task_type is not None:
        templates_stmt = templates_stmt.where(TaskTemplate.task_type == payload.task_type)
    templates = db.scalars(templates_stmt).all()

    created = 0
    for acc in accounts:
        for tpl in templates:
            exists = db.scalar(
                select(func.count(TaskInstance.id)).where(
                    TaskInstance.account_id == acc.account_id,
                    TaskInstance.template_id == tpl.id,
                    TaskInstance.period_key == payload.period_key,
                )
            )
            if exists:
                continue
            db.add(
                TaskInstance(
                    account_id=acc.account_id,
                    template_id=tpl.id,
                    period_key=payload.period_key,
                    status=TaskStatus.todo,
                    start_at=payload.start_at,
                    deadline_at=payload.deadline_at,
                    priority=tpl.default_priority,
                )
            )
            created += 1

    db.commit()
    return TaskGenerateOut(created=created)
