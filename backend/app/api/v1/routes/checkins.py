"""Daily check-ins and the caller's own heatmap."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import (
    get_challenge,
    get_current_user,
    get_membership,
    get_participant,
    require_csrf,
)
from app.models.domain import Challenge, ChallengeParticipant, TeamMember, User
from app.schemas.domain import CheckinCreate
from app.services import checkins as checkin_service
from app.services import goals as goal_service
from app.services.clock import local_date

router = APIRouter(tags=["checkins"])


@router.post("/me/checkins", dependencies=[Depends(require_csrf)])
def save_checkin(
    payload: CheckinCreate,
    participant: ChallengeParticipant = Depends(get_participant),
    member: TeamMember = Depends(get_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    checkin = checkin_service.save_checkin(
        db,
        participant=participant,
        user_id=user.id,
        payload=payload,
        team_id=member.team_id,
    )
    db.commit()
    return {
        "id": checkin.id,
        "date": checkin.checkin_date,
        "note": checkin.note,
        "updates": len(payload.updates),
    }


@router.get("/me/checkins")
def my_checkins(
    participant: ChallengeParticipant = Depends(get_participant),
    challenge: Challenge = Depends(get_challenge),
    db: Session = Depends(get_db),
) -> dict:
    return checkin_service.heatmap(db, participant, challenge)


@router.get("/me/checkins/{day}")
def checkin_for_day(
    day: date,
    participant: ChallengeParticipant = Depends(get_participant),
    challenge: Challenge = Depends(get_challenge),
    db: Session = Depends(get_db),
) -> dict:
    """One day's check-in plus the goals to update, for the check-in form."""
    # Bounds in challenge-local dates, matching how check-in dates are stored.
    first = local_date(challenge, challenge.start_at)
    last = local_date(challenge, challenge.end_at)
    if day < first or day > last:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "That date is outside the challenge",
        )
    checkin = checkin_service.checkin_for_date(db, participant, day)
    goals = goal_service.load_goal_tree(db, participant.id)
    return {
        "date": day,
        "note": checkin.note if checkin else None,
        "exists": checkin is not None,
        "goals": [serializers.goal_detail(goal) for goal in goals],
    }
