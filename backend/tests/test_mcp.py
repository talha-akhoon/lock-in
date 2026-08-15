"""Personal access tokens, Bearer auth, and MCP tool privacy."""

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.mcp import tools
from app.models.domain import GoalVisibility, McpToken
from app.schemas.domain import CheckinUpdate

SECRET = "Therapy every week"


def _mint(client, name: str = "Claude") -> dict:
    response = client.post("/api/v1/me/mcp-tokens", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_mcp_token_is_shown_once_and_only_the_hash_is_stored(team_setup, db) -> None:
    body = _mint(team_setup.admin_client)

    assert body["token"].startswith("lin_")
    assert body["prefix"] == body["token"][:12]
    stored = db.get(McpToken, body["id"])
    assert stored is not None
    assert body["token"] not in stored.token_hash
    assert stored.token_hash.startswith("$2b$")

    listed = team_setup.admin_client.get("/api/v1/me/mcp-tokens").json()
    assert listed[0]["prefix"] == body["prefix"]
    assert "token" not in listed[0]
    assert "token_hash" not in listed[0]


def test_bearer_token_authenticates_the_rest_api(team_setup, app) -> None:
    raw = _mint(team_setup.admin_client)["token"]
    client = TestClient(app, headers={"Authorization": f"Bearer {raw}"})

    body = client.get("/api/v1/auth/me").json()
    assert body["user"]["id"] == str(team_setup.admin.id)


def test_invalid_and_revoked_tokens_are_rejected(team_setup, app) -> None:
    created = _mint(team_setup.admin_client)
    client = TestClient(app, headers={"Authorization": "Bearer lin_notarealtokenvalue"})
    assert client.get("/api/v1/auth/me").status_code == 401

    team_setup.admin_client.delete(f"/api/v1/me/mcp-tokens/{created['id']}")
    revoked = TestClient(app, headers={"Authorization": f"Bearer {created['token']}"})
    assert revoked.get("/api/v1/auth/me").status_code == 401


def test_a_token_cannot_mint_or_list_tokens(team_setup, app) -> None:
    raw = _mint(team_setup.admin_client)["token"]
    client = TestClient(app, headers={"Authorization": f"Bearer {raw}"})

    assert client.get("/api/v1/me/mcp-tokens").status_code == 401
    assert (
        client.post("/api/v1/me/mcp-tokens", json={"name": "Nope"}).status_code == 401
    )


def test_bearer_skips_csrf_on_a_checkin(team_setup, app, make_goal) -> None:
    from app.services.checkins import challenge_today

    goal = make_goal(
        team_setup.admin_participant,
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )
    raw = _mint(team_setup.admin_client)["token"]
    client = TestClient(app, headers={"Authorization": f"Bearer {raw}"})

    response = client.post(
        "/api/v1/me/checkins",
        json={
            "date": challenge_today(team_setup.challenge).isoformat(),
            "note": "via token",
            "updates": [{"goal_id": str(goal.id), "completed": True}],
        },
    )
    assert response.status_code == 200, response.text


def test_mcp_http_requires_a_bearer_token(app) -> None:
    with TestClient(app) as client:
        response = client.post("/mcp")
        assert response.status_code == 401
        challenge = response.headers["www-authenticate"]
        assert 'error="invalid_token"' in challenge
        assert "resource_metadata=" in challenge
        assert (
            client.post(
                "/mcp", headers={"Authorization": "Bearer lin_nope"}
            ).status_code
            == 401
        )


def test_mcp_http_accepts_a_valid_token(team_setup, app) -> None:
    raw = _mint(team_setup.admin_client)["token"]
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {raw}"},
            json={},
        )
    assert response.status_code != 401


def test_team_tools_reject_a_user_with_no_team(client_factory, make_user, db) -> None:
    user = make_user()
    with pytest.raises(HTTPException) as exc:
        tools.get_team_standings(db, user)
    assert exc.value.status_code == 403


def test_log_checkin_cannot_update_another_members_goal(
    team_setup, make_goal, db
) -> None:
    admin_goal = make_goal(
        team_setup.admin_participant,
        tracking_type="MILESTONE",
        baseline_value=None,
        target_value=None,
        current_value=None,
        target_direction=None,
    )
    with pytest.raises(HTTPException) as exc:
        tools.log_checkin(
            db,
            team_setup.member,
            updates=[CheckinUpdate(goal_id=admin_goal.id, completed=True)],
        )
    assert exc.value.status_code == 404


def test_mcp_tools_never_leak_a_teammates_private_goal(
    team_setup, make_goal, db
) -> None:
    make_goal(team_setup.member_participant, title="Deadlift 120kg")
    private = make_goal(
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
    team_setup.member_client.post(
        f"/api/v1/goals/{private.id}/progress",
        json={"entry_date": "2026-08-14", "completed": True, "note": SECRET},
    )
    db.expire_all()

    payloads = {
        "standings": tools.get_team_standings(db, team_setup.admin),
        "member": tools.get_member_progress(
            db, team_setup.admin, user_id=team_setup.member.id
        ),
        "named": tools.get_member_progress(
            db, team_setup.admin, display_name="Teammate"
        ),
        "activity": tools.get_activity(db, team_setup.admin),
        "context": tools.get_context(db, team_setup.admin),
    }
    for name, payload in payloads.items():
        assert SECRET not in json.dumps(payload, default=str), name

    profile = payloads["member"]
    assert [goal["title"] for goal in profile["goals"]] == ["Deadlift 120kg"]
    assert profile["private_committed"] == 1
    assert profile["is_self"] is False
    assert "email" not in profile["user"]

    own = tools.get_my_goals(db, team_setup.member)
    assert SECRET in json.dumps(own, default=str)
    assert "email" not in tools.get_context(db, team_setup.member)["user"]
