"""Object-assisted driver observations for phone, eating, and drinking cues."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from importlib import import_module
from math import hypot
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "livesense-mpl"))

mp = import_module("mediapipe")

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "models" / "efficientdet_lite0.tflite"
)

PHONE_LABELS = {"cell phone"}
DRINK_LABELS = {"bottle", "wine glass", "cup"}
FOOD_LABELS = {
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
}
OBSERVATION_LABELS = sorted(PHONE_LABELS | DRINK_LABELS | FOOD_LABELS)


@dataclass(frozen=True, slots=True)
class ObjectObservation:
    """Relevant object cues positioned around the face."""

    phone_near_ear: bool = False
    drink_near_mouth: bool = False
    food_near_mouth: bool = False
    strongest_label: str = ""


def _distance_to_box(point: tuple[float, float], box: tuple[int, int, int, int]) -> float:
    x, y, width, height = box
    nearest_x = max(x, min(point[0], x + width))
    nearest_y = max(y, min(point[1], y + height))
    return hypot(point[0] - nearest_x, point[1] - nearest_y)


def classify_object_cues(
    objects: list[tuple[str, float, tuple[int, int, int, int]]],
    face_box: tuple[int, int, int, int],
) -> ObjectObservation:
    """Interpret labelled object boxes relative to approximate ears and mouth."""
    left, top, width, height = face_box
    ears = ((left, top + height * 0.48), (left + width, top + height * 0.48))
    mouth = (left + width * 0.5, top + height * 0.76)
    phone_radius = max(width * 0.52, height * 0.34)
    mouth_radius = max(width * 0.62, height * 0.34)

    phone = False
    drinking = False
    eating = False
    strongest_label = ""
    strongest_score = 0.0
    for label, score, box in objects:
        if score > strongest_score:
            strongest_score = score
            strongest_label = label
        near_ear = min(_distance_to_box(ear, box) for ear in ears) <= phone_radius
        if label in PHONE_LABELS and near_ear:
            phone = True
        elif label in DRINK_LABELS and _distance_to_box(mouth, box) <= mouth_radius:
            drinking = True
        elif label in FOOD_LABELS and _distance_to_box(mouth, box) <= mouth_radius:
            eating = True
    return ObjectObservation(phone, drinking, eating, strongest_label)


def seatbelt_visible(
    image_bgr: np.ndarray,
    face_box: tuple[int, int, int, int],
) -> bool:
    """Look for a sustained diagonal belt-like edge across the upper torso."""
    frame_height, frame_width = image_bgr.shape[:2]
    left, top, width, height = face_box
    x1 = max(0, int(left - width * 0.65))
    x2 = min(frame_width, int(left + width * 1.65))
    y1 = max(0, int(top + height * 0.88))
    y2 = min(frame_height, int(top + height * 2.65))
    roi = image_bgr[y1:y2, x1:x2]
    if roi.shape[0] < max(24, int(height * 0.45)) or roi.shape[1] < 40:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 120)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(18, width // 5),
        minLineLength=max(28, int(width * 0.48)),
        maxLineGap=max(8, width // 10),
    )
    if lines is None:
        return False
    for x_start, y_start, x_end, y_end in np.asarray(lines).reshape(-1, 4):
        dx = abs(int(x_end) - int(x_start))
        dy = abs(int(y_end) - int(y_start))
        if dx > 0 and 0.42 <= dy / dx <= 2.4:
            return True
    return False


class ObjectObservationAnalyzer:
    """Run a filtered object detector and map detections to driver observations."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Object detector model not found: {path}")
        options = mp.tasks.vision.ObjectDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            max_results=5,
            score_threshold=0.34,
            category_allowlist=OBSERVATION_LABELS,
        )
        self._detector = mp.tasks.vision.ObjectDetector.create_from_options(options)
        self._last_timestamp_ms = 0

    def analyze(
        self,
        image_bgr: np.ndarray,
        face_box: tuple[int, int, int, int],
        timestamp_ms: int,
    ) -> ObjectObservation:
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        image_rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        result = self._detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb),
            timestamp_ms,
        )
        objects: list[tuple[str, float, tuple[int, int, int, int]]] = []
        for detection in result.detections:
            if not detection.categories:
                continue
            category = detection.categories[0]
            bounding_box = detection.bounding_box
            objects.append(
                (
                    str(category.category_name),
                    float(category.score),
                    (
                        int(bounding_box.origin_x),
                        int(bounding_box.origin_y),
                        int(bounding_box.width),
                        int(bounding_box.height),
                    ),
                )
            )
        return classify_object_cues(objects, face_box)

    def close(self) -> None:
        self._detector.close()
