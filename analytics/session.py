"""Thread-safe live session history and event generation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock

from signals import SignalEvent, SignalSnapshot


@dataclass(frozen=True, slots=True)
class SessionView:
    """Read-only copy of the current session for dashboard rendering."""

    current: SignalSnapshot
    history: tuple[SignalSnapshot, ...]
    events: tuple[SignalEvent, ...]


class SignalSession:
    """Collect rolling signal history without blocking the video thread."""

    def __init__(self, history_size: int = 900, sample_interval: float = 1.0) -> None:
        self._lock = Lock()
        self._current = SignalSnapshot.waiting()
        self._history: deque[SignalSnapshot] = deque(maxlen=history_size)
        self._events: deque[SignalEvent] = deque(maxlen=50)
        self._sample_interval = sample_interval
        self._last_sample_at = 0.0
        self._last_event_at = 0.0
        self._last_activity = self._current.activity
        self._last_sleep_state = self._current.sleep_state
        self._last_cough_count = 0
        self._eating_active = False
        self._drinking_active = False
        self._seatbelt_warning = False
        self._face_missing_warning = False

    def update(self, snapshot: SignalSnapshot) -> None:
        """Store a signal result and emit debounced activity events."""
        with self._lock:
            self._current = snapshot
            if snapshot.timestamp - self._last_sample_at >= self._sample_interval:
                self._history.append(snapshot)
                self._last_sample_at = snapshot.timestamp

            if snapshot.alarm_active and self._last_sleep_state != "Sleeping":
                self._events.appendleft(
                    SignalEvent(
                        snapshot.timestamp,
                        "critical",
                        "Sleep alarm",
                        "Sustained eye closure indicates possible sleep. "
                        "Wake the person immediately.",
                    )
                )
                self._last_event_at = snapshot.timestamp
            elif (
                snapshot.sleep_state in {"Dozing", "Drowsy"}
                and snapshot.sleep_state != self._last_sleep_state
            ):
                self._events.appendleft(
                    SignalEvent(
                        snapshot.timestamp,
                        "warning",
                        f"{snapshot.sleep_state} detected",
                        "Eye, yawn, or head-position cues indicate increasing drowsiness.",
                    )
                )
                self._last_event_at = snapshot.timestamp

            if snapshot.cough_count > self._last_cough_count:
                self._events.appendleft(
                    SignalEvent(
                        snapshot.timestamp,
                        "info",
                        "Suspected cough",
                        "A short broadband audio burst matched the cough heuristic.",
                    )
                )
                self._last_event_at = snapshot.timestamp

            observation_events = (
                (
                    snapshot.drinking_detected and not self._drinking_active,
                    "Drinking detected",
                    "A cup or bottle remained near the mouth.",
                ),
                (
                    snapshot.eating_detected and not self._eating_active,
                    "Eating detected",
                    "Food, a utensil, or a hand remained near the mouth.",
                ),
                (
                    snapshot.seatbelt_warning and not self._seatbelt_warning,
                    "Seat belt not confirmed",
                    "Buckle the seat belt or adjust the camera so it is visible.",
                ),
                (
                    snapshot.face_missing_warning and not self._face_missing_warning,
                    "Face not detected",
                    "Return the face to view so safety monitoring can continue.",
                ),
            )
            for activated, title, detail in observation_events:
                if activated:
                    self._events.appendleft(
                        SignalEvent(snapshot.timestamp, "warning", title, detail)
                    )
                    self._last_event_at = snapshot.timestamp

            changed = snapshot.activity != self._last_activity
            can_emit = snapshot.timestamp - self._last_event_at >= 5.0
            if changed and can_emit and snapshot.activity in {"Looking away", "Moving"}:
                level = "warning" if snapshot.activity != "Moving" else "info"
                detail = {
                    "Looking away": "Attention moved outside the central monitoring area.",
                    "Moving": "A noticeable movement change was detected.",
                }[snapshot.activity]
                self._events.appendleft(
                    SignalEvent(snapshot.timestamp, level, snapshot.activity, detail)
                )
                self._last_event_at = snapshot.timestamp
            self._last_activity = snapshot.activity
            self._last_sleep_state = snapshot.sleep_state
            self._last_cough_count = snapshot.cough_count
            self._eating_active = snapshot.eating_detected
            self._drinking_active = snapshot.drinking_detected
            self._seatbelt_warning = snapshot.seatbelt_warning
            self._face_missing_warning = snapshot.face_missing_warning

    def snapshot(self) -> SessionView:
        """Return a consistent view for the live API rendering thread."""
        with self._lock:
            return SessionView(self._current, tuple(self._history), tuple(self._events))

    def reset(self) -> None:
        """Start a new in-memory monitoring session."""
        with self._lock:
            self._current = SignalSnapshot.waiting()
            self._history.clear()
            self._events.clear()
            self._last_sample_at = 0.0
            self._last_event_at = 0.0
            self._last_activity = self._current.activity
            self._last_sleep_state = self._current.sleep_state
            self._last_cough_count = 0
            self._eating_active = False
            self._drinking_active = False
            self._seatbelt_warning = False
            self._face_missing_warning = False
