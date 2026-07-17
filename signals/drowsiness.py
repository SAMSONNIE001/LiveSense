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
        dozing_seconds: float = 0.25,
        sleeping_seconds: float = 0.70,
    ) -> None:
        self.dozing_seconds = dozing_seconds
        self.sleeping_seconds = sleeping_seconds
        self._last_at: float | None = None
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
        if self._last_at is None:
            elapsed = 0.0
        else:
            elapsed = max(0.0, min(0.25, timestamp - self._last_at))
        self._last_at = timestamp

        if not face_detected:
            self._closure_seconds = max(0.0, self._closure_seconds - elapsed * 2.0)
            self._yawn_was_active = False
            return DrowsinessResult("No face", 0.0, self._closure_seconds, False, False)

        if eyes_closed:
            self._closure_seconds += elapsed
        else:
            self._closure_seconds = max(0.0, self._closure_seconds - elapsed * 3.0)

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

        # LiveSense is intentionally configured as a high-sensitivity safety
        # monitor: one reliable closed-eye landmark result raises the alarm.
        # This also avoids extra wall-clock delay on lower-FPS computers.
        sleeping = eyes_closed
        if sleeping:
            score = 100.0
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

    def reset(self) -> None:
        self._last_at = None
        self._closure_seconds = 0.0
        self._yawn_until = 0.0
        self._yawn_was_active = False
