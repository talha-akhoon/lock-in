"""Challenge lifecycle, final scoring and forfeit calculation."""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Challenge,
    ChallengeOutcome,
    ChallengeParticipant,
    ChallengeStatus,
    ForfeitObligation,
    Goal,
    GoalProgressEntry,
    GoalVisibility,
    NotificationType,
    ParticipantStatus,
    User,
)
from app.services import notifications
from app.services.clock import (
    as_utc,
    challenge_day_number,
    challenge_days_remaining,
    challenge_total_days,
    utcnow,
)
from app.services.goals import load_goal_tree
from app.services.progress import goal_is_complete, overall_progress

OPEN_CHALLENGE_STATUSES = (
    ChallengeStatus.DRAFT,
    ChallengeStatus.UPCOMING,
    ChallengeStatus.ACTIVE,
)


def open_challenge(db: Session, team_id: uuid.UUID) -> Challenge | None:
    return db.scalar(
        select(Challenge).where(
            Challenge.team_id == team_id,
            Challenge.status.in_(OPEN_CHALLENGE_STATUSES),
        )
    )


def latest_challenge(db: Session, team_id: uuid.UUID) -> Challenge | None:
    """The open challenge if there is one, else the most recent completed one."""
    return open_challenge(db, team_id) or db.scalar(
        select(Challenge)
        .where(Challenge.team_id == team_id)
        .order_by(Challenge.start_at.desc())
    )


def assert_no_open_challenge(db: Session, team_id: uuid.UUID) -> None:
    """Mirror of the uq_challenges_one_open_per_team index as a clean 409."""
    if open_challenge(db, team_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "CHALLENGE_ALREADY_OPEN",
                "message": "This team already has an open challenge",
            },
        )


def derived_status(
    challenge: Challenge, now: datetime | None = None
) -> ChallengeStatus:
    moment = as_utc(now or utcnow())
    if moment >= as_utc(challenge.end_at):
        return ChallengeStatus.COMPLETED
    if moment < as_utc(challenge.start_at):
        return ChallengeStatus.UPCOMING
    return ChallengeStatus.ACTIVE


def sync_challenge_status(
    db: Session, challenge: Challenge, now: datetime | None = None
) -> Challenge:
    """Advance UPCOMING -> ACTIVE -> COMPLETED as time passes.

    DRAFT is left alone: it is an editorial state an admin exits deliberately.
    Callers that already have a clock (the evening dispatch job) pass it in
    so a historical `now` cannot complete a challenge that is still running
    at that moment.
    """
    if challenge.status == ChallengeStatus.DRAFT:
        return challenge
    target = derived_status(challenge, now)
    if challenge.status != target:
        challenge.status = target
        if target == ChallengeStatus.COMPLETED:
            evaluate_challenge(db, challenge)
    return challenge


def require_team_challenge(
    db: Session, challenge_id: uuid.UUID, team_id: uuid.UUID
) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if not challenge or challenge.team_id != team_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Challenge not found")
    return challenge


def summary(challenge: Challenge) -> dict:
    return {
        "id": challenge.id,
        "name": challenge.name,
        "description": challenge.description,
        "start_at": challenge.start_at,
        "end_at": challenge.end_at,
        "timezone": challenge.timezone,
        "status": challenge.status,
        "goal_submission_days": challenge.goal_submission_days,
        "forfeit_amount_pence": challenge.forfeit_amount_pence,
        "day_number": challenge_day_number(challenge),
        "total_days": challenge_total_days(challenge),
        "days_remaining": challenge_days_remaining(challenge),
    }


