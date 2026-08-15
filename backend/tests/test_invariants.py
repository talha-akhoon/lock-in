"""One active team per user, one open challenge per team.

Both are enforced twice: a service-layer 409 for a clean API error, and a
partial unique index so a race cannot slip past it. Each is tested at both
levels, because get_membership and get_participant assume a single row and
behave arbitrarily if that assumption ever breaks.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.domain import (
    Challenge,
    ChallengeStatus,
    MembershipStatus,
    TeamMember,
    TeamRole,
)


def test_creating_a_second_team_is_rejected(team_setup) -> None:
    response = team_setup.admin_client.post("/api/v1/teams", json={"name": "Another"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_IN_TEAM"


def test_redeeming_into_a_second_team_is_rejected(
    team_setup, make_user, make_team, client_factory
) -> None:
    other_admin = make_user("Other Admin")
    other_team = make_team(other_admin, name="Rivals")
    code = (
        client_factory(other_admin.id)
        .post(f"/api/v1/teams/{other_team.id}/invitations", json={"max_uses": 5})
        .json()["code"]
    )

    response = team_setup.member_client.post(
        "/api/v1/invitations/redeem", json={"code": code}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_IN_TEAM"


def test_database_rejects_a_second_active_membership(
    db, team_setup, make_user, make_team
) -> None:
    """Defence in depth: the index must hold even without the service guard."""
    other_team = make_team(make_user("Rival Admin"), name="Rivals")
    db.add(
        TeamMember(
            team_id=other_team.id,
            user_id=team_setup.member.id,
            role=TeamRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_removed_membership_does_not_block_joining_another_team(
    db, team_setup, make_user, make_team
) -> None:
    membership = db.query(TeamMember).filter_by(user_id=team_setup.member.id).one()
    membership.status = MembershipStatus.REMOVED
    db.commit()

    other_team = make_team(make_user("Rival Admin"), name="Rivals")
    db.add(
        TeamMember(
            team_id=other_team.id,
            user_id=team_setup.member.id,
            role=TeamRole.MEMBER,
        )
    )
    db.commit()

    assert (
        db.query(TeamMember)
        .filter_by(user_id=team_setup.member.id, status=MembershipStatus.ACTIVE)
        .count()
        == 1
    )


def test_creating_a_second_open_challenge_is_rejected(team_setup) -> None:
    now = datetime.now(UTC)
    response = team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/challenges",
        json={
            "name": "Overlapping",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CHALLENGE_ALREADY_OPEN"


def test_database_rejects_a_second_open_challenge(db, team_setup) -> None:
    now = datetime.now(UTC)
    db.add(
        Challenge(
            team_id=team_setup.team.id,
            name="Draft overlap",
            start_at=now,
            end_at=now + timedelta(days=30),
            timezone="Europe/London",
            goal_submission_days=5,
            forfeit_amount_pence=20000,
            status=ChallengeStatus.DRAFT,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_new_challenge_is_allowed_once_the_previous_one_is_complete(
    db, team_setup
) -> None:
    challenge = db.get(Challenge, team_setup.challenge.id)
    challenge.status = ChallengeStatus.COMPLETED
    db.commit()

    now = datetime.now(UTC)
    response = team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/challenges",
        json={
            "name": "Round two",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=90)).isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Round two"


def test_challenge_end_must_follow_its_start(team_setup, db) -> None:
    db.get(Challenge, team_setup.challenge.id).status = ChallengeStatus.COMPLETED
    db.commit()

    now = datetime.now(UTC)
    response = team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/challenges",
        json={
            "name": "Backwards",
            "start_at": now.isoformat(),
            "end_at": (now - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 422
