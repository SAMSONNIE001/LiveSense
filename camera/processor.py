"""Real-time visual signal processing for the browser WebRTC stream."""

from __future__ import annotations

from math import hypot
from threading import Lock
from time import monotonic, time

import av
import cv2
import numpy as np

from analytics import SignalSession
from signals import SignalSnapshot
from utils.fps import FPSMeter


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class CameraProcessor:
    """Detect face presence, motion, attention proxies, and signal quality."""

    def __init__(
        self,
        mirrored: bool = True,
        show_fps: bool = True,
        privacy_blur: bool = False,
    ) -> None:
        self._mirrored = mirrored
        self._show_fps = show_fps
        self._privacy_blur = privacy_blur
        self._settings_lock = Lock()
        self._fps = FPSMeter()
        self.session = SignalSession()

        cascade_root = cv2.data.haarcascades
        self._face_detector = cv2.CascadeClassifier(
            f"{cascade_root}haarcascade_frontalface_default.xml"
        )
        self._eye_detector = cv2.CascadeClassifier(f"{cascade_root}haarcascade_eye.xml")
        self._previous_motion_frame: np.ndarray | None = None
        self._frame_number = 0
        self._last_face: tuple[int, int, int, int] | None = None
        self._eyes_missing_for = 0.0
        self._last_frame_at = monotonic()
        self._calibration_until = 0.0

    def configure(
        self,
        *,
        mirrored: bool,
        show_fps: bool,
        privacy_blur: bool = False,
    ) -> None:
        """Apply UI settings safely while the video thread is running."""
        with self._settings_lock:
            self._mirrored = mirrored
            self._show_fps = show_fps
            self._privacy_blur = privacy_blur

    def start_calibration(self, duration: float = 10.0) -> None:
        """Start a visible baseline observation window."""
        self._calibration_until = monotonic() + duration

    def reset_session(self) -> None:
        """Clear all rolling charts and event insights."""
        self.session.reset()
        self._eyes_missing_for = 0.0

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Transform one WebRTC frame and publish its live signal snapshot."""
        image = frame.to_ndarray(format="bgr24")
        fps = self._fps.tick()

        with self._settings_lock:
            mirrored = self._mirrored
            show_fps = self._show_fps
            privacy_blur = self._privacy_blur
        if mirrored:
            image = np.ascontiguousarray(image[:, ::-1])

        snapshot = self._analyze(image, fps)
        self.session.update(snapshot)
        if privacy_blur and self._last_face is not None:
            self._blur_face(image, self._last_face)
        self._draw_overlay(image, snapshot, self._last_face, show_fps)
        return av.VideoFrame.from_ndarray(image, format="bgr24")

    def _analyze(self, image: np.ndarray, fps: float) -> SignalSnapshot:
        now = monotonic()
        frame_interval = min(0.25, max(0.0, now - self._last_frame_at))
        self._last_frame_at = now
        self._frame_number += 1

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        clarity = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        motion = self._measure_motion(gray)

        if self._frame_number % 4 == 1 or self._last_face is None:
            faces = self._face_detector.detectMultiScale(
                gray,
                scaleFactor=1.14,
                minNeighbors=5,
                minSize=(max(50, image.shape[1] // 12),) * 2,
            )
            self._last_face = max(faces, key=lambda box: box[2] * box[3], default=None)

        face = self._last_face
        face_detected = face is not None
        eyes_detected = 0
        attention = 0.0
        face_scale_score = 0.0

        if face is not None:
            x, y, width, height = face
            face_region = gray[y : y + int(height * 0.62), x : x + width]
            eyes = self._eye_detector.detectMultiScale(
                face_region,
                scaleFactor=1.12,
                minNeighbors=5,
                minSize=(max(12, width // 10), max(8, height // 12)),
            )
            eyes_detected = len(eyes)
            frame_height, frame_width = gray.shape
            center_x = x + width / 2
            center_y = y + height / 2
            offset = hypot(
                (center_x - frame_width / 2) / (frame_width / 2),
                (center_y - frame_height / 2) / (frame_height / 2),
            )
            center_score = _clamp(100.0 - offset * 95.0)
            attention = _clamp(center_score * 0.82 + min(eyes_detected, 2) * 9.0)
            area_ratio = (width * height) / (frame_width * frame_height)
            face_scale_score = _clamp(100.0 - abs(area_ratio - 0.18) * 420.0)

        if face_detected and eyes_detected == 0:
            self._eyes_missing_for += frame_interval
        else:
            self._eyes_missing_for = max(0.0, self._eyes_missing_for - frame_interval * 2.0)

        lighting_score = _clamp(100.0 - abs(brightness - 128.0) * 0.75)
        clarity_score = _clamp(clarity / 4.0)
        signal_quality = _clamp(
            lighting_score * 0.30
            + clarity_score * 0.20
            + face_scale_score * 0.35
            + (15.0 if face_detected else 0.0)
        )
        fatigue = 0.0 if not face_detected else _clamp(8.0 + self._eyes_missing_for * 16.0)
        tension = _clamp(motion * 2.6)
        readiness = _clamp(attention * 0.45 + signal_quality * 0.35 + (100.0 - fatigue) * 0.20)

        if not face_detected:
            activity = "No face"
            status = "Signal Interrupted"
        elif attention < 48.0:
            activity = "Looking away"
            status = "Needs Attention"
        elif motion > 16.0:
            activity = "Moving"
            status = "Monitoring Movement"
        else:
            activity = "Attentive"
            status = "Normal" if readiness >= 60.0 else "Calibrating"

        return SignalSnapshot(
            timestamp=time(),
            face_detected=face_detected,
            activity=activity,
            driver_status=status,
            fatigue=fatigue,
            attention=attention,
            readiness=readiness,
            tension=tension,
            signal_quality=signal_quality,
            fps=fps,
            brightness=brightness,
            calibration_remaining=max(0.0, self._calibration_until - now),
        )

    def _measure_motion(self, gray: np.ndarray) -> float:
        sample = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
        if self._previous_motion_frame is None:
            motion = 0.0
        else:
            motion = float(cv2.absdiff(sample, self._previous_motion_frame).mean())
        self._previous_motion_frame = sample
        return motion

    @staticmethod
    def _blur_face(image: np.ndarray, face: tuple[int, int, int, int]) -> None:
        x, y, width, height = face
        region = image[y : y + height, x : x + width]
        if region.size:
            kernel = max(15, (min(width, height) // 5) | 1)
            image[y : y + height, x : x + width] = cv2.GaussianBlur(
                region,
                (kernel, kernel),
                0,
            )

    @staticmethod
    def _draw_overlay(
        image: np.ndarray,
        snapshot: SignalSnapshot,
        face: tuple[int, int, int, int] | None,
        show_fps: bool,
    ) -> None:
        green = (62, 180, 116)
        amber = (34, 155, 233)
        if face is not None:
            x, y, width, height = face
            color = green if snapshot.attention >= 48.0 else amber
            cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)

        badges = [
            ("Face detected" if snapshot.face_detected else "No face", snapshot.face_detected),
            (
                "Signal stable" if snapshot.signal_quality >= 55.0 else "Signal adjusting",
                snapshot.signal_quality >= 55.0,
            ),
            (f"Activity: {snapshot.activity}", snapshot.activity == "Attentive"),
        ]
        if show_fps:
            badges.append((f"{snapshot.fps:4.1f} FPS", True))

        y_position = image.shape[0] - 18 - (len(badges) - 1) * 27
        for label, positive in badges:
            color = green if positive else amber
            width = max(126, 18 + len(label) * 8)
            cv2.rectangle(
                image, (14, y_position - 19), (14 + width, y_position + 5), (20, 25, 26), -1
            )
            cv2.rectangle(image, (14, y_position - 19), (18, y_position + 5), color, -1)
            cv2.putText(
                image,
                label,
                (25, y_position),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (245, 248, 247),
                1,
                cv2.LINE_AA,
            )
            y_position += 27

        if snapshot.calibration_remaining > 0:
            text = f"Calibrating baseline: {snapshot.calibration_remaining:.0f}s"
            cv2.putText(
                image,
                text,
                (image.shape[1] - 270, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
