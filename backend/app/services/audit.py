"""Append-only log of admin actions.

With real money riding on the outcome, every privileged action a member cannot
undo themselves needs a trail: who did it, to what, and when.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import AuditLog, User

INVITATION_CREATED = "INVITATION_CREATED"
INVITATION_REVOKED = "INVITATION_REVOKED"
MEMBER_REMOVED = "MEMBER_REMOVED"
MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
CHALLENGE_PUBLISHED = "CHALLENGE_PUBLISHED"
CHALLENGE_DATES_CHANGED = "CHALLENGE_DATES_CHANGED"
CHALLENGE_FORFEIT_CHANGED = "CHALLENGE_FORFEIT_CHANGED"
GOAL_UNLOCKED = "GOAL_UNLOCKED"
GOAL_EDITED_UNDER_OVERRIDE = "GOAL_EDITED_UNDER_OVERRIDE"

ACTIONS = (
    INVITATION_CREATED,
    INVITATION_REVOKED,
    MEMBER_REMOVED,
    MEMBER_ROLE_CHANGED,
    CHALLENGE_PUBLISHED,
    CHALLENGE_DATES_CHANGED,
    CHALLENGE_FORFEIT_CHANGED,
    GOAL_UNLOCKED,
    GOAL_EDITED_UNDER_OVERRIDE,
)


def record(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    team_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        # The acting user is already in the identity map, so this resolves the
        # relationship without a query and keeps the entry serializable.
        actor=db.get(User, actor_user_id),
        team_id=team_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata,
    )
    db.add(entry)
    return entry


def recent(db: Session, team_id: uuid.UUID, limit: int = 200) -> list[AuditLog]:
    """Newest first, with the actor loaded so the log still names them once they
    have left the team."""
    return list(
        db.scalars(
            select(AuditLog)
            .options(selectinload(AuditLog.actor))
            .where(AuditLog.team_id == team_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        ).all()
    )
