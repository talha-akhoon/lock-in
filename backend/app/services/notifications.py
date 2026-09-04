"""Pressure nudges plus muteable Web Push on deadlines.

A GitHub Action each hour (and any caller with the dispatch token) runs `run()`
so people who have not opened the app still get lock-screen pings. Inserts are
still keyed on (user, type, dedupe_key).
"""

import html
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    Goal,
    GoalProgressEntry,
    GoalVisibility,
    MembershipStatus,
    Notification,
    NotificationType,
    TeamMember,
    User,
)
from app.services.clock import (
    as_utc,
    challenge_days_remaining,
    utcnow,
)

MILESTONE_DAYS = (100, 30, 7)
_PUSH_KINDS = frozenset(NotificationType) - {NotificationType.MEMBER_JOINED}

PREFERENCE_TYPES: tuple[dict[str, str], ...] = (
    {
        "type": NotificationType.MEMBER_CHECKED_IN.value,
        "group": "Team",
        "label": "Teammate logged progress",
        "description": "Every save — how much they logged, not the target.",
    },
    {
        "type": NotificationType.MEMBER_COMPLETED_GOAL.value,
        "group": "Team",
        "label": "Teammate finished a goal",
        "description": "A team-visible goal hit 100%.",
    },
    {
        "type": NotificationType.MEMBER_QUIET.value,
        "group": "Team",
        "label": "Teammate gone quiet",
        "description": "No check-in for three days.",
    },
    {
        "type": NotificationType.MEMBER_JOINED.value,
        "group": "Team",
        "label": "Someone joined the team",
        "description": "In the bell only, not on the lock screen.",
    },
    {
        "type": NotificationType.CHECKIN_DUE.value,
        "group": "You",
        "label": "You have not checked in today",
        "description": "Evening ping in the challenge timezone.",
    },
    {
        "type": NotificationType.STREAK_AT_RISK.value,
        "group": "You",
        "label": "Streak about to die",
        "description": "You logged yesterday. Today is still empty.",
    },
    {
        "type": NotificationType.PACE_BEHIND.value,
        "group": "You",
        "label": "Behind on a required goal",
        "description": "Weekly, if a required goal is off the pace to the forfeit line.",
    },
    {
        "type": NotificationType.LEADERBOARD_POSITION.value,
        "group": "You",
        "label": "Your leaderboard position",
        "description": "You moved up or down on the team board.",
    },
    {
        "type": NotificationType.GOALS_DUE_SOON.value,
        "group": "Deadlines",
        "label": "3 days left to submit goals",
        "description": "Before your commitment locks.",
    },
    {
        "type": NotificationType.GOALS_LOCK_TOMORROW.value,
        "group": "Deadlines",
        "label": "Goals lock tomorrow",
        "description": "Last chance to change wording and targets.",
    },
    {
        "type": NotificationType.GOALS_LOCKED.value,
        "group": "Deadlines",
        "label": "Goals locked",
        "description": "Your commitment is now fixed.",
    },
    {
        "type": NotificationType.CHALLENGE_MILESTONE.value,
        "group": "Deadlines",
        "label": "Challenge countdown",
        "description": "100 / 30 / 7 days left.",
    },
    {
        "type": NotificationType.CHALLENGE_COMPLETE.value,
        "group": "Deadlines",
        "label": "Challenge finished",
        "description": "Results and any forfeits.",
    },
)


def muted_types_for(db: Session, user_id: uuid.UUID) -> set[str]:
    user = db.get(User, user_id)
    if not user:
        return set()
    return set(user.muted_notification_types or [])


def preference_payload(user: User) -> dict:
    return {
        "muted_types": list(user.muted_notification_types or []),
        "types": list(PREFERENCE_TYPES),
    }


def set_muted_types(user: User, types: list[str]) -> list[str]:
    allowed = {item["type"] for item in PREFERENCE_TYPES}
    unknown = [item for item in types if item not in allowed]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Unknown notification type: {unknown[0]}",
        )
    # Preserve catalog order, drop duplicates.
    ordered = [item["type"] for item in PREFERENCE_TYPES if item["type"] in set(types)]
    user.muted_notification_types = ordered
    return ordered


def _plain(value: str | None) -> str | None:
    """Notification text is shown as plaintext on iOS; stored HTML entities leak."""
    if value is None:
        return None
    return html.unescape(value)


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
    if kind.value in muted_types_for(db, user_id):
        return None
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
        title=_plain(title) or title,
        body=_plain(body),
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
    db: Session,
    participant: ChallengeParticipant,
    locked: bool,
    now: datetime | None = None,
) -> None:
    challenge_id = participant.challenge_id
    moment = now or utcnow()
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

    remaining = as_utc(participant.goals_due_at) - moment
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
    db: Session,
    participant: ChallengeParticipant,
    challenge: Challenge,
    now: datetime | None = None,
) -> None:
    moment = now or utcnow()
    if moment >= as_utc(challenge.end_at):
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
    if moment < as_utc(challenge.start_at):
        return

    remaining = challenge_days_remaining(challenge, moment)
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
    db: Session,
    *,
    goal: Goal,
    participant: ChallengeParticipant,
    team_id: uuid.UUID,
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


