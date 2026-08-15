"""Daily check-ins and the activity heatmap."""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import Challenge, ChallengeParticipant, DailyCheckin, Goal
from app.schemas.domain import CheckinCreate, ProgressCreate
from app.services.clock import challenge_today, local_date
from app.services.goals import add_progress, require_goal
from app.services.progress import checkin_streak


def save_checkin(
    db: Session,
    *,
    participant: ChallengeParticipant,
    user_id: uuid.UUID,
    payload: CheckinCreate,
    team_id: uuid.UUID | None = None,
) -> DailyCheckin:
    """Write the day's note and every goal update as one unit.

    Wrapped in a savepoint so a bad goal id halfway through the list does not
    leave the earlier updates applied; the member sees a clean failure and can
    resubmit the whole day.
    """
    with db.begin_nested():
        checkin = db.scalar(
            select(DailyCheckin).where(
                DailyCheckin.challenge_participant_id == participant.id,
                DailyCheckin.checkin_date == payload.date,
            )
        )
        if checkin:
            checkin.note = payload.note
        else:
            checkin = DailyCheckin(
                challenge_participant_id=participant.id,
                checkin_date=payload.date,
                note=payload.note,
            )
            db.add(checkin)

        for update in payload.updates:
            goal = require_goal(db, update.goal_id, participant)
            if goal.children:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "Update the sub-goals instead of the parent",
                )
            add_progress(
                db,
                goal=goal,
                participant=participant,
                user_id=user_id,
                team_id=team_id,
                payload=ProgressCreate(
                    **update.model_dump(exclude={"goal_id", "entry_date"}),
                    entry_date=payload.date,
                ),
            )
        db.flush()
    return checkin


def checkin_for_date(
    db: Session, participant: ChallengeParticipant, day: date
) -> DailyCheckin | None:
    return db.scalar(
        select(DailyCheckin).where(
            DailyCheckin.challenge_participant_id == participant.id,
            DailyCheckin.checkin_date == day,
        )
    )


def checkin_dates(db: Session, participant_id: uuid.UUID) -> list[date]:
    return list(
        db.scalars(
            select(DailyCheckin.checkin_date)
            .where(DailyCheckin.challenge_participant_id == participant_id)
            .order_by(DailyCheckin.checkin_date)
        ).all()
    )


def update_counts(db: Session, participant_id: uuid.UUID) -> dict[date, int]:
    from app.models.domain import GoalProgressEntry

    return dict(
        db.execute(
            select(GoalProgressEntry.entry_date, func.count())
            .join(Goal, Goal.id == GoalProgressEntry.goal_id)
            .where(Goal.challenge_participant_id == participant_id)
            .group_by(GoalProgressEntry.entry_date)
        ).all()
    )


def heatmap(
    db: Session, participant: ChallengeParticipant, challenge: Challenge
) -> dict:
    """Streak plus one entry per logged day, bounded by the challenge itself.

    The window is derived from the challenge dates rather than a fixed length so
    a 90-day or 365-day challenge renders correctly.
    """
    rows = list(
        db.scalars(
            select(DailyCheckin)
            .where(DailyCheckin.challenge_participant_id == participant.id)
            .order_by(DailyCheckin.checkin_date)
        ).all()
    )
    counts = update_counts(db, participant.id)
    today = challenge_today(challenge)
    return {
        "start_date": local_date(challenge, challenge.start_at),
        "end_date": local_date(challenge, challenge.end_at),
        "today": today,
        "streak": checkin_streak([row.checkin_date for row in rows], today),
        "total_days_logged": len(rows),
        "days": [
            {
                "date": row.checkin_date,
                "note": row.note,
                "updates": counts.get(row.checkin_date, 0),
            }
            for row in rows
        ],
    }
