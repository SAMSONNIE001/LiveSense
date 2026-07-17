"""Low-latency audio burst analysis for suspected cough events."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic

import av
import numpy as np


@dataclass(frozen=True, slots=True)
class AudioActivityState:
    level: float = 0.0
    cough_detected: bool = False
    cough_count: int = 0


class AudioActivityDetector:
    """Detect short, high-energy, broadband bursts consistent with coughing.

    This is deliberately reported as a suspected cough cue: it is not a speech
    recognizer or medical classifier.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._noise_floor = 0.008
        self._level = 0.0
        self._burst_started_at: float | None = None
        self._burst_peak = 0.0
        self._burst_zcr = 0.0
        self._burst_frames = 0
        self._recent_cough_until = 0.0
        self._cough_count = 0
        self._last_cough_at = float("-inf")

    def observe(self, samples: np.ndarray, timestamp: float | None = None) -> None:
        now = monotonic() if timestamp is None else timestamp
        mono = np.asarray(samples, dtype=np.float32).reshape(-1)
        if not mono.size:
            return
        maximum = float(np.max(np.abs(mono)))
        if maximum > 1.5:
            mono /= 32768.0
        rms = float(np.sqrt(np.mean(np.square(mono))))
        zero_crossing = float(np.mean(np.abs(np.diff(np.signbit(mono))))) if mono.size > 1 else 0.0

        with self._lock:
            self._level = min(100.0, rms * 700.0)
            threshold = max(0.035, self._noise_floor * 3.8)
            loud = rms >= threshold
            if not loud:
                self._noise_floor = self._noise_floor * 0.98 + rms * 0.02

            if loud:
                if self._burst_started_at is None:
                    self._burst_started_at = now
                    self._burst_peak = rms
                    self._burst_zcr = zero_crossing
                    self._burst_frames = 1
                else:
                    self._burst_peak = max(self._burst_peak, rms)
                    self._burst_zcr += zero_crossing
                    self._burst_frames += 1
            elif self._burst_started_at is not None:
                duration = now - self._burst_started_at
                average_zcr = self._burst_zcr / max(1, self._burst_frames)
                cough_shape = (
                    0.06 <= duration <= 0.85
                    and self._burst_peak >= threshold * 1.25
                    and 0.015 <= average_zcr <= 0.48
                )
                if cough_shape and now - self._last_cough_at >= 1.2:
                    self._cough_count += 1
                    self._last_cough_at = now
                    self._recent_cough_until = now + 2.0
                self._burst_started_at = None
                self._burst_peak = 0.0
                self._burst_zcr = 0.0
                self._burst_frames = 0

    def snapshot(self, timestamp: float | None = None) -> AudioActivityState:
        now = monotonic() if timestamp is None else timestamp
        with self._lock:
            return AudioActivityState(
                level=self._level,
                cough_detected=now < self._recent_cough_until,
                cough_count=self._cough_count,
            )

    def reset(self) -> None:
        with self._lock:
            self._recent_cough_until = 0.0
            self._cough_count = 0
            self._last_cough_at = float("-inf")


class AudioActivityProcessor:
    """WebRTC audio processor that publishes analysis and returns input frames."""

    def __init__(self, detector: AudioActivityDetector) -> None:
        self.detector = detector

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        self.detector.observe(frame.to_ndarray())
        return frame
