"""In-memory token buckets used by /mcp."""

from app.services.rate_limit import allow, reset


def setup_function() -> None:
    reset()


def test_burst_then_deny() -> None:
    assert allow("u", per_minute=60, burst=2, now=0.0) == (True, 0)
    assert allow("u", per_minute=60, burst=2, now=0.0) == (True, 0)
    allowed, retry = allow("u", per_minute=60, burst=2, now=0.0)
    assert allowed is False
    assert retry >= 1


def test_refill_allows_another_call() -> None:
    allow("u", per_minute=60, burst=1, now=0.0)
    allowed, _retry = allow("u", per_minute=60, burst=1, now=0.0)
    assert allowed is False
    assert allow("u", per_minute=60, burst=1, now=1.0) == (True, 0)


def test_keys_are_independent() -> None:
    assert allow("a", per_minute=60, burst=1, now=0.0)[0] is True
    assert allow("b", per_minute=60, burst=1, now=0.0)[0] is True
    assert allow("a", per_minute=60, burst=1, now=0.0)[0] is False


def test_non_positive_per_minute_disables_the_limit() -> None:
    for _ in range(5):
        assert allow("u", per_minute=0, burst=1, now=0.0) == (True, 0)
