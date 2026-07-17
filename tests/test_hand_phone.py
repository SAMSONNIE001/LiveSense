"""Tests for hand-at-ear phone-use detection."""

import numpy as np

from vision import HandPhoneAnalyzer, hand_near_face_ear


def test_hand_beside_face_is_classified_as_phone_use() -> None:
    result = hand_near_face_ear((95.0, 70.0), (100, 40, 80, 100))

    assert result.hand_near_ear is True
    assert result.side == "left"


def test_hand_away_from_face_is_clear() -> None:
    result = hand_near_face_ear((20.0, 200.0), (100, 40, 80, 100))

    assert result.hand_near_ear is False


def test_hand_in_front_of_mouth_is_not_mistaken_for_phone_at_ear() -> None:
    result = hand_near_face_ear((140.0, 92.0), (100, 40, 80, 100))

    assert result.hand_near_ear is False


def test_hand_landmarker_model_loads() -> None:
    analyzer = HandPhoneAnalyzer()
    try:
        result = analyzer.analyze(
            np.zeros((120, 160, 3), dtype=np.uint8),
            (50, 20, 60, 80),
            timestamp_ms=1,
        )
        assert result.hand_near_ear is False
        assert result.palm_positions == ()
    finally:
        analyzer.close()
