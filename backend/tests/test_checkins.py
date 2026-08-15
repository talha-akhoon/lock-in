"""Daily check-ins, including the all-or-nothing write."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.domain import DailyCheckin, Goal, GoalProgressEntry


@pytest.fixture
def today(team_setup) -> str:
    """The challenge's local today.

    Derived rather than hardcoded: check-in dates are local dates, so a fixed
    literal would break whenever UTC and the challenge timezone disagree.
    """
    from app.services.clock import challenge_today

    return challenge_today(team_setup.challenge).isoformat()


@pytest.fixture
def goals(team_setup, make_goal):
    return {
        "numeric": make_goal(team_setup.admin_participant, title="Deadlift 120kg"),
        "count": make_goal(
            team_setup.admin_participant,
            title="Read scripture 5 times",
            category="RELIGIOUS",
            tracking_type="COUNT",
            baseline_value=Decimal(0),
            current_value=Decimal(0),
            target_value=Decimal(5),
            unit="completions",
        ),
        "manual": make_goal(
            team_setup.admin_participant,
            title="Ship prototype",
            category="BUSINESS",
            tracking_type="MANUAL",
            manual_progress_percentage=0,
            baseline_value=None,
            target_value=None,
            current_value=None,
            target_direction=None,
        ),
    }


def test_a_checkin_applies_every_update(team_setup, today, goals, db) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "note": "Solid day",
            "updates": [
                {"goal_id": str(goals["numeric"].id), "numeric_value": "105"},
                {"goal_id": str(goals["count"].id), "numeric_delta": "1"},
                {"goal_id": str(goals["manual"].id), "manual_percentage": 40},
            ],
        },
    )

    assert response.status_code == 200
    db.expire_all()
    assert db.get(Goal, goals["numeric"].id).current_value == Decimal("105.0000")
    assert db.get(Goal, goals["count"].id).current_value == Decimal("1.0000")
    assert db.get(Goal, goals["manual"].id).manual_progress_percentage == 40
    assert db.query(GoalProgressEntry).count() == 3


def test_resubmitting_a_day_updates_the_note(team_setup, today, goals, db) -> None:
    for note in ("first", "second"):
        team_setup.admin_client.post(
            "/api/v1/me/checkins", json={"date": today, "note": note}
        )

    rows = db.query(DailyCheckin).all()
    assert len(rows) == 1
    assert rows[0].note == "second"


def test_a_bad_goal_id_rolls_the_whole_day_back(team_setup, today, goals, db) -> None:
    """A partial write would leave the member's numbers silently wrong."""
    response = team_setup.admin_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "note": "Should not persist",
            "updates": [
                {"goal_id": str(goals["numeric"].id), "numeric_value": "105"},
                {"goal_id": str(uuid.uuid4()), "numeric_value": "1"},
            ],
        },
    )

    assert response.status_code == 404
    db.expire_all()
    assert db.query(DailyCheckin).count() == 0
    assert db.query(GoalProgressEntry).count() == 0
    assert db.get(Goal, goals["numeric"].id).current_value == Decimal("90.0000")


def test_another_members_goal_id_rolls_the_day_back(
    team_setup, today, goals, make_goal, db
) -> None:
    teammate_goal = make_goal(team_setup.member_participant, title="Not yours")

    response = team_setup.admin_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [
                {"goal_id": str(goals["numeric"].id), "numeric_value": "110"},
                {"goal_id": str(teammate_goal.id), "numeric_value": "999"},
            ],
        },
    )

    assert response.status_code == 404
    db.expire_all()
    assert db.query(GoalProgressEntry).count() == 0
    assert db.get(Goal, goals["numeric"].id).current_value == Decimal("90.0000")


