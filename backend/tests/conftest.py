"""Test harness.

Runs against a real PostgreSQL database rather than SQLite: the schema relies on
partial unique indexes and native enums, and those invariants are exactly what
the tests need to prove. Set TEST_DATABASE_URL to point somewhere else.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres@127.0.0.1:55432/lockin_test",
)
CSRF_TOKEN = "test-csrf-token"

# Set before any test module imports app.config: get_settings() is lru_cached,
# so whichever URL is present at first import is the one the app uses.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

TABLES = (
    "audit_logs",
    "notifications",
    "push_subscriptions",
    "forfeit_obligations",
    "challenge_outcomes",
    "daily_checkins",
    "goal_progress_entries",
    "goals",
    "challenge_participants",
    "challenges",
    "invitations",
    "oauth_auth_codes",
    "oauth_clients",
    "mcp_tokens",
    "team_members",
    "teams",
    "users",
)


def _alembic_config(url: str) -> Config:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(root, "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(scope="session")
def engine() -> Engine:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unavailable at {TEST_DATABASE_URL}: {exc}")

    config = _alembic_config(TEST_DATABASE_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return engine


@pytest.fixture
def sessionmaker_for_tests(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_database(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))


@pytest.fixture
def db(sessionmaker_for_tests: sessionmaker) -> Iterator[Session]:
    with sessionmaker_for_tests() as session:
        yield session


@pytest.fixture
def app(sessionmaker_for_tests: sessionmaker):
    """The FastAPI app with its database dependency pointed at the test engine."""
    from app.db.session import get_db
    from app.main import app as fastapi_app

    def override_get_db() -> Iterator[Session]:
        with sessionmaker_for_tests() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def anon(app) -> Iterator[TestClient]:
    """Unauthenticated client that does not send a CSRF header."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_factory(app):
    """Build an authenticated client for a given user.

    Google token verification is exercised separately in test_auth; everywhere
    else it is faster and clearer to mint the session cookie directly.
    """
    from app.dependencies.auth import CSRF_COOKIE, SESSION_COOKIE, create_session_token

    created: list[TestClient] = []

    def make(user_id: uuid.UUID, *, csrf: bool = True) -> TestClient:
        headers = {"X-CSRF-Token": CSRF_TOKEN} if csrf else {}
        client = TestClient(app, headers=headers)
        client.cookies.set(SESSION_COOKIE, create_session_token(user_id))
        client.cookies.set(CSRF_COOKIE, CSRF_TOKEN)
        created.append(client)
        return client

    yield make
    for client in created:
        client.close()


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------


@pytest.fixture
def make_user(db: Session):
    def make(name: str = "Member", email: str | None = None):
        from app.models.domain import User

        suffix = uuid.uuid4().hex[:8]
        user = User(
            google_sub=f"sub-{suffix}",
            email=email or f"{name.lower().replace(' ', '.')}.{suffix}@example.com",
            display_name=name,
        )
        db.add(user)
        db.commit()
        return user

    return make


@pytest.fixture
def make_team(db: Session):
    def make(owner, name: str = "The Boys"):
        from app.models.domain import Team, TeamMember, TeamRole

        team = Team(name=name, created_by=owner.id)
        db.add(team)
        db.flush()
        db.add(TeamMember(team_id=team.id, user_id=owner.id, role=TeamRole.ADMIN))
        db.commit()
        return team

    return make


@pytest.fixture
def make_challenge(db: Session):
    def make(
        team,
        *,
        days: int = 184,
        submission_days: int = 5,
        forfeit_pence: int = 20000,
        start_offset: timedelta = timedelta(0),
        status=None,
    ):
        from app.models.domain import Challenge, ChallengeStatus

        now = datetime.now(UTC)
        challenge = Challenge(
            team_id=team.id,
            name="6 Month Lock-In",
            start_at=now + start_offset,
            end_at=now + start_offset + timedelta(days=days),
            timezone="Europe/London",
            goal_submission_days=submission_days,
            forfeit_amount_pence=forfeit_pence,
            status=status or ChallengeStatus.ACTIVE,
        )
        db.add(challenge)
        db.commit()
        return challenge

    return make


@pytest.fixture
def make_participant(db: Session):
    def make(challenge, user, *, due_offset: timedelta | None = None, locked=False):
        from app.models.domain import ChallengeParticipant
        from app.services.goals import goal_submission_deadline

        now = datetime.now(UTC)
        participant = ChallengeParticipant(
            challenge_id=challenge.id,
            user_id=user.id,
            joined_at=now,
            goals_due_at=(
                now + due_offset
                if due_offset is not None
                else goal_submission_deadline(challenge, now)
            ),
            goals_locked_at=now if locked else None,
        )
        db.add(participant)
        db.commit()
        return participant

    return make


@pytest.fixture
def make_member(db: Session):
    def make(team, user, role=None):
        from app.models.domain import TeamMember, TeamRole

        member = TeamMember(
            team_id=team.id, user_id=user.id, role=role or TeamRole.MEMBER
        )
        db.add(member)
        db.commit()
        return member

    return make


@pytest.fixture
def make_goal(db: Session):
    def make(participant, **overrides):
        from decimal import Decimal

        from app.models.domain import Goal, GoalCategory, TargetDirection, TrackingType

        values = {
            "challenge_participant_id": participant.id,
            "category": GoalCategory.PHYSICAL,
            "title": "Deadlift 120kg",
            "tracking_type": TrackingType.NUMERIC,
            "baseline_value": Decimal(90),
            "target_value": Decimal(120),
            "current_value": Decimal(90),
            "target_direction": TargetDirection.AT_LEAST,
            "unit": "kg",
            "required": True,
        }
        values.update(overrides)
        goal = Goal(**values)
        db.add(goal)
        db.commit()
        return goal

    return make


@pytest.fixture
def team_setup(
    make_user, make_team, make_challenge, make_participant, make_member, client_factory
):
    """An admin plus one member, both enrolled in an active challenge."""

    class Setup:
        def __init__(self) -> None:
            self.admin = make_user("Admin")
            self.member = make_user("Teammate")
            self.team = make_team(self.admin)
            make_member(self.team, self.member)
            self.challenge = make_challenge(self.team)
            self.admin_participant = make_participant(self.challenge, self.admin)
            self.member_participant = make_participant(self.challenge, self.member)
            self.admin_client = client_factory(self.admin.id)
            self.member_client = client_factory(self.member.id)

    return Setup()