def activity_entries(
    db: Session,
    *,
    challenge_id: uuid.UUID,
    viewer_id: uuid.UUID,
    limit: int = 100,
) -> list[dict]:
    """Recent progress entries. Private goals appear only to their owner."""
    rows = db.execute(
        select(GoalProgressEntry, Goal, User)
        .join(Goal, Goal.id == GoalProgressEntry.goal_id)
        .join(
            ChallengeParticipant,
            ChallengeParticipant.id == Goal.challenge_participant_id,
        )
        .join(User, User.id == GoalProgressEntry.user_id)
        .where(
            ChallengeParticipant.challenge_id == challenge_id,
            (Goal.visibility == GoalVisibility.TEAM)
            | (ChallengeParticipant.user_id == viewer_id),
        )
        .order_by(GoalProgressEntry.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [
        {
            "id": entry.id,
            "user_id": author.id,
            "display_name": author.display_name,
            "avatar_url": author.avatar_url,
            "goal_id": goal.id,
            "goal_title": goal.title,
            "goal_category": goal.category,
            "unit": goal.unit,
            "entry_date": entry.entry_date,
            "numeric_value": entry.numeric_value,
            "numeric_delta": entry.numeric_delta,
            "manual_percentage": entry.manual_percentage,
            "completed": entry.completed,
            "note": entry.note,
            "created_at": entry.created_at,
        }
        for entry, goal, author in rows
    ]


def active_participants(
    db: Session, challenge_id: uuid.UUID
) -> list[ChallengeParticipant]:
    return list(
        db.scalars(
            select(ChallengeParticipant)
            .options(selectinload(ChallengeParticipant.user))
            .where(
                ChallengeParticipant.challenge_id == challenge_id,
                ChallengeParticipant.status != ParticipantStatus.REMOVED,
            )
        ).all()
    )


def evaluate_challenge(db: Session, challenge: Challenge) -> list[ChallengeOutcome]:
    """Score every participant once and record who owes whom.

    Idempotent: outcomes already written are returned untouched, so repeated
    reads of a finished challenge cannot double-charge anyone.
    """
    existing = list(
        db.scalars(
            select(ChallengeOutcome)
            .join(
                ChallengeParticipant,
                ChallengeParticipant.id == ChallengeOutcome.challenge_participant_id,
            )
            .where(ChallengeParticipant.challenge_id == challenge.id)
        ).all()
    )
    if existing:
        return existing

    participants = active_participants(db, challenge.id)
    outcomes: list[ChallengeOutcome] = []
    for participant in participants:
        roots = load_goal_tree(db, participant.id)
        required = [goal for goal in roots if goal.required]
        optional = [goal for goal in roots if not goal.required]
        required_done = sum(1 for goal in required if goal_is_complete(goal))
        optional_done = sum(1 for goal in optional if goal_is_complete(goal))
        # Same figure the member watched on the dashboard: category means,
        # required goals only, all-optional categories left out of overall.
        progress = overall_progress(roots)
        # Submitting nothing is a failure, not a free pass.
        succeeded = bool(required) and required_done == len(required)
        participant.status = (
            ParticipantStatus.COMPLETED if succeeded else ParticipantStatus.FORFEIT_DUE
        )
        participant.completed_at = utcnow()
        recipients = [
            other for other in participants if other.user_id != participant.user_id
        ]
        total_forfeit = (
            0 if succeeded else challenge.forfeit_amount_pence * len(recipients)
        )
        outcome = ChallengeOutcome(
            challenge_participant_id=participant.id,
            required_goals_total=len(required),
            required_goals_completed=required_done,
            optional_goals_total=len(optional),
            optional_goals_completed=optional_done,
            final_progress_percentage=Decimal(str(round(progress, 2))),
            succeeded=succeeded,
            total_forfeit_pence=total_forfeit,
        )
        db.add(outcome)
        outcomes.append(outcome)
        if not succeeded:
            for recipient in recipients:
                db.add(
                    ForfeitObligation(
                        challenge_id=challenge.id,
                        from_user_id=participant.user_id,
                        to_user_id=recipient.user_id,
                        amount_pence=challenge.forfeit_amount_pence,
                    )
                )
        notifications.notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge.id,
            kind=NotificationType.CHALLENGE_COMPLETE,
            dedupe_key=f"complete:{challenge.id}",
            title=f"{challenge.name} has finished",
            body="See the final results and any forfeits owed.",
            link_path="/dashboard",
        )

    challenge.status = ChallengeStatus.COMPLETED
    db.flush()
    return outcomes


def forfeit_lines(db: Session, challenge_id: uuid.UUID) -> list[dict]:
    """Itemised "X owes Y £Z" lines for the challenge-complete screen."""
    rows = db.execute(
        select(ForfeitObligation)
        .where(ForfeitObligation.challenge_id == challenge_id)
        .order_by(ForfeitObligation.created_at)
    ).scalars()
    lines = []
    for row in rows:
        payer = db.get(User, row.from_user_id)
        payee = db.get(User, row.to_user_id)
        lines.append(
            {
                "id": row.id,
                "from_user_id": row.from_user_id,
                "from_display_name": payer.display_name if payer else "Unknown",
                "to_user_id": row.to_user_id,
                "to_display_name": payee.display_name if payee else "Unknown",
                "amount_pence": row.amount_pence,
                "status": row.status,
                "settled_at": row.settled_at,
            }
        )
    return lines


def outcome_rows(db: Session, challenge_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(ChallengeOutcome, ChallengeParticipant, User)
        .join(
            ChallengeParticipant,
            ChallengeParticipant.id == ChallengeOutcome.challenge_participant_id,
        )
        .join(User, User.id == ChallengeParticipant.user_id)
        .where(ChallengeParticipant.challenge_id == challenge_id)
        .order_by(ChallengeOutcome.succeeded.desc(), User.display_name)
    ).all()
    return [
        {
            "participant_id": outcome.challenge_participant_id,
            "user_id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "required_goals_total": outcome.required_goals_total,
            "required_goals_completed": outcome.required_goals_completed,
            "optional_goals_total": outcome.optional_goals_total,
            "optional_goals_completed": outcome.optional_goals_completed,
            "final_progress_percentage": outcome.final_progress_percentage,
            "succeeded": outcome.succeeded,
            "total_forfeit_pence": outcome.total_forfeit_pence,
        }
        for outcome, _participant, user in rows
    ]
