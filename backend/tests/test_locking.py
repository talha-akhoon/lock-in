from datetime import UTC, datetime, timedelta

from app.models.domain import Challenge, ChallengeParticipant
from app.services.goals import participant_is_locked


def participant(
    *,
    due_offset: timedelta,
    explicitly_locked: bool = False,
    end_offset: timedelta = timedelta(days=180),
):
    now = datetime.now(UTC)
    return ChallengeParticipant(
        joined_at=now - timedelta(days=1),
        goals_due_at=now + due_offset,
        goals_locked_at=now if explicitly_locked else None,
        challenge=Challenge(
            name="H1",
            start_at=now - timedelta(days=1),
            end_at=now + end_offset,
        ),
    )


def test_open_before_deadline() -> None:
    assert not participant_is_locked(participant(due_offset=timedelta(days=2)))


def test_locked_after_deadline() -> None:
    assert participant_is_locked(participant(due_offset=-timedelta(seconds=1)))


def test_early_commit_locks_immediately() -> None:
    assert participant_is_locked(
        participant(due_offset=timedelta(days=2), explicitly_locked=True)
    )


def test_a_finished_challenge_locks_an_open_window() -> None:
    """An admin override late in the run can outlive the challenge itself."""
    assert participant_is_locked(
        participant(due_offset=timedelta(days=2), end_offset=-timedelta(seconds=1))
    )
