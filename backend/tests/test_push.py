"""Web Push subscriptions and fan-out when a teammate logs or finishes a goal."""

from pywebpush import WebPushException

from app.models.domain import PushSubscription

ENDPOINT = "https://push.example.com/subscription/abc"
KEYS = {"p256dh": "B" + "x" * 86, "auth": "a" * 22}


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.reason = "Gone" if status_code == 410 else "OK"
        self.text = ""


def test_push_config_returns_a_vapid_public_key(team_setup) -> None:
    body = team_setup.admin_client.get("/api/v1/me/push/config").json()

    assert body["enabled"] is True
    assert len(body["public_key"]) > 20
    # Uncompressed P-256 point, URL-safe, no padding.
    assert "+" not in body["public_key"]
    assert "/" not in body["public_key"]
    assert "=" not in body["public_key"]


def test_an_anonymous_caller_cannot_read_push_config(anon) -> None:
    assert anon.get("/api/v1/me/push/config").status_code == 401


def test_a_member_can_subscribe_and_unsubscribe(team_setup, db) -> None:
    created = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    assert created.status_code == 201
    assert created.json()["endpoint"] == ENDPOINT
    assert db.query(PushSubscription).count() == 1

    again = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": {**KEYS, "auth": "b" * 22}},
    )
    assert again.status_code == 201
    assert db.query(PushSubscription).count() == 1
    assert db.query(PushSubscription).one().auth == "b" * 22

    gone = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions/unsubscribe",
        json={"endpoint": ENDPOINT},
    )
    assert gone.json() == {"removed": True}
    assert db.query(PushSubscription).count() == 0


def test_a_device_moves_to_whoever_is_signed_in(team_setup, db) -> None:
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    team_setup.member_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )

    row = db.query(PushSubscription).one()
    assert row.user_id == team_setup.member.id


def test_http_push_endpoints_are_rejected(team_setup) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": "http://evil.example/push", "keys": KEYS},
    )
    assert response.status_code == 422


def test_a_local_http_endpoint_is_allowed(team_setup) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": "http://127.0.0.1:8000/push", "keys": KEYS},
    )
    assert response.status_code == 201


def test_unsubscribing_an_unknown_endpoint_is_a_noop(team_setup) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions/unsubscribe",
        json={"endpoint": ENDPOINT},
    )
    assert response.json() == {"removed": False}


def test_a_push_failure_does_not_roll_back_the_checkin(
    team_setup, make_goal, monkeypatch, db
) -> None:
    from app.services.clock import challenge_today

    def fake_webpush(**kwargs):
        raise RuntimeError("push network down")

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    goal = make_goal(team_setup.member_participant)
    today = challenge_today(team_setup.challenge).isoformat()
    response = team_setup.member_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [{"goal_id": str(goal.id), "numeric_value": "100"}],
        },
    )
    assert response.status_code == 200
    assert "MEMBER_CHECKED_IN" in [
        row["type"]
        for row in team_setup.admin_client.get("/api/v1/me/notifications").json()[
            "notifications"
        ]
    ]
    assert db.query(PushSubscription).count() == 1


def test_a_non_gone_push_error_keeps_the_subscription(
    team_setup, make_goal, monkeypatch, db
) -> None:
    def fake_webpush(**kwargs):
        raise WebPushException("nope", response=_Response(500))

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    goal = make_goal(team_setup.member_participant)
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    )
    assert db.query(PushSubscription).count() == 1


def test_an_mcp_token_cannot_manage_push_subscriptions(team_setup, db, anon) -> None:
    from app.services.mcp_tokens import mint

    _row, raw = mint(db, user_id=team_setup.admin.id, name="Cursor")
    db.commit()
    response = anon.get(
        "/api/v1/me/push/config",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 401


def test_completing_a_goal_sends_web_push(team_setup, make_goal, monkeypatch) -> None:
    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        return _Response(201)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    goal = make_goal(team_setup.member_participant, title="Deadlift 120kg")
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    )

    assert len(sent) == 1
    assert "Teammate completed a goal" in sent[0]["data"]
    assert "Teammate logged progress" not in sent[0]["data"]
    assert "Deadlift 120kg" in sent[0]["data"]


def test_a_checkin_sends_web_push(team_setup, make_goal, monkeypatch) -> None:
    from app.services.clock import challenge_today

    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        return _Response(201)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    goal = make_goal(team_setup.member_participant)
    today = challenge_today(team_setup.challenge).isoformat()
    team_setup.member_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "note": "Graft",
            "updates": [{"goal_id": str(goal.id), "numeric_value": "100"}],
        },
    )

    assert len(sent) == 1
    assert "Teammate logged progress" in sent[0]["data"]
    assert "Deadlift 120kg" in sent[0]["data"]


def test_a_gone_subscription_is_dropped(team_setup, make_goal, monkeypatch, db) -> None:
    def fake_webpush(**kwargs):
        raise WebPushException("gone", response=_Response(410))

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    goal = make_goal(team_setup.member_participant)
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "120"},
    )

    assert db.query(PushSubscription).count() == 0


def test_the_actor_does_not_receive_push_for_their_own_checkin(
    team_setup, make_goal, monkeypatch
) -> None:
    from decimal import Decimal

    from app.services.clock import challenge_today

    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        return _Response(201)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.member_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    # Admin stays ahead so this log is not also a rank change for the actor.
    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    goal = make_goal(team_setup.member_participant)
    today = challenge_today(team_setup.challenge).isoformat()
    team_setup.member_client.post(
        "/api/v1/me/checkins",
        json={
            "date": today,
            "updates": [{"goal_id": str(goal.id), "numeric_value": "100"}],
        },
    )

    assert sent == []


def test_a_rank_change_sends_web_push(team_setup, make_goal, monkeypatch) -> None:
    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        return _Response(201)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
    make_goal(team_setup.admin_participant)
    goal = make_goal(team_setup.member_participant)
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "105"},
    )

    payloads = [item["data"] for item in sent]
    assert any("You dropped to #2" in data for data in payloads)


def test_two_progress_logs_send_two_pushes(team_setup, make_goal, monkeypatch) -> None:
    from decimal import Decimal

    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        return _Response(201)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={"endpoint": ENDPOINT, "keys": KEYS},
    )
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

    assert len(sent) == 2
    assert all("Teammate logged progress" in item["data"] for item in sent)
