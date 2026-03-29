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
    minutes_to_waveplate_full,
    normalize_resources,
    recover_resources,
    spend_resources,
    warn_level,
)
from .models import Account, AccountCheckin, TaskInstance, TaskStatus, TaskTemplate
from .schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    DailyFlagUpdateIn,
    DashboardAccountOut,
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
AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
AUTH_REQUIRED_PERMISSION = os.getenv("AUTH_REQUIRED_PERMISSION", "manage")
AUTH_VALIDATE_TIMEOUT_SECONDS = float(os.getenv("AUTH_VALIDATE_TIMEOUT_SECONDS", "3"))
ALLOWED_FLAG_KEYS = {
    "daily_task",
    "daily_nest",
    "weekly_door",
    "weekly_boss",
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
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_period_type ON account_checkins (period_type)",
        "CREATE INDEX IF NOT EXISTS ix_account_checkins_period_key ON account_checkins (period_key)",
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
                "flag_key = CASE "
                "WHEN flag_key = 'daily_done' THEN 'daily_task' "
                "WHEN flag_key = 'nest_cleared' THEN 'daily_nest' "
                "WHEN flag_key = 'door' THEN 'weekly_door' "
                "ELSE flag_key END"
            )
        )


def now_tz() -> datetime:
    return datetime.now(ZoneInfo(APP_TZ))


def today_tz() -> date:
    return now_tz().date()


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
    to_full = minutes_to_waveplate_full(current_wp)
    return EnergyOut(
        account_id=account.account_id,
        id=account.id,
        current_waveplate=current_wp,
        current_waveplate_crystal=current_crystal,
        last_waveplate=account.last_waveplate,
        last_waveplate_updated_at=account.last_waveplate_updated_at,
        waveplate_full_in_minutes=to_full,
        eta_waveplate_full=now + timedelta(minutes=to_full),
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


def get_account_by_id(db: Session, game_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.id == game_id))
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


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
    period_type, period_key, status_date = resolve_period(normalized_key, today_tz())
    item = db.scalar(
        select(AccountCheckin).where(
            AccountCheckin.account_id == account.account_id,
            AccountCheckin.period_type == period_type,
            AccountCheckin.period_key == period_key,
            AccountCheckin.flag_key == normalized_key,
        )
    )
    if item is None:
        item = AccountCheckin(
            account_id=account.account_id,
            status_date=status_date,
            period_type=period_type,
            period_key=period_key,
            flag_key=normalized_key,
            is_done=payload.is_done,
        )
        db.add(item)
    else:
        item.is_done = payload.is_done
        item.status_date = status_date
        item.period_type = period_type
        item.period_key = period_key
    db.commit()
    return {"ok": True, "flag_key": normalized_key, "is_done": payload.is_done}


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
    _, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    account.last_waveplate = clamp_waveplate(payload.current_waveplate)
    if payload.current_waveplate_crystal is None:
        account.waveplate_crystal = current_crystal
    else:
        account.waveplate_crystal = clamp_waveplate_crystal(payload.current_waveplate_crystal)
    account.last_waveplate_updated_at = now

    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-id/{id}/energy/set", response_model=EnergyOut)
def set_current_waveplate_by_id(id: str, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    account = get_account_by_id(db, id)
    now = now_tz()
    _, current_crystal = recover_resources(
        account.last_waveplate,
        account.waveplate_crystal,
        account.last_waveplate_updated_at,
        now,
    )
    account.last_waveplate = clamp_waveplate(payload.current_waveplate)
    if payload.current_waveplate_crystal is None:
        account.waveplate_crystal = current_crystal
    else:
        account.waveplate_crystal = clamp_waveplate_crystal(payload.current_waveplate_crystal)
    account.last_waveplate_updated_at = now
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
    today = now.date()
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
    flags_map: dict[int, dict[str, bool]] = {}
    for flag in flags:
        flags_map.setdefault(flag.account_id, {})[flag.flag_key] = bool(flag.is_done)

    for acc in accounts:
        current_wp, current_crystal = snapshot_resources_for_now(acc, now)
        to_full = minutes_to_waveplate_full(current_wp)
        acc_flags = flags_map.get(acc.account_id, {})

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
                daily_task=acc_flags.get("daily_task", False),
                daily_nest=acc_flags.get("daily_nest", False),
                weekly_door=acc_flags.get("weekly_door", False),
                weekly_boss=acc_flags.get("weekly_boss", False),
                daily_done=acc_flags.get("daily_task", False),
                nest_cleared=acc_flags.get("daily_nest", False),
                waveplate_full_in_minutes=to_full,
                eta_waveplate_full=now + timedelta(minutes=to_full),
                todo_count=todo_count or 0,
                done_count=done_count or 0,
            )
        )

    db.commit()
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

    flags_map: dict[int, dict[str, bool]] = {}
    for item in checkins:
        if (item.period_type, item.period_key) not in expected_set:
            continue
        flags_map.setdefault(item.account_id, {})[item.flag_key] = bool(item.is_done)

    rows: list[PeriodicAccountOut] = []
    for acc in accounts:
        acc_flags = flags_map.get(acc.account_id, {})
        rows.append(
            PeriodicAccountOut(
                account_id=acc.account_id,
                id=acc.id,
                abbr=acc.abbr,
                nickname=acc.nickname,
                phone_number=acc.phone_number,
                version_matrix_soldier=acc_flags.get("version_matrix_soldier", False),
                version_small_coral_exchange=acc_flags.get("version_small_coral_exchange", False),
                version_hologram_challenge=acc_flags.get("version_hologram_challenge", False),
                version_echo_template_adjust=acc_flags.get("version_echo_template_adjust", False),
                hv_trial_character=acc_flags.get("hv_trial_character", False),
                monthly_tower_exchange=acc_flags.get("monthly_tower_exchange", False),
                four_week_tower=acc_flags.get("four_week_tower", False),
                four_week_ruins=acc_flags.get("four_week_ruins", False),
                range_lahailuo_cube=acc_flags.get("range_lahailuo_cube", False),
                range_music_game=acc_flags.get("range_music_game", False),
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
