"""Authorisation: URL tampering, admin-only routes and cross-team access.

Every team-scoped route takes a team_id from the path, so each one has to be
checked against the caller's own membership rather than trusted.
"""

import uuid

import pytest


@pytest.fixture
def rival(make_user, make_team, make_challenge, make_participant, client_factory):
    class Rival:
        def __init__(self) -> None:
            self.user = make_user("Rival Admin")
            self.team = make_team(self.user, name="Rivals")
            self.challenge = make_challenge(self.team)
            self.participant = make_participant(self.challenge, self.user)
            self.client = client_factory(self.user.id)

    return Rival()


TEAM_SCOPED_READS = [
    "/api/v1/teams/{team_id}/members",
    "/api/v1/teams/{team_id}/invitations",
    "/api/v1/teams/{team_id}/audit-logs",
    "/api/v1/teams/{team_id}/participants",
]


@pytest.mark.parametrize("template", TEAM_SCOPED_READS)
def test_another_teams_id_in_the_url_is_refused(team_setup, rival, template) -> None:
    path = template.format(team_id=rival.team.id)
    assert team_setup.admin_client.get(path).status_code == 403


def test_another_teams_member_profile_is_refused(team_setup, rival) -> None:
    response = team_setup.admin_client.get(
        f"/api/v1/teams/{rival.team.id}/members/{rival.user.id}"
    )
    assert response.status_code == 403


def test_another_teams_challenge_is_not_found(team_setup, rival) -> None:
    for path in (
        f"/api/v1/challenges/{rival.challenge.id}",
        f"/api/v1/challenges/{rival.challenge.id}/dashboard",
        f"/api/v1/challenges/{rival.challenge.id}/activity",
        f"/api/v1/challenges/{rival.challenge.id}/forfeits",
    ):
        assert team_setup.admin_client.get(path).status_code == 404, path


def test_another_members_goal_is_not_found(team_setup, rival, make_goal) -> None:
    goal = make_goal(rival.participant, title="Rival secret")

    assert team_setup.admin_client.get(f"/api/v1/goals/{goal.id}").status_code == 404
    assert (
        team_setup.admin_client.patch(
            f"/api/v1/goals/{goal.id}", json={"sort_order": 3}
        ).status_code
        == 404
    )
    assert team_setup.admin_client.delete(f"/api/v1/goals/{goal.id}").status_code == 404


def test_a_teammates_goal_in_the_same_challenge_is_not_editable(
    team_setup, make_goal
) -> None:
    """get_participant scopes to the caller, so a teammate's goal is invisible."""
    goal = make_goal(team_setup.member_participant, title="Teammate goal")

    response = team_setup.admin_client.patch(
        f"/api/v1/goals/{goal.id}", json={"sort_order": 9}
    )
    assert response.status_code == 404


def test_admin_routes_are_closed_to_members(team_setup, rival) -> None:
    team = team_setup.team.id
    member = team_setup.member_client

    assert member.get(f"/api/v1/teams/{team}/invitations").status_code == 403
    assert member.get(f"/api/v1/teams/{team}/audit-logs").status_code == 403
    assert (
        member.post(
            f"/api/v1/teams/{team}/invitations", json={"max_uses": 1}
        ).status_code
        == 403
    )
    assert (
        member.delete(f"/api/v1/teams/{team}/members/{team_setup.admin.id}").status_code
        == 403
    )
    assert (
        member.patch(
            f"/api/v1/teams/{team}/members/{team_setup.admin.id}",
            json={"role": "MEMBER"},
        ).status_code
        == 403
    )


def test_a_member_cannot_unlock_a_commitment(team_setup, make_goal) -> None:
    goal = make_goal(team_setup.member_participant)
    response = team_setup.member_client.post(f"/api/v1/goals/{goal.id}/unlock")
    assert response.status_code == 403


def test_an_admin_cannot_unlock_across_teams(team_setup, rival, make_goal) -> None:
    goal = make_goal(rival.participant)
    response = team_setup.admin_client.post(f"/api/v1/goals/{goal.id}/unlock")
    assert response.status_code == 403


def test_a_user_with_no_team_is_refused_team_scoped_routes(
    client_factory, make_user
) -> None:
    client = client_factory(make_user().id)

    assert client.get("/api/v1/teams/current").status_code == 403
    assert client.get("/api/v1/me/goals").status_code == 403
    assert client.get(f"/api/v1/teams/{uuid.uuid4()}/members").status_code == 403


def test_a_team_with_no_challenge_reports_404_not_500(
    client_factory, make_user, make_team
) -> None:
    user = make_user("Solo")
    make_team(user, name="Empty")
    client = client_factory(user.id)

    assert client.get("/api/v1/challenges/current").status_code == 404
    assert client.get("/api/v1/me/goals").status_code == 404


def test_a_member_not_enrolled_in_the_challenge_is_refused(
    team_setup, make_user, make_member, client_factory, db
) -> None:
    from app.models.domain import ChallengeParticipant

    latecomer = make_user("Latecomer")
    make_member(team_setup.team, latecomer)
    client = client_factory(latecomer.id)

    assert db.query(ChallengeParticipant).filter_by(user_id=latecomer.id).count() == 0
    assert client.get("/api/v1/me/goals").status_code == 403
