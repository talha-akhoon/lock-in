"""PRIVATE goals must never leak a title to a teammate.

The README promises this, so it is asserted against every teammate-facing
payload rather than just the one that happened to be written first.
"""

import json

import pytest

from app.models.domain import GoalVisibility

SECRET = "Therapy every week"


@pytest.fixture
def private_goal(team_setup, make_goal):
    return make_goal(
        team_setup.member_participant,
        title=SECRET,
        description="Deeply personal detail",
        visibility=GoalVisibility.PRIVATE,
        category="PERSONAL",
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )


@pytest.fixture
def public_goal(team_setup, make_goal):
    return make_goal(team_setup.member_participant, title="Deadlift 120kg")


def teammate_payloads(client, setup) -> dict[str, object]:
    """Every response an admin can fetch that touches a teammate's goals."""
    team, challenge, member = setup.team.id, setup.challenge.id, setup.member.id
    return {
        path: client.get(path).json()
        for path in (
            f"/api/v1/teams/{team}/members/{member}",
            f"/api/v1/challenges/{challenge}/dashboard",
            f"/api/v1/challenges/{challenge}/activity",
            f"/api/v1/teams/{team}/participants",
        )
    }


def test_no_teammate_facing_payload_contains_a_private_title(
    team_setup, private_goal, public_goal
) -> None:
    team_setup.member_client.post(
        f"/api/v1/goals/{private_goal.id}/progress",
        json={"entry_date": "2026-08-14", "completed": True},
    )

    for path, payload in teammate_payloads(team_setup.admin_client, team_setup).items():
        assert SECRET not in json.dumps(payload, default=str), path


def test_a_teammate_sees_private_goals_only_as_counts(
    team_setup, private_goal, public_goal
) -> None:
    profile = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    ).json()

    titles = [goal["title"] for goal in profile["goals"]]
    assert titles == ["Deadlift 120kg"]
    assert profile["private_committed"] == 1
    assert profile["goals_committed"] == 2
    assert profile["is_self"] is False


def test_a_private_goal_still_counts_towards_progress(
    team_setup, private_goal, public_goal
) -> None:
    """Accountability survives privacy: the headline number includes everything."""
    team_setup.member_client.post(
        f"/api/v1/goals/{private_goal.id}/progress",
        json={"entry_date": "2026-08-14", "completed": True},
    )

    profile = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    ).json()

    assert profile["categories"]["PERSONAL"] == 100.0
    assert profile["private_completed"] == 1


def test_the_owner_sees_their_own_private_goal_in_full(
    team_setup, private_goal
) -> None:
    own = team_setup.member_client.get("/api/v1/me/goals").json()
    assert [goal["title"] for goal in own["goals"]] == [SECRET]

    profile = team_setup.member_client.get(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    ).json()
    assert profile["is_self"] is True
    assert [goal["title"] for goal in profile["goals"]] == [SECRET]
    assert profile["private_committed"] == 0


def test_the_activity_feed_hides_a_teammates_private_entries(
    team_setup, private_goal, public_goal
) -> None:
    for goal in (private_goal, public_goal):
        team_setup.member_client.post(
            f"/api/v1/goals/{goal.id}/progress",
            json={"entry_date": "2026-08-14", "note": "logged"},
        )

    path = f"/api/v1/challenges/{team_setup.challenge.id}/activity"
    as_teammate = team_setup.admin_client.get(path).json()
    as_owner = team_setup.member_client.get(path).json()

    assert [row["goal_title"] for row in as_teammate] == ["Deadlift 120kg"]
    assert sorted(row["goal_title"] for row in as_owner) == [
        "Deadlift 120kg",
        SECRET,
    ]


def test_a_private_sub_goal_is_redacted_from_a_visible_parent(
    team_setup, make_goal
) -> None:
    parent = make_goal(
        team_setup.member_participant,
        title="Interview ready",
        category="CAREER",
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )
    make_goal(
        team_setup.member_participant,
        parent_goal_id=parent.id,
        title=SECRET,
        visibility=GoalVisibility.PRIVATE,
    )
    make_goal(
        team_setup.member_participant,
        parent_goal_id=parent.id,
        title="Public sub-goal",
    )

    profile = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    ).json()

    children = profile["goals"][0]["children"]
    assert [child["title"] for child in children] == ["Public sub-goal"]
    assert profile["private_committed"] == 1


def test_mcp_teammate_tools_hide_private_titles(
    team_setup, private_goal, public_goal, db
) -> None:
    """The MCP path uses the same redaction as the HTTP profile and feed."""
    from app.mcp import tools

    team_setup.member_client.post(
        f"/api/v1/goals/{private_goal.id}/progress",
        json={"entry_date": "2026-08-14", "completed": True},
    )
    db.expire_all()

    payloads = {
        "standings": tools.get_team_standings(db, team_setup.admin),
        "member": tools.get_member_progress(
            db, team_setup.admin, user_id=team_setup.member.id
        ),
        "activity": tools.get_activity(db, team_setup.admin),
    }
    for path, payload in payloads.items():
        assert SECRET not in json.dumps(payload, default=str), path


def test_a_completion_notification_is_not_sent_for_a_private_goal(
    team_setup, private_goal
) -> None:
    team_setup.member_client.post(
        f"/api/v1/goals/{private_goal.id}/progress",
        json={"entry_date": "2026-08-14", "completed": True},
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    titles = [row["title"] for row in body["notifications"]]
    bodies = [row["body"] for row in body["notifications"]]

    assert not any("completed a goal" in title for title in titles)
    assert SECRET not in bodies


def test_a_checkin_notification_does_not_name_a_private_goal(
    team_setup, private_goal
) -> None:
    from app.services.clock import challenge_today

    today = challenge_today(team_setup.challenge).isoformat()
    team_setup.member_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [{"goal_id": str(private_goal.id), "completed": True}],
        },
    )

    body = team_setup.admin_client.get("/api/v1/me/notifications").json()
    checkins = [
        row for row in body["notifications"] if row["type"] == "MEMBER_CHECKED_IN"
    ]
    assert len(checkins) == 1
    assert SECRET not in checkins[0]["title"]
    assert SECRET not in (checkins[0]["body"] or "")
    types = [row["type"] for row in body["notifications"]]
    assert "MEMBER_COMPLETED_GOAL" not in types
