"""Populate a migrated database with a single-member example challenge.

Deliberately does not create tables: calling create_all() here would build a
schema Alembic has no version row for, and every later `alembic upgrade` would
then fail on already-existing tables.
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import inspect, select

from app.db.session import SessionLocal, engine
from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    ChallengeStatus,
    Goal,
    GoalCategory,
    Team,
    TeamMember,
    TeamRole,
    TrackingType,
    User,
)
from app.services.goals import goal_submission_deadline

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "talha@example.com")
ADMIN_NAME = os.environ.get("SEED_ADMIN_NAME", "Talha Akhoon")
TEAM_NAME = os.environ.get("SEED_TEAM_NAME", "The Boys")
CHALLENGE_NAME = os.environ.get("SEED_CHALLENGE_NAME", "6 Month Lock-In")
FORFEIT_PENCE = int(os.environ.get("SEED_FORFEIT_PENCE", "20000"))
CHALLENGE_DAYS = int(os.environ.get("SEED_CHALLENGE_DAYS", "184"))


class NotMigrated(RuntimeError):
    pass


def require_migrated_database() -> None:
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables:
        raise NotMigrated(
            "Database has no alembic_version table. "
            "Run `alembic upgrade head` before seeding."
        )
    missing = {"users", "teams", "challenges", "goals"} - tables
    if missing:
        raise NotMigrated(
            f"Database is missing tables {sorted(missing)}. "
            "Run `alembic upgrade head` before seeding."
        )


def seed() -> None:
    require_migrated_database()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if not user:
            user = User(
                google_sub="local-development-admin",
                email=ADMIN_EMAIL,
                display_name=ADMIN_NAME,
            )
            db.add(user)
            db.flush()
        if db.scalar(select(TeamMember).where(TeamMember.user_id == user.id)):
            print(f"{ADMIN_EMAIL} already has a team; nothing to seed.")
            return

        team = Team(name=TEAM_NAME, created_by=user.id)
        db.add(team)
        db.flush()
        db.add(TeamMember(team_id=team.id, user_id=user.id, role=TeamRole.ADMIN))

        now = datetime.now(UTC)
        challenge = Challenge(
            team_id=team.id,
            name=CHALLENGE_NAME,
            description="Commit publicly. Track consistently. Finish.",
            start_at=now,
            end_at=now + timedelta(days=CHALLENGE_DAYS),
            goal_submission_days=5,
            forfeit_amount_pence=FORFEIT_PENCE,
            status=ChallengeStatus.ACTIVE,
        )
        db.add(challenge)
        db.flush()
        participant = ChallengeParticipant(
            challenge_id=challenge.id,
            user_id=user.id,
            joined_at=now,
            goals_due_at=goal_submission_deadline(challenge, now),
        )
        db.add(participant)
        db.flush()

        def numeric(
            title: str,
            baseline: int,
            target: int,
            unit: str,
            direction: str = "AT_LEAST",
        ) -> Goal:
            return Goal(
                challenge_participant_id=participant.id,
                category=GoalCategory.PHYSICAL,
                title=title,
                tracking_type=TrackingType.NUMERIC,
                baseline_value=Decimal(baseline),
                current_value=Decimal(baseline),
                target_value=Decimal(target),
                target_direction=direction,
                unit=unit,
            )

        db.add_all(
            [
                numeric("Reach 75kg", 82, 75, "kg", "AT_MOST"),
                numeric("Deadlift 120kg", 90, 120, "kg"),
                numeric("Bench press 65kg", 45, 65, "kg"),
                Goal(
                    challenge_participant_id=participant.id,
                    category=GoalCategory.RELIGIOUS,
                    title="Read scripture 5 times",
                    tracking_type=TrackingType.COUNT,
                    baseline_value=Decimal(0),
                    current_value=Decimal(0),
                    target_value=Decimal(5),
                    target_direction="AT_LEAST",
                    unit="completions",
                ),
                Goal(
                    challenge_participant_id=participant.id,
                    category=GoalCategory.CAREER,
                    title="Land a Staff / AI Engineer role",
                    tracking_type=TrackingType.MILESTONE,
                ),
                Goal(
                    challenge_participant_id=participant.id,
                    category=GoalCategory.BUSINESS,
                    title="Build a working Vector prototype",
                    tracking_type=TrackingType.MANUAL,
                    manual_progress_percentage=0,
                ),
            ]
        )
        db.commit()
        print(f"Seeded team '{TEAM_NAME}' with challenge '{CHALLENGE_NAME}'.")


if __name__ == "__main__":
    try:
        seed()
    except NotMigrated as exc:
        sys.exit(str(exc))
