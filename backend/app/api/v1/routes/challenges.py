"""Challenge creation, the dashboard, the activity feed and final outcomes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.db.session import get_db
from app.dependencies.auth import (
    get_challenge,
    get_current_user,
    get_membership,
    require_admin,
    require_csrf,
    require_team,
)
from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    ChallengeStatus,
    Goal,
    GoalProgressEntry,
    GoalVisibility,
    TeamMember,
    User,
)
from app.schemas.domain import ChallengeCreate, ChallengeUpdate
from app.services import audit
from app.services import challenges as challenge_service
from app.services import checkins as checkin_service
from app.services.clock import utcnow
from app.services.goals import (
    goal_submission_deadline,
    load_goal_tree,
    sync_participant_lock,
)
from app.services.progress import checkin_streak
from app.services.teams import active_members

router = APIRouter(tags=["challenges"])


@router.post("/teams/{team_id}/challenges", dependencies=[Depends(require_csrf)])
def create_challenge(
    team_id: uuid.UUID,
    payload: ChallengeCreate,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    require_team(team_id, admin)
    challenge_service.assert_no_open_challenge(db, team_id)
    challenge = Challenge(team_id=team_id, **payload.model_dump())
    challenge.status = challenge_service.derived_status(challenge)
    db.add(challenge)
    db.flush()

    now = utcnow()
    for member in active_members(db, team_id):
        db.add(
            ChallengeParticipant(
                challenge_id=challenge.id,
                user_id=member.user_id,
                joined_at=now,
                goals_due_at=goal_submission_deadline(challenge, now),
            )
        )
    audit.record(
        db,
        actor_user_id=admin.user_id,
        team_id=team_id,
        action=audit.CHALLENGE_PUBLISHED,
        entity_type="challenge",
        entity_id=challenge.id,
        metadata={
            "start_at": challenge.start_at.isoformat(),
            "end_at": challenge.end_at.isoformat(),
            "forfeit_amount_pence": challenge.forfeit_amount_pence,
        },
    )
    db.commit()
    return challenge_service.summary(challenge)


@router.get("/challenges/current")
def current_challenge(
    challenge: Challenge = Depends(get_challenge), db: Session = Depends(get_db)
) -> dict:
    challenge_service.sync_challenge_status(db, challenge)
    db.commit()
    return challenge_service.summary(challenge)


@router.get("/challenges/{challenge_id}")
def challenge_detail(
    challenge_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    db: Session = Depends(get_db),
) -> dict:
    challenge = challenge_service.require_team_challenge(
        db, challenge_id, member.team_id
    )
    challenge_service.sync_challenge_status(db, challenge)
    db.commit()
    return challenge_service.summary(challenge)


@router.patch("/challenges/{challenge_id}", dependencies=[Depends(require_csrf)])
def update_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeUpdate,
    admin: TeamMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    challenge = challenge_service.require_team_challenge(
        db, challenge_id, admin.team_id
    )
    if challenge.status == ChallengeStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A completed challenge cannot be edited"
        )
    changes = payload.model_dump(exclude_unset=True)
    publish = changes.pop("publish", None)

    start_at = changes.get("start_at", challenge.start_at)
    end_at = changes.get("end_at", challenge.end_at)
    if end_at <= start_at:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "end_at must be after start_at"
        )

    dates_changed = {"start_at", "end_at"}.intersection(changes)
    forfeit_changed = "forfeit_amount_pence" in changes
    previous = {
        "start_at": challenge.start_at.isoformat(),
        "end_at": challenge.end_at.isoformat(),
        "forfeit_amount_pence": challenge.forfeit_amount_pence,
    }
    for key, value in changes.items():
        setattr(challenge, key, value)

    if dates_changed:
        audit.record(
            db,
            actor_user_id=admin.user_id,
            team_id=admin.team_id,
            action=audit.CHALLENGE_DATES_CHANGED,
            entity_type="challenge",
            entity_id=challenge.id,
            metadata={
                "from": {
                    "start_at": previous["start_at"],
                    "end_at": previous["end_at"],
                },
                "to": {
                    "start_at": challenge.start_at.isoformat(),
                    "end_at": challenge.end_at.isoformat(),
                },
            },
        )
    if forfeit_changed:
        audit.record(
            db,
            actor_user_id=admin.user_id,
            team_id=admin.team_id,
            action=audit.CHALLENGE_FORFEIT_CHANGED,
            entity_type="challenge",
            entity_id=challenge.id,
            metadata={
                "from": previous["forfeit_amount_pence"],
                "to": challenge.forfeit_amount_pence,
            },
        )
    if publish and challenge.status == ChallengeStatus.DRAFT:
        challenge.status = challenge_service.derived_status(challenge)
        audit.record(
            db,
            actor_user_id=admin.user_id,
            team_id=admin.team_id,
            action=audit.CHALLENGE_PUBLISHED,
            entity_type="challenge",
            entity_id=challenge.id,
        )
    elif challenge.status != ChallengeStatus.DRAFT:
        challenge_service.sync_challenge_status(db, challenge)
    db.commit()
    return challenge_service.summary(challenge)


@router.get("/challenges/{challenge_id}/dashboard")
def dashboard(
    challenge_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    challenge = challenge_service.require_team_challenge(
        db, challenge_id, member.team_id
    )
    challenge_service.sync_challenge_status(db, challenge)
    participants = challenge_service.active_participants(db, challenge.id)
    today = checkin_service.challenge_today(challenge)

    cards = []
    for participant in participants:
        sync_participant_lock(db, participant)
        goals = load_goal_tree(db, participant.id)
        cards.append(
            serializers.member_card(
                participant=participant,
                goals=goals,
                streak=checkin_streak(
                    checkin_service.checkin_dates(db, participant.id), today
                ),
                viewer_id=user.id,
            )
        )
    db.commit()
    cards.sort(key=lambda card: (-card["overall_progress"], card["display_name"]))
    submitted = [card for card in cards if card["goals_submitted"]]
    return {
        "challenge": challenge_service.summary(challenge),
        "team_progress": round(
            sum(card["overall_progress"] for card in submitted) / len(submitted), 1
        )
        if submitted
        else 0.0,
        "members": cards,
    }


@router.get("/challenges/{challenge_id}/activity")
def activity_feed(
    challenge_id: uuid.UUID,
    limit: int = 100,
    member: TeamMember = Depends(get_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Recent progress entries. Private goals appear only to their owner."""
    challenge_service.require_team_challenge(db, challenge_id, member.team_id)
    rows = db.execute(
        select(GoalProgressEntry, Goal, User)
        .join(Goal, Goal.id == GoalProgressEntry.goal_id)
        .join(
            ChallengeParticipant,
            ChallengeParticipant.id == Goal.challenge_participant_id,
        )
        .join(User, User.id == GoalProgressEntry.user_id)
        .where(
            ChallengeParticipant.challenge_id == challenge_id,
            (Goal.visibility == GoalVisibility.TEAM)
            | (ChallengeParticipant.user_id == user.id),
        )
        .order_by(GoalProgressEntry.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [
        {
            "id": entry.id,
            "user_id": author.id,
            "display_name": author.display_name,
            "avatar_url": author.avatar_url,
            "goal_id": goal.id,
            "goal_title": goal.title,
            "goal_category": goal.category,
            "unit": goal.unit,
            "entry_date": entry.entry_date,
            "numeric_value": entry.numeric_value,
            "numeric_delta": entry.numeric_delta,
            "manual_percentage": entry.manual_percentage,
            "completed": entry.completed,
            "note": entry.note,
            "created_at": entry.created_at,
        }
        for entry, goal, author in rows
    ]


@router.get("/challenges/{challenge_id}/outcomes")
def challenge_outcomes(
    challenge_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    db: Session = Depends(get_db),
) -> dict:
    challenge = challenge_service.require_team_challenge(
        db, challenge_id, member.team_id
    )
    if utcnow() < challenge.end_at:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This challenge has not finished yet"
        )
    challenge_service.evaluate_challenge(db, challenge)
    db.commit()
    return {
        "challenge": challenge_service.summary(challenge),
        "outcomes": challenge_service.outcome_rows(db, challenge.id),
        "forfeits": challenge_service.forfeit_lines(db, challenge.id),
    }


@router.get("/challenges/{challenge_id}/forfeits")
def challenge_forfeits(
    challenge_id: uuid.UUID,
    member: TeamMember = Depends(get_membership),
    db: Session = Depends(get_db),
) -> list[dict]:
    challenge = challenge_service.require_team_challenge(
        db, challenge_id, member.team_id
    )
    return challenge_service.forfeit_lines(db, challenge.id)
