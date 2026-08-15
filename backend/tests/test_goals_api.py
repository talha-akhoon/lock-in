"""Goal creation across all four tracking types, sub-goals, and the dashboard."""

from decimal import Decimal

import pytest

MILESTONE = {
    "category": "CAREER",
    "title": "Land a Staff role",
    "tracking_type": "MILESTONE",
}
NUMERIC = {
    "category": "PHYSICAL",
    "title": "Deadlift 120kg",
    "tracking_type": "NUMERIC",
    "baseline_value": "90",
    "current_value": "90",
    "target_value": "120",
    "target_direction": "AT_LEAST",
    "unit": "kg",
}
COUNT = {
    "category": "RELIGIOUS",
    "title": "Read scripture 5 times",
    "tracking_type": "COUNT",
    "target_value": "5",
    "unit": "completions",
}
MANUAL = {
    "category": "BUSINESS",
    "title": "Ship the prototype",
    "tracking_type": "MANUAL",
    "manual_progress_percentage": 0,
}


@pytest.mark.parametrize(
    "payload", [MILESTONE, NUMERIC, COUNT, MANUAL], ids=lambda p: p["tracking_type"]
)
def test_each_tracking_type_can_be_created(team_setup, payload) -> None:
    response = team_setup.admin_client.post("/api/v1/me/goals", json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["title"] == payload["title"]


def test_a_count_goal_gets_a_zero_baseline_and_at_least_direction(team_setup) -> None:
    body = team_setup.admin_client.post("/api/v1/me/goals", json=COUNT).json()

    assert Decimal(body["baseline_value"]) == 0
    assert body["target_direction"] == "AT_LEAST"


def test_a_count_goal_can_start_from_an_existing_total(team_setup) -> None:
    body = team_setup.admin_client.post(
        "/api/v1/me/goals",
        json={**COUNT, "baseline_value": "2", "current_value": "2"},
    ).json()

    assert Decimal(body["baseline_value"]) == 0
    assert Decimal(body["current_value"]) == Decimal(2)
    assert body["progress_percentage"] == pytest.approx(40.0)


def test_a_milestone_goal_has_no_numeric_fields(team_setup) -> None:
    body = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()

    assert body["baseline_value"] is None
    assert body["target_value"] is None
    assert body["target_direction"] is None


def test_a_numeric_goal_without_a_target_is_rejected(team_setup) -> None:
    payload = {**NUMERIC}
    payload.pop("target_value")
    response = team_setup.admin_client.post("/api/v1/me/goals", json=payload)
    assert response.status_code == 422


def test_a_count_goal_needs_a_positive_target(team_setup) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**COUNT, "target_value": "0"}
    )
    assert response.status_code == 422


def test_a_sub_goal_can_be_nested_one_level(team_setup) -> None:
    parent = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()

    child = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": parent["id"]}
    )

    assert child.status_code == 201
    tree = team_setup.admin_client.get("/api/v1/me/goals").json()["goals"]
    assert len(tree) == 1
    assert [c["title"] for c in tree[0]["children"]] == ["Deadlift 120kg"]


def test_a_sub_goal_takes_its_parents_category(team_setup) -> None:
    parent = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()

    child = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": parent["id"]}
    ).json()

    assert parent["category"] == "CAREER"
    assert NUMERIC["category"] == "PHYSICAL"
    assert child["category"] == "CAREER"


def test_nesting_deeper_than_one_level_is_rejected(team_setup) -> None:
    parent = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()
    child = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": parent["id"]}
    ).json()

    grandchild = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**COUNT, "parent_goal_id": child["id"]}
    )

    assert grandchild.status_code == 422


def test_a_parent_goal_from_another_member_is_not_found(team_setup, make_goal) -> None:
    theirs = make_goal(team_setup.member_participant)

    response = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": str(theirs.id)}
    )
    assert response.status_code == 404


def test_a_parent_reports_the_mean_of_its_required_children(team_setup) -> None:
    parent = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()
    first = team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": parent["id"]}
    ).json()
    team_setup.admin_client.post(
        "/api/v1/me/goals",
        json={**MANUAL, "parent_goal_id": parent["id"], "required": False},
    )

    team_setup.admin_client.post(
        f"/api/v1/goals/{first['id']}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "105"},
    )

    tree = team_setup.admin_client.get("/api/v1/me/goals").json()["goals"]
    assert tree[0]["progress_percentage"] == 50.0


def test_progress_history_is_returned_newest_first(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.admin_participant)
    for day, value in (("2026-08-12", "95"), ("2026-08-13", "100")):
        team_setup.admin_client.post(
            f"/api/v1/goals/{goal.id}/progress",
            json={"entry_date": day, "numeric_value": value},
        )

    body = team_setup.admin_client.get(f"/api/v1/goals/{goal.id}/progress").json()

    assert [row["entry_date"] for row in body["entries"]] == [
        "2026-08-13",
        "2026-08-12",
    ]
    assert body["goal"]["current_value"] is not None


def test_a_goal_can_be_deleted_before_the_lock(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.admin_participant)

    assert team_setup.admin_client.delete(f"/api/v1/goals/{goal.id}").status_code == 204
    assert team_setup.admin_client.get("/api/v1/me/goals").json()["goals"] == []


def test_deleting_a_parent_removes_its_children(team_setup) -> None:
    parent = team_setup.admin_client.post("/api/v1/me/goals", json=MILESTONE).json()
    team_setup.admin_client.post(
        "/api/v1/me/goals", json={**NUMERIC, "parent_goal_id": parent["id"]}
    )

    team_setup.admin_client.delete(f"/api/v1/goals/{parent['id']}")

    assert team_setup.admin_client.get("/api/v1/me/goals").json()["goals"] == []


def test_reaching_the_target_completes_a_goal(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.admin_participant)

    body = team_setup.admin_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    ).json()

    assert body["goal"]["progress_percentage"] == 100.0
    assert body["goal"]["completed_at"] is not None


def test_a_decreasing_goal_measures_downwards(team_setup, make_goal) -> None:
    goal = make_goal(
        team_setup.admin_participant,
        title="Reach 75kg",
        baseline_value=Decimal(82),
        current_value=Decimal(82),
        target_value=Decimal(75),
        target_direction="AT_MOST",
    )

    body = team_setup.admin_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "78"},
    ).json()

    assert body["goal"]["progress_percentage"] == 57.1


def test_the_dashboard_ranks_members_and_flags_missing_submissions(
    team_setup, make_goal
) -> None:
    make_goal(team_setup.admin_participant, current_value=Decimal(120))

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/dashboard"
    ).json()
    by_name = {card["display_name"]: card for card in body["members"]}

    assert [card["display_name"] for card in body["members"]] == ["Admin", "Teammate"]
    assert by_name["Admin"]["goals_submitted"] is True
    assert by_name["Admin"]["is_self"] is True
    assert by_name["Teammate"]["goals_submitted"] is False
    assert by_name["Teammate"]["overall_progress"] == 0
    assert body["team_progress"] == 100.0


def test_the_dashboard_never_includes_goal_titles(team_setup, make_goal) -> None:
    """Cards are aggregate-only by design, for every member including yourself."""
    import json

    make_goal(team_setup.admin_participant, title="Deadlift 120kg")

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/dashboard"
    ).json()

    assert "Deadlift 120kg" not in json.dumps(body)
