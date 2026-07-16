"""Real-time video processing used by the browser WebRTC stream."""

from __future__ import annotations

from threading import Lock

import av
import cv2
import numpy as np

from utils.fps import FPSMeter


class CameraProcessor:
    """Mirror camera frames and draw a lightweight live FPS badge."""

    def __init__(self, mirrored: bool = True, show_fps: bool = True) -> None:
        self._mirrored = mirrored
        self._show_fps = show_fps
        self._settings_lock = Lock()
        self._fps = FPSMeter()

    def configure(self, *, mirrored: bool, show_fps: bool) -> None:
        """Apply UI settings safely while the video thread is running."""
        with self._settings_lock:
            self._mirrored = mirrored
            self._show_fps = show_fps

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Transform one WebRTC video frame."""
        image = frame.to_ndarray(format="bgr24")
        fps = self._fps.tick()

        with self._settings_lock:
            mirrored = self._mirrored
            show_fps = self._show_fps

        if mirrored:
            image = np.ascontiguousarray(image[:, ::-1])
        if show_fps:
            self._draw_fps(image, fps)

        return av.VideoFrame.from_ndarray(image, format="bgr24")

    @staticmethod
    def _draw_fps(image: np.ndarray, fps: float) -> None:
        label = f"LIVE  {fps:4.1f} FPS"
        cv2.rectangle(image, (18, 18), (190, 56), (10, 17, 24), -1)
        cv2.circle(image, (36, 37), 6, (120, 255, 80), -1)
        cv2.putText(
            image,
            label,
            (50, 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (238, 245, 244),
            1,
            cv2.LINE_AA,
        )
