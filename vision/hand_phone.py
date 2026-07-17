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
    hand_near_mouth: bool = False
    palm_positions: tuple[tuple[float, float], ...] = ()


def hand_near_face_ear(
    palm: tuple[float, float],
    face_box: tuple[int, int, int, int],
) -> HandPhoneResult:
    """Classify an image-space palm position against an image-space face box."""
    left, top, width, height = face_box
    if width <= 0 or height <= 0:
        return HandPhoneResult()
    ear_y = top + height * 0.48
    radius = max(width * 0.68, height * 0.42)
    left_distance = hypot(palm[0] - left, palm[1] - ear_y)
    right_distance = hypot(palm[0] - (left + width), palm[1] - ear_y)
    distance = min(left_distance, right_distance)
    beside_face = palm[0] <= left + width * 0.38 or palm[0] >= left + width * 0.62
    if distance > radius or not beside_face:
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
            num_hands=2,
            min_hand_detection_confidence=0.30,
            min_hand_presence_confidence=0.30,
            min_tracking_confidence=0.30,
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

        height, width = image_bgr.shape[:2]
        palm_indexes = (0, 5, 9, 13, 17)
        left, top, face_width, face_height = face_box
        mouth = (left + face_width * 0.5, top + face_height * 0.76)
        mouth_radius = max(face_width * 0.82, face_height * 0.52)
        palms: list[tuple[float, float]] = []
        near_ear = False
        side = ""
        near_mouth = False
        for landmarks in result.hand_landmarks:
            palm = (
                sum(float(landmarks[index].x) for index in palm_indexes)
                * width
                / len(palm_indexes),
                sum(float(landmarks[index].y) for index in palm_indexes)
                * height
                / len(palm_indexes),
            )
            palms.append(palm)
            ear_result = hand_near_face_ear(palm, face_box)
            if ear_result.hand_near_ear and not near_ear:
                near_ear = True
                side = ear_result.side
            near_mouth = near_mouth or (
                not ear_result.hand_near_ear
                and hypot(palm[0] - mouth[0], palm[1] - mouth[1]) <= mouth_radius
            )
        return HandPhoneResult(near_ear, side, near_mouth, tuple(palms))

    def close(self) -> None:
        self._landmarker.close()