def _format_amount(value: Decimal) -> str:
    """Drop trailing zeros so a COUNT of 6 is '6', not '6.0000'."""
    integral = value.to_integral_value()
    if value == integral:
        return str(int(integral))
    return format(value.normalize(), "f")


def progress_log_body(
    goal: Goal,
    entry: GoalProgressEntry,
    *,
    previous_value: Decimal | None = None,
) -> str:
    """Lead with the change so the banner is not mistaken for finishing the target.

    A COUNT of +6 applications on 'Submit 100 Job Applications' used to show
    only the title, which reads as if they submitted all 100.
    """
    unit = f" {goal.unit}" if goal.unit else ""
    title = goal.title
    delta = entry.numeric_delta
    if delta is None and entry.numeric_value is not None and previous_value is not None:
        delta = entry.numeric_value - previous_value
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        return f"{sign}{_format_amount(delta)}{unit} on {title}"
    if entry.numeric_value is not None:
        return f"now {_format_amount(entry.numeric_value)}{unit} on {title}"
    if entry.manual_percentage is not None:
        return f"now {entry.manual_percentage}% on {title}"
    return title


def member_logged_progress(
    db: Session,
    *,
    goal: Goal,
    participant: ChallengeParticipant,
    team_id: uuid.UUID,
    entry: GoalProgressEntry,
    previous_value: Decimal | None = None,
) -> None:
    """Ping the team on every log, without leaking a private goal's title."""
    if goal.visibility == GoalVisibility.PRIVATE:
        return
    notify_team(
        db,
        team_id=team_id,
        challenge_id=participant.challenge_id,
        kind=NotificationType.MEMBER_CHECKED_IN,
        dedupe_key=f"progress:{entry.id}",
        title=f"{participant.user.display_name} logged progress",
        body=progress_log_body(goal, entry, previous_value=previous_value),
        link_path=f"/team/members/{participant.user_id}",
        exclude_user_id=participant.user_id,
    )


def leaderboard_position_copy(old_rank: int, new_rank: int) -> tuple[str, str]:
    """Title and body for a rank change. Lower number is a climb."""
    if new_rank < old_rank:
        title = f"You moved up to #{new_rank}"
    else:
        title = f"You dropped to #{new_rank}"
    return title, f"Was #{old_rank}."


def leaderboard_snapshot(db: Session, challenge_id: uuid.UUID) -> dict[uuid.UUID, dict]:
    """Current 1-based ranks plus who has goals, matching the dashboard sort."""
    from app.services.challenges import active_participants
    from app.services.goals import load_goal_tree
    from app.services.progress import leaderboard_ranks, overall_progress

    rows: list[tuple[uuid.UUID, float, str]] = []
    submitted: dict[uuid.UUID, bool] = {}
    for participant in active_participants(db, challenge_id):
        goals = load_goal_tree(db, participant.id)
        rows.append(
            (
                participant.user_id,
                overall_progress(goals),
                participant.user.display_name,
            )
        )
        submitted[participant.user_id] = bool(goals)
    ranks = leaderboard_ranks(rows)
    return {
        user_id: {"rank": ranks[user_id], "submitted": submitted[user_id]}
        for user_id in ranks
    }


def leaderboard_position_changes(
    db: Session,
    *,
    challenge_id: uuid.UUID,
    before: dict[uuid.UUID, dict],
    after: dict[uuid.UUID, dict],
    cause_key: str,
) -> None:
    """Ping each member whose visible dashboard place actually moved."""
    for user_id, place in after.items():
        previous = before.get(user_id)
        if previous is None:
            continue
        if not place["submitted"]:
            # Unsubmitted cards hide the number, so a shuffle is not a place change.
            continue
        old_rank = previous["rank"]
        new_rank = place["rank"]
        if old_rank == new_rank:
            continue
        title, body = leaderboard_position_copy(old_rank, new_rank)
        notify(
            db,
            user_id=user_id,
            challenge_id=challenge_id,
            kind=NotificationType.LEADERBOARD_POSITION,
            dedupe_key=f"rank:{challenge_id}:{user_id}:{old_rank}:{new_rank}:{cause_key}",
            title=title,
            body=body,
            link_path="/dashboard",
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
