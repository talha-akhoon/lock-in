import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class TeamRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class ChallengeStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ParticipantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"
    COMPLETED = "COMPLETED"
    FORFEIT_DUE = "FORFEIT_DUE"


class GoalCategory(str, enum.Enum):
    RELIGIOUS = "RELIGIOUS"
    PHYSICAL = "PHYSICAL"
    CAREER = "CAREER"
    BUSINESS = "BUSINESS"
    PERSONAL = "PERSONAL"


class TrackingType(str, enum.Enum):
    MILESTONE = "MILESTONE"
    NUMERIC = "NUMERIC"
    COUNT = "COUNT"
    MANUAL = "MANUAL"


class TargetDirection(str, enum.Enum):
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"


class GoalVisibility(str, enum.Enum):
    TEAM = "TEAM"
    PRIVATE = "PRIVATE"


class ForfeitType(str, enum.Enum):
    PER_OTHER_MEMBER = "PER_OTHER_MEMBER"


class ObligationStatus(str, enum.Enum):
    OUTSTANDING = "OUTSTANDING"
    SETTLED = "SETTLED"


class NotificationType(str, enum.Enum):
    GOALS_DUE_SOON = "GOALS_DUE_SOON"
    GOALS_LOCK_TOMORROW = "GOALS_LOCK_TOMORROW"
    GOALS_LOCKED = "GOALS_LOCKED"
    CHALLENGE_MILESTONE = "CHALLENGE_MILESTONE"
    CHALLENGE_COMPLETE = "CHALLENGE_COMPLETE"
    MEMBER_COMPLETED_GOAL = "MEMBER_COMPLETED_GOAL"
    MEMBER_JOINED = "MEMBER_JOINED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class McpToken(TimestampMixin, Base):
    """Personal access token for the MCP endpoint. Only the hash is stored."""

    __tablename__ = "mcp_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(255))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class OAuthClient(TimestampMixin, Base):
    """Client registered through OAuth dynamic client registration."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    client_name: Mapped[str | None] = mapped_column(String(255))
    redirect_uris: Mapped[list[str]] = mapped_column(JSON)
    token_endpoint_auth_method: Mapped[str] = mapped_column(String(64), default="none")


class OAuthAuthCode(TimestampMixin, Base):
    """One-time authorization code for the MCP OAuth + PKCE flow."""

    __tablename__ = "oauth_auth_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(255), unique=True)
    client_id: Mapped[str] = mapped_column(String(512), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    code_challenge: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        Index(
            "uq_team_members_one_active_team",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[TeamRole] = mapped_column(Enum(TeamRole), default=TeamRole.MEMBER)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus), default=MembershipStatus.ACTIVE
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user: Mapped[User] = relationship()
    team: Mapped[Team] = relationship()


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    code_hash: Mapped[str] = mapped_column(String(255))
    code_prefix: Mapped[str] = mapped_column(String(4))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"
    __table_args__ = (
        Index(
            "uq_challenges_one_open_per_team",
            "team_id",
            unique=True,
            postgresql_where=text("status IN ('DRAFT', 'UPCOMING', 'ACTIVE')"),
            sqlite_where=text("status IN ('DRAFT', 'UPCOMING', 'ACTIVE')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/London")
    goal_submission_days: Mapped[int] = mapped_column(Integer, default=5)
    forfeit_type: Mapped[ForfeitType] = mapped_column(
        Enum(ForfeitType), default=ForfeitType.PER_OTHER_MEMBER
    )
    forfeit_amount_pence: Mapped[int] = mapped_column(Integer, default=20000)
    status: Mapped[ChallengeStatus] = mapped_column(
        Enum(ChallengeStatus), default=ChallengeStatus.DRAFT
    )


class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"
    __table_args__ = (
        UniqueConstraint(
            "challenge_id", "user_id", name="uq_participants_challenge_user"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    goals_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    goals_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    goals_committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(ParticipantStatus), default=ParticipantStatus.ACTIVE
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()
    challenge: Mapped[Challenge] = relationship()
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_participants.id", ondelete="CASCADE"), index=True
    )
    parent_goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[GoalCategory] = mapped_column(Enum(GoalCategory))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    tracking_type: Mapped[TrackingType] = mapped_column(Enum(TrackingType))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    unit: Mapped[str | None] = mapped_column(String(64))
    target_direction: Mapped[TargetDirection | None] = mapped_column(
        Enum(TargetDirection)
    )
    manual_progress_percentage: Mapped[int | None] = mapped_column(Integer)
    visibility: Mapped[GoalVisibility] = mapped_column(
        Enum(GoalVisibility), default=GoalVisibility.TEAM
    )
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant: Mapped[ChallengeParticipant] = relationship(back_populates="goals")
    parent: Mapped["Goal | None"] = relationship(
        remote_side="Goal.id", back_populates="children"
    )
    children: Mapped[list["Goal"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )


class GoalProgressEntry(TimestampMixin, Base):
    __tablename__ = "goal_progress_entries"
    __table_args__ = (
        Index("ix_progress_goal_date", "goal_id", "entry_date"),
        Index("ix_progress_user_date", "user_id", "entry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    entry_date: Mapped[date] = mapped_column(Date)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    numeric_delta: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    manual_percentage: Mapped[int | None] = mapped_column(Integer)
    completed: Mapped[bool | None] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(2048))
    goal: Mapped[Goal] = relationship()


class DailyCheckin(TimestampMixin, Base):
    __tablename__ = "daily_checkins"
    __table_args__ = (
        UniqueConstraint(
            "challenge_participant_id",
            "checkin_date",
            name="uq_checkin_participant_day",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_participants.id", ondelete="CASCADE"), index=True
    )
    checkin_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChallengeOutcome(Base):
    __tablename__ = "challenge_outcomes"
    __table_args__ = (
        UniqueConstraint("challenge_participant_id", name="uq_outcome_participant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_participants.id", ondelete="CASCADE")
    )
    required_goals_total: Mapped[int] = mapped_column(Integer)
    required_goals_completed: Mapped[int] = mapped_column(Integer)
    optional_goals_total: Mapped[int] = mapped_column(Integer)
    optional_goals_completed: Mapped[int] = mapped_column(Integer)
    final_progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    succeeded: Mapped[bool] = mapped_column(Boolean)
    total_forfeit_pence: Mapped[int] = mapped_column(Integer, default=0)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ForfeitObligation(TimestampMixin, Base):
    __tablename__ = "forfeit_obligations"
    __table_args__ = (
        UniqueConstraint(
            "challenge_id",
            "from_user_id",
            "to_user_id",
            name="uq_forfeit_challenge_from_to",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"))
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount_pence: Mapped[int] = mapped_column(Integer)
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(ObligationStatus), default=ObligationStatus.OUTSTANDING
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "type", "dedupe_key", name="uq_notification_dedupe"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    challenge_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE")
    )
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    dedupe_key: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(String(500))
    link_path: Mapped[str | None] = mapped_column(String(500))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

    actor: Mapped["User"] = relationship(lazy="raise")
