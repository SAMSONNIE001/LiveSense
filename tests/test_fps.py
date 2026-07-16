"""Tests for rolling FPS measurement."""

import pytest

from utils.fps import FPSMeter


def test_fps_meter_uses_frame_intervals() -> None:
    times = iter([10.0, 10.1, 10.2])
    meter = FPSMeter(window_size=3, clock=lambda: next(times))

    assert meter.tick() == 0.0
    assert meter.tick() == pytest.approx(10.0)
    assert meter.tick() == pytest.approx(10.0)


def test_fps_meter_rejects_too_small_window() -> None:
    try:
        FPSMeter(window_size=1)
    except ValueError as error:
        assert "at least 2" in str(error)
    else:
        raise AssertionError("Expected a ValueError")
