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

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "id" not in d and "player_id" in d:
            d["id"] = d["player_id"]
        if "abbr" not in d and "account_code" in d:
            d["abbr"] = d["account_code"]
        if "nickname" not in d and "account_name" in d:
            d["nickname"] = d["account_name"]
        if "phone_number" not in d and "phone" in d:
            d["phone_number"] = d["phone"]
        if "remark" not in d and "note" in d:
            d["remark"] = d["note"]
        if "last_waveplate" not in d and "energy_at_prev_4am" in d:
            d["last_waveplate"] = d["energy_at_prev_4am"]
        return d


class AccountUpdate(BaseModel):
    phone_number: str | None = None
    nickname: str | None = None
    abbr: str | None = None
    remark: str | None = None
    tacet: str | None = None
    is_active: bool | None = None
    last_waveplate: int | None = Field(default=None, ge=0, le=240)
    waveplate_crystal: int | None = Field(default=None, ge=0, le=480)

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "abbr" not in d and "account_code" in d:
            d["abbr"] = d["account_code"]
        if "nickname" not in d and "account_name" in d:
            d["nickname"] = d["account_name"]
        if "phone_number" not in d and "phone" in d:
            d["phone_number"] = d["phone"]
        if "remark" not in d and "note" in d:
            d["remark"] = d["note"]
        if "last_waveplate" not in d and "energy_at_prev_4am" in d:
            d["last_waveplate"] = d["energy_at_prev_4am"]
        return d


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
    current_waveplate: int = Field(default=0, ge=0, le=240)
    current_waveplate_crystal: int | None = Field(default=None, ge=0, le=480)

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_field(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "current_waveplate" not in d and "current_energy" in d:
            d["current_waveplate"] = d["current_energy"]
        if "current_waveplate_crystal" not in d and "waveplate_crystal" in d:
            d["current_waveplate_crystal"] = d["waveplate_crystal"]
        return d


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
    is_done: bool


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
    daily_done: bool = False
    nest_cleared: bool = False
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
    version_matrix_soldier: bool = False
    version_small_coral_exchange: bool = False
    version_hologram_challenge: bool = False
    version_echo_template_adjust: bool = False
    hv_trial_character: bool = False
    monthly_tower_exchange: bool = False
    four_week_tower: bool = False
    four_week_ruins: bool = False
    range_lahailuo_cube: bool = False
    range_music_game: bool = False
