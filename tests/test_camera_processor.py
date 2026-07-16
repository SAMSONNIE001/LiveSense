"""Tests for the real-time camera frame processor."""

import av
import numpy as np

from camera import CameraProcessor


def test_camera_processor_mirrors_frames() -> None:
    image = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(image, format="bgr24")
    processor = CameraProcessor(mirrored=True, show_fps=False)

    result = processor.recv(frame).to_ndarray(format="bgr24")

    np.testing.assert_array_equal(result, image[:, ::-1])


def test_camera_processor_can_disable_mirroring() -> None:
    image = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(image, format="bgr24")
    processor = CameraProcessor(mirrored=True, show_fps=False)
    processor.configure(mirrored=False, show_fps=False)

    result = processor.recv(frame).to_ndarray(format="bgr24")

    np.testing.assert_array_equal(result, image)
