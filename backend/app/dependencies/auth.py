import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    MembershipStatus,
    TeamMember,
    TeamRole,
    User,
)
from app.services.challenges import latest_challenge

SESSION_COOKIE = "lockin_session"
CSRF_COOKIE = "lockin_csrf"
SESSION_DAYS = 30


def create_session_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=SESSION_DAYS)},
        settings.secret_key,
        algorithm="HS256",
    )


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def get_current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Double-submit cookie check on every state-changing request.

    The session cookie is SameSite=Lax, which already blocks cross-site POSTs in
    modern browsers; this is the second layer that does not depend on that.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if (
        not csrf_cookie
        or not csrf_header
        or not secrets.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token mismatch")


def get_membership(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TeamMember:
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


def require_admin(membership: TeamMember = Depends(get_membership)) -> TeamMember:
    if membership.role != TeamRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return membership


def require_team(team_id: uuid.UUID, membership: TeamMember) -> TeamMember:
    """Reject a team id in the URL that is not the caller's own team."""
    if membership.team_id != team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this team")
    return membership


def get_challenge(
    membership: TeamMember = Depends(get_membership), db: Session = Depends(get_db)
) -> Challenge:
    challenge = latest_challenge(db, membership.team_id)
    if not challenge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This team has no challenge yet")
    return challenge


def get_participant(
    challenge: Challenge = Depends(get_challenge),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
