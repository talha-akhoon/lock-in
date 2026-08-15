"""Request-scoped caller identity for MCP tool handlers."""

from contextvars import ContextVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    MembershipStatus,
    TeamMember,
    User,
)
from app.services.challenges import latest_challenge

current_user: ContextVar[User] = ContextVar("mcp_user")
current_db: ContextVar[Session] = ContextVar("mcp_db")


def require_membership(db: Session, user: User) -> TeamMember:
    membership = db.scalar(
        select(TeamMember)
        .where(
            TeamMember.user_id == user.id,
            TeamMember.status == MembershipStatus.ACTIVE,
        )
        .order_by(TeamMember.joined_at)
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active team membership")
    return membership


def require_challenge(db: Session, membership: TeamMember) -> Challenge:
    challenge = latest_challenge(db, membership.team_id)
    if not challenge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This team has no challenge yet")
    return challenge


def require_participant(
    db: Session, challenge: Challenge, user: User
) -> ChallengeParticipant:
    participant = db.scalar(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge.id,
            ChallengeParticipant.user_id == user.id,
        )
    )
    if not participant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enrolled in this challenge")
    return participant
