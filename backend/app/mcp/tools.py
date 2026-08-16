"""MCP tool implementations. Call these from tests; the server only wraps them."""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import serializers
from app.mcp.context import require_challenge, require_membership, require_participant
from app.models.domain import ChallengeParticipant, Team, User
from app.schemas.domain import CheckinCreate, CheckinUpdate, GoalCreate, GoalUpdate
from app.services import challenges as challenge_service
from app.services import checkins as checkin_service
from app.services import goals as goal_service
from app.services.clock import is_before_start
from app.services.goals import load_goal_tree, sync_participant_lock
from app.services.progress import checkin_streak
from app.services.teams import active_members, require_member


def get_context(db: Session, user: User) -> dict:
    membership = require_membership(db, user)
    team = db.get(Team, membership.team_id)
    challenge = require_challenge(db, membership)
    challenge_service.sync_challenge_status(db, challenge)
    participant = require_participant(db, challenge, user)
    sync_participant_lock(db, participant)
    goals = load_goal_tree(db, participant.id)
    today = checkin_service.challenge_today(challenge)
    dates = checkin_service.checkin_dates(db, participant.id)
    return {
        "user": {"id": user.id, "display_name": user.display_name},
        "team": {"id": team.id, "name": team.name, "role": membership.role},
        "challenge": challenge_service.summary(challenge),
        "overall_progress": serializers.overall_progress(goals),
        "categories": serializers.category_progress(goals),
        "streak": checkin_streak(dates, today),
        "checked_in_today": today in set(dates),
        "goals_locked": participant.goals_locked_at is not None,
        "goals_committed": len(goals),
        "goals_completed": sum(1 for goal in goals if goal.completed_at),
    }


def get_my_goals(db: Session, user: User) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    participant = require_participant(db, challenge, user)
    locked = sync_participant_lock(db, participant)
    goals = load_goal_tree(db, participant.id)
    return {
        "goals_locked": locked,
        "goals_due_at": participant.goals_due_at,
        "goals_committed_at": participant.goals_committed_at,
        "overall_progress": serializers.overall_progress(goals),
        "categories": serializers.category_progress(goals),
        "goals": [serializers.goal_detail(goal) for goal in goals],
    }


def get_team_standings(db: Session, user: User) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    challenge_service.sync_challenge_status(db, challenge)
    participants = challenge_service.active_participants(db, challenge.id)
    today = checkin_service.challenge_today(challenge)

    cards = []
    for participant in participants:
        sync_participant_lock(db, participant)
        goals = load_goal_tree(db, participant.id)
        dates = set(checkin_service.checkin_dates(db, participant.id))
        card = serializers.member_card(
            participant=participant,
            goals=goals,
            streak=checkin_streak(dates, today),
            viewer_id=user.id,
        )
        card["checked_in_today"] = today in dates
        cards.append(card)
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


def _resolve_member(db: Session, team_id: uuid.UUID, user_id, display_name):
    if user_id:
        return require_member(db, team_id, user_id)
    if not display_name or not display_name.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Provide user_id or display_name",
        )
    needle = display_name.strip().lower()
    members = active_members(db, team_id)
    exact = [row for row in members if row.user.display_name.lower() == needle]
    matches = exact or [
        row for row in members if needle in row.user.display_name.lower()
    ]
    if not matches:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if len(matches) > 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That name matches more than one teammate; pass user_id",
        )
    return matches[0]


def get_member_progress(
    db: Session,
    user: User,
    *,
    user_id: uuid.UUID | None = None,
    display_name: str | None = None,
) -> dict:
    membership = require_membership(db, user)
    target = _resolve_member(db, membership.team_id, user_id, display_name)
    challenge = require_challenge(db, membership)
    participant = db.scalar(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge.id,
            ChallengeParticipant.user_id == target.user_id,
        )
    )
    if not participant:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This member is not in the current challenge"
        )
    sync_participant_lock(db, participant)
    goals = load_goal_tree(db, participant.id)
    viewer_is_owner = target.user_id == user.id
    tree = serializers.goal_tree(goals, viewer_is_owner=viewer_is_owner)
    heatmap = checkin_service.heatmap(db, participant, challenge)
    return {
        "user": serializers.member_public(target),
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


def get_activity(db: Session, user: User, *, limit: int = 50) -> list[dict]:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    challenge_service.require_team_challenge(db, challenge.id, membership.team_id)
    return challenge_service.activity_entries(
        db, challenge_id=challenge.id, viewer_id=user.id, limit=limit
    )


def get_my_checkin(db: Session, user: User, *, day: date | None = None) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    participant = require_participant(db, challenge, user)
    target = day or checkin_service.challenge_today(challenge)
    checkin_service.assert_checkin_date_allowed(challenge, target, writing=False)
    checkin = checkin_service.checkin_for_date(db, participant, target)
    goals = load_goal_tree(db, participant.id)
    return {
        "date": target,
        "note": checkin.note if checkin else None,
        "exists": checkin is not None,
        "pre_start": is_before_start(challenge, target),
        "goals": [serializers.goal_detail(goal) for goal in goals],
    }


def add_goal(db: Session, user: User, *, payload: GoalCreate) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    participant = require_participant(db, challenge, user)
    goal = goal_service.create_goal(db, participant, payload)
    return serializers.goal_detail(goal)


def update_goal(
    db: Session, user: User, *, goal_id: uuid.UUID, payload: GoalUpdate
) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    participant = require_participant(db, challenge, user)
    goal = goal_service.require_goal(db, goal_id, participant)
    goal_service.update_goal(db, participant, goal, payload)
    return serializers.goal_detail(goal)


def log_checkin(
    db: Session,
    user: User,
    *,
    day: date | None = None,
    note: str | None = None,
    updates: list[CheckinUpdate] | None = None,
) -> dict:
    membership = require_membership(db, user)
    challenge = require_challenge(db, membership)
    participant = require_participant(db, challenge, user)
    payload = CheckinCreate(
        date=day or checkin_service.challenge_today(challenge),
        note=note,
        updates=updates or [],
    )
    checkin = checkin_service.save_checkin(
        db,
        participant=participant,
        challenge=challenge,
        user_id=user.id,
        payload=payload,
        team_id=membership.team_id,
    )
    return {
        "id": checkin.id,
        "date": checkin.checkin_date,
        "note": checkin.note,
        "updates": len(payload.updates),
    }
