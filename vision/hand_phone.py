"""Low-frequency hand-at-ear detection for possible phone use."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from importlib import import_module
from math import hypot
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "livesense-mpl"))

mp = import_module("mediapipe")

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "models" / "hand_landmarker.task"
)


@dataclass(frozen=True, slots=True)
class HandPhoneResult:
    """Result of checking whether a detected hand is held beside an ear."""

    hand_near_ear: bool = False
    side: str = ""


def hand_near_face_ear(
    palm: tuple[float, float],
    face_box: tuple[int, int, int, int],
) -> HandPhoneResult:
    """Classify an image-space palm position against an image-space face box."""
    left, top, width, height = face_box
    if width <= 0 or height <= 0:
        return HandPhoneResult()
    ear_y = top + height * 0.48
    radius = max(width * 0.48, height * 0.3)
    left_distance = hypot(palm[0] - left, palm[1] - ear_y)
    right_distance = hypot(palm[0] - (left + width), palm[1] - ear_y)
    distance = min(left_distance, right_distance)
    if distance > radius:
        return HandPhoneResult()
    return HandPhoneResult(True, "left" if left_distance <= right_distance else "right")


class HandPhoneAnalyzer:
    """Track one hand and report a hand held next to either ear."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Hand landmark model not found: {path}")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = 0

    def analyze(
        self,
        image_bgr: np.ndarray,
        face_box: tuple[int, int, int, int],
        timestamp_ms: int,
    ) -> HandPhoneResult:
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        image_rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        result = self._landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb),
            timestamp_ms,
        )
        if not result.hand_landmarks:
            return HandPhoneResult()

        landmarks = result.hand_landmarks[0]
        height, width = image_bgr.shape[:2]
        palm_indexes = (0, 5, 9, 13, 17)
        palm = (
            sum(float(landmarks[index].x) for index in palm_indexes) * width / len(palm_indexes),
            sum(float(landmarks[index].y) for index in palm_indexes) * height / len(palm_indexes),
        )
        return hand_near_face_ear(palm, face_box)

    def close(self) -> None:
        self._landmarker.close()
