from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.domain import Goal, TargetDirection, TrackingType
from app.services.progress import calculate_goal_progress, checkin_streak


def numeric_goal(**overrides) -> Goal:
    values = {
        "title": "Deadlift",
        "category": "PHYSICAL",
        "tracking_type": TrackingType.NUMERIC,
        "baseline_value": Decimal(90),
        "target_value": Decimal(120),
        "current_value": Decimal(105),
        "target_direction": TargetDirection.AT_LEAST,
        "required": True,
    }
    values.update(overrides)
    return Goal(**values)


def test_increasing_numeric_progress() -> None:
    assert calculate_goal_progress(numeric_goal()) == 50


def test_decreasing_numeric_progress() -> None:
    goal = numeric_goal(
        baseline_value=Decimal(82),
        target_value=Decimal(75),
        current_value=Decimal(78),
        target_direction=TargetDirection.AT_MOST,
    )
    assert round(calculate_goal_progress(goal)) == 57


def test_progress_is_clamped_when_target_is_exceeded() -> None:
    assert calculate_goal_progress(numeric_goal(current_value=Decimal(140))) == 100


def test_equal_baseline_and_target_does_not_divide_by_zero() -> None:
    goal = numeric_goal(
        baseline_value=Decimal(100),
        target_value=Decimal(100),
        current_value=Decimal(99),
    )
    assert calculate_goal_progress(goal) == 0
    goal.current_value = Decimal(100)
    assert calculate_goal_progress(goal) == 100


def test_manual_progress_is_clamped() -> None:
    goal = Goal(
        title="Prototype",
        category="BUSINESS",
        tracking_type=TrackingType.MANUAL,
        manual_progress_percentage=65,
        required=True,
    )
    assert calculate_goal_progress(goal) == 65


def test_parent_averages_required_children_only() -> None:
    parent = Goal(
        title="Interview ready",
        category="CAREER",
        tracking_type=TrackingType.MILESTONE,
        required=True,
    )
    parent.children = [
        numeric_goal(current_value=Decimal(105)),
        numeric_goal(current_value=Decimal(120)),
        numeric_goal(current_value=Decimal(90), required=False),
    ]
    assert calculate_goal_progress(parent) == 75


def test_streak_allows_today_to_be_missing() -> None:
    today = date(2026, 8, 14)
    assert (
        checkin_streak([today - timedelta(days=1), today - timedelta(days=2)], today)
        == 2
    )


def test_milestone_completion() -> None:
    goal = Goal(
        title="Land role",
        category="CAREER",
        tracking_type=TrackingType.MILESTONE,
        required=True,
        completed_at=datetime.now(UTC),
    )
    assert calculate_goal_progress(goal) == 100
