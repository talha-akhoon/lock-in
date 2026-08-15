"""Team membership, invitations and admin member management."""

import secrets
import uuid
from datetime import datetime

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    Invitation,
    MembershipStatus,
    ParticipantStatus,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from app.services import audit, notifications
from app.services.challenges import open_challenge
from app.services.clock import utcnow
from app.services.goals import goal_submission_deadline

# No I, O, 0 or 1: invitation codes get read aloud and typed by hand.
INVITATION_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def assert_no_active_team(db: Session, user_id: uuid.UUID) -> None:
    """Mirror of the uq_team_members_one_active_team index as a clean 409."""
    existing = db.scalar(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.status == MembershipStatus.ACTIVE,
        )
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "ALREADY_IN_TEAM",
                "message": "You already belong to an active team",
            },
        )


def create_team(db: Session, *, name: str, user_id: uuid.UUID) -> Team:
    assert_no_active_team(db, user_id)
    team = Team(name=name, created_by=user_id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user_id, role=TeamRole.ADMIN))
    db.flush()
    return team


def active_members(db: Session, team_id: uuid.UUID) -> list[TeamMember]:
    return list(
        db.scalars(
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(
                TeamMember.team_id == team_id,
                TeamMember.status == MembershipStatus.ACTIVE,
            )
            .order_by(TeamMember.joined_at)
        ).all()
    )


def require_member(db: Session, team_id: uuid.UUID, user_id: uuid.UUID) -> TeamMember:
    member = db.scalar(
        select(TeamMember)
        .options(selectinload(TeamMember.user))
        .where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == MembershipStatus.ACTIVE,
        )
    )
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return member


def create_invitation(
    db: Session,
    *,
    team_id: uuid.UUID,
    created_by: uuid.UUID,
    expires_at: datetime | None,
    max_uses: int | None,
) -> tuple[Invitation, str]:
    """Return the invitation and its plaintext code.

    Only the hash is stored, so this is the one and only chance to show the
    code; `code_prefix` exists purely to narrow the bcrypt comparison at redeem
    time.
    """
    raw = "".join(secrets.choice(INVITATION_ALPHABET) for _ in range(8))
    code = f"{raw[:4]}-{raw[4:]}"
    invitation = Invitation(
        team_id=team_id,
        created_by=created_by,
        code_hash=bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode(),
        code_prefix=raw[:4],
        expires_at=expires_at,
        max_uses=max_uses,
    )
    db.add(invitation)
    db.flush()
    audit.record(
        db,
        actor_user_id=created_by,
        team_id=team_id,
        action=audit.INVITATION_CREATED,
        entity_type="invitation",
        entity_id=invitation.id,
        metadata={"max_uses": max_uses},
    )
    return invitation, code


def revoke_invitation(
    db: Session, *, invitation: Invitation, actor_user_id: uuid.UUID
) -> None:
    invitation.revoked_at = utcnow()
    audit.record(
        db,
        actor_user_id=actor_user_id,
        team_id=invitation.team_id,
        action=audit.INVITATION_REVOKED,
        entity_type="invitation",
        entity_id=invitation.id,
    )


def redeem_invitation(db: Session, *, code: str, user_id: uuid.UUID) -> TeamMember:
    now = utcnow()
    candidates = db.scalars(
        select(Invitation).where(Invitation.code_prefix == code[:4])
    ).all()
    invitation = next(
        (
            item
            for item in candidates
            if bcrypt.checkpw(code.encode(), item.code_hash.encode())
        ),
        None,
    )
    if not invitation or invitation.revoked_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid invitation code")
    if invitation.expires_at and invitation.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation has expired")
    if invitation.max_uses is not None and invitation.use_count >= invitation.max_uses:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invitation has already been used"
        )

    existing = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == invitation.team_id,
            TeamMember.user_id == user_id,
        )
    )
    if existing:
        if existing.status == MembershipStatus.REMOVED:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Your membership of this team was removed"
            )
        return existing

    # Without this a user could hold two active memberships, and get_membership
    # would then pick one arbitrarily.
    assert_no_active_team(db, user_id)

    member = TeamMember(team_id=invitation.team_id, user_id=user_id)
    db.add(member)
    invitation.use_count += 1
    db.flush()

    challenge = open_challenge(db, invitation.team_id)
    if challenge:
        db.add(
            ChallengeParticipant(
                challenge_id=challenge.id,
                user_id=user_id,
                joined_at=now,
                goals_due_at=goal_submission_deadline(challenge, now),
            )
        )
    user = db.get(User, user_id)
    notifications.member_joined(
        db,
        team_id=invitation.team_id,
        challenge_id=challenge.id if challenge else None,
        user_id=user_id,
        display_name=user.display_name if user else "A new member",
    )
    db.flush()
    return member


def remove_member(db: Session, *, member: TeamMember, actor_user_id: uuid.UUID) -> None:
    if member.user_id == actor_user_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "You cannot remove yourself"
        )
    if member.role == TeamRole.ADMIN and count_admins(db, member.team_id) <= 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The team must keep at least one admin",
        )
    member.status = MembershipStatus.REMOVED
    for participant in db.scalars(
        select(ChallengeParticipant)
        .join(Challenge, Challenge.id == ChallengeParticipant.challenge_id)
        .where(
            ChallengeParticipant.user_id == member.user_id,
            Challenge.team_id == member.team_id,
        )
    ).all():
        participant.status = ParticipantStatus.REMOVED
    audit.record(
        db,
        actor_user_id=actor_user_id,
        team_id=member.team_id,
        action=audit.MEMBER_REMOVED,
        entity_type="team_member",
        entity_id=member.id,
        metadata={"user_id": str(member.user_id)},
    )


def count_admins(db: Session, team_id: uuid.UUID) -> int:
    return len(
        db.scalars(
            select(TeamMember.id).where(
                TeamMember.team_id == team_id,
                TeamMember.status == MembershipStatus.ACTIVE,
                TeamMember.role == TeamRole.ADMIN,
            )
        ).all()
    )


def change_role(
    db: Session, *, member: TeamMember, role: TeamRole, actor_user_id: uuid.UUID
) -> TeamMember:
    if (
        member.role == TeamRole.ADMIN
        and role == TeamRole.MEMBER
        and count_admins(db, member.team_id) <= 1
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The team must keep at least one admin",
        )
    previous = member.role
    member.role = role
    audit.record(
        db,
        actor_user_id=actor_user_id,
        team_id=member.team_id,
        action=audit.MEMBER_ROLE_CHANGED,
        entity_type="team_member",
        entity_id=member.id,
        metadata={
            "user_id": str(member.user_id),
            "from": previous.value,
            "to": role.value,
        },
    )
    return member
