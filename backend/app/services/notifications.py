"""Notification generation.

Notifications are derived lazily when a user reads their feed rather than by a
scheduler, so the free-tier deployment needs no always-on worker. Every insert
is keyed on (user, type, dedupe_key) so repeated reads cannot duplicate a
notification.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    Goal,
    GoalVisibility,
    MembershipStatus,
    Notification,
    NotificationType,
    TeamMember,
)
from app.services.clock import (
    as_utc,
    challenge_days_remaining,
    utcnow,
)

MILESTONE_DAYS = (100, 30, 7)
_PUSH_KINDS = frozenset(
    {
        NotificationType.MEMBER_COMPLETED_GOAL,
        NotificationType.MEMBER_CHECKED_IN,
    }
)


def notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    challenge_id: uuid.UUID | None,
    kind: NotificationType,
    dedupe_key: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
) -> Notification | None:
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == kind,
            Notification.dedupe_key == dedupe_key,
        )
    )
    if existing:
        return None
    row = Notification(
        user_id=user_id,
        challenge_id=challenge_id,
        type=kind,
        dedupe_key=dedupe_key,
        title=title,
        body=body,
        link_path=link_path,
    )
    db.add(row)
    db.flush()
    if kind in _PUSH_KINDS:
        from app.services import push

        push.deliver(db, row)
    return row


def notify_team(
    db: Session,
    *,
    team_id: uuid.UUID,
    challenge_id: uuid.UUID | None,
    kind: NotificationType,
    dedupe_key: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
    exclude_user_id: uuid.UUID | None = None,
) -> None:
    recipients = db.scalars(
        select(TeamMember.user_id).where(
            TeamMember.team_id == team_id,
            TeamMember.status == MembershipStatus.ACTIVE,
        )
    ).all()
    for user_id in recipients:
        if user_id == exclude_user_id:
            continue
        notify(
            db,
            user_id=user_id,
            challenge_id=challenge_id,
            kind=kind,
            dedupe_key=dedupe_key,
            title=title,
            body=body,
            link_path=link_path,
        )


def goal_deadline_notifications(
    db: Session, participant: ChallengeParticipant, locked: bool
) -> None:
    challenge_id = participant.challenge_id
    if locked:
        notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge_id,
            kind=NotificationType.GOALS_LOCKED,
            dedupe_key=f"locked:{challenge_id}",
            title="Your goals are locked",
            body="Your commitment is now fixed for the rest of the challenge.",
            link_path="/goals",
        )
        return

    remaining = as_utc(participant.goals_due_at) - utcnow()
    if remaining <= timedelta(days=1):
        notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge_id,
            kind=NotificationType.GOALS_LOCK_TOMORROW,
            dedupe_key=f"tomorrow:{challenge_id}",
            title="Your goals lock tomorrow",
            body="Last chance to change what you are committing to.",
            link_path="/goals",
        )
    elif remaining <= timedelta(days=3):
        notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge_id,
            kind=NotificationType.GOALS_DUE_SOON,
            dedupe_key=f"three-days:{challenge_id}",
            title="3 days left to submit your goals",
            link_path="/goals",
        )


def challenge_notifications(
    db: Session, participant: ChallengeParticipant, challenge: Challenge
) -> None:
    now = utcnow()
    if now >= as_utc(challenge.end_at):
        notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge.id,
            kind=NotificationType.CHALLENGE_COMPLETE,
            dedupe_key=f"complete:{challenge.id}",
            title=f"{challenge.name} has finished",
            body="See the final results and any forfeits owed.",
            link_path="/dashboard",
        )
        return
    if now < as_utc(challenge.start_at):
        return

    remaining = challenge_days_remaining(challenge, now)
    # Ascending, so the *nearest* milestone wins: at 5 days left the member
    # should be told "7 days left", not "100 days left".
    for threshold in sorted(MILESTONE_DAYS):
        if remaining <= threshold:
            notify(
                db,
                user_id=participant.user_id,
                challenge_id=challenge.id,
                kind=NotificationType.CHALLENGE_MILESTONE,
                dedupe_key=f"milestone:{challenge.id}:{threshold}",
                title=f"{threshold} days left",
                body=f"{remaining} days remain in {challenge.name}.",
                link_path="/dashboard",
            )
            break


def member_completed_goal(
    db: Session, *, goal: Goal, participant: ChallengeParticipant, team_id: uuid.UUID
) -> None:
    """Tell the team when someone finishes a goal, but never leak a private one."""
    if goal.visibility == GoalVisibility.PRIVATE:
        return
    notify_team(
        db,
        team_id=team_id,
        challenge_id=participant.challenge_id,
        kind=NotificationType.MEMBER_COMPLETED_GOAL,
        dedupe_key=f"goal-complete:{goal.id}",
        title=f"{participant.user.display_name} completed a goal",
        body=goal.title,
        link_path=f"/team/members/{participant.user_id}",
        exclude_user_id=participant.user_id,
    )


def member_checked_in(
    db: Session,
    *,
    participant: ChallengeParticipant,
    team_id: uuid.UUID,
    day: date,
    updates: int,
) -> None:
    """Tell the team someone logged a day, without leaking what they logged."""
    name = participant.user.display_name
    if updates:
        noun = "goal" if updates == 1 else "goals"
        body = f"Logged progress on {updates} {noun}"
    else:
        body = "Left a check-in note"
    notify_team(
        db,
        team_id=team_id,
        challenge_id=participant.challenge_id,
        kind=NotificationType.MEMBER_CHECKED_IN,
        dedupe_key=f"checkin:{participant.id}:{day.isoformat()}",
        title=f"{name} checked in",
        body=body,
        link_path=f"/team/members/{participant.user_id}",
        exclude_user_id=participant.user_id,
    )


def member_joined(
    db: Session,
    *,
    team_id: uuid.UUID,
    challenge_id: uuid.UUID | None,
    user_id: uuid.UUID,
    display_name: str,
) -> None:
    notify_team(
        db,
        team_id=team_id,
        challenge_id=challenge_id,
        kind=NotificationType.MEMBER_JOINED,
        dedupe_key=f"joined:{team_id}:{user_id}",
        title=f"{display_name} joined the team",
        link_path="/team",
        exclude_user_id=user_id,
    )


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return len(
        db.scalars(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        ).all()
    )


def for_user(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )
