"""Google Sign-In, session cookies and the bootstrap `/auth/me` call."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.session import get_db
from app.dependencies.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SESSION_DAYS,
    create_session_token,
    get_current_user,
    new_csrf_token,
    require_csrf,
)
from app.models.domain import (
    ChallengeParticipant,
    MembershipStatus,
    TeamMember,
    User,
)
from app.schemas.domain import AuthMe, GoogleAuthRequest, TeamRead, UserRead
from app.services.challenges import latest_challenge, sync_challenge_status
from app.services.goals import participant_is_locked, sync_participant_lock

router = APIRouter(tags=["auth"])


def _cookie_options() -> dict:
    settings = get_settings()
    return {
        "secure": settings.secure_cookies,
        "samesite": "lax",
        "path": "/",
    }


@router.post("/auth/google")
def google_auth(
    payload: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)
) -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google authentication is not configured",
        )
    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid Google token"
        ) from exc
    if not claims.get("email_verified"):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Google email is not verified"
        )

    user = db.scalar(select(User).where(User.google_sub == claims["sub"]))
    if not user:
        user = User(
            google_sub=claims["sub"],
            email=claims["email"],
            display_name=claims.get("name") or claims["email"].split("@")[0],
            avatar_url=claims.get("picture"),
        )
        db.add(user)
    else:
        user.email = claims["email"]
        user.display_name = claims.get("name") or user.display_name
        user.avatar_url = claims.get("picture")
    db.commit()

    options = _cookie_options()
    max_age = 60 * 60 * 24 * SESSION_DAYS
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        httponly=True,
        max_age=max_age,
        **options,
    )
    # Readable by JavaScript on purpose: the SPA echoes it back in X-CSRF-Token.
    response.set_cookie(
        CSRF_COOKIE, new_csrf_token(), httponly=False, max_age=max_age, **options
    )
    return {"user": UserRead.model_validate(user)}


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response) -> dict[str, bool]:
    # secure/samesite must match how the cookies were set or some browsers
    # decline to clear them.
    options = _cookie_options()
    response.delete_cookie(SESSION_COOKIE, httponly=True, **options)
    response.delete_cookie(CSRF_COOKIE, httponly=False, **options)
    return {"ok": True}


@router.get("/auth/me", response_model=AuthMe)
def auth_me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AuthMe:
    member = db.scalar(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(
            TeamMember.user_id == user.id,
            TeamMember.status == MembershipStatus.ACTIVE,
        )
        .order_by(TeamMember.joined_at)
    )
    challenge = latest_challenge(db, member.team_id) if member else None
    participant = None
    if challenge:
        sync_challenge_status(db, challenge)
        participant = db.scalar(
            select(ChallengeParticipant).where(
                ChallengeParticipant.challenge_id == challenge.id,
                ChallengeParticipant.user_id == user.id,
            )
        )
        if participant:
            sync_participant_lock(db, participant)
    db.commit()
    return AuthMe(
        user=UserRead.model_validate(user),
        team=TeamRead.model_validate(member.team) if member else None,
        role=member.role.value if member else None,
        challenge_id=challenge.id if challenge else None,
        challenge_status=challenge.status.value if challenge else None,
        participant_id=participant.id if participant else None,
        goals_due_at=participant.goals_due_at if participant else None,
        goals_locked=participant_is_locked(participant) if participant else False,
        goals_committed_at=participant.goals_committed_at if participant else None,
    )
