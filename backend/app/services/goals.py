"""Goal creation, mutation and the commitment lock."""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    Goal,
    GoalProgressEntry,
    TrackingType,
)
from app.schemas.domain import GoalCreate, GoalUpdate, ProgressCreate
from app.services import notifications
from app.services.clock import as_utc, local_date, local_midnight, utcnow
from app.services.progress import goal_is_complete

# Editing any of these after the lock would change what was committed to.
# `visibility` stays mutable (revealing a personal goal changes nothing about
# the commitment) and so does `sort_order` (pure display preference).
IMMUTABLE_GOAL_FIELDS = frozenset(
    {
        "category",
        "title",
        "description",
        "tracking_type",
        "baseline_value",
        "target_value",
        "unit",
        "target_direction",
        "required",
        "parent_goal_id",
    }
)

GOALS_LOCKED = {"code": "GOALS_LOCKED", "message": "Your commitment is locked"}


def locked_conflict() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=GOALS_LOCKED)


def goal_submission_deadline(challenge: Challenge, joined_at: datetime) -> datetime:
    """Local midnight, `goal_submission_days` after the local join date.

    Anchoring to the challenge timezone keeps the deadline consistent with
    check-in dates and streaks, which are all local-date based. A raw
    `joined_at + N days` would fall mid-afternoon and drift from the day
    boundary members actually see.
    """
    due_day = local_date(challenge, joined_at) + timedelta(
        days=challenge.goal_submission_days
    )
    return local_midnight(challenge, due_day)


def participant_is_locked(participant: ChallengeParticipant) -> bool:
    if participant.goals_locked_at is not None:
        return True
    now = utcnow()
    # A challenge that has ended is final even if the member's own submission
    # window never closed — an admin override late in the run can outlive it.
    if now >= as_utc(participant.challenge.end_at):
        return True
    return now >= as_utc(participant.goals_due_at)


def sync_participant_lock(db: Session, participant: ChallengeParticipant) -> bool:
    """Persist the lock once the deadline passes.

    Without this the lock is only ever derived, so `goals_locked_at` stays null
    forever and there is no record of *when* the commitment became final.
    """
    locked = participant_is_locked(participant)
    if locked and participant.goals_locked_at is None:
        participant.goals_locked_at = min(
            as_utc(participant.goals_due_at), as_utc(participant.challenge.end_at)
        )
        for goal in db.scalars(
            select(Goal).where(Goal.challenge_participant_id == participant.id)
        ).all():
            goal.locked_at = goal.locked_at or participant.goals_locked_at
    return locked


def load_goal_tree(db: Session, participant_id: uuid.UUID) -> list[Goal]:
    return list(
        db.scalars(
            select(Goal)
            .options(selectinload(Goal.children))
            .where(
                Goal.challenge_participant_id == participant_id,
                Goal.parent_goal_id.is_(None),
            )
            .order_by(Goal.category, Goal.sort_order, Goal.created_at)
        ).all()
    )


def require_goal(
    db: Session, goal_id: uuid.UUID, participant: ChallengeParticipant
) -> Goal:
    goal = db.get(Goal, goal_id)
    if not goal or goal.challenge_participant_id != participant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    return goal


def create_goal(
    db: Session, participant: ChallengeParticipant, payload: GoalCreate
) -> Goal:
    if sync_participant_lock(db, participant):
        raise locked_conflict()
    parent: Goal | None = None
    if payload.parent_goal_id:
        parent = db.get(Goal, payload.parent_goal_id)
        if not parent or parent.challenge_participant_id != participant.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Parent goal not found")
        if parent.parent_goal_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "One nesting level only"
            )
    data = payload.model_dump()
    if parent is not None:
        # Children render nested under their parent, so a category of their own
        # would put them in a section they are never drawn in.
        data["category"] = parent.category
    if payload.tracking_type == TrackingType.NUMERIC and data["baseline_value"] is None:
        data["baseline_value"] = data["current_value"] or 0
    goal = Goal(challenge_participant_id=participant.id, **data)
    db.add(goal)
    db.flush()
    return goal


