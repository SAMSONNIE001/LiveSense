"""Integration test for the bundled MediaPipe face model."""

import numpy as np

from vision import FaceLandmarkAnalyzer


def test_bundled_face_landmarker_loads_and_handles_empty_frame() -> None:
    analyzer = FaceLandmarkAnalyzer()
    try:
        result = analyzer.analyze(np.zeros((120, 160, 3), dtype=np.uint8), timestamp_ms=1)
    finally:
        analyzer.close()

    assert result is None
