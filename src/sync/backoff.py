"""
Exponential backoff with optional jitter for opportunistic reconnection.

Delays grow as ``base * factor ** attempt`` capped at ``max_delay``. When jitter
is enabled the delay is scaled by a uniform random factor (full jitter), which
spreads out reconnection storms when many offline nodes come back online at
once. The random source is injectable so the behaviour stays deterministic in
tests.
"""

import random
from typing import Callable, Optional


class ExponentialBackoff:
    def __init__(
        self,
        base: float = 1.0,
        factor: float = 2.0,
        max_delay: float = 300.0,
        jitter: bool = True,
        random_fn: Optional[Callable[[], float]] = None,
    ):
        if base <= 0:
            raise ValueError("base must be positive")
        if factor < 1:
            raise ValueError("factor must be >= 1")
        if max_delay < base:
            raise ValueError("max_delay must be >= base")

        self.base = base
        self.factor = factor
        self.max_delay = max_delay
        self.jitter = jitter
        self._random = random_fn if random_fn is not None else random.random
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    def next_delay(self) -> float:
        """Return the delay for the current attempt and advance the counter."""
        raw = min(self.base * (self.factor ** self._attempt), self.max_delay)
        self._attempt += 1
        if self.jitter:
            return raw * self._random()
        return raw

    def peek_delay(self) -> float:
        """Return what the next ``next_delay`` would be without advancing."""
        return min(self.base * (self.factor ** self._attempt), self.max_delay)

    def reset(self) -> None:
        self._attempt = 0
