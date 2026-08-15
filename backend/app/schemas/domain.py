import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

from app.config import get_settings
from app.models.domain import (
    GoalCategory,
    GoalVisibility,
    TargetDirection,
    TeamRole,
    TrackingType,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserRead(ApiModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class TeamRead(ApiModel):
    id: uuid.UUID
    name: str


class InvitationCreate(BaseModel):
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=1, ge=1, le=100)


class InvitationRedeem(BaseModel):
    code: str = Field(pattern=r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")


class ChallengeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    start_at: datetime
    end_at: datetime
    # Every local date in the product — check-in days, streaks, submission
    # deadlines — is resolved in this zone, so it defaults to the deployment's
    # configured zone rather than being hardcoded per request.
    timezone: str = Field(default_factory=lambda: get_settings().challenge_timezone)
    goal_submission_days: int = Field(default=5, ge=1, le=30)
    forfeit_amount_pence: int = Field(default=20000, ge=0)

    @model_validator(mode="after")
    def validate_challenge(self) -> "ChallengeCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {self.timezone}") from exc
        return self


class ChallengeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    forfeit_amount_pence: int | None = Field(default=None, ge=0)
    publish: bool | None = None


class MemberRoleUpdate(BaseModel):
    role: TeamRole


class GoalBase(BaseModel):
    category: GoalCategory
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tracking_type: TrackingType
    baseline_value: Decimal | None = None
    target_value: Decimal | None = None
    current_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=64)
    target_direction: TargetDirection | None = None
    manual_progress_percentage: int | None = Field(default=None, ge=0, le=100)
    visibility: GoalVisibility = GoalVisibility.TEAM
    required: bool = True
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_tracking_fields(self) -> "GoalBase":
        if self.tracking_type == TrackingType.NUMERIC:
            if self.target_value is None or self.target_direction is None:
                raise ValueError("Numeric goals need a target and direction")
        elif self.tracking_type == TrackingType.COUNT:
            if self.target_value is None or self.target_value <= 0:
                raise ValueError("Count goals need a positive target")
            self.baseline_value = Decimal(0)
            self.target_direction = TargetDirection.AT_LEAST
        elif self.tracking_type == TrackingType.MILESTONE:
            self.baseline_value = self.target_value = self.current_value = None
            self.target_direction = None
        return self


class GoalCreate(GoalBase):
    parent_goal_id: uuid.UUID | None = None


class GoalUpdate(BaseModel):
    category: GoalCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    tracking_type: TrackingType | None = None
    baseline_value: Decimal | None = None
    target_value: Decimal | None = None
    unit: str | None = None
    target_direction: TargetDirection | None = None
    visibility: GoalVisibility | None = None
    required: bool | None = None
    parent_goal_id: uuid.UUID | None = None
    sort_order: int | None = None


class GoalRead(ApiModel):
    id: uuid.UUID
    parent_goal_id: uuid.UUID | None
    category: GoalCategory
    title: str
    description: str | None
    tracking_type: TrackingType
    baseline_value: Decimal | None
    target_value: Decimal | None
    current_value: Decimal | None
    unit: str | None
    target_direction: TargetDirection | None
    manual_progress_percentage: int | None
    visibility: GoalVisibility
    required: bool
    completed_at: datetime | None
    progress_percentage: float = 0
    children: list["GoalRead"] = []


class ProgressCreate(BaseModel):
    entry_date: date
    numeric_value: Decimal | None = None
    numeric_delta: Decimal | None = None
    manual_percentage: int | None = Field(default=None, ge=0, le=100)
    completed: bool | None = None
    note: str | None = Field(default=None, max_length=2000)
    evidence_url: HttpUrl | None = None


class CheckinUpdate(ProgressCreate):
    goal_id: uuid.UUID
    entry_date: date | None = None


class CheckinCreate(BaseModel):
    date: date
    note: str | None = Field(default=None, max_length=2000)
    updates: list[CheckinUpdate] = Field(default_factory=list)


class AuthMe(BaseModel):
    user: UserRead
    team: TeamRead | None = None
    role: str | None = None
    challenge_id: uuid.UUID | None = None
    challenge_status: str | None = None
    participant_id: uuid.UUID | None = None
    goals_due_at: datetime | None = None
    goals_locked: bool = False
    goals_committed_at: datetime | None = None