def update_goal(
    db: Session,
    participant: ChallengeParticipant,
    goal: Goal,
    payload: GoalUpdate,
) -> Goal:
    changes = payload.model_dump(exclude_unset=True)
    locked = sync_participant_lock(db, participant)
    if locked and IMMUTABLE_GOAL_FIELDS.intersection(changes):
        raise locked_conflict()
    for key, value in changes.items():
        setattr(goal, key, value)
    db.flush()
    return goal


def delete_goal(db: Session, participant: ChallengeParticipant, goal: Goal) -> None:
    if sync_participant_lock(db, participant):
        raise locked_conflict()
    db.delete(goal)


def commit_goals(db: Session, participant: ChallengeParticipant) -> datetime:
    """Lock the commitment early, at the member's own choosing."""
    if sync_participant_lock(db, participant):
        raise locked_conflict()
    if not load_goal_tree(db, participant.id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Add at least one goal before committing",
        )
    now = utcnow()
    participant.goals_committed_at = now
    participant.goals_locked_at = now
    for goal in db.scalars(
        select(Goal).where(Goal.challenge_participant_id == participant.id)
    ).all():
        goal.locked_at = goal.locked_at or now
    return now


def unlock_participant(
    db: Session, participant: ChallengeParticipant, *, hours: int = 24
) -> datetime:
    """Admin override: reopen the commitment for a fixed window."""
    participant.goals_locked_at = None
    participant.goals_committed_at = None
    participant.goals_due_at = utcnow() + timedelta(hours=hours)
    for goal in db.scalars(
        select(Goal).where(Goal.challenge_participant_id == participant.id)
    ).all():
        goal.locked_at = None
    return participant.goals_due_at


def cascade_completion(db: Session, goal: Goal) -> None:
    """Mark a parent complete once all of its required children are.

    Progress is computed from children on read, but `completed_at` is what the
    dashboard counts and what the final outcome is scored against, so it has to
    be written too.
    """
    if not goal.parent_goal_id:
        return
    parent = db.get(Goal, goal.parent_goal_id)
    if not parent:
        return
    required = [child for child in parent.children if child.required]
    if required and all(goal_is_complete(child) for child in required):
        parent.completed_at = parent.completed_at or utcnow()
    else:
        parent.completed_at = None


def add_progress(
    db: Session,
    *,
    goal: Goal,
    participant: ChallengeParticipant,
    user_id: uuid.UUID,
    payload: ProgressCreate,
    team_id: uuid.UUID | None = None,
) -> GoalProgressEntry:
    data = payload.model_dump()
    evidence = data.pop("evidence_url")
    entry = GoalProgressEntry(
        goal_id=goal.id,
        user_id=user_id,
        evidence_url=str(evidence) if evidence else None,
        **data,
    )
    if payload.numeric_value is not None:
        goal.current_value = payload.numeric_value
    elif payload.numeric_delta is not None:
        goal.current_value = (goal.current_value or 0) + payload.numeric_delta
    if payload.manual_percentage is not None:
        goal.manual_progress_percentage = payload.manual_percentage

    was_complete = goal.completed_at is not None
    if payload.completed is False:
        goal.completed_at = None
    elif payload.completed is True or goal_is_complete(goal):
        goal.completed_at = goal.completed_at or utcnow()

    db.add(entry)
    db.flush()
    cascade_completion(db, goal)
    if team_id and goal.completed_at and not was_complete:
        notifications.member_completed_goal(
            db, goal=goal, participant=participant, team_id=team_id
        )
    return entry


def progress_history(
    db: Session, goal_id: uuid.UUID, limit: int = 200
) -> list[GoalProgressEntry]:
    return list(
        db.scalars(
            select(GoalProgressEntry)
            .where(GoalProgressEntry.goal_id == goal_id)
            .order_by(
                GoalProgressEntry.entry_date.desc(),
                GoalProgressEntry.created_at.desc(),
            )
            .limit(limit)
        ).all()
    )
