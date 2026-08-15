"""The seed script must never build a schema Alembic has no version row for."""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app import seed as seed_module
from app.models.domain import Challenge, Goal, Team, TeamMember, User


def test_seeding_a_migrated_database_creates_a_usable_team(db, engine) -> None:
    seed_module.seed()

    user = db.query(User).filter_by(email=seed_module.ADMIN_EMAIL).one()
    team = db.query(Team).one()
    challenge = db.query(Challenge).one()

    assert db.query(TeamMember).filter_by(user_id=user.id).one().role.value == "ADMIN"
    assert team.name == seed_module.TEAM_NAME
    assert challenge.forfeit_amount_pence == seed_module.FORFEIT_PENCE
    # One goal per category from the original spec, plus two extra physical ones.
    assert db.query(Goal).count() == 6
    assert {goal.category.value for goal in db.query(Goal).all()} == {
        "PHYSICAL",
        "RELIGIOUS",
        "CAREER",
        "BUSINESS",
    }


def test_seeding_twice_changes_nothing(db) -> None:
    seed_module.seed()
    seed_module.seed()

    assert db.query(Team).count() == 1
    assert db.query(Goal).count() == 6


def test_seeding_an_unmigrated_database_is_refused(engine: Engine, monkeypatch) -> None:
    """Otherwise create_all() would desync alembic_version and break upgrades."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))

    try:
        with pytest.raises(seed_module.NotMigrated, match="alembic_version"):
            seed_module.seed()
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE alembic_version ("
                    "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('0003')")
            )


def test_the_seeded_deadline_lands_on_local_midnight(db) -> None:
    from zoneinfo import ZoneInfo

    from app.models.domain import ChallengeParticipant

    seed_module.seed()

    challenge = db.query(Challenge).one()
    participant = db.query(ChallengeParticipant).one()
    local = participant.goals_due_at.astimezone(ZoneInfo(challenge.timezone))

    assert (local.hour, local.minute) == (0, 0)
