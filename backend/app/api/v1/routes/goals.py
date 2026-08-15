"""The caller's own goals: the wizard, the commitment, and progress entries."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import (
    get_current_user,
    get_membership,
    get_participant,
    require_csrf,
)
from app.models.domain import ChallengeParticipant, TeamMember, User
from app.schemas.domain import GoalCreate, GoalUpdate, ProgressCreate
from app.services import goals as goal_service

router = APIRouter(tags=["goals"])


@router.get("/me/goals")
def my_goals(
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    locked = goal_service.sync_participant_lock(db, participant)
    db.commit()
    goals = goal_service.load_goal_tree(db, participant.id)
    return {
        "goals_locked": locked,
        "goals_due_at": participant.goals_due_at,
        "goals_committed_at": participant.goals_committed_at,
        "overall_progress": serializers.overall_progress(goals),
        "categories": serializers.category_progress(goals),
        "goals": [serializers.goal_detail(goal) for goal in goals],
    }


@router.post(
    "/me/goals",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    payload: GoalCreate,
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    goal = goal_service.create_goal(db, participant, payload)
    db.commit()
    return serializers.goal_detail(goal)


@router.post("/me/goals/commit", dependencies=[Depends(require_csrf)])
def commit_goals(
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    locked_at = goal_service.commit_goals(db, participant)
    db.commit()
    return {"locked": True, "locked_at": locked_at}


@router.get("/goals/{goal_id}")
def goal_detail(
    goal_id: uuid.UUID,
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    goal = goal_service.require_goal(db, goal_id, participant)
    return serializers.goal_detail(goal)


@router.patch("/goals/{goal_id}", dependencies=[Depends(require_csrf)])
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    goal = goal_service.require_goal(db, goal_id, participant)
    goal_service.update_goal(db, participant, goal, payload)
    db.commit()
    return serializers.goal_detail(goal)


@router.delete(
    "/goals/{goal_id}",
    dependencies=[Depends(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_goal(
    goal_id: uuid.UUID,
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> Response:
    goal = goal_service.require_goal(db, goal_id, participant)
    goal_service.delete_goal(db, participant, goal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/goals/{goal_id}/progress")
def goal_progress_history(
    goal_id: uuid.UUID,
    participant: ChallengeParticipant = Depends(get_participant),
    db: Session = Depends(get_db),
) -> dict:
    goal = goal_service.require_goal(db, goal_id, participant)
    entries = goal_service.progress_history(db, goal.id)
    return {
        "goal": serializers.goal_detail(goal),
        "entries": [serializers.progress_entry(entry) for entry in entries],
    }


@router.post("/goals/{goal_id}/progress", dependencies=[Depends(require_csrf)])
def add_goal_progress(
    goal_id: uuid.UUID,
    payload: ProgressCreate,
    participant: ChallengeParticipant = Depends(get_participant),
    member: TeamMember = Depends(get_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    goal = goal_service.require_goal(db, goal_id, participant)
    entry = goal_service.add_progress(
        db,
        goal=goal,
        participant=participant,
        user_id=user.id,
        payload=payload,
        team_id=member.team_id,
    )
    db.commit()
    return {"id": entry.id, "goal": serializers.goal_detail(goal)}
