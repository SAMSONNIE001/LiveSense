"""MediaPipe facial landmarks for eye, mouth, and head-state cues."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from importlib import import_module
from math import atan2, degrees, hypot, sqrt
from pathlib import Path

import numpy as np

# MediaPipe imports matplotlib internally. Keep its cache in the system temp
# directory so LiveSense never writes into a user's profile or repository.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "livesense-mpl"))

mp = import_module("mediapipe")


DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "models" / "face_landmarker.task"
)

LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


@dataclass(frozen=True, slots=True)
class FaceLandmarkResult:
    """Cues derived from one MediaPipe face-landmark result."""

    bounding_box: tuple[int, int, int, int]
    eye_aspect_ratio: float
    blink_score: float
    mouth_open_score: float
    eyes_closed: bool
    yawning: bool
    head_pitch: float
    head_yaw: float


def _distance(first: object, second: object) -> float:
    return hypot(float(first.x) - float(second.x), float(first.y) - float(second.y))


def _eye_aspect_ratio(landmarks: list, indexes: tuple[int, ...]) -> float:
    p1, p2, p3, p4, p5, p6 = (landmarks[index] for index in indexes)
    width = max(_distance(p1, p4), 1e-6)
    return (_distance(p2, p6) + _distance(p3, p5)) / (2.0 * width)


def _head_angles(matrix: np.ndarray) -> tuple[float, float]:
    """Return approximate pitch and yaw degrees from a face transform."""
    rotation = matrix[:3, :3]
    sy = sqrt(float(rotation[0, 0] ** 2 + rotation[1, 0] ** 2))
    if sy > 1e-6:
        pitch = atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        yaw = atan2(float(-rotation[2, 0]), sy)
    else:
        pitch = atan2(float(-rotation[1, 2]), float(rotation[1, 1]))
        yaw = atan2(float(-rotation[2, 0]), sy)
    return degrees(pitch), degrees(yaw)


class FaceLandmarkAnalyzer:
    """Run MediaPipe Face Landmarker in video mode."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Face landmark model not found: {path}")
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self._last_timestamp_ms = 0

    def analyze(self, image_bgr: np.ndarray, timestamp_ms: int) -> FaceLandmarkResult | None:
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        image_rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        result = self._landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb),
            timestamp_ms,
        )
        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]
        height, width = image_bgr.shape[:2]
        xs = [float(point.x) for point in landmarks]
        ys = [float(point.y) for point in landmarks]
        left = max(0, int(min(xs) * width))
        top = max(0, int(min(ys) * height))
        right = min(width, int(max(xs) * width))
        bottom = min(height, int(max(ys) * height))

        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE)
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE)
        ear = (left_ear + right_ear) / 2.0

        blendshapes = {
            category.category_name: float(category.score)
            for category in (result.face_blendshapes[0] if result.face_blendshapes else [])
        }
        blink_score = (
            blendshapes.get("eyeBlinkLeft", 0.0) + blendshapes.get("eyeBlinkRight", 0.0)
        ) / 2.0
        mouth_open = blendshapes.get("jawOpen", 0.0)
        eyes_closed = blink_score >= 0.52 or ear < 0.18
        yawning = mouth_open >= 0.58

        pitch = 0.0
        yaw = 0.0
        if result.facial_transformation_matrixes:
            pitch, yaw = _head_angles(result.facial_transformation_matrixes[0])

        return FaceLandmarkResult(
            bounding_box=(left, top, max(1, right - left), max(1, bottom - top)),
            eye_aspect_ratio=ear,
            blink_score=blink_score,
            mouth_open_score=mouth_open,
            eyes_closed=eyes_closed,
            yawning=yawning,
            head_pitch=pitch,
            head_yaw=yaw,
        )

    def close(self) -> None:
        self._landmarker.close()
