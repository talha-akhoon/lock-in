from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.domain import Goal, TargetDirection, TrackingType
from app.services.progress import (
    average_progress,
    calculate_goal_progress,
    checkin_streak,
    leaderboard_ranks,
    scored_goals,
)


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


def test_a_running_total_counts_the_starting_amount() -> None:
    goal = Goal(
        title="Read 150",
        category="RELIGIOUS",
        tracking_type=TrackingType.COUNT,
        baseline_value=Decimal(2),
        current_value=Decimal(2),
        target_value=Decimal(150),
        target_direction=TargetDirection.AT_LEAST,
        required=True,
    )
    assert round(calculate_goal_progress(goal), 1) == 1.3


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


def test_optional_goal_does_not_dilute_the_average() -> None:
    """Committing to extra, unforfeited work must not cost you percentage."""
    goals = [
        numeric_goal(current_value=Decimal(120)),
        numeric_goal(current_value=Decimal(105)),
    ]
    before = average_progress(goals)
    goals.append(numeric_goal(current_value=Decimal(90), required=False))
    assert average_progress(goals) == before == 75.0


def test_average_falls_back_to_optional_when_nothing_is_required() -> None:
    goals = [numeric_goal(current_value=Decimal(120), required=False)]
    assert average_progress(goals) == 100.0


def test_leaderboard_ranks_sort_by_progress_then_name() -> None:
    admin, teammate, zed = "admin", "teammate", "zed"
    ranks = leaderboard_ranks(
        [
            (admin, 40.0, "Admin"),
            (teammate, 70.0, "Teammate"),
            (zed, 70.0, "Zed"),
        ]
    )
    assert ranks == {teammate: 1, zed: 2, admin: 3}


def test_scored_goals_keeps_only_required() -> None:
    required = numeric_goal()
    optional = numeric_goal(required=False)
    assert scored_goals([required, optional]) == [required]
