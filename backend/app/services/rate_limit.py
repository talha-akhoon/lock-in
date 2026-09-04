"""In-memory token buckets. Fine for Cloud Run max-instances=1; a restart
resets counts, which is the safe direction.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_buckets: dict[str, tuple[float, float]] = {}


def reset() -> None:
    with _lock:
        _buckets.clear()


def allow(
    key: str,
    *,
    per_minute: int,
    burst: int,
    now: float | None = None,
) -> tuple[bool, int]:
    """Take one token. Returns (allowed, retry_after_seconds).

    ``per_minute <= 0`` disables the limiter. Burst is the number of calls
    allowed in a short burst before the steady refill (per_minute / 60).
    """
    if per_minute <= 0:
        return True, 0
    burst = max(1, burst)
    now = time.monotonic() if now is None else now
    rate = per_minute / 60.0
    with _lock:
        tokens, last = _buckets.get(key, (float(burst), now))
        tokens = min(float(burst), tokens + max(0.0, now - last) * rate)
        if tokens < 1.0:
            _buckets[key] = (tokens, now)
            wait = (1.0 - tokens) / rate if rate > 0 else 60
            return False, max(1, int(wait + 0.999))
        _buckets[key] = (tokens - 1.0, now)
        if len(_buckets) > 4096:
            _prune_unlocked(now)
        return True, 0


def _prune_unlocked(now: float) -> None:
    stale = now - 3600
    dead = [key for key, (_tokens, last) in _buckets.items() if last < stale]
    for key in dead:
        del _buckets[key]
