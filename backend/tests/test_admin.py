"""Admin operations and the audit trail behind them."""

from datetime import UTC, datetime, timedelta

from app.models.domain import ChallengeParticipant, MembershipStatus, TeamMember
from app.services import audit


def actions(client, team_id) -> list[str]:
    logs = client.get(f"/api/v1/teams/{team_id}/audit-logs").json()
    return [row["action"] for row in logs]


def test_removing_a_member_deactivates_their_participation(team_setup, db) -> None:
    response = team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    )

    assert response.status_code == 204
    db.expire_all()
    membership = db.query(TeamMember).filter_by(user_id=team_setup.member.id).one()
    participant = db.get(ChallengeParticipant, team_setup.member_participant.id)
    assert membership.status == MembershipStatus.REMOVED
    assert participant.status.value == "REMOVED"


def test_a_removed_member_disappears_from_the_member_list(team_setup) -> None:
    team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}"
    )

    rows = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/members"
    ).json()
    assert [row["display_name"] for row in rows] == ["Admin"]


def test_an_admin_cannot_remove_themselves(team_setup) -> None:
    response = team_setup.admin_client.delete(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.admin.id}"
    )
    assert response.status_code == 422


def test_the_last_admin_cannot_be_demoted(team_setup) -> None:
    """Otherwise a team locks itself out of its own admin screens."""
    team_setup.admin_client.patch(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}",
        json={"role": "ADMIN"},
    )
    team_setup.admin_client.patch(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}",
        json={"role": "MEMBER"},
    )

    response = team_setup.admin_client.patch(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.admin.id}",
        json={"role": "MEMBER"},
    )
    assert response.status_code == 422


def test_promoting_a_member_grants_admin_routes(team_setup) -> None:
    assert (
        team_setup.member_client.get(
            f"/api/v1/teams/{team_setup.team.id}/audit-logs"
        ).status_code
        == 403
    )

    team_setup.admin_client.patch(
        f"/api/v1/teams/{team_setup.team.id}/members/{team_setup.member.id}",
        json={"role": "ADMIN"},
    )

    assert (
        team_setup.member_client.get(
            f"/api/v1/teams/{team_setup.team.id}/audit-logs"
        ).status_code
        == 200
    )


def test_an_admin_can_amend_the_challenge(team_setup) -> None:
    new_end = (datetime.now(UTC) + timedelta(days=200)).isoformat()

    response = team_setup.admin_client.patch(
        f"/api/v1/challenges/{team_setup.challenge.id}",
        json={"end_at": new_end, "forfeit_amount_pence": 30000},
    )

    assert response.status_code == 200
    assert response.json()["forfeit_amount_pence"] == 30000


def test_challenge_dates_must_stay_ordered(team_setup) -> None:
    past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    response = team_setup.admin_client.patch(
        f"/api/v1/challenges/{team_setup.challenge.id}", json={"end_at": past}
    )
    assert response.status_code == 422


def test_a_completed_challenge_cannot_be_edited(team_setup, db) -> None:
    from app.models.domain import Challenge, ChallengeStatus

    db.get(Challenge, team_setup.challenge.id).status = ChallengeStatus.COMPLETED
    db.commit()

    response = team_setup.admin_client.patch(
        f"/api/v1/challenges/{team_setup.challenge.id}",
        json={"forfeit_amount_pence": 1},
    )
    assert response.status_code == 409


def test_participants_view_shows_who_has_not_committed(team_setup, make_goal) -> None:
    make_goal(team_setup.admin_participant)
    team_setup.admin_client.post("/api/v1/me/goals/commit")

    rows = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/participants"
    ).json()
    by_user = {row["user_id"]: row for row in rows}

    assert by_user[str(team_setup.admin.id)]["goals_committed"] == 1
    assert by_user[str(team_setup.admin.id)]["goals_committed_at"] is not None
    assert by_user[str(team_setup.member.id)]["goals_committed"] == 0
    assert by_user[str(team_setup.member.id)]["goals_committed_at"] is None


def test_every_audited_action_is_recorded(team_setup, make_goal, db) -> None:
    """All nine actions in audit.ACTIONS must actually be emitted somewhere."""
    from app.models.domain import Challenge, ChallengeStatus

    team = team_setup.team.id
    client = team_setup.admin_client

    invitation = client.post(
        f"/api/v1/teams/{team}/invitations", json={"max_uses": 1}
    ).json()
    client.delete(f"/api/v1/teams/{team}/invitations/{invitation['id']}")
    client.patch(
        f"/api/v1/teams/{team}/members/{team_setup.member.id}", json={"role": "ADMIN"}
    )
    client.patch(
        f"/api/v1/teams/{team}/members/{team_setup.member.id}", json={"role": "MEMBER"}
    )
    client.patch(
        f"/api/v1/challenges/{team_setup.challenge.id}",
        json={
            "end_at": (datetime.now(UTC) + timedelta(days=190)).isoformat(),
            "forfeit_amount_pence": 25000,
        },
    )
    goal = make_goal(team_setup.member_participant)
    client.post(f"/api/v1/goals/{goal.id}/unlock")
    client.post(
        f"/api/v1/teams/{team}/participants/{team_setup.member.id}"
        f"/goals/{goal.id}/override"
    )
    client.delete(f"/api/v1/teams/{team}/members/{team_setup.member.id}")

    # CHALLENGE_PUBLISHED comes from publishing a draft.
    db.get(Challenge, team_setup.challenge.id).status = ChallengeStatus.COMPLETED
    db.commit()
    now = datetime.now(UTC)
    draft = client.post(
        f"/api/v1/teams/{team}/challenges",
        json={
            "name": "Round two",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=90)).isoformat(),
        },
    )
    assert draft.status_code == 200

    recorded = set(actions(client, team))
    assert set(audit.ACTIONS) <= recorded, set(audit.ACTIONS) - recorded


def test_audit_entries_name_the_actor(team_setup) -> None:
    team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/invitations", json={"max_uses": 1}
    )

    logs = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/audit-logs"
    ).json()

    assert logs[0]["actor_user_id"] == str(team_setup.admin.id)
    # The name travels with the entry so the log still reads correctly once the
    # actor has left the team.
    assert logs[0]["actor"] == team_setup.admin.display_name
    assert logs[0]["created_at"]


def test_audit_logs_are_scoped_to_one_team(
    team_setup, make_user, make_team, client_factory
) -> None:
    other_admin = make_user("Other Admin")
    other_team = make_team(other_admin, name="Rivals")
    other_client = client_factory(other_admin.id)
    other_client.post(
        f"/api/v1/teams/{other_team.id}/invitations", json={"max_uses": 1}
    )
    team_setup.admin_client.post(
        f"/api/v1/teams/{team_setup.team.id}/invitations", json={"max_uses": 1}
    )

    mine = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/audit-logs"
    ).json()
    theirs = other_client.get(f"/api/v1/teams/{other_team.id}/audit-logs").json()

    assert len(mine) == 1
    assert len(theirs) == 1
    assert mine[0]["id"] != theirs[0]["id"]
