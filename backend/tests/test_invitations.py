"""Invitation codes: hashing, expiry, use limits, revocation and re-redemption."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.domain import (
    ChallengeParticipant,
    Invitation,
    MembershipStatus,
    TeamMember,
)


@pytest.fixture
def invite(team_setup):
    def make(**payload):
        response = team_setup.admin_client.post(
            f"/api/v1/teams/{team_setup.team.id}/invitations",
            json={"max_uses": 1, **payload},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return make


@pytest.fixture
def outsider(make_user, client_factory):
    user = make_user("Outsider")
    return user, client_factory(user.id)


def test_only_the_hash_is_stored(invite, db) -> None:
    body = invite()
    stored = db.get(Invitation, body["id"])

    assert body["code"] not in stored.code_hash
    assert stored.code_hash.startswith("$2b$")
    assert stored.code_prefix == body["code"].split("-")[0]


def test_redeeming_joins_the_team_and_the_open_challenge(
    invite, outsider, db, team_setup
) -> None:
    _user, client = outsider
    code = invite()["code"]

    response = client.post("/api/v1/invitations/redeem", json={"code": code})

    assert response.status_code == 200
    assert response.json()["team_id"] == str(team_setup.team.id)
    membership = db.query(TeamMember).filter_by(user_id=_user.id).one()
    assert membership.status == MembershipStatus.ACTIVE
    assert db.query(ChallengeParticipant).filter_by(user_id=_user.id).count() == 1


def test_the_use_count_increments(invite, outsider, db) -> None:
    body = invite(max_uses=5)
    _user, client = outsider
    client.post("/api/v1/invitations/redeem", json={"code": body["code"]})

    db.expire_all()
    assert db.get(Invitation, body["id"]).use_count == 1


def test_an_exhausted_invitation_is_refused(
    invite, outsider, make_user, client_factory
) -> None:
    code = invite(max_uses=1)["code"]
    _first, first_client = outsider
    first_client.post("/api/v1/invitations/redeem", json={"code": code})

    second_client = client_factory(make_user("Second").id)
    response = second_client.post("/api/v1/invitations/redeem", json={"code": code})

    assert response.status_code == 400
    assert "already been used" in response.json()["detail"]


def test_an_expired_invitation_is_refused(invite, outsider) -> None:
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    code = invite(expires_at=past)["code"]
    _user, client = outsider

    response = client.post("/api/v1/invitations/redeem", json={"code": code})

    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_a_revoked_invitation_is_refused(invite, outsider, team_setup) -> None:
    body = invite()
    team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/invitations/{body['id']}"
    )
    _user, client = outsider

    response = client.post("/api/v1/invitations/redeem", json={"code": body["code"]})

    assert response.status_code == 400
    assert "Invalid invitation" in response.json()["detail"]


def test_an_unknown_code_is_refused(outsider) -> None:
    _user, client = outsider
    response = client.post("/api/v1/invitations/redeem", json={"code": "ZZZZ-ZZZZ"})
    assert response.status_code == 400


def test_a_malformed_code_is_rejected_by_validation(outsider) -> None:
    _user, client = outsider
    assert (
        client.post("/api/v1/invitations/redeem", json={"code": "nope"}).status_code
        == 422
    )


def test_redeeming_twice_is_a_no_op_for_the_same_user(invite, outsider, db) -> None:
    code = invite(max_uses=5)["code"]
    _user, client = outsider

    first = client.post("/api/v1/invitations/redeem", json={"code": code})
    second = client.post("/api/v1/invitations/redeem", json={"code": code})

    assert first.status_code == 200
    assert second.status_code == 200
    assert db.query(TeamMember).filter_by(user_id=_user.id).count() == 1


def test_a_removed_member_cannot_redeem_their_way_back_in(
    invite, outsider, team_setup, db
) -> None:
    code = invite(max_uses=5)["code"]
    user, client = outsider
    client.post("/api/v1/invitations/redeem", json={"code": code})

    team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/members/{user.id}"
    )

    response = client.post("/api/v1/invitations/redeem", json={"code": code})
    assert response.status_code == 403
    assert "removed" in response.json()["detail"]


def test_listing_invitations_never_exposes_a_code(invite, team_setup) -> None:
    invite()
    rows = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/invitations"
    ).json()

    assert len(rows) == 1
    assert "code" not in rows[0]
    assert "code_hash" not in rows[0]
    assert rows[0]["code_prefix"]


def test_revoking_an_unknown_invitation_is_not_found(team_setup) -> None:
    import uuid

    response = team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/invitations/{uuid.uuid4()}"
    )
    assert response.status_code == 404


def test_a_new_member_gets_a_local_midnight_goal_deadline(
    invite, outsider, db, team_setup
) -> None:
    from zoneinfo import ZoneInfo

    code = invite()["code"]
    user, client = outsider
    client.post("/api/v1/invitations/redeem", json={"code": code})

    participant = db.query(ChallengeParticipant).filter_by(user_id=user.id).one()
    local = participant.goals_due_at.astimezone(ZoneInfo(team_setup.challenge.timezone))
    assert (local.hour, local.minute, local.second) == (0, 0, 0)
