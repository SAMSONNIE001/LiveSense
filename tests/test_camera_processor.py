"""Tests for the real-time camera frame processor."""

import av
import numpy as np

from camera import CameraProcessor


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


def test_privacy_blur_changes_only_the_face_region() -> None:
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    image[10:30:2, 10:30] = 255
    original = image.copy()

    CameraProcessor._blur_face(image, (10, 10, 20, 20))

    assert not np.array_equal(image[10:30, 10:30], original[10:30, 10:30])
    np.testing.assert_array_equal(image[:10], original[:10])
