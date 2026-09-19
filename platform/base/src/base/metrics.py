"""
Lightweight in-process rate/latency counters for service instrumentation
(admin dashboard `/metrics` endpoints).

# ponytail: in-memory per-process counter, resets on restart and isn't
shared across replicas — move to a real metrics backend (e.g. Prometheus)
if this needs to survive restarts or aggregate across instances.
"""

from __future__ import annotations

import math
import time
from collections import deque


class RateCounter:
    """Records timestamped samples and reports rates/percentiles over a window."""

    def __init__(self, max_age_seconds: float = 300.0) -> None:
        self._max_age_seconds = max_age_seconds
        self._samples: deque[tuple[float, float]] = deque()

    def record(self, value: float = 1.0) -> None:
        """Record one sample with the current timestamp."""
        now = time.monotonic()
        self._samples.append((now, value))
        self._prune(now)

    def rate_last(self, seconds: float) -> float:
        """Sum of values recorded in the window, divided by the window length."""
        now = time.monotonic()
        self._prune(now)
        cutoff = now - seconds
        total = sum(v for t, v in self._samples if t >= cutoff)
        return total / seconds if seconds > 0 else 0.0

    def percentiles_last(
        self, seconds: float, pcts: list[float]
    ) -> dict[float, float | None]:
        """Percentiles (linear interpolation) of values recorded in the window."""
        now = time.monotonic()
        self._prune(now)
        cutoff = now - seconds
        values = sorted(v for t, v in self._samples if t >= cutoff)
        if not values:
            return {p: None for p in pcts}
        return {p: _percentile(values, p) for p in pcts}

    def _prune(self, now: float) -> None:
        cutoff = now - self._max_age_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()


def _percentile(sorted_values: list[float], pct: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)
