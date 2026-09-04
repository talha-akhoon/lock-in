"""Daily check-ins and the activity heatmap."""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    DailyCheckin,
    Goal,
    GoalProgressEntry,
    TrackingType,
)
from app.schemas.domain import CheckinCreate, ProgressCreate
from app.services import notifications
from app.services.clock import challenge_today, is_before_start, local_date
from app.services.goals import add_progress, require_goal
from app.services.progress import checkin_streak


def checkin_date_window(challenge: Challenge) -> tuple[date, date]:
    """Dates the form may open.

    Before kick-off the only legal day is today, so a member can record their
    starting point. Once the challenge is running the window is the challenge
    itself.
    """
    today = challenge_today(challenge)
    start = local_date(challenge, challenge.start_at)
    end = local_date(challenge, challenge.end_at)
    return min(start, today), end


def assert_checkin_date_allowed(
    challenge: Challenge, day: date, *, writing: bool
) -> None:
    first, last = checkin_date_window(challenge)
    today = challenge_today(challenge)
    if writing:
        last = min(last, today)
    if day < first or day > last:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "That date is outside the challenge",
        )


def save_checkin(
    db: Session,
    *,
    participant: ChallengeParticipant,
    challenge: Challenge,
    user_id: uuid.UUID,
    payload: CheckinCreate,
    team_id: uuid.UUID | None = None,
) -> DailyCheckin:
    """Write the day's note and every goal update as one unit.

    Wrapped in a savepoint so a bad goal id halfway through the list does not
    leave the earlier updates applied; the member sees a clean failure and can
    resubmit the whole day.

    A write before kick-off is a starting-point snapshot: numeric and count
    values become the baseline progress is measured from once the challenge
    begins.
    """
    assert_checkin_date_allowed(challenge, payload.date, writing=True)
    pre_start = is_before_start(challenge, payload.date)
    watch_rank = bool(team_id) and not pre_start
    before_ranks = (
        notifications.leaderboard_snapshot(db, challenge.id) if watch_rank else None
    )
    entries: list[GoalProgressEntry] = []
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
            fields = update.model_dump(exclude={"goal_id", "entry_date"})
            if (
                pre_start
                and fields.get("numeric_delta") is not None
                and fields.get("numeric_value") is None
            ):
                # Starting point is an absolute figure, even if a client sent
                # the daily-check-in delta shape.
                fields["numeric_value"] = fields["numeric_delta"]
                fields["numeric_delta"] = None
            entry = add_progress(
                db,
                goal=goal,
                participant=participant,
                user_id=user_id,
                team_id=team_id,
                payload=ProgressCreate(**fields, entry_date=payload.date),
                announce_rank=False,
            )
            entries.append(entry)
            if (
                pre_start
                and goal.tracking_type == TrackingType.NUMERIC
                and goal.current_value is not None
            ):
                # A number-to-target goal measures improvement from this
                # snapshot. Running totals keep a zero baseline so the
                # starting amount already counts as progress.
                goal.baseline_value = goal.current_value
        db.flush()
    if before_ranks is not None and entries:
        notifications.leaderboard_position_changes(
            db,
            challenge_id=challenge.id,
            before=before_ranks,
            after=notifications.leaderboard_snapshot(db, challenge.id),
            cause_key=str(entries[-1].id),
        )
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
    start = local_date(challenge, challenge.start_at)
    challenge_days = [row.checkin_date for row in rows if row.checkin_date >= start]
    return {
        "start_date": start,
        "end_date": local_date(challenge, challenge.end_at),
        "today": today,
        "pre_start": is_before_start(challenge, today),
        "streak": checkin_streak(challenge_days, today),
        "total_days_logged": len(challenge_days),
        "days": [
            {
                "date": row.checkin_date,
                "note": row.note,
                "updates": counts.get(row.checkin_date, 0),
            }
            for row in rows
        ],
    }
