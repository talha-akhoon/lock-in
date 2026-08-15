"""Invitation codes: create, list, revoke, redeem."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import (
    get_current_user,
    require_admin,
    require_csrf,
    require_team,
)
from app.models.domain import Invitation, TeamMember, User
from app.schemas.domain import InvitationCreate, InvitationRedeem
from app.services import teams as team_service

router = APIRouter(tags=["invitations"])


def _row(invitation: Invitation) -> dict:
    return {
        "id": invitation.id,
        "code_prefix": invitation.code_prefix,
        "expires_at": invitation.expires_at,
        "max_uses": invitation.max_uses,
        "use_count": invitation.use_count,
        "revoked_at": invitation.revoked_at,
        "created_at": invitation.created_at,
    }


@router.post("/teams/{team_id}/invitations", dependencies=[Depends(require_csrf)])
def create_invitation(
    team_id: uuid.UUID,
    payload: InvitationCreate,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    require_team(team_id, admin)
    invitation, code = team_service.create_invitation(
        db,
        team_id=team_id,
        created_by=admin.user_id,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
    )
    db.commit()
    # The plaintext code is shown once and never stored.
    return {**_row(invitation), "code": code}


@router.get("/teams/{team_id}/invitations")
def list_invitations(
    team_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_team(team_id, admin)
    rows = db.scalars(
        select(Invitation)
        .where(Invitation.team_id == team_id)
        .order_by(Invitation.created_at.desc())
    ).all()
    return [_row(row) for row in rows]


@router.delete(
    "/teams/{team_id}/invitations/{invitation_id}",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invitation(
    team_id: uuid.UUID,
    invitation_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    require_team(team_id, admin)
    invitation = db.get(Invitation, invitation_id)
    if not invitation or invitation.team_id != team_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    team_service.revoke_invitation(
        db, invitation=invitation, actor_user_id=admin.user_id
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invitations/redeem", dependencies=[Depends(require_csrf)])
def redeem_invitation(
    payload: InvitationRedeem,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    member = team_service.redeem_invitation(db, code=payload.code, user_id=user.id)
    db.commit()
    return {"team_id": member.team_id, "joined": True}
