"""The notification feed plus mute preferences.

Deadline rows are still generated lazily when the feed is read. Check-in, streak,
quiet and pace nudges (and a second pass of the deadline rows for lock-screen
push) are inserted by the hourly dispatch job.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import (
    get_current_user,
    get_membership,
    get_session_user,
    require_csrf,
)
from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    Notification,
    TeamMember,
    User,
)
from app.services import notifications as notification_service
from app.services.challenges import latest_challenge, sync_challenge_status
from app.services.clock import utcnow
from app.services.goals import sync_participant_lock

router = APIRouter(tags=["notifications"])


class NotificationPreferencesUpdate(BaseModel):
    muted_types: list[str] = Field(max_length=32)


def _refresh(db: Session, user: User, membership: TeamMember | None) -> None:
    if not membership:
        return
    challenge: Challenge | None = latest_challenge(db, membership.team_id)
    if not challenge:
        return
    sync_challenge_status(db, challenge)
    participant = db.scalar(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge.id,
            ChallengeParticipant.user_id == user.id,
        )
    )
    if not participant:
        return
    locked = sync_participant_lock(db, participant)
    notification_service.goal_deadline_notifications(db, participant, locked)
    notification_service.challenge_notifications(db, participant, challenge)


@router.get("/me/notifications")
def list_notifications(
    user: User = Depends(get_current_user),
    membership: TeamMember = Depends(get_membership),
    db: Session = Depends(get_db),
) -> dict:
    _refresh(db, user, membership)
    db.commit()
    rows = notification_service.for_user(db, user.id)
    return {
        "unread_count": sum(1 for row in rows if row.read_at is None),
        "notifications": [serializers.notification_row(row) for row in rows],
    }


@router.post(
    "/me/notifications/{notification_id}/read", dependencies=[Depends(require_csrf)]
)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Notification, notification_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    row.read_at = row.read_at or utcnow()
    db.commit()
    return {"id": row.id, "read_at": row.read_at}


@router.post("/me/notifications/read-all", dependencies=[Depends(require_csrf)])
def mark_all_read(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    now = utcnow()
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ).all()
    for row in rows:
        row.read_at = now
    db.commit()
    return {"marked": len(rows)}


@router.get("/me/notification-preferences")
def notification_preferences(
    user: User = Depends(get_session_user),
) -> dict:
    return notification_service.preference_payload(user)


@router.put(
    "/me/notification-preferences",
    dependencies=[Depends(require_csrf)],
)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    user: User = Depends(get_session_user),
    db: Session = Depends(get_db),
) -> dict:
    notification_service.set_muted_types(user, payload.muted_types)
    db.commit()
    db.refresh(user)
    return notification_service.preference_payload(user)
