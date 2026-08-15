"""The notification feed.

Notifications are generated on read rather than by a background scheduler, so
the deployment needs no always-on worker.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_membership, require_csrf
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
