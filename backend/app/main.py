import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .energy import (
    current_energy,
    infer_base_energy_from_current,
    minutes_to_target,
    previous_4am,
    warn_level,
)
from .models import Account, TaskInstance, TaskStatus, TaskTemplate
from .schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    DashboardAccountOut,
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

app = FastAPI(title="Wuwa Account Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def now_tz() -> datetime:
    return datetime.now(ZoneInfo(APP_TZ))


def energy_payload(account: Account, now: datetime) -> EnergyOut:
    current = current_energy(account.energy_at_prev_4am, account.prev_4am_at, now)
    to_240 = minutes_to_target(current, 240) or 0
    to_480 = minutes_to_target(current, 480) or 0
    return EnergyOut(
        account_id=account.id,
        player_id=account.player_id,
        current_energy=current,
        energy_at_prev_4am=account.energy_at_prev_4am,
        prev_4am_at=account.prev_4am_at,
        time_to_240_minutes=to_240,
        time_to_480_minutes=to_480,
        eta_240=now + timedelta(minutes=to_240),
        eta_480=now + timedelta(minutes=to_480),
        warn_level=warn_level(current),
    )


def rebase_anchor_for_now(account: Account, now: datetime) -> None:
    pivot = previous_4am(now, APP_TZ)
    current = current_energy(account.energy_at_prev_4am, account.prev_4am_at, now)
    account.prev_4am_at = pivot
    account.energy_at_prev_4am = infer_base_energy_from_current(current, pivot, now)


def get_account_by_player_id(db: Session, player_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.player_id == player_id))
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/accounts", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    now = now_tz()
    account = Account(
        player_id=payload.player_id,
        account_code=payload.account_code,
        account_name=payload.account_name,
        phone=payload.phone,
        note=payload.note,
        is_active=payload.is_active,
        energy_at_prev_4am=payload.energy_at_prev_4am,
        prev_4am_at=previous_4am(now, APP_TZ),
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="player_id or account_code already exists") from exc
    db.refresh(account)
    return account


@app.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), active_only: bool = False) -> list[Account]:
    stmt = select(Account).order_by(Account.created_at.desc())
    if active_only:
        stmt = stmt.where(Account.is_active.is_(True))
    return db.scalars(stmt).all()


@app.get("/accounts/by-player/{player_id}", response_model=AccountOut)
def get_account_by_player(player_id: str, db: Session = Depends(get_db)) -> Account:
    return get_account_by_player_id(db, player_id)


@app.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    data = payload.model_dump(exclude_unset=True)
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
    account = get_account_by_player_id(db, player_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


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
    account = get_account_by_player_id(db, player_id)
    db.delete(account)
    db.commit()
    return {"ok": True}


@app.get("/accounts/{account_id}/energy", response_model=EnergyOut)
def get_account_energy(account_id: int, db: Session = Depends(get_db)) -> EnergyOut:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    now = now_tz()
    rebase_anchor_for_now(account, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.get("/accounts/by-player/{player_id}/energy", response_model=EnergyOut)
def get_account_energy_by_player(player_id: str, db: Session = Depends(get_db)) -> EnergyOut:
    account = get_account_by_player_id(db, player_id)
    now = now_tz()
    rebase_anchor_for_now(account, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/{account_id}/energy/set", response_model=EnergyOut)
def set_current_energy(account_id: int, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    now = now_tz()
    pivot = previous_4am(now, APP_TZ)
    account.prev_4am_at = pivot
    account.energy_at_prev_4am = infer_base_energy_from_current(payload.current_energy, pivot, now)

    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-player/{player_id}/energy/set", response_model=EnergyOut)
def set_current_energy_by_player(player_id: str, payload: EnergySetIn, db: Session = Depends(get_db)) -> EnergyOut:
    account = get_account_by_player_id(db, player_id)
    now = now_tz()
    pivot = previous_4am(now, APP_TZ)
    account.prev_4am_at = pivot
    account.energy_at_prev_4am = infer_base_energy_from_current(payload.current_energy, pivot, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/{account_id}/energy/spend", response_model=EnergyOut)
def spend_energy(account_id: int, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.cost not in {40, 60, 80, 120}:
        raise HTTPException(status_code=400, detail="cost must be one of 40, 60, 80, 120")

    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    now = now_tz()
    current = current_energy(account.energy_at_prev_4am, account.prev_4am_at, now)
    updated = max(0, current - payload.cost)

    pivot = previous_4am(now, APP_TZ)
    account.prev_4am_at = pivot
    account.energy_at_prev_4am = infer_base_energy_from_current(updated, pivot, now)

    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.post("/accounts/by-player/{player_id}/energy/spend", response_model=EnergyOut)
def spend_energy_by_player(player_id: str, payload: EnergySpendIn, db: Session = Depends(get_db)) -> EnergyOut:
    if payload.cost not in {40, 60, 80, 120}:
        raise HTTPException(status_code=400, detail="cost must be one of 40, 60, 80, 120")
    account = get_account_by_player_id(db, player_id)
    now = now_tz()
    current = current_energy(account.energy_at_prev_4am, account.prev_4am_at, now)
    updated = max(0, current - payload.cost)
    pivot = previous_4am(now, APP_TZ)
    account.prev_4am_at = pivot
    account.energy_at_prev_4am = infer_base_energy_from_current(updated, pivot, now)
    db.commit()
    db.refresh(account)
    return energy_payload(account, now)


@app.get("/dashboard/accounts", response_model=list[DashboardAccountOut])
def dashboard_accounts(db: Session = Depends(get_db)) -> list[DashboardAccountOut]:
    now = now_tz()
    accounts = db.scalars(select(Account).where(Account.is_active.is_(True)).order_by(Account.account_code)).all()
    rows: list[DashboardAccountOut] = []

    for acc in accounts:
        rebase_anchor_for_now(acc, now)
        current = current_energy(acc.energy_at_prev_4am, acc.prev_4am_at, now)
        to_240 = minutes_to_target(current, 240) or 0

        todo_count = db.scalar(
            select(func.count(TaskInstance.id)).where(
                TaskInstance.account_id == acc.id,
                TaskInstance.status == TaskStatus.todo,
            )
        )
        done_count = db.scalar(
            select(func.count(TaskInstance.id)).where(
                TaskInstance.account_id == acc.id,
                TaskInstance.status == TaskStatus.done,
            )
        )

        rows.append(
            DashboardAccountOut(
                account_id=acc.id,
                player_id=acc.player_id,
                account_code=acc.account_code,
                account_name=acc.account_name,
                current_energy=current,
                warn_level=warn_level(current),
                time_to_240_minutes=to_240,
                eta_240=now + timedelta(minutes=to_240),
                todo_count=todo_count or 0,
                done_count=done_count or 0,
            )
        )

    db.commit()
    rows.sort(key=lambda item: item.eta_240)
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
                    TaskInstance.account_id == acc.id,
                    TaskInstance.template_id == tpl.id,
                    TaskInstance.period_key == payload.period_key,
                )
            )
            if exists:
                continue
            db.add(
                TaskInstance(
                    account_id=acc.id,
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