def test_a_parent_goal_cannot_be_updated_directly(
    team_setup, today, make_goal, db
) -> None:
    parent = make_goal(
        team_setup.admin_participant,
        title="Interview ready",
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )
    make_goal(team_setup.admin_participant, parent_goal_id=parent.id, title="Sub")

    response = team_setup.admin_client.post(
        "/api/v1/me/checkins",
        json={"date": today, "updates": [{"goal_id": str(parent.id)}]},
    )

    assert response.status_code == 422
    assert db.query(DailyCheckin).count() == 0


def test_completing_all_required_children_completes_the_parent(
    team_setup, today, make_goal, db
) -> None:
    parent = make_goal(
        team_setup.admin_participant,
        title="Interview ready",
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )
    first = make_goal(
        team_setup.admin_participant, parent_goal_id=parent.id, title="Sub one"
    )
    second = make_goal(
        team_setup.admin_participant, parent_goal_id=parent.id, title="Sub two"
    )
    optional = make_goal(
        team_setup.admin_participant,
        parent_goal_id=parent.id,
        title="Nice to have",
        required=False,
    )

    team_setup.admin_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [
                {"goal_id": str(first.id), "numeric_value": "120"},
                {"goal_id": str(second.id), "numeric_value": "120"},
            ],
        },
    )

    db.expire_all()
    assert db.get(Goal, parent.id).completed_at is not None
    assert db.get(Goal, optional.id).completed_at is None


def test_the_heatmap_window_comes_from_the_challenge(
    make_user, make_team, make_challenge, make_participant, client_factory
) -> None:
    """A 90-day challenge must not render a hardcoded 184-day grid."""
    from app.services.clock import local_date

    user = make_user("Short")
    team = make_team(user, name="Sprint")
    challenge = make_challenge(team, days=90)
    make_participant(challenge, user)

    body = client_factory(user.id).get("/api/v1/me/checkins").json()

    assert body["start_date"] == local_date(challenge, challenge.start_at).isoformat()
    assert body["end_date"] == local_date(challenge, challenge.end_at).isoformat()
    span = (
        date.fromisoformat(body["end_date"]) - date.fromisoformat(body["start_date"])
    ).days
    assert 88 <= span <= 90, "window must track the challenge, not a fixed 184 days"


def test_the_streak_counts_consecutive_days(team_setup, today, goals) -> None:
    latest = date.fromisoformat(today)
    for offset in (2, 1, 0):
        team_setup.admin_client.post(
            "/api/v1/me/checkins",
            json={"date": (latest - timedelta(days=offset)).isoformat()},
        )

    body = team_setup.admin_client.get("/api/v1/me/checkins").json()

    assert body["total_days_logged"] == 3
    assert len(body["days"]) == 3
    assert body["streak"] == 3


def test_a_gap_breaks_the_streak(team_setup, today, goals) -> None:
    latest = date.fromisoformat(today)
    for offset in (5, 4, 0):
        team_setup.admin_client.post(
            "/api/v1/me/checkins",
            json={"date": (latest - timedelta(days=offset)).isoformat()},
        )

    body = team_setup.admin_client.get("/api/v1/me/checkins").json()

    assert body["total_days_logged"] == 3
    assert body["streak"] == 1


def test_a_single_day_can_be_fetched_for_the_form(team_setup, today, goals) -> None:
    team_setup.admin_client.post(
        "/api/v1/me/checkins", json={"date": today, "note": "Done"}
    )

    body = team_setup.admin_client.get(f"/api/v1/me/checkins/{today}").json()

    assert body["exists"] is True
    assert body["note"] == "Done"
    assert len(body["goals"]) == 3


def test_a_day_with_no_checkin_reports_that_it_is_empty(
    team_setup, today, goals
) -> None:
    body = team_setup.admin_client.get(f"/api/v1/me/checkins/{today}").json()

    assert body["exists"] is False
    assert body["note"] is None


def test_a_date_outside_the_challenge_is_rejected(team_setup, today, goals) -> None:
    response = team_setup.admin_client.get("/api/v1/me/checkins/2020-01-01")
    assert response.status_code == 422
