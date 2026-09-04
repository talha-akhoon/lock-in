"""Evening nudges for people who have not opened the app."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    ChallengeStatus,
    DailyCheckin,
    Goal,
    MembershipStatus,
    NotificationType,
    ParticipantStatus,
    TeamMember,
)
from app.services import notifications as notification_service
from app.services.challenges import sync_challenge_status
from app.services.checkins import checkin_dates
from app.services.clock import (
    as_utc,
    challenge_day_number,
    challenge_total_days,
    local_date,
    local_now,
    utcnow,
)
from app.services.goals import load_goal_tree, sync_participant_lock
from app.services.progress import calculate_goal_progress, checkin_streak

EVENING_HOUR = 20
QUIET_DAYS = 3
PACE_SLACK = 15
PACE_GRACE_DAYS = 7
PACE_WEEKDAY = 6  # Sunday in Python (Monday = 0)


def _in_the_game(db: Session, participant: ChallengeParticipant) -> bool:
    if participant.goals_committed_at is not None:
        return True
    return (
        db.scalar(
            select(Goal.id)
            .where(Goal.challenge_participant_id == participant.id)
            .limit(1)
        )
        is not None
    )


def _team_size(db: Session, team_id) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.status == MembershipStatus.ACTIVE,
            )
        )
        or 0
    )


def _checked_in_on(db: Session, participant_id, day) -> bool:
    return (
        db.scalar(
            select(DailyCheckin.id).where(
                DailyCheckin.challenge_participant_id == participant_id,
                DailyCheckin.checkin_date == day,
            )
        )
        is not None
    )


def _last_checkin_day(db: Session, participant: ChallengeParticipant):
    latest = db.scalar(
        select(func.max(DailyCheckin.checkin_date)).where(
            DailyCheckin.challenge_participant_id == participant.id
        )
    )
    if latest is not None:
        return latest
    return local_date(
        participant.challenge, participant.challenge.start_at
    ) - timedelta(days=1)


def _pace_behind_titles(
    db: Session, participant: ChallengeParticipant, now: datetime
) -> list[str]:
    challenge = participant.challenge
    expected = (
        challenge_day_number(challenge, now) / challenge_total_days(challenge)
    ) * 100
    behind: list[str] = []
    for goal in load_goal_tree(db, participant.id):
        if not goal.required:
            continue
        if calculate_goal_progress(goal) + PACE_SLACK < expected:
            behind.append(goal.title)
    return behind


def _dispatch_evening_checkins(
    db: Session, now: datetime, participants: list[ChallengeParticipant]
) -> None:
    for participant in participants:
        challenge = participant.challenge
        local = local_now(challenge, now)
        if local.hour < EVENING_HOUR:
            continue
        today = local.date()
        if today < local_date(challenge, challenge.start_at):
            continue
        if not _in_the_game(db, participant):
            continue
        if _checked_in_on(db, participant.id, today):
            continue
        streak = checkin_streak(checkin_dates(db, participant.id), today)
        if streak >= 2:
            notification_service.notify(
                db,
                user_id=participant.user_id,
                challenge_id=challenge.id,
                kind=NotificationType.STREAK_AT_RISK,
                dedupe_key=f"streak:{challenge.id}:{today.isoformat()}",
                title="Your streak is on the line",
                body=f"Log progress today to keep a {streak}-day streak.",
                link_path="/check-in",
            )
        else:
            notification_service.notify(
                db,
                user_id=participant.user_id,
                challenge_id=challenge.id,
                kind=NotificationType.CHECKIN_DUE,
                dedupe_key=f"due:{challenge.id}:{today.isoformat()}",
                title="You have not checked in today",
                body="Your team can see today's board. Log progress before the day ends.",
                link_path="/check-in",
            )


def _dispatch_quiet_members(
    db: Session, now: datetime, participants: list[ChallengeParticipant]
) -> None:
    for participant in participants:
        challenge = participant.challenge
        if _team_size(db, challenge.team_id) < 2:
            continue
        if not _in_the_game(db, participant):
            continue
        today = local_date(challenge, now)
        if today < local_date(challenge, challenge.start_at):
            continue
        last = _last_checkin_day(db, participant)
        if (today - last).days < QUIET_DAYS:
            continue
        notification_service.notify_team(
            db,
            team_id=challenge.team_id,
            challenge_id=challenge.id,
            kind=NotificationType.MEMBER_QUIET,
            dedupe_key=f"quiet:{challenge.id}:{participant.user_id}:{last.isoformat()}",
            title=f"{participant.user.display_name} has gone quiet",
            body=f"No check-in in {QUIET_DAYS}+ days.",
            link_path=f"/team/members/{participant.user_id}",
            exclude_user_id=participant.user_id,
        )


def _dispatch_pace(
    db: Session, now: datetime, participants: list[ChallengeParticipant]
) -> None:
    for participant in participants:
        challenge = participant.challenge
        local = local_now(challenge, now)
        if local.weekday() != PACE_WEEKDAY or local.hour < EVENING_HOUR:
            continue
        elapsed = (as_utc(now) - as_utc(challenge.start_at)).total_seconds() / 86400
        if elapsed < PACE_GRACE_DAYS:
            continue
        if not _in_the_game(db, participant):
            continue
        titles = _pace_behind_titles(db, participant, now)
        if not titles:
            continue
        week = local.date().isoformat()
        listed = ", ".join(titles[:3])
        extra = f" and {len(titles) - 3} more" if len(titles) > 3 else ""
        verb = "is" if len(titles) == 1 else "are"
        body = f"{listed}{extra} {verb} behind the expected pace."
        notification_service.notify(
            db,
            user_id=participant.user_id,
            challenge_id=challenge.id,
            kind=NotificationType.PACE_BEHIND,
            dedupe_key=f"pace:{challenge.id}:{week}",
            title="You are behind on a required goal",
            body=body[:500],
            link_path="/goals",
        )


def _dispatch_existing_reminders(
    db: Session, now: datetime, participants: list[ChallengeParticipant]
) -> None:
    for participant in participants:
        locked = sync_participant_lock(db, participant, now=now)
        notification_service.goal_deadline_notifications(
            db, participant, locked, now=now
        )
        notification_service.challenge_notifications(
            db, participant, participant.challenge, now=now
        )


def _load_participants(db: Session, now: datetime) -> list[ChallengeParticipant]:
    open_challenges = db.scalars(
        select(Challenge).where(
            Challenge.status.in_((ChallengeStatus.UPCOMING, ChallengeStatus.ACTIVE))
        )
    ).all()
    for challenge in open_challenges:
        sync_challenge_status(db, challenge, now=now)

    cutoff = now - timedelta(days=2)
    return list(
        db.scalars(
            select(ChallengeParticipant)
            .join(Challenge, Challenge.id == ChallengeParticipant.challenge_id)
            .options(
                joinedload(ChallengeParticipant.user),
                joinedload(ChallengeParticipant.challenge),
            )
            .where(
                Challenge.status != ChallengeStatus.DRAFT,
                ChallengeParticipant.status != ParticipantStatus.REMOVED,
                Challenge.end_at >= cutoff,
            )
        ).unique()
    )


def run(db: Session, *, now: datetime | None = None) -> None:
    now = as_utc(now or utcnow())
    participants = _load_participants(db, now)
    active = [
        row for row in participants if row.challenge.status == ChallengeStatus.ACTIVE
    ]
    _dispatch_evening_checkins(db, now, active)
    _dispatch_quiet_members(db, now, active)
    _dispatch_pace(db, now, active)
    _dispatch_existing_reminders(db, now, participants)
