"""Real-time visual and audio-assisted human-state processing."""

from __future__ import annotations

from math import hypot
from threading import Lock
from time import monotonic, time

import av
import cv2
import numpy as np

from analytics import SignalSession
from signals import DrowsinessMonitor, SignalSnapshot, StableObservation
from utils.fps import FPSMeter
from vision import (
    FaceLandmarkAnalyzer,
    FaceLandmarkResult,
    HandPhoneAnalyzer,
    HandPhoneResult,
    ObjectObservation,
    ObjectObservationAnalyzer,
    seatbelt_visible,
)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def classify_distracted_activity(
    *,
    hand_near_ear: bool,
    hand_near_mouth: bool,
    mouth_open_score: float,
    phone_object_score: int,
    drink_object_score: int,
    food_object_score: int,
) -> tuple[bool, bool, bool]:
    """Return raw phone, drinking and eating evidence without cross-classifying them."""
    phone = hand_near_ear or phone_object_score >= 1
    if phone:
        return True, False, False
    drinking = drink_object_score >= 1
    eating = food_object_score >= 1 or (hand_near_mouth and mouth_open_score >= 0.22)
    return False, drinking, eating


class CameraProcessor:
    """Publish low-latency face, sleep, attention, movement, and phone-use signals."""

    def __init__(
        self,
        mirrored: bool = True,
        show_fps: bool = True,
        privacy_blur: bool = False,
        enable_landmarks: bool = True,
        enable_phone_detection: bool = True,
        dozing_seconds: float = 0.25,
        sleeping_seconds: float = 0.70,
    ) -> None:
        self._mirrored = mirrored
        self._show_fps = show_fps
        self._privacy_blur = privacy_blur
        self._settings_lock = Lock()
        self._process_lock = Lock()
        self._fps = FPSMeter()
        self.session = SignalSession()
        self._drowsiness = DrowsinessMonitor(
            dozing_seconds=dozing_seconds,
            sleeping_seconds=sleeping_seconds,
        )

        cascade_root = cv2.data.haarcascades
        self._face_detector = cv2.CascadeClassifier(
            f"{cascade_root}haarcascade_frontalface_default.xml"
        )
        self._eye_detector = cv2.CascadeClassifier(f"{cascade_root}haarcascade_eye.xml")
        self._landmark_analyzer: FaceLandmarkAnalyzer | None = None
        self._phone_analyzer: HandPhoneAnalyzer | None = None
        self._object_analyzer: ObjectObservationAnalyzer | None = None
        if enable_landmarks:
            try:
                self._landmark_analyzer = FaceLandmarkAnalyzer()
            except (FileNotFoundError, RuntimeError, ValueError):
                self._landmark_analyzer = None
        if enable_landmarks and enable_phone_detection:
            try:
                self._phone_analyzer = HandPhoneAnalyzer()
            except (FileNotFoundError, RuntimeError, ValueError):
                self._phone_analyzer = None
            try:
                self._object_analyzer = ObjectObservationAnalyzer()
            except (FileNotFoundError, RuntimeError, ValueError):
                self._object_analyzer = None

        self._previous_motion_frame: np.ndarray | None = None
        self._frame_number = 0
        self._last_face: tuple[int, int, int, int] | None = None
        self._last_landmarks: FaceLandmarkResult | None = None
        self._last_phone_result = HandPhoneResult()
        self._last_object_result = ObjectObservation()
        self._object_streaks = {"phone": 0, "drink": 0, "food": 0}
        self._last_seatbelt_visible = False
        # Object and hand cues must persist before a warning is published.  The
        # longer clear time prevents the top notice from flickering between
        # frames when a cup, phone, hand, or face is briefly occluded.
        self._phone_object = StableObservation(activate_seconds=0.20, clear_seconds=0.80)
        self._phone_hand = StableObservation(activate_seconds=0.35, clear_seconds=0.80)
        self._drinking = StableObservation(activate_seconds=0.35, clear_seconds=0.90)
        self._eating = StableObservation(activate_seconds=0.35, clear_seconds=0.90)
        self._seatbelt_missing = StableObservation(activate_seconds=5.0, clear_seconds=2.0)
        self._face_missing = StableObservation(activate_seconds=2.0, clear_seconds=1.0)
        self._calibration_until = 0.0

    def configure(
        self,
        *,
        mirrored: bool,
        show_fps: bool,
        privacy_blur: bool = False,
    ) -> None:
        with self._settings_lock:
            self._mirrored = mirrored
            self._show_fps = show_fps
            self._privacy_blur = privacy_blur

    def start_calibration(self, duration: float = 10.0) -> None:
        self._calibration_until = monotonic() + duration

    def reset_session(self) -> None:
        self.session.reset()
        self._drowsiness.reset()
        self._last_phone_result = HandPhoneResult()
        self._last_object_result = ObjectObservation()
        self._object_streaks = {"phone": 0, "drink": 0, "food": 0}
        for observation in (
            self._phone_object,
            self._phone_hand,
            self._drinking,
            self._eating,
            self._seatbelt_missing,
            self._face_missing,
        ):
            observation.reset()

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        image = frame.to_ndarray(format="bgr24")
        self.process_image(image)
        return av.VideoFrame.from_ndarray(image, format="bgr24")

    def process_image(self, image: np.ndarray) -> SignalSnapshot:
        """Analyze one BGR camera frame and publish its latest safety signals."""
        with self._process_lock:
            return self._process_image_locked(image)

    def _process_image_locked(self, image: np.ndarray) -> SignalSnapshot:
        fps = self._fps.tick()
        with self._settings_lock:
            mirrored = self._mirrored
            privacy_blur = self._privacy_blur
        if mirrored:
            image[:] = image[:, ::-1].copy()

        analysis_image, scale_x, scale_y = self._analysis_frame(image)
        snapshot = self._analyze(analysis_image, fps)
        self.session.update(snapshot)
        if self._last_face is not None:
            x, y, width, height = self._last_face
            display_face = (
                int(x * scale_x),
                int(y * scale_y),
                int(width * scale_x),
                int(height * scale_y),
            )
        else:
            display_face = None
        if privacy_blur and display_face is not None:
            self._blur_face(image, display_face)
        return snapshot

    @staticmethod
    def _analysis_frame(image: np.ndarray, max_width: int = 480) -> tuple[np.ndarray, float, float]:
        """Return a smaller inference frame while preserving the clear output frame."""
        height, width = image.shape[:2]
        if width <= max_width:
            return image, 1.0, 1.0
        analysis_width = max_width
        analysis_height = max(1, round(height * analysis_width / width))
        resized = cv2.resize(image, (analysis_width, analysis_height), interpolation=cv2.INTER_AREA)
        return resized, width / analysis_width, height / analysis_height

    def _analyze(self, image: np.ndarray, fps: float) -> SignalSnapshot:
        now = monotonic()
        self._frame_number += 1
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        clarity = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        motion = self._measure_motion(gray)

        landmarks = self._detect_landmarks(image, now)
        if landmarks is not None:
            self._last_face = landmarks.bounding_box
            face = landmarks.bounding_box
            face_detected = True
            eyes_closed = landmarks.eyes_closed
            yawning = landmarks.yawning
            head_pitch = landmarks.head_pitch
            head_yaw = landmarks.head_yaw
            eyes_detected = 0 if eyes_closed else 2
        elif self._landmark_analyzer is None:
            face, eyes_detected = self._haar_fallback(gray, image.shape[1])
            face_detected = face is not None
            # Haar eye absence is too ambiguous to activate a sleep alarm. It is
            # used for attention fallback only; sleep decisions require landmarks.
            eyes_closed = False
            yawning = False
            head_pitch = 0.0
            head_yaw = 0.0
        else:
            face = None
            eyes_detected = 0
            face_detected = False
            eyes_closed = False
            yawning = False
            head_pitch = 0.0
            head_yaw = 0.0
        self._last_face = face

        attention, face_scale_score = self._attention_scores(
            face, gray.shape, eyes_detected, head_yaw
        )
        drowsiness = self._drowsiness.update(
            timestamp=now,
            face_detected=landmarks is not None,
            eyes_closed=eyes_closed,
            yawning=yawning,
            head_pitch=head_pitch,
        )
        phone_result = self._detect_phone_use(image, face, now)
        self._detect_objects(image, face, phone_result.palm_positions, now)
        mouth_open_score = landmarks.mouth_open_score if landmarks is not None else 0.0
        phone_raw, drinking_raw, eating_raw = classify_distracted_activity(
            hand_near_ear=phone_result.hand_near_ear,
            hand_near_mouth=phone_result.hand_near_mouth,
            mouth_open_score=mouth_open_score,
            phone_object_score=self._object_streaks["phone"],
            drink_object_score=self._object_streaks["drink"],
            food_object_score=self._object_streaks["food"],
        )
        phone_object_active = self._phone_object.update(
            phone_raw and self._object_streaks["phone"] >= 1,
            now,
        )
        phone_hand_active = self._phone_hand.update(phone_raw and phone_result.hand_near_ear, now)
        phone_at_ear = phone_object_active or phone_hand_active
        drinking_detected = self._drinking.update(drinking_raw, now)
        eating_detected = self._eating.update(eating_raw, now)
        if phone_at_ear:
            self._drinking.reset()
            self._eating.reset()
            drinking_detected = False
            eating_detected = False
        if face is not None and self._frame_number % 6 == 1:
            self._last_seatbelt_visible = seatbelt_visible(image, face)
        seatbelt_warning = self._seatbelt_missing.update(
            face_detected and not self._last_seatbelt_visible,
            now,
        )
        face_missing_warning = self._face_missing.update(not face_detected, now)

        lighting_score = _clamp(100.0 - abs(brightness - 128.0) * 0.75)
        clarity_score = _clamp(clarity / 4.0)
        signal_quality = _clamp(
            lighting_score * 0.30
            + clarity_score * 0.20
            + face_scale_score * 0.35
            + (15.0 if face_detected else 0.0)
        )
        fatigue = drowsiness.score
        tension = _clamp(motion * 2.6)
        readiness = _clamp(attention * 0.42 + signal_quality * 0.33 + (100.0 - fatigue) * 0.25)

        if drowsiness.alarm_active:
            activity = "Sleeping"
            status = "SLEEP ALARM"
        elif drowsiness.state in {"Dozing", "Drowsy"}:
            activity = drowsiness.state
            status = "Drowsiness Detected"
        elif phone_at_ear:
            activity = "Phone use"
            status = "Phone Warning"
        elif drinking_detected:
            activity = "Drinking"
            status = "Drinking Warning"
        elif eating_detected:
            activity = "Eating"
            status = "Eating Warning"
        elif seatbelt_warning:
            activity = "Seat belt not visible"
            status = "Seat Belt Warning"
        elif face_missing_warning:
            activity = "No face"
            status = "Face Not Detected"
        elif not face_detected:
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
            sleep_state=drowsiness.state,
            eyes_closed=eyes_closed,
            eye_closure_seconds=drowsiness.eye_closure_seconds,
            drowsiness=drowsiness.score,
            head_pitch=head_pitch,
            yawning=yawning,
            cough_detected=False,
            cough_count=0,
            audio_level=0.0,
            alarm_active=drowsiness.alarm_active,
            phone_at_ear=phone_at_ear,
            phone_side=phone_result.side if phone_at_ear else "",
            eating_detected=eating_detected,
            drinking_detected=drinking_detected,
            seatbelt_visible=self._last_seatbelt_visible,
            seatbelt_warning=seatbelt_warning,
            face_missing_warning=face_missing_warning,
        )

    def _detect_landmarks(
        self,
        image: np.ndarray,
        now: float,
    ) -> FaceLandmarkResult | None:
        if self._landmark_analyzer is None:
            return None
        if self._frame_number % 3 == 1:
            try:
                self._last_landmarks = self._landmark_analyzer.analyze(image, int(now * 1000))
            except (RuntimeError, ValueError):
                self._last_landmarks = None
        return self._last_landmarks

    def _detect_phone_use(
        self,
        image: np.ndarray,
        face: tuple[int, int, int, int] | None,
        now: float,
    ) -> HandPhoneResult:
        if self._phone_analyzer is None or face is None:
            self._last_phone_result = HandPhoneResult()
            return self._last_phone_result
        if self._frame_number % 3 == 1:
            try:
                self._last_phone_result = self._phone_analyzer.analyze(
                    image,
                    face,
                    int(now * 1000),
                )
            except (RuntimeError, ValueError):
                self._last_phone_result = HandPhoneResult()
        return self._last_phone_result

    def _detect_objects(
        self,
        image: np.ndarray,
        face: tuple[int, int, int, int] | None,
        hand_points: tuple[tuple[float, float], ...],
        now: float,
    ) -> ObjectObservation:
        if self._object_analyzer is None or face is None:
            self._last_object_result = ObjectObservation()
            self._object_streaks = {"phone": 0, "drink": 0, "food": 0}
            return self._last_object_result
        if self._frame_number % 4 == 1:
            try:
                self._last_object_result = self._object_analyzer.analyze(
                    image,
                    face,
                    int(now * 1000),
                    hand_points,
                )
            except (RuntimeError, ValueError):
                self._last_object_result = ObjectObservation()
            observed = {
                "phone": (
                    self._last_object_result.phone_near_ear
                    or self._last_object_result.phone_near_hand
                ),
                "drink": self._last_object_result.drink_near_mouth,
                "food": self._last_object_result.food_near_mouth,
            }
            for name, active in observed.items():
                if active:
                    self._object_streaks[name] = min(3, self._object_streaks[name] + 1)
                else:
                    self._object_streaks[name] = max(0, self._object_streaks[name] - 1)
        return self._last_object_result

    def _haar_fallback(
        self,
        gray: np.ndarray,
        frame_width: int,
    ) -> tuple[tuple[int, int, int, int] | None, int]:
        if self._frame_number % 4 == 1 or self._last_face is None:
            faces = self._face_detector.detectMultiScale(
                gray,
                scaleFactor=1.14,
                minNeighbors=5,
                minSize=(max(50, frame_width // 12),) * 2,
            )
            self._last_face = max(faces, key=lambda box: box[2] * box[3], default=None)
        face = self._last_face
        if face is None:
            return None, 0
        x, y, width, height = face
        face_region = gray[y : y + int(height * 0.62), x : x + width]
        eyes = self._eye_detector.detectMultiScale(
            face_region,
            scaleFactor=1.12,
            minNeighbors=5,
            minSize=(max(12, width // 10), max(8, height // 12)),
        )
        return face, len(eyes)

    @staticmethod
    def _attention_scores(
        face: tuple[int, int, int, int] | None,
        frame_shape: tuple[int, int],
        eyes_detected: int,
        head_yaw: float,
    ) -> tuple[float, float]:
        if face is None:
            return 0.0, 0.0
        x, y, width, height = face
        frame_height, frame_width = frame_shape
        center_x = x + width / 2
        center_y = y + height / 2
        offset = hypot(
            (center_x - frame_width / 2) / (frame_width / 2),
            (center_y - frame_height / 2) / (frame_height / 2),
        )
        center_score = _clamp(100.0 - offset * 95.0)
        yaw_penalty = min(35.0, abs(head_yaw) * 1.4)
        attention = _clamp(center_score * 0.82 + min(eyes_detected, 2) * 9.0 - yaw_penalty)
        area_ratio = (width * height) / (frame_width * frame_height)
        scale_score = _clamp(100.0 - abs(area_ratio - 0.18) * 420.0)
        return attention, scale_score

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
        red = (48, 48, 235)
        if face is not None:
            x, y, width, height = face
            color = red if snapshot.alarm_active else green if snapshot.attention >= 48.0 else amber
            cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)

        badges = [
            (f"State: {snapshot.sleep_state}", snapshot.sleep_state == "Awake"),
            (f"Eyes: {'closed' if snapshot.eyes_closed else 'open'}", not snapshot.eyes_closed),
            (f"Coughs: {snapshot.cough_count}", not snapshot.cough_detected),
            (f"Activity: {snapshot.activity}", snapshot.activity == "Attentive"),
        ]
        if show_fps:
            badges.append((f"{snapshot.fps:4.1f} FPS", True))

        y_position = image.shape[0] - 18 - (len(badges) - 1) * 27
        for label, positive in badges:
            color = green if positive else red if snapshot.alarm_active else amber
            label_width = max(126, 18 + len(label) * 8)
            cv2.rectangle(
                image,
                (14, y_position - 19),
                (14 + label_width, y_position + 5),
                (20, 25, 26),
                -1,
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

        if snapshot.alarm_active:
            cv2.rectangle(image, (4, 4), (image.shape[1] - 5, image.shape[0] - 5), red, 6)
            cv2.rectangle(image, (0, 0), (image.shape[1], 54), (28, 28, 180), -1)
            cv2.putText(
                image,
                "WAKE UP - SLEEP DETECTED",
                (20, 37),
                cv2.FONT_HERSHEY_DUPLEX,
                0.9,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        elif snapshot.calibration_remaining > 0:
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

    def __del__(self) -> None:
        analyzer = getattr(self, "_landmark_analyzer", None)
        if analyzer is not None:
            try:
                analyzer.close()
            except RuntimeError:
                pass
        phone_analyzer = getattr(self, "_phone_analyzer", None)
        if phone_analyzer is not None:
            try:
                phone_analyzer.close()
            except RuntimeError:
                pass
        object_analyzer = getattr(self, "_object_analyzer", None)
        if object_analyzer is not None:
            try:
                object_analyzer.close()
            except RuntimeError:
                pass
