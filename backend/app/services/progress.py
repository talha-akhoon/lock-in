"""Pure progress arithmetic. No database access, so it is cheap to test."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.domain import Goal, TargetDirection, TrackingType


def scored_goals(goals: list[Goal]) -> list[Goal]:
    """The goals a percentage is measured over: the required ones.

    Optional goals are upside. Averaging them in means committing to one
    instantly dilutes the number, so a member is punished for taking on more
    than the forfeit demanded. Falls back to the whole list when nothing in it
    is required, so an all-optional set still reads as real progress instead of
    vanishing from the aggregate.
    """
    required = [goal for goal in goals if goal.required]
    return required or goals


def calculate_goal_progress(goal: Goal) -> float:
    """Percentage complete, always clamped to 0..100.

    A parent goal is the mean of its *required* children only; optional
    sub-goals are upside and must not drag a parent's percentage down.
    """
    if goal.children:
        required = [child for child in goal.children if child.required]
        if not required:
            return 100.0
        return sum(calculate_goal_progress(child) for child in required) / len(required)

    if goal.completed_at and goal.tracking_type == TrackingType.MILESTONE:
        return 100.0
    if goal.tracking_type == TrackingType.MANUAL:
        return float(max(0, min(100, goal.manual_progress_percentage or 0)))
    if goal.tracking_type == TrackingType.MILESTONE:
        return 0.0

    # A running total already includes work done before the challenge.
    # Measuring from a raised baseline would hide that as 0%.
    baseline = (
        Decimal(0)
        if goal.tracking_type == TrackingType.COUNT
        else (goal.baseline_value or Decimal(0))
    )
    current = goal.current_value if goal.current_value is not None else baseline
    target = goal.target_value
    if target is None:
        return 0.0
    if target == baseline:
        # No range to measure against, so it is binary: has the target been met?
        reached = (
            current <= target
            if goal.target_direction == TargetDirection.AT_MOST
            else current >= target
        )
        return 100.0 if reached else 0.0

    if (
        goal.tracking_type == TrackingType.COUNT
        or goal.target_direction == TargetDirection.AT_LEAST
    ):
        raw = (current - baseline) / (target - baseline)
    else:
        raw = (baseline - current) / (baseline - target)
    return float(max(Decimal(0), min(Decimal(1), raw)) * 100)


def goal_is_complete(goal: Goal) -> bool:
    return calculate_goal_progress(goal) >= 100


def category_progress(goals: list[Goal]) -> dict[str, float]:
    """Mean progress per category over required goals, private ones included.

    Optional goals are left out of each category's score, matching how a
    parent scores its steps. An all-optional category still reports, so a
    category the member created does not vanish from the dashboard.
    """
    buckets: dict[str, list[Goal]] = {}
    for goal in goals:
        buckets.setdefault(goal.category.value, []).append(goal)
    return {
        category: round(
            sum(calculate_goal_progress(goal) for goal in scored) / len(scored),
            1,
        )
        for category, members in buckets.items()
        if (scored := scored_goals(members))
    }


def overall_progress(goals: list[Goal]) -> float:
    """Mean of category scores that contain a required goal.

    An all-optional category still appears on the dashboard (see
    category_progress) but must not dilute the headline number. If nothing
    is required, fall back to averaging what is there so an all-optional
    board is not a silent 0%.
    """
    required = [goal for goal in goals if goal.required]
    categories = category_progress(required or goals)
    if not categories:
        return 0.0
    return round(sum(categories.values()) / len(categories), 1)


def average_progress(goals: list[Goal]) -> float:
    if not goals:
        return 0.0
    scored = scored_goals(goals)
    return round(sum(calculate_goal_progress(goal) for goal in scored) / len(scored), 1)


def checkin_streak(dates: list[date], today: date) -> int:
    """Consecutive days ending today, or yesterday if today is not logged yet.

    Not having checked in *yet* today should not read as a broken streak.
    """
    unique = set(dates)
    cursor = today if today in unique else today - timedelta(days=1)
    streak = 0
    while cursor in unique:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
