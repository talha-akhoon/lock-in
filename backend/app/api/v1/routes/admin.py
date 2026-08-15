"""Admin-only operations: member management, goal unlock, audit log."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import require_admin, require_csrf, require_team
from app.models.domain import Challenge, ChallengeParticipant, Goal, TeamMember
from app.schemas.domain import MemberRoleUpdate
from app.services import audit
from app.services import goals as goal_service
from app.services import teams as team_service

router = APIRouter(tags=["admin"])


@router.delete(
    "/teams/{team_id}/members/{user_id}",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    require_team(team_id, admin)
    member = team_service.require_member(db, team_id, user_id)
    team_service.remove_member(db, member=member, actor_user_id=admin.user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/teams/{team_id}/members/{user_id}", dependencies=[Depends(require_csrf)]
)
def change_member_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    require_team(team_id, admin)
    member = team_service.require_member(db, team_id, user_id)
    team_service.change_role(
        db, member=member, role=payload.role, actor_user_id=admin.user_id
    )
    db.commit()
    return serializers.member_row(member)


@router.post("/goals/{goal_id}/unlock", dependencies=[Depends(require_csrf)])
def unlock_goal(
    goal_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Reopen a member's whole commitment for 24 hours.

    Scoped to the participant rather than the single goal: a commitment is
    reviewed as a set, and unlocking one goal in isolation would let someone
    swap a hard goal for an easy one while the rest stayed frozen.
    """
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    participant = db.get(ChallengeParticipant, goal.challenge_participant_id)
    challenge = db.get(Challenge, participant.challenge_id)
    if challenge.team_id != admin.team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this team")
    unlocked_until = goal_service.unlock_participant(db, participant)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        team_id=admin.team_id,
        action=audit.GOAL_UNLOCKED,
        entity_type="challenge_participant",
        entity_id=participant.id,
        metadata={
            "goal_id": str(goal.id),
            "user_id": str(participant.user_id),
            "override_expires_at": unlocked_until.isoformat(),
        },
    )
    db.commit()
    return {"unlocked_until": unlocked_until, "user_id": participant.user_id}


@router.post(
    "/teams/{team_id}/participants/{user_id}/goals/{goal_id}/override",
    dependencies=[Depends(require_csrf)],
)
def record_override_edit(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Log that a locked goal was edited under an admin override.

    The edit itself goes through PATCH /goals/{id} as the member; this records
    who authorised it, which is the part an audit needs.
    """
    require_team(team_id, admin)
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    entry = audit.record(
        db,
        actor_user_id=admin.user_id,
        team_id=team_id,
        action=audit.GOAL_EDITED_UNDER_OVERRIDE,
        entity_type="goal",
        entity_id=goal.id,
        metadata={"user_id": str(user_id), "title": goal.title},
    )
    db.commit()
    return serializers.audit_row(entry)


@router.get("/teams/{team_id}/audit-logs")
def audit_logs(
    team_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_team(team_id, admin)
    return [serializers.audit_row(row) for row in audit.recent(db, team_id)]


@router.get("/teams/{team_id}/participants")
def team_participants(
    team_id: uuid.UUID,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Commitment state per member, so an admin can see who has not submitted."""
    require_team(team_id, admin)
    rows = db.execute(
        select(ChallengeParticipant, Challenge)
        .join(Challenge, Challenge.id == ChallengeParticipant.challenge_id)
        .where(Challenge.team_id == team_id)
        .order_by(Challenge.start_at.desc())
    ).all()
    payload = []
    for participant, challenge in rows:
        goals = goal_service.load_goal_tree(db, participant.id)
        payload.append(
            {
                "participant_id": participant.id,
                "challenge_id": challenge.id,
                "challenge_name": challenge.name,
                "user_id": participant.user_id,
                "display_name": participant.user.display_name,
                "status": participant.status,
                "goals_due_at": participant.goals_due_at,
                "goals_locked_at": participant.goals_locked_at,
                "goals_committed_at": participant.goals_committed_at,
                "goals_committed": len(goals),
                "first_goal_id": goals[0].id if goals else None,
            }
        )
    return payload
