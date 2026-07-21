"""Immutable signal and event models shared by vision and dashboard layers."""

from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass(frozen=True, slots=True)
class SignalSnapshot:
    """One point-in-time interpretation of the live camera feed."""

    timestamp: float
    face_detected: bool
    activity: str
    driver_status: str
    fatigue: float
    attention: float
    readiness: float
    tension: float
    signal_quality: float
    fps: float
    brightness: float
    calibration_remaining: float = 0.0
    sleep_state: str = "No face"
    eyes_closed: bool = False
    eye_closure_seconds: float = 0.0
    drowsiness: float = 0.0
    head_pitch: float = 0.0
    yawning: bool = False
    cough_detected: bool = False
    cough_count: int = 0
    audio_level: float = 0.0
    alarm_active: bool = False
    phone_at_ear: bool = False
    phone_side: str = ""
    one_hand_visible: bool = False
    eating_detected: bool = False
    drinking_detected: bool = False
    seatbelt_visible: bool = False
    seatbelt_warning: bool = False
    face_missing_warning: bool = False

    @classmethod
    def waiting(cls) -> SignalSnapshot:
        """Return a neutral state before camera frames arrive."""
        return cls(
            timestamp=time(),
            face_detected=False,
            activity="Waiting for camera",
            driver_status="Camera Ready",
            fatigue=0.0,
            attention=0.0,
            readiness=0.0,
            tension=0.0,
            signal_quality=0.0,
            fps=0.0,
            brightness=0.0,
        )


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """A notable state change observed during the session."""

    timestamp: float
    level: str
    title: str
    detail: str
