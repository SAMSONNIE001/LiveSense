"""Tests for the real-time camera frame processor."""

import av
import numpy as np
import pytest

from camera import CameraProcessor, classify_distracted_activity
from vision import FaceLandmarkResult


def test_food_and_drink_evidence_is_not_suppressed_by_hand_or_phone_cues() -> None:
    phone, drinking, eating = classify_distracted_activity(
        hand_near_ear=True,
        hand_near_mouth=True,
        mouth_open_score=0.5,
        phone_object_score=1,
        drink_object_score=2,
        food_object_score=2,
    )

    assert (phone, drinking, eating) == (True, True, True)


def test_drinking_requires_a_detected_drink_object() -> None:
    without_object = classify_distracted_activity(
        hand_near_ear=False,
        hand_near_mouth=True,
        mouth_open_score=0.08,
        phone_object_score=0,
        drink_object_score=0,
        food_object_score=0,
    )
    with_object = classify_distracted_activity(
        hand_near_ear=False,
        hand_near_mouth=True,
        mouth_open_score=0.08,
        phone_object_score=0,
        drink_object_score=2,
        food_object_score=0,
    )

    assert without_object == (False, False, False)
    assert with_object == (False, True, False)


def test_single_object_frame_and_hand_motion_do_not_trigger_food_or_drink() -> None:
    result = classify_distracted_activity(
        hand_near_ear=False,
        hand_near_mouth=True,
        mouth_open_score=0.20,
        phone_object_score=0,
        drink_object_score=1,
        food_object_score=1,
    )

    assert result == (False, False, False)


def test_clear_hand_to_mouth_and_jaw_motion_can_detect_eating() -> None:
    result = classify_distracted_activity(
        hand_near_ear=False,
        hand_near_mouth=True,
        mouth_open_score=0.40,
        phone_object_score=0,
        drink_object_score=0,
        food_object_score=0,
    )

    assert result == (False, False, True)


def test_camera_processor_mirrors_frames() -> None:
    image = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(image, format="bgr24")
    processor = CameraProcessor(mirrored=True, show_fps=False, enable_landmarks=False)

    result = processor.recv(frame).to_ndarray(format="bgr24")

    np.testing.assert_array_equal(result, image[:, ::-1])


def test_camera_processor_can_disable_mirroring() -> None:
    image = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(image, format="bgr24")
    processor = CameraProcessor(mirrored=True, show_fps=False, enable_landmarks=False)
    processor.configure(mirrored=False, show_fps=False)

    result = processor.recv(frame).to_ndarray(format="bgr24")

    np.testing.assert_array_equal(result, image)


def test_camera_processor_publishes_bounded_live_signals() -> None:
    image = np.full((120, 160, 3), 128, dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(image, format="bgr24")
    processor = CameraProcessor(mirrored=False, show_fps=False, enable_landmarks=False)

    processor.recv(frame)
    current = processor.session.snapshot().current

    assert current.activity == "No face"
    assert 0.0 <= current.signal_quality <= 100.0
    assert 0.0 <= current.attention <= 100.0
    assert current.brightness == 128.0


def test_cached_closed_eye_result_cannot_advance_sleep_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = FaceLandmarkResult(
        bounding_box=(40, 20, 70, 80),
        eye_aspect_ratio=0.17,
        blink_score=0.8,
        mouth_open_score=0.0,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
        head_yaw=0.0,
    )

    class FakeLandmarker:
        def analyze(self, image: np.ndarray, timestamp_ms: int) -> FaceLandmarkResult:
            return closed

        def close(self) -> None:
            pass

    processor = CameraProcessor(mirrored=False, show_fps=False, enable_landmarks=False)
    processor._landmark_analyzer = FakeLandmarker()  # type: ignore[assignment]
    timestamps = iter((10.0, 12.5))
    monkeypatch.setattr("camera.processor.monotonic", lambda: next(timestamps))
    image = np.full((120, 160, 3), 128, dtype=np.uint8)

    first = processor._analyze(image, fps=2.0)
    cached = processor._analyze(image, fps=2.0)

    assert first.alarm_active is False
    assert cached.alarm_active is False
    assert cached.eye_closure_seconds == 0.0


def test_privacy_blur_changes_only_the_face_region() -> None:
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    image[10:30:2, 10:30] = 255
    original = image.copy()

    CameraProcessor._blur_face(image, (10, 10, 20, 20))

    assert not np.array_equal(image[10:30, 10:30], original[10:30, 10:30])
    np.testing.assert_array_equal(image[:10], original[:10])
