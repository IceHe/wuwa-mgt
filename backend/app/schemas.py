from datetime import datetime

from pydantic import BaseModel, Field

from .models import TaskStatus, TaskType


class AccountBase(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    account_code: str = Field(min_length=1, max_length=32)
    account_name: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    note: str | None = None
    is_active: bool = True


class AccountCreate(AccountBase):
    energy_at_prev_4am: int = 0


class AccountUpdate(BaseModel):
    account_code: str | None = None
    account_name: str | None = None
    phone: str | None = None
    note: str | None = None
    is_active: bool | None = None
    energy_at_prev_4am: int | None = Field(default=None, ge=0, le=480)


class AccountOut(AccountBase):
    id: int
    energy_at_prev_4am: int
    prev_4am_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnergySetIn(BaseModel):
    current_energy: int = Field(ge=0, le=480)


class EnergySpendIn(BaseModel):
    cost: int = Field(description="Allowed: 40, 60, 80, 120")


class EnergyOut(BaseModel):
    account_id: int
    player_id: str
    current_energy: int
    energy_at_prev_4am: int
    prev_4am_at: datetime
    time_to_240_minutes: int
    time_to_480_minutes: int
    eta_240: datetime
    eta_480: datetime
    warn_level: str


class TaskTemplateCreate(BaseModel):
    name: str
    task_type: TaskType
    default_priority: int = 3
    description: str | None = None
    is_active: bool = True


class TaskTemplateUpdate(BaseModel):
    name: str | None = None
    task_type: TaskType | None = None
    default_priority: int | None = None
    description: str | None = None
    is_active: bool | None = None


class TaskTemplateOut(BaseModel):
    id: int
    name: str
    task_type: TaskType
    default_priority: int
    description: str | None
    is_active: bool

    class Config:
        from_attributes = True


class TaskInstanceCreate(BaseModel):
    account_id: int
    template_id: int
    period_key: str
    status: TaskStatus = TaskStatus.todo
    start_at: datetime
    deadline_at: datetime | None = None
    priority: int = 3
    note: str | None = None


class TaskInstanceUpdate(BaseModel):
    status: TaskStatus | None = None
    deadline_at: datetime | None = None
    priority: int | None = None
    note: str | None = None


class TaskInstanceOut(BaseModel):
    id: int
    account_id: int
    template_id: int
    period_key: str
    status: TaskStatus
    start_at: datetime
    deadline_at: datetime | None
    priority: int
    note: str | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class TaskGenerateIn(BaseModel):
    period_key: str
    start_at: datetime
    deadline_at: datetime | None = None
    task_type: TaskType | None = None


class TaskGenerateOut(BaseModel):
    created: int


class DashboardAccountOut(BaseModel):
    account_id: int
    player_id: str
    account_code: str
    account_name: str
    current_energy: int
    warn_level: str
    time_to_240_minutes: int
    eta_240: datetime
    todo_count: int
    done_count: int
