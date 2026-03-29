from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from .models import TaskStatus, TaskType


class AccountBase(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    phone_number: str | None = Field(default=None, max_length=32)
    nickname: str = Field(min_length=1, max_length=128)
    abbr: str = Field(min_length=1, max_length=32)
    remark: str | None = None
    tacet: str = ""
    is_active: bool = True


class AccountCreate(AccountBase):
    last_waveplate: int = Field(default=0, ge=0, le=240)
    waveplate_crystal: int = Field(default=0, ge=0, le=480)


class AccountUpdate(BaseModel):
    phone_number: str | None = None
    nickname: str | None = None
    abbr: str | None = None
    remark: str | None = None
    tacet: str | None = None
    is_active: bool | None = None
    last_waveplate: int | None = Field(default=None, ge=0, le=240)
    waveplate_crystal: int | None = Field(default=None, ge=0, le=480)


class AccountOut(AccountBase):
    account_id: int
    last_waveplate: int
    last_waveplate_updated_at: datetime
    waveplate_crystal: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnergySetIn(BaseModel):
    current_waveplate: int | None = Field(default=None, ge=0, le=240)
    current_waveplate_crystal: int | None = Field(default=None, ge=0, le=480)
    full_waveplate_at: datetime | None = None

    @model_validator(mode="after")
    def validate_energy_set_mode(self):
        if self.current_waveplate is None and self.full_waveplate_at is None:
            raise ValueError("current_waveplate or full_waveplate_at is required")
        return self


class EnergySpendIn(BaseModel):
    cost: int = Field(description="Allowed: 40, 60, 80, 120")


class EnergyGainIn(BaseModel):
    amount: int = Field(description="Allowed: 40, 60")


class EnergyOut(BaseModel):
    account_id: int
    id: str
    current_waveplate: int
    current_waveplate_crystal: int
    last_waveplate: int
    last_waveplate_updated_at: datetime
    waveplate_full_in_minutes: int
    eta_waveplate_full: datetime
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


class DailyFlagUpdateIn(BaseModel):
    flag_key: str = Field(min_length=1, max_length=64)
    is_done: bool | None = None
    status: str | None = Field(default=None, pattern="^(todo|done|skipped)$")

    @model_validator(mode="after")
    def validate_one_of(self):
        if self.status is None and self.is_done is None:
            raise ValueError("status or is_done is required")
        return self


class TacetUpdateIn(BaseModel):
    tacet: str


class DashboardAccountOut(BaseModel):
    account_id: int
    id: str
    abbr: str
    nickname: str
    phone_number: str | None
    remark: str | None
    tacet: str = ""
    current_waveplate: int
    current_waveplate_crystal: int
    warn_level: str
    daily_task: bool = False
    daily_nest: bool = False
    weekly_door: bool = False
    weekly_boss: bool = False
    daily_task_status: str = "todo"
    daily_nest_status: str = "todo"
    weekly_door_status: str = "todo"
    weekly_boss_status: str = "todo"
    waveplate_full_in_minutes: int
    eta_waveplate_full: datetime
    todo_count: int
    done_count: int


class PeriodicAccountOut(BaseModel):
    account_id: int
    id: str
    abbr: str
    nickname: str
    phone_number: str | None
    created_at: datetime
    updated_at: datetime
    version_matrix_soldier: bool = False
    version_matrix_soldier_status: str = "todo"
    version_small_coral_exchange: bool = False
    version_small_coral_exchange_status: str = "todo"
    version_hologram_challenge: bool = False
    version_hologram_challenge_status: str = "todo"
    version_echo_template_adjust: bool = False
    version_echo_template_adjust_status: str = "todo"
    hv_trial_character: bool = False
    hv_trial_character_status: str = "todo"
    monthly_tower_exchange: bool = False
    monthly_tower_exchange_status: str = "todo"
    four_week_tower: bool = False
    four_week_tower_status: str = "todo"
    four_week_ruins: bool = False
    four_week_ruins_status: str = "todo"
    range_lahailuo_cube: bool = False
    range_lahailuo_cube_status: str = "todo"
    range_music_game: bool = False
    range_music_game_status: str = "todo"
