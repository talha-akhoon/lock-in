"""Hourly nudges, mute preferences, and the dispatch endpoint's HMAC gate."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.api.v1.routes.internal import dispatch_hmac_token
from app.models.domain import (
    Challenge,
    ChallengeParticipant,
    ChallengeStatus,
    DailyCheckin,
    Notification,
    NotificationType,
    User,
)
from app.services import notification_dispatch
from app.services.clock import as_utc

LONDON = ZoneInfo("Europe/London")
WED_EVENING = datetime(2026, 8, 19, 21, 0, tzinfo=LONDON)
SUN_EVENING = datetime(2026, 8, 16, 21, 0, tzinfo=LONDON)
WED_MORNING = datetime(2026, 8, 19, 10, 0, tzinfo=LONDON)


def align_challenge(db, challenge, now, *, started_days_ago=10, days=184):
    row = db.get(Challenge, challenge.id)
    moment = as_utc(now)
    row.start_at = moment - timedelta(days=started_days_ago)
    row.end_at = row.start_at + timedelta(days=days)
    row.status = ChallengeStatus.ACTIVE
    db.commit()
    return row


def types_in(db, user_id) -> list[str]:
    return [
        row.type.value if hasattr(row.type, "value") else row.type
        for row in db.query(Notification).filter_by(user_id=user_id).all()
    ]


def add_checkin(db, participant, day):
    db.add(
        DailyCheckin(
            challenge_participant_id=participant.id,
            checkin_date=day,
        )
    )
    db.commit()


def test_dispatch_without_a_token_is_rejected(anon) -> None:
    assert anon.post("/api/v1/internal/notifications/dispatch").status_code == 401


def test_dispatch_with_a_bad_hmac_is_rejected(anon) -> None:
    assert (
        anon.post(
            "/api/v1/internal/notifications/dispatch",
            headers={"X-LockIn-Dispatch": "0" * 64},
        ).status_code
        == 401
    )


def test_dispatch_with_a_valid_hmac_runs(
    anon, team_setup, make_goal, db, monkeypatch
) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    monkeypatch.setattr(
        "app.services.notification_dispatch.utcnow", lambda: as_utc(WED_EVENING)
    )
    response = anon.post(
        "/api/v1/internal/notifications/dispatch",
        headers={"X-LockIn-Dispatch": dispatch_hmac_token()},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    db.expire_all()
    assert NotificationType.CHECKIN_DUE.value in types_in(db, team_setup.admin.id)


def test_evening_without_a_checkin_sends_due(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.CHECKIN_DUE.value in types_in(db, team_setup.admin.id)
    assert NotificationType.STREAK_AT_RISK.value not in types_in(
        db, team_setup.admin.id
    )


def test_morning_does_not_send_a_due_nudge(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, WED_MORNING)
    notification_dispatch.run(db, now=WED_MORNING)

    assert NotificationType.CHECKIN_DUE.value not in types_in(db, team_setup.admin.id)


def test_a_checkin_today_suppresses_the_due_nudge(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    add_checkin(db, team_setup.admin_participant, WED_EVENING.date())
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.CHECKIN_DUE.value not in types_in(db, team_setup.admin.id)


def test_a_live_streak_becomes_streak_at_risk(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    today = WED_EVENING.date()
    add_checkin(db, team_setup.admin_participant, today - timedelta(days=1))
    add_checkin(db, team_setup.admin_participant, today - timedelta(days=2))
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.STREAK_AT_RISK.value in types_in(db, team_setup.admin.id)
    assert NotificationType.CHECKIN_DUE.value not in types_in(db, team_setup.admin.id)


def test_a_quiet_member_is_announced_to_the_team(team_setup, make_goal, db) -> None:
    make_goal(team_setup.member_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    last = WED_EVENING.date() - timedelta(days=4)
    add_checkin(db, team_setup.member_participant, last)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.MEMBER_QUIET.value in types_in(db, team_setup.admin.id)
    assert NotificationType.MEMBER_QUIET.value not in types_in(db, team_setup.member.id)
    row = (
        db.query(Notification)
        .filter_by(user_id=team_setup.admin.id, type=NotificationType.MEMBER_QUIET)
        .one()
    )
    assert row.title == "Teammate has gone quiet"
    assert "Therapy" not in (row.body or "")


def test_quiet_does_not_repeat_until_they_check_in_again(
    team_setup, make_goal, db
) -> None:
    make_goal(team_setup.member_participant)
    align_challenge(db, team_setup.challenge, WED_EVENING)
    add_checkin(
        db, team_setup.member_participant, WED_EVENING.date() - timedelta(days=4)
    )
    notification_dispatch.run(db, now=WED_EVENING)
    notification_dispatch.run(db, now=WED_EVENING + timedelta(days=1))

    assert (
        db.query(Notification)
        .filter_by(user_id=team_setup.admin.id, type=NotificationType.MEMBER_QUIET)
        .count()
        == 1
    )


def test_sunday_evening_pace_nudge(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    align_challenge(db, team_setup.challenge, SUN_EVENING, started_days_ago=20, days=30)
    notification_dispatch.run(db, now=SUN_EVENING)

    assert NotificationType.PACE_BEHIND.value in types_in(db, team_setup.admin.id)
    row = (
        db.query(Notification)
        .filter_by(user_id=team_setup.admin.id, type=NotificationType.PACE_BEHIND)
        .one()
    )
    assert "Deadlift 120kg" in (row.body or "")


def test_optional_goals_do_not_trigger_pace(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant, required=False)
    align_challenge(db, team_setup.challenge, SUN_EVENING, started_days_ago=20, days=30)
    notification_dispatch.run(db, now=SUN_EVENING)

    assert NotificationType.PACE_BEHIND.value not in types_in(db, team_setup.admin.id)


def test_dispatch_promotes_lock_tomorrow_to_a_stored_row(team_setup, db) -> None:
    participant = db.get(ChallengeParticipant, team_setup.admin_participant.id)
    participant.goals_due_at = as_utc(WED_EVENING) + timedelta(hours=20)
    participant.goals_locked_at = None
    db.commit()
    align_challenge(db, team_setup.challenge, WED_EVENING, started_days_ago=1)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.GOALS_LOCK_TOMORROW.value in types_in(
        db, team_setup.admin.id
    )


def test_muting_a_type_skips_the_bell_and_push(
    team_setup, make_goal, monkeypatch, db
) -> None:
    sent: list[dict] = []

    def fake_webpush(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr("app.services.push.webpush", fake_webpush)
    team_setup.admin_client.post(
        "/api/v1/me/push/subscriptions",
        json={
            "endpoint": "https://push.example.com/subscription/mute",
            "keys": {"p256dh": "B" + "x" * 86, "auth": "a" * 22},
        },
    )
    admin = db.get(User, team_setup.admin.id)
    admin.muted_notification_types = [NotificationType.MEMBER_CHECKED_IN.value]
    db.commit()

    goal = make_goal(team_setup.member_participant, title="LeetCode problems")
    team_setup.member_client.post(
        f"/api/v1/goals/{goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "91"},
    )

    assert NotificationType.MEMBER_CHECKED_IN.value not in types_in(
        db, team_setup.admin.id
    )
    assert sent == []


def test_muting_checkin_due_skips_the_evening_nudge(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)
    admin = db.get(User, team_setup.admin.id)
    admin.muted_notification_types = [NotificationType.CHECKIN_DUE.value]
    db.commit()
    align_challenge(db, team_setup.challenge, WED_EVENING)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.CHECKIN_DUE.value not in types_in(db, team_setup.admin.id)


def test_preferences_round_trip(team_setup) -> None:
    body = team_setup.admin_client.get("/api/v1/me/notification-preferences").json()
    types = [item["type"] for item in body["types"]]
    assert "CHECKIN_DUE" in types
    assert "MEMBER_CHECKED_IN" in types
    assert body["muted_types"] == []

    updated = team_setup.admin_client.put(
        "/api/v1/me/notification-preferences",
        json={"muted_types": ["MEMBER_JOINED", "CHECKIN_DUE"]},
    )
    assert updated.status_code == 200
    assert updated.json()["muted_types"] == ["MEMBER_JOINED", "CHECKIN_DUE"]


def test_unknown_mute_types_are_rejected(team_setup) -> None:
    response = team_setup.admin_client.put(
        "/api/v1/me/notification-preferences",
        json={"muted_types": ["NOT_A_TYPE"]},
    )
    assert response.status_code == 422


def test_an_mcp_token_cannot_read_preferences(team_setup, db, anon) -> None:
    from app.services.mcp_tokens import mint

    _row, raw = mint(db, user_id=team_setup.admin.id, name="Cursor")
    db.commit()
    response = anon.get(
        "/api/v1/me/notification-preferences",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 401


def test_a_solo_member_does_not_get_a_quiet_ping(
    make_user, make_team, make_challenge, make_participant, make_goal, db
) -> None:
    admin = make_user("Solo")
    team = make_team(admin)
    challenge = make_challenge(team)
    participant = make_participant(challenge, admin)
    make_goal(participant)
    align_challenge(db, challenge, WED_EVENING)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.MEMBER_QUIET.value not in types_in(db, admin.id)


def test_no_goal_means_no_due_nudge(team_setup, db) -> None:
    align_challenge(db, team_setup.challenge, WED_EVENING)
    notification_dispatch.run(db, now=WED_EVENING)

    assert NotificationType.CHECKIN_DUE.value not in types_in(db, team_setup.admin.id)
