"""Pure progress arithmetic. No database access, so it is cheap to test."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.domain import Goal, TargetDirection, TrackingType


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


def average_progress(goals: list[Goal]) -> float:
    if not goals:
        return 0.0
    return round(sum(calculate_goal_progress(goal) for goal in goals) / len(goals), 1)


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
