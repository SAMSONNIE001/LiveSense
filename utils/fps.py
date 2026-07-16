"""Thread-safe frames-per-second measurement."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic


class FPSMeter:
    """Measure rolling FPS over a bounded window of frame timestamps."""

    def __init__(
        self,
        window_size: int = 30,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        self._timestamps: deque[float] = deque(maxlen=window_size)
        self._clock = clock
        self._lock = Lock()

    def tick(self) -> float:
        """Record a frame and return the current rolling FPS."""
        with self._lock:
            self._timestamps.append(self._clock())
            if len(self._timestamps) < 2:
                return 0.0
            elapsed = self._timestamps[-1] - self._timestamps[0]
            return 0.0 if elapsed <= 0 else (len(self._timestamps) - 1) / elapsed
