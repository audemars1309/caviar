"""In-process, per-user sliding-window rate limiting.

Scope honestly stated: this limiter lives in process memory. It resets on
restart and is per-worker if the app is ever run with multiple processes.
That is the right cost/benefit for Caviar's current single-instance
deployment stage - it stops accidental client loops and casual abuse of
the expensive upload path without introducing Redis or any other
infrastructure. If/when the backend runs multi-instance, this module is
the single place to swap in a shared backend; callers depend only on
``SlidingWindowRateLimiter.check``.

asyncio-safety note: no lock is needed. All mutation happens synchronously
inside ``check`` with no ``await`` points, and FastAPI runs async
dependencies on a single event loop - so a check is atomic with respect to
other requests.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from app.core.exceptions import RateLimitedError


class SlidingWindowRateLimiter:
    """Allows at most ``max_events`` per key within any rolling
    ``window_seconds`` interval."""

    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        if max_events <= 0 or window_seconds <= 0:
            raise ValueError("max_events and window_seconds must be positive.")
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._events: dict[uuid.UUID, deque[float]] = defaultdict(deque)

    def check(self, key: uuid.UUID, *, now: float | None = None) -> None:
        """Record one event for ``key``; raise ``RateLimitedError`` if the
        key has exceeded its budget for the current window."""
        current = time.monotonic() if now is None else now
        window_start = current - self._window_seconds
        events = self._events[key]
        while events and events[0] <= window_start:
            events.popleft()
        if len(events) >= self._max_events:
            retry_after = int(events[0] + self._window_seconds - current) + 1
            raise RateLimitedError(
                "Too many uploads. Please try again later.",
                details={"retry_after_seconds": max(retry_after, 1)},
            )
        events.append(current)
