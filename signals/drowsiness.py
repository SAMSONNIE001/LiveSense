"""Duration-based awake, dozing, and sleeping state machine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrowsinessResult:
    state: str
    score: float
    eye_closure_seconds: float
    head_drop: bool
    alarm_active: bool


class DrowsinessMonitor:
    """Combine persistent eye closure, yawning, and head angle over time."""

    def __init__(
        self,
        dozing_seconds: float = 1.0,
        sleeping_seconds: float = 2.0,
    ) -> None:
        self.dozing_seconds = dozing_seconds
        self.sleeping_seconds = sleeping_seconds
        self._closed_since: float | None = None
        self._open_since: float | None = None
        self._closure_seconds = 0.0
        self._yawn_until = 0.0
        self._yawn_was_active = False

    def update(
        self,
        *,
        timestamp: float,
        face_detected: bool,
        eyes_closed: bool,
        yawning: bool,
        head_pitch: float,
    ) -> DrowsinessResult:
        if not face_detected:
            self._closed_since = None
            self._open_since = None
            self._closure_seconds = 0.0
            self._yawn_was_active = False
            return DrowsinessResult("No face", 0.0, self._closure_seconds, False, False)

        if eyes_closed:
            if self._closed_since is None:
                self._closed_since = timestamp
            self._open_since = None
            self._closure_seconds = max(0.0, timestamp - self._closed_since)
        else:
            if self._open_since is None:
                self._open_since = timestamp
            # One brief open/missed landmark sample must not erase a genuine
            # two-second closure. Sustained open eyes still reset promptly.
            if timestamp - self._open_since >= 0.75:
                self._closed_since = None
                self._closure_seconds = 0.0

        if yawning and not self._yawn_was_active:
            self._yawn_until = timestamp + 8.0
        self._yawn_was_active = yawning
        recent_yawn = timestamp < self._yawn_until
        head_drop = abs(head_pitch) >= 24.0

        closure_score = min(80.0, self._closure_seconds / self.sleeping_seconds * 80.0)
        score = min(
            100.0,
            closure_score + (18.0 if recent_yawn else 0.0) + (12.0 if head_drop else 0.0),
        )

        sleeping = eyes_closed and self._closure_seconds >= self.sleeping_seconds
        dozing = self._closure_seconds >= self.dozing_seconds or score >= 45.0
        if sleeping:
            state = "Sleeping"
        elif dozing:
            state = "Dozing"
        elif recent_yawn:
            state = "Drowsy"
        else:
            state = "Awake"
        return DrowsinessResult(state, score, self._closure_seconds, head_drop, sleeping)

    def suppress_yawn(self) -> None:
        """Discard a mouth-opening cue explained by eating or drinking."""
        self._yawn_until = 0.0
        self._yawn_was_active = False

    def reset(self) -> None:
        self._closed_since = None
        self._open_since = None
        self._closure_seconds = 0.0
        self._yawn_until = 0.0
        self._yawn_was_active = False
