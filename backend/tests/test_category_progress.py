"""Optional goals are upside: they must not move a headline percentage.

Adding an optional goal used to enlarge the divisor while contributing almost
nothing, so a member's category score fell the moment they committed to extra
work that carried no forfeit.
"""

from decimal import Decimal

from app.api.v1.serializers import category_progress, overall_progress
from app.models.domain import Goal, GoalCategory, TargetDirection, TrackingType


def goal(category: GoalCategory, percent: int, *, required: bool = True) -> Goal:
    return Goal(
        title=f"{category.value} {percent}",
        category=category,
        tracking_type=TrackingType.NUMERIC,
        baseline_value=Decimal(0),
        target_value=Decimal(100),
        current_value=Decimal(percent),
        target_direction=TargetDirection.AT_LEAST,
        required=required,
    )


def test_optional_goal_does_not_lower_its_category() -> None:
    required = [
        goal(GoalCategory.PHYSICAL, 100),
        goal(GoalCategory.PHYSICAL, 50),
    ]
    assert category_progress(required)["PHYSICAL"] == 75.0

    with_optional = [*required, goal(GoalCategory.PHYSICAL, 1, required=False)]
    assert category_progress(with_optional)["PHYSICAL"] == 75.0


def test_optional_goal_does_not_lower_overall() -> None:
    goals = [goal(GoalCategory.PHYSICAL, 60), goal(GoalCategory.CAREER, 40)]
    assert overall_progress(goals) == 50.0

    goals.append(goal(GoalCategory.PHYSICAL, 0, required=False))
    assert overall_progress(goals) == 50.0


def test_category_of_only_optional_goals_still_reports() -> None:
    """Falling back beats hiding a category the member deliberately created."""
    goals = [
        goal(GoalCategory.PHYSICAL, 80),
        goal(GoalCategory.PERSONAL, 30, required=False),
    ]
    assert category_progress(goals) == {"PHYSICAL": 80.0, "PERSONAL": 30.0}


def test_completing_an_optional_goal_is_not_punished_either() -> None:
    """The rule is symmetric: optional work neither helps nor hurts the score."""
    goals = [goal(GoalCategory.CAREER, 20)]
    assert category_progress(goals)["CAREER"] == 20.0

    goals.append(goal(GoalCategory.CAREER, 100, required=False))
    assert category_progress(goals)["CAREER"] == 20.0
