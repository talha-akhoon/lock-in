"""Time helpers.

Every stored timestamp is UTC; every user-facing *date* (check-ins, streaks,
goal deadlines) is resolved in the challenge's timezone. Mixing the two is the
easiest way to produce off-by-one-day bugs, so the conversion lives here.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models.domain import Challenge


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Treat a naive timestamp as UTC so comparisons never raise."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def challenge_zone(challenge: Challenge) -> ZoneInfo:
    return ZoneInfo(challenge.timezone)


def challenge_today(challenge: Challenge, moment: datetime | None = None) -> date:
    if moment is None:
        return datetime.now(challenge_zone(challenge)).date()
    return local_date(challenge, moment)


def local_now(challenge: Challenge, moment: datetime | None = None) -> datetime:
    return as_utc(moment or utcnow()).astimezone(challenge_zone(challenge))


def is_before_start(challenge: Challenge, day: date | None = None) -> bool:
    """True while the challenge-local calendar is still before kick-off."""
    day = day if day is not None else challenge_today(challenge)
    return day < local_date(challenge, challenge.start_at)


def local_date(challenge: Challenge, moment: datetime) -> date:
    return as_utc(moment).astimezone(challenge_zone(challenge)).date()


def local_midnight(challenge: Challenge, day: date) -> datetime:
    """The UTC instant at which `day` begins in the challenge's timezone."""
    return datetime.combine(day, time.min, tzinfo=challenge_zone(challenge)).astimezone(
        UTC
    )


def challenge_day_number(challenge: Challenge, moment: datetime | None = None) -> int:
    """1-based day index, clamped to the challenge length."""
    moment = moment or utcnow()
    elapsed = (
        local_date(challenge, moment) - local_date(challenge, challenge.start_at)
    ).days
    return max(1, min(challenge_total_days(challenge), elapsed + 1))


def challenge_total_days(challenge: Challenge) -> int:
    return max(
        1,
        (
            local_date(challenge, challenge.end_at)
            - local_date(challenge, challenge.start_at)
        ).days,
    )


def challenge_days_remaining(
    challenge: Challenge, moment: datetime | None = None
) -> int:
    moment = moment or utcnow()
    remaining = (
        local_date(challenge, challenge.end_at) - local_date(challenge, moment)
    ).days
    return max(0, remaining)


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
