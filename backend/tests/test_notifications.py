"""All eight notification types, and the dedupe that makes lazy generation safe."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.domain import Challenge, ChallengeParticipant, Notification
from app.services.notifications import progress_log_body


def test_progress_body_leads_with_the_logged_amount() -> None:
    goal = SimpleNamespace(title="Submit 100 Job Applications", unit="applications")
    entry = SimpleNamespace(
        numeric_delta=Decimal("6.0000"),
        numeric_value=None,
        manual_percentage=None,
    )
    assert (
        progress_log_body(goal, entry)
        == "+6 applications on Submit 100 Job Applications"
    )


def test_progress_body_uses_the_numeric_change_when_the_log_is_a_new_figure() -> None:
    goal = SimpleNamespace(title="Deadlift 120kg", unit="kg")
    entry = SimpleNamespace(
        numeric_delta=None,
        numeric_value=Decimal(105),
        manual_percentage=None,
    )
    assert (
        progress_log_body(goal, entry, previous_value=Decimal(90))
        == "+15 kg on Deadlift 120kg"
    )


def test_progress_body_keeps_a_minus_sign_on_a_drop() -> None:
    goal = SimpleNamespace(title="Body fat to 12%", unit="%")
    entry = SimpleNamespace(
        numeric_delta=Decimal("-0.5"),
        numeric_value=None,
        manual_percentage=None,
    )
    assert progress_log_body(goal, entry) == "-0.5 % on Body fat to 12%"


def test_progress_body_falls_back_to_the_title_for_a_note_only_log() -> None:
    goal = SimpleNamespace(title="Get promoted", unit=None)
    entry = SimpleNamespace(
        numeric_delta=None, numeric_value=None, manual_percentage=None
    )
    assert progress_log_body(goal, entry) == "Get promoted"


def types_for(client) -> list[str]:
    body = client.get("/api/v1/me/notifications").json()
    return [row["type"] for row in body["notifications"]]


@pytest.fixture
def set_deadline(db):
    def apply(participant, offset: timedelta):
        row = db.get(ChallengeParticipant, participant.id)
        row.goals_due_at = datetime.now(UTC) + offset
        row.goals_locked_at = None
        db.commit()

    return apply


def test_three_days_out_warns_that_goals_are_due(team_setup, set_deadline) -> None:
    set_deadline(team_setup.admin_participant, timedelta(days=2, hours=12))
    assert "GOALS_DUE_SOON" in types_for(team_setup.admin_client)


def test_one_day_out_warns_that_goals_lock_tomorrow(team_setup, set_deadline) -> None:
    set_deadline(team_setup.admin_participant, timedelta(hours=20))
    assert "GOALS_LOCK_TOMORROW" in types_for(team_setup.admin_client)


def test_a_passed_deadline_reports_that_goals_are_locked(
    team_setup, set_deadline
) -> None:
    set_deadline(team_setup.admin_participant, -timedelta(minutes=1))
    assert "GOALS_LOCKED" in types_for(team_setup.admin_client)


def test_a_distant_deadline_produces_no_goal_warning(team_setup, set_deadline) -> None:
    set_deadline(team_setup.admin_participant, timedelta(days=20))
    assert not {"GOALS_DUE_SOON", "GOALS_LOCK_TOMORROW", "GOALS_LOCKED"}.intersection(
        types_for(team_setup.admin_client)
    )


@pytest.mark.parametrize("threshold", [100, 30, 7])
def test_challenge_milestones_fire_at_each_threshold(team_setup, db, threshold) -> None:
    challenge = db.get(Challenge, team_setup.challenge.id)
    challenge.end_at = datetime.now(UTC) + timedelta(days=threshold)
    db.commit()

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    milestones = [
        row for row in body["notifications"] if row["type"] == "CHALLENGE_MILESTONE"
    ]

    assert len(milestones) == 1
    assert milestones[0]["title"] == f"{threshold} days left"


def test_only_the_nearest_milestone_fires(team_setup, db) -> None:
    """At 5 days remaining the member should not also be told "100 days left"."""
    challenge = db.get(Challenge, team_setup.challenge.id)
    challenge.end_at = datetime.now(UTC) + timedelta(days=5)
    db.commit()

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    milestones = [
        row for row in body["notifications"] if row["type"] == "CHALLENGE_MILESTONE"
    ]

    assert [row["title"] for row in milestones] == ["7 days left"]


def test_the_end_of_the_challenge_is_announced(team_setup, db) -> None:
    challenge = db.get(Challenge, team_setup.challenge.id)
    challenge.start_at = datetime.now(UTC) - timedelta(days=184)
    challenge.end_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    assert "CHALLENGE_COMPLETE" in types_for(team_setup.admin_client)


def test_a_new_member_is_announced_to_the_team(
    team_setup, make_user, client_factory
) -> None:
    code = team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/invitations", json={"max_uses": 1}
    ).json()["code"]
    newcomer = make_user("Newcomer")
    client_factory(newcomer.id).post("/api/v1/invitations/redeem", json={"code": code})

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    joined = [row for row in body["notifications"] if row["type"] == "MEMBER_JOINED"]

    assert len(joined) == 1
    assert joined[0]["title"] == "Newcomer joined the team"


def test_a_teammate_completing_a_goal_is_announced(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.member_participant, title="Deadlift 120kg")
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    completions = [
        row for row in body["notifications"] if row["type"] == "MEMBER_COMPLETED_GOAL"
    ]

    assert len(completions) == 1
    assert completions[0]["title"] == "Teammate completed a goal"
    assert completions[0]["body"] == "Deadlift 120kg"
    assert "MEMBER_CHECKED_IN" not in types_for(team_setup.admin_client)


def test_the_owner_is_not_notified_about_their_own_completion(
    team_setup, make_goal
) -> None:
    goal = make_goal(team_setup.member_participant)
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    )

    assert "MEMBER_COMPLETED_GOAL" not in types_for(team_setup.member_client)


def test_a_teammate_logging_progress_is_announced(team_setup, make_goal) -> None:
    from decimal import Decimal

    goal = make_goal(
        team_setup.member_participant,
        title="Submit 100 Job Applications",
        tracking_type="COUNT",
        baseline_value=Decimal(0),
        current_value=Decimal(0),
        target_value=Decimal(100),
        unit="applications",
    )
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_delta": "6"},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    logs = [row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"]

    assert len(logs) == 1
    assert logs[0]["title"] == "Teammate logged progress"
    assert logs[0]["body"] == "+6 applications on Submit 100 Job Applications"


def test_the_owner_is_not_notified_about_their_own_log(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.member_participant)
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "91"},
    )

    assert "MEMBER_CHECKED_IN" not in types_for(team_setup.member_client)


def test_a_numeric_log_shows_the_change_from_the_previous_figure(
    team_setup, make_goal
) -> None:
    goal = make_goal(team_setup.member_participant, title="Deadlift 120kg")
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "105"},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    logs = [row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"]
    assert logs[0]["body"] == "+15 kg on Deadlift 120kg"


def test_a_manual_log_shows_the_new_percentage(team_setup, make_goal) -> None:
    goal = make_goal(
        team_setup.member_participant,
        title="Ship the side project",
        tracking_type="MANUAL",
        baseline_value=None,
        current_value=None,
        target_value=None,
        target_direction=None,
        unit=None,
        manual_progress_percentage=20,
    )
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "manual_percentage": 35},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    logs = [row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"]
    assert logs[0]["body"] == "now 35% on Ship the side project"


def test_each_progress_log_notifies_again(team_setup, make_goal) -> None:
    """A second LC problem (or any later log) is a new ping, not one-per-day."""
    from decimal import Decimal

    goal = make_goal(
        team_setup.member_participant,
        title="LeetCode problems",
        tracking_type="COUNT",
        baseline_value=Decimal(0),
        current_value=Decimal(0),
        target_value=Decimal(150),
        unit="problems",
    )
    for _ in range(2):
        team_setup.member_client.post(
            f"/api/v1/goals/{goal.id}/progress",
            json={"entry_date": "2026-08-14", "numeric_delta": "1"},
        )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    logs = [row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"]
    assert len(logs) == 2
    assert all(row["body"] == "+1 problems on LeetCode problems" for row in logs)


def test_html_entities_in_a_goal_title_are_shown_as_text(team_setup, make_goal) -> None:
    goal = make_goal(
        team_setup.member_participant, title="Lock the design &amp; branding"
    )
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "91"},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    logs = [row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"]
    assert logs[0]["body"] == "+1 kg on Lock the design & branding"


def test_a_starting_point_snapshot_does_not_announce_progress(
    team_setup, make_goal, db
) -> None:
    """Before kick-off the form records a baseline, not work done."""
    from datetime import UTC, datetime, timedelta

    from app.models.domain import ChallengeStatus

    team_setup.challenge.start_at = datetime.now(UTC) + timedelta(days=3)
    team_setup.challenge.status = ChallengeStatus.UPCOMING
    db.commit()

    goal = make_goal(team_setup.member_participant, current_value=90)
    today = team_setup.member_client.get("/api/v1/me/checkins").json()["today"]
    response = team_setup.member_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [{"goal_id": str(goal.id), "numeric_value": "92"}],
        },
    )
    assert response.status_code == 200

    assert "MEMBER_CHECKED_IN" not in types_for(team_setup.admin_client)


def test_repeated_reads_do_not_duplicate_notifications(
    team_setup, set_deadline, db
) -> None:
    """Lazy generation runs on every read, so dedupe has to hold."""
    set_deadline(team_setup.admin_participant, timedelta(hours=20))
    for _ in range(4):
        team_setup.admin_client.get("/api/v1/me/notifications")

    assert (
        db.query(Notification)
        .filter_by(user_id=team_setup.admin.id, type="GOALS_LOCK_TOMORROW")
        .count()
        == 1
    )


def test_marking_one_notification_read(team_setup, set_deadline) -> None:
    set_deadline(team_setup.admin_participant, timedelta(hours=20))
    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    first = body["notifications"][0]
    assert body["unread_count"] >= 1

    response = team_setup.admin_client.post(
        f"/api/v1/me/notifications/{first['id']}/read"
    )
    assert response.status_code == 200

    after = team_setup.admin_client.get("/api/v1/me/notifications").json()
    updated = next(row for row in after["notifications"] if row["id"] == first["id"])
    assert updated["read_at"] is not None
    assert after["unread_count"] == body["unread_count"] - 1


def test_marking_everything_read(team_setup, set_deadline) -> None:
    set_deadline(team_setup.admin_participant, timedelta(hours=20))
    team_setup.admin_client.get("/api/v1/me/notifications")

    team_setup.admin_client.post("/api/v1/me/notifications/read-all")

    assert (
        team_setup.admin_client.get("/api/v1/me/notifications").json()["unread_count"]
        == 0
    )


def test_another_users_notification_cannot_be_marked_read(
    team_setup, set_deadline
) -> None:
    set_deadline(team_setup.admin_participant, timedelta(hours=20))
    mine = team_setup.admin_client.get("/api/v1/me/notifications").json()[
        "notifications"
    ][0]

    response = team_setup.member_client.post(
        f"/api/v1/me/notifications/{mine['id']}/read"
    )
    assert response.status_code == 404
