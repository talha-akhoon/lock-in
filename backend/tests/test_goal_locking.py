"""The commitment lock.

The lock is the product's whole point: once it closes, what you committed to
cannot be softened. Each immutable field is checked individually, because a
single missing entry in IMMUTABLE_GOAL_FIELDS would be a silent hole.
"""

from datetime import timedelta

import pytest

from app.models.domain import ChallengeParticipant, Goal
from app.services.goals import IMMUTABLE_GOAL_FIELDS

IMMUTABLE_CASES = {
    "category": "CAREER",
    "title": "Something easier",
    "description": "Reworded commitment",
    "tracking_type": "MANUAL",
    "baseline_value": "10",
    "target_value": "95",
    "current_value": "95",
    "manual_progress_percentage": 10,
    "unit": "lbs",
    "target_direction": "AT_MOST",
    "required": False,
}
MUTABLE_CASES = {
    "visibility": "PRIVATE",
    "sort_order": 7,
}


def test_every_immutable_field_has_a_case() -> None:
    """Guards against a field being added to the set without a test."""
    assert set(IMMUTABLE_CASES) | {"parent_goal_id"} == set(IMMUTABLE_GOAL_FIELDS)


@pytest.fixture
def locked_goal(team_setup, make_goal, db):
    goal = make_goal(team_setup.admin_participant)
    participant = db.get(ChallengeParticipant, team_setup.admin_participant.id)
    participant.goals_locked_at = participant.goals_due_at
    db.commit()
    return goal


@pytest.mark.parametrize(("field", "value"), sorted(IMMUTABLE_CASES.items()))
def test_immutable_fields_are_refused_once_locked(
    team_setup, locked_goal, field, value
) -> None:
    response = team_setup.admin_client.patch(
        f"/api/v1/goals/{locked_goal.id}", json={field: value}
    )

    assert response.status_code == 409, field
    assert response.json()["detail"]["code"] == "GOALS_LOCKED"


@pytest.mark.parametrize(("field", "value"), sorted(MUTABLE_CASES.items()))
def test_display_only_fields_stay_editable_once_locked(
    team_setup, locked_goal, field, value
) -> None:
    response = team_setup.admin_client.patch(
        f"/api/v1/goals/{locked_goal.id}", json={field: value}
    )

    assert response.status_code == 200, field
    assert response.json()[field] == value


def test_goals_cannot_be_added_once_locked(team_setup, locked_goal) -> None:
    response = team_setup.admin_client.post(
        "/api/v1/me/goals",
        json={
            "category": "PERSONAL",
            "title": "Late addition",
            "tracking_type": "MILESTONE",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GOALS_LOCKED"


def test_goals_cannot_be_deleted_once_locked(team_setup, locked_goal) -> None:
    response = team_setup.admin_client.delete(f"/api/v1/goals/{locked_goal.id}")
    assert response.status_code == 409


def test_progress_can_still_be_logged_once_locked(team_setup, locked_goal) -> None:
    """Locking freezes the commitment, not the tracking."""
    response = team_setup.admin_client.post(
        f"/api/v1/goals/{locked_goal.id}/progress",
        json={"entry_date": "2026-08-14", "numeric_value": "100"},
    )
    assert response.status_code == 200


def test_committing_locks_immediately(team_setup, make_goal, db) -> None:
    make_goal(team_setup.admin_participant)

    response = team_setup.admin_client.post("/api/v1/me/goals/commit")

    assert response.status_code == 200
    db.expire_all()
    participant = db.get(ChallengeParticipant, team_setup.admin_participant.id)
    assert participant.goals_locked_at is not None
    assert participant.goals_committed_at is not None


def test_committing_without_goals_is_rejected(team_setup) -> None:
    response = team_setup.admin_client.post("/api/v1/me/goals/commit")
    assert response.status_code == 422


def test_committing_twice_is_refused(team_setup, make_goal) -> None:
    make_goal(team_setup.admin_participant)
    team_setup.admin_client.post("/api/v1/me/goals/commit")

    response = team_setup.admin_client.post("/api/v1/me/goals/commit")
    assert response.status_code == 409


def test_the_deadline_passing_persists_the_lock(
    team_setup, make_user, make_member, make_participant, make_goal, client_factory, db
) -> None:
    """goals_locked_at must be written, not merely derived on read."""
    latecomer = make_user("Latecomer")
    make_member(team_setup.team, latecomer)
    participant = make_participant(
        team_setup.challenge, latecomer, due_offset=-timedelta(minutes=1)
    )
    goal = make_goal(participant, title="Was never committed")
    client = client_factory(latecomer.id)

    assert participant.goals_locked_at is None
    body = client.get("/api/v1/me/goals").json()

    assert body["goals_locked"] is True
    db.expire_all()
    assert db.get(ChallengeParticipant, participant.id).goals_locked_at is not None
    assert db.get(Goal, goal.id).locked_at is not None


def test_an_admin_can_reopen_a_commitment(team_setup, locked_goal, db) -> None:
    response = team_setup.admin_client.post(f"/api/v1/goals/{locked_goal.id}/unlock")

    assert response.status_code == 200
    db.expire_all()
    participant = db.get(ChallengeParticipant, team_setup.admin_participant.id)
    assert participant.goals_locked_at is None

    edit = team_setup.admin_client.patch(
        f"/api/v1/goals/{locked_goal.id}", json={"title": "Revised with permission"}
    )
    assert edit.status_code == 200
    assert edit.json()["title"] == "Revised with permission"


def test_unlocking_is_audited(team_setup, locked_goal) -> None:
    team_setup.admin_client.post(f"/api/v1/goals/{locked_goal.id}/unlock")

    logs = team_setup.admin_client.get(
        f"/api/v1/teams/{team_setup.team.id}/audit-logs"
    ).json()
    unlocks = [row for row in logs if row["action"] == "GOAL_UNLOCKED"]

    assert len(unlocks) == 1
    assert unlocks[0]["metadata"]["goal_id"] == str(locked_goal.id)
    assert unlocks[0]["metadata"]["override_expires_at"]
