"""The fresh-install path: sign in, create a team, start a challenge, commit goals.

This is the sequence a first user has to be able to complete with no seed data,
so it is walked end to end rather than assembled from fixtures.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.domain import ChallengeParticipant, TeamMember, TeamRole


@pytest.fixture
def founder(make_user, client_factory):
    user = make_user("Founder")
    return user, client_factory(user.id)


def test_a_new_user_can_take_themselves_all_the_way_to_a_commitment(
    founder, db
) -> None:
    user, client = founder

    assert client.get("/api/v1/auth/me").json()["team"] is None

    team = client.post("/api/v1/teams", json={"name": "The Boys"}).json()
    assert team["name"] == "The Boys"

    membership = db.query(TeamMember).filter_by(user_id=user.id).one()
    assert membership.role == TeamRole.ADMIN

    now = datetime.now(UTC)
    challenge = client.post(
        f"/api/v1/teams/{team['id']}/challenges",
        json={
            "name": "6 Month Lock-In",
            "description": "Commit publicly.",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=184)).isoformat(),
            "forfeit_amount_pence": 20000,
        },
    ).json()
    assert challenge["status"] == "ACTIVE"
    assert challenge["day_number"] == 1
    # Counted in challenge-local dates, so a 184x24h span covers 183 or 184
    # local days depending on whether a DST change falls inside it.
    assert challenge["total_days"] in (183, 184)

    # Creating the challenge must enrol the existing members.
    participant = db.query(ChallengeParticipant).filter_by(user_id=user.id).one()
    assert participant.goals_due_at > now

    for payload in (
        {
            "category": "PHYSICAL",
            "title": "Deadlift 120kg",
            "tracking_type": "NUMERIC",
            "baseline_value": "90",
            "current_value": "90",
            "target_value": "120",
            "target_direction": "AT_LEAST",
            "unit": "kg",
        },
        {
            "category": "CAREER",
            "title": "Land a Staff role",
            "tracking_type": "MILESTONE",
        },
    ):
        assert client.post("/api/v1/me/goals", json=payload).status_code == 201

    assert client.post("/api/v1/me/goals/commit").status_code == 200

    me = client.get("/api/v1/auth/me").json()
    assert me["role"] == "ADMIN"
    assert me["goals_locked"] is True
    assert me["goals_committed_at"] is not None

    dashboard = client.get(f"/api/v1/challenges/{challenge['id']}/dashboard").json()
    assert [card["display_name"] for card in dashboard["members"]] == ["Founder"]
    assert dashboard["members"][0]["goals_committed"] == 2


def test_the_team_name_is_validated(founder) -> None:
    _user, client = founder
    assert client.post("/api/v1/teams", json={"name": "x"}).status_code == 422


def test_the_current_team_endpoint_reports_the_member_count(founder, db) -> None:
    _user, client = founder
    client.post("/api/v1/teams", json={"name": "The Boys"})

    body = client.get("/api/v1/teams/current").json()

    assert body["name"] == "The Boys"
    assert body["role"] == "ADMIN"
    assert body["member_count"] == 1


def test_a_future_challenge_starts_as_upcoming(founder) -> None:
    _user, client = founder
    team = client.post("/api/v1/teams", json={"name": "The Boys"}).json()

    now = datetime.now(UTC)
    challenge = client.post(
        f"/api/v1/teams/{team['id']}/challenges",
        json={
            "name": "Starts next month",
            "start_at": (now + timedelta(days=30)).isoformat(),
            "end_at": (now + timedelta(days=214)).isoformat(),
        },
    ).json()

    assert challenge["status"] == "UPCOMING"
    assert challenge["days_remaining"] in (213, 214)


def test_a_second_member_joining_mid_challenge_gets_their_own_deadline(
    founder, make_user, client_factory, db
) -> None:
    _user, client = founder
    team = client.post("/api/v1/teams", json={"name": "The Boys"}).json()
    now = datetime.now(UTC)
    client.post(
        f"/api/v1/teams/{team['id']}/challenges",
        json={
            "name": "6 Month Lock-In",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=184)).isoformat(),
            "goal_submission_days": 5,
        },
    )
    code = client.post(
        f"/api/v1/teams/{team['id']}/invitations", json={"max_uses": 1}
    ).json()["code"]

    joiner = make_user("Joiner")
    joiner_client = client_factory(joiner.id)
    assert (
        joiner_client.post(
            "/api/v1/invitations/redeem", json={"code": code}
        ).status_code
        == 200
    )

    participant = db.query(ChallengeParticipant).filter_by(user_id=joiner.id).one()
    assert participant.goals_due_at > now
    assert joiner_client.get("/api/v1/me/goals").json()["goals_locked"] is False
