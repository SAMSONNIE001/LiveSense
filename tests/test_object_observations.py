"""Tests for object-position and seat-belt observation helpers."""

import cv2
import numpy as np

from vision import ObjectObservationAnalyzer, classify_object_cues, seatbelt_visible

FACE = (100, 40, 80, 100)


def test_phone_must_be_close_to_an_ear() -> None:
    close = classify_object_cues([("cell phone", 0.9, (82, 72, 18, 38))], FACE)
    far = classify_object_cues([("cell phone", 0.9, (10, 180, 18, 38))], FACE)

    assert close.phone_near_ear is True
    assert far.phone_near_ear is False


def test_drink_and_food_must_be_close_to_mouth() -> None:
    drink = classify_object_cues([("cup", 0.8, (128, 110, 24, 32))], FACE)
    food = classify_object_cues([("sandwich", 0.8, (125, 108, 32, 28))], FACE)

    assert drink.drink_near_mouth is True
    assert food.food_near_mouth is True


def test_diagonal_torso_edge_can_confirm_seatbelt() -> None:
    image = np.zeros((360, 640, 3), dtype=np.uint8)
    face = (250, 40, 100, 100)
    cv2.line(image, (210, 145), (390, 300), (255, 255, 255), 8)

    assert seatbelt_visible(image, face) is True
    assert seatbelt_visible(np.zeros_like(image), face) is False


def test_object_detector_model_loads() -> None:
    analyzer = ObjectObservationAnalyzer()
    try:
        result = analyzer.analyze(
            np.zeros((120, 160, 3), dtype=np.uint8),
            (50, 20, 60, 80),
            timestamp_ms=1,
        )
        assert result.phone_near_ear is False
    finally:
        analyzer.close()
