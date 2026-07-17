"""Tests for suspected cough audio bursts."""

import numpy as np

from signals import AudioActivityDetector


def test_short_broadband_burst_registers_suspected_cough() -> None:
    detector = AudioActivityDetector()
    sample_rate = 16_000
    timeline = np.arange(800, dtype=np.float32) / sample_rate
    burst = 0.22 * np.sin(2 * np.pi * 900 * timeline)
    quiet = np.zeros(800, dtype=np.float32)

    detector.observe(quiet, timestamp=0.0)
    detector.observe(burst, timestamp=0.10)
    detector.observe(burst, timestamp=0.20)
    detector.observe(quiet, timestamp=0.32)
    state = detector.snapshot(timestamp=0.40)

    assert state.cough_detected is True
    assert state.cough_count == 1


def test_continuous_long_audio_is_not_labelled_as_cough() -> None:
    detector = AudioActivityDetector()
    burst = np.tile(np.array([-0.2, 0.2], dtype=np.float32), 400)
    detector.observe(burst, timestamp=0.0)
    detector.observe(burst, timestamp=0.5)
    detector.observe(burst, timestamp=1.0)
    detector.observe(np.zeros(800, dtype=np.float32), timestamp=1.1)

    assert detector.snapshot(timestamp=1.2).cough_count == 0
