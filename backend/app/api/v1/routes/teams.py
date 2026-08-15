"""Team creation, the member list and member profiles."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import (
    get_current_user,
    get_membership,
    require_csrf,
    require_team,
)
from app.models.domain import ChallengeParticipant, Team, TeamMember, User
from app.schemas.domain import TeamCreate, TeamRead
from app.services import checkins as checkin_service
from app.services import teams as team_service
from app.services.challenges import latest_challenge
from app.services.goals import load_goal_tree, sync_participant_lock

router = APIRouter(tags=["teams"])


@router.post("/teams", dependencies=[Depends(require_csrf)], response_model=TeamRead)
def create_team(
    payload: TeamCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Team:
    team = team_service.create_team(db, name=payload.name, user_id=user.id)
    db.commit()
    return team


@router.get("/teams/current")
def current_team(
    member: TeamMember = Depends(get_membership), db: Session = Depends(get_db)
) -> dict:
    team = db.get(Team, member.team_id)
    return {
        "id": team.id,
        "name": team.name,
        "role": member.role,
        "member_count": len(team_service.active_members(db, team.id)),
    }


@router.get("/teams/{team_id}/members")
def team_members(
    team_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_team(team_id, member)
    return [
        serializers.member_row(row) for row in team_service.active_members(db, team_id)
    ]


@router.get("/teams/{team_id}/members/{member_id}")
def member_profile(
    team_id: uuid.UUID,
    member_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Profile, category breakdown, goals and heatmap for one member.

    Goals are redacted unless the viewer is the member themselves.
    """
    require_team(team_id, member)
    target = team_service.require_member(db, team_id, member_id)
    challenge = latest_challenge(db, team_id)
    if not challenge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This team has no challenge yet")
    participant = db.scalar(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge.id,
            ChallengeParticipant.user_id == member_id,
        )
    )
    if not participant:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This member is not in the current challenge"
        )
    sync_participant_lock(db, participant)
    db.commit()

    goals = load_goal_tree(db, participant.id)
    viewer_is_owner = member_id == user.id
    tree = serializers.goal_tree(goals, viewer_is_owner=viewer_is_owner)
    heatmap = checkin_service.heatmap(db, participant, challenge)
    return {
        "user": serializers.member_row(target),
        "is_self": viewer_is_owner,
        "challenge_id": challenge.id,
        "participant_status": participant.status,
        "goals_locked": participant.goals_locked_at is not None,
        "goals_due_at": participant.goals_due_at,
        "goals_committed_at": participant.goals_committed_at,
        "overall_progress": serializers.overall_progress(goals),
        "categories": serializers.category_progress(goals),
        "goals_committed": len(goals),
        "goals_completed": sum(1 for goal in goals if goal.completed_at),
        "private_committed": tree["private_committed"],
        "private_completed": tree["private_completed"],
        "goals": tree["goals"],
        "streak": heatmap["streak"],
        "heatmap": heatmap,
    }
