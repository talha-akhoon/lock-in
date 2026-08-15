"""Final scoring and forfeits.

The money is the sharp edge of this product, so the arithmetic and its
idempotency are asserted directly.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.domain import Challenge, ChallengeStatus, ForfeitObligation


@pytest.fixture
def finished(team_setup, db):
    """Wind the challenge back so it has already ended."""

    def finish():
        challenge = db.get(Challenge, team_setup.challenge.id)
        now = datetime.now(UTC)
        challenge.start_at = now - timedelta(days=184)
        challenge.end_at = now - timedelta(minutes=1)
        db.commit()
        return challenge

    return finish


def test_outcomes_cannot_be_read_before_the_challenge_ends(team_setup) -> None:
    response = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    )
    assert response.status_code == 409


def test_a_member_who_finished_everything_owes_nothing(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(team_setup.member_participant, current_value=Decimal(120))
    finished()

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    ).json()

    assert all(row["succeeded"] for row in body["outcomes"])
    assert all(row["total_forfeit_pence"] == 0 for row in body["outcomes"])
    assert body["forfeits"] == []


def test_a_member_who_missed_a_required_goal_owes_every_other_member(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(team_setup.member_participant, current_value=Decimal(95))
    finished()

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    ).json()
    failed = next(
        row for row in body["outcomes"] if row["user_id"] == str(team_setup.member.id)
    )

    # Two participants, so one debt of £200 to the single other member.
    assert failed["succeeded"] is False
    assert failed["total_forfeit_pence"] == 20000
    assert len(body["forfeits"]) == 1
    line = body["forfeits"][0]
    assert line["from_user_id"] == str(team_setup.member.id)
    assert line["to_user_id"] == str(team_setup.admin.id)
    assert line["amount_pence"] == 20000
    assert line["status"] == "OUTSTANDING"


def test_forfeits_scale_with_the_number_of_other_members(
    team_setup, make_user, make_member, make_participant, make_goal, finished, db
) -> None:
    from decimal import Decimal

    third = make_user("Third")
    make_member(team_setup.team, third)
    third_participant = make_participant(team_setup.challenge, third)

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(team_setup.member_participant, current_value=Decimal(120))
    make_goal(third_participant, current_value=Decimal(90))
    finished()

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    ).json()
    failed = next(row for row in body["outcomes"] if row["user_id"] == str(third.id))

    assert failed["total_forfeit_pence"] == 40000
    assert len(body["forfeits"]) == 2
    assert {line["to_user_id"] for line in body["forfeits"]} == {
        str(team_setup.admin.id),
        str(team_setup.member.id),
    }


def test_submitting_no_goals_counts_as_a_failure(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    finished()

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    ).json()
    absent = next(
        row for row in body["outcomes"] if row["user_id"] == str(team_setup.member.id)
    )

    assert absent["succeeded"] is False
    assert absent["required_goals_total"] == 0


def test_optional_goals_do_not_decide_the_outcome(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(
        team_setup.admin_participant,
        title="Stretch goal",
        required=False,
        current_value=Decimal(90),
    )
    finished()

    body = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    ).json()
    row = next(
        item for item in body["outcomes"] if item["user_id"] == str(team_setup.admin.id)
    )

    assert row["succeeded"] is True
    assert row["optional_goals_total"] == 1
    assert row["optional_goals_completed"] == 0


def test_re_evaluation_does_not_double_charge(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(team_setup.member_participant, current_value=Decimal(95))
    finished()
    path = f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"

    first = team_setup.admin_client.get(path).json()
    second = team_setup.admin_client.get(path).json()

    assert first["outcomes"] == second["outcomes"]
    assert db.query(ForfeitObligation).count() == 1


def test_evaluating_marks_the_challenge_completed(
    team_setup, make_goal, finished, db
) -> None:
    """The status has to be persisted, not just derived on each read."""
    finished()
    team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    )

    db.expire_all()
    assert db.get(Challenge, team_setup.challenge.id).status == (
        ChallengeStatus.COMPLETED
    )


def test_reading_the_challenge_after_it_ends_completes_it(
    team_setup, finished, db
) -> None:
    finished()

    body = team_setup.admin_client.get("/api/v1/challenges/current").json()

    assert body["status"] == "COMPLETED"
    db.expire_all()
    assert db.get(Challenge, team_setup.challenge.id).status == (
        ChallengeStatus.COMPLETED
    )


def test_forfeit_lines_are_readable_on_their_own(
    team_setup, make_goal, finished, db
) -> None:
    from decimal import Decimal

    make_goal(team_setup.admin_participant, current_value=Decimal(120))
    make_goal(team_setup.member_participant, current_value=Decimal(95))
    finished()
    team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/outcomes"
    )

    lines = team_setup.admin_client.get(
        f"/api/v1/challenges/{team_setup.challenge.id}/forfeits"
    ).json()

    assert len(lines) == 1
    assert lines[0]["from_display_name"] == "Teammate"
    assert lines[0]["to_display_name"] == "Admin"
