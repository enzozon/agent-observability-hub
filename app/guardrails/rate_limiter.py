"""Sliding-window rate limiter, in-memory."""
import time
from typing import Callable


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds the allowed calls in the window."""


class RateLimiter:
    # ponytail: in-memory per-process limiter; swap for Redis if running multiple workers
    def __init__(self, max_calls: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._clock = clock
        self._calls: dict[str, tuple[float, ...]] = {}

    def acquire(self, key: str = "global") -> None:
        now = self._clock()
        recent = tuple(t for t in self._calls.get(key, ()) if now - t < self.window_seconds)
        if len(recent) >= self.max_calls:
            raise RateLimitExceeded(
                f"Rate limit exceeded for '{key}': {self.max_calls} calls per {self.window_seconds}s"
            )
        self._calls[key] = recent + (now,)
