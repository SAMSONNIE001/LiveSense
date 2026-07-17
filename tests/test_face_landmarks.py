"""Integration test for the bundled MediaPipe face model."""

import numpy as np

from vision.face_landmarks import (
    FaceLandmarkAnalyzer,
    eyes_appear_closed,
    mouth_appears_yawning,
)


def test_eye_closure_combines_blink_and_eyelid_geometry() -> None:
    assert eyes_appear_closed(0.16, 0.17, 0.10, 0.10) is True
    assert eyes_appear_closed(0.27, 0.28, 0.70, 0.68) is True
    assert eyes_appear_closed(0.27, 0.28, 0.10, 0.12) is False


def test_yawn_threshold_catches_moderate_sustained_jaw_opening() -> None:
    assert mouth_appears_yawning(0.38) is True
    assert mouth_appears_yawning(0.30) is False


def test_bundled_face_landmarker_loads_and_handles_empty_frame() -> None:
    analyzer = FaceLandmarkAnalyzer()
    try:
        result = analyzer.analyze(np.zeros((120, 160, 3), dtype=np.uint8), timestamp_ms=1)
    finally:
        analyzer.close()

    assert result is None
