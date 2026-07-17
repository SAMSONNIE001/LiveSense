"""Reference-aligned LiveSense monitoring dashboard."""

from __future__ import annotations

from datetime import datetime
from html import escape
from textwrap import dedent

import streamlit as st
import streamlit.components.v1 as components
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from camera import CameraProcessor
from config import load_settings
from dashboard.theme import THEME_CSS
from signals import SignalSnapshot


def _processor() -> CameraProcessor | None:
    value = st.session_state.get("live_processor")
    return value if isinstance(value, CameraProcessor) else None


def _live_view() -> tuple[SignalSnapshot, tuple, tuple]:
    processor = _processor()
    if processor is None:
        return SignalSnapshot.waiting(), (), ()
    view = processor.session.snapshot()
    return view.current, view.history, view.events


def _quality_label(value: float) -> str:
    if value >= 72:
        return "Stable"
    if value >= 45:
        return "Adjusting"
    return "Weak"


def _render_alarm_notification() -> None:
    """Emit one browser notification and audible alarm per sleep episode."""
    st.html(
        """
        <script>
          const active = sessionStorage.getItem("livesense-alarm-active") === "true";
          if (!active) {
            sessionStorage.setItem("livesense-alarm-active", "true");
            if (window.Notification && Notification.permission === "granted") {
              window.__livesenseAlarmNotification = new Notification("LiveSense sleep alarm", {
                body: "Sleep detected. Pull over now and stop in a safe place.",
                requireInteraction: true,
                tag: "livesense-sleep-warning"
              });
            }
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
              const context = new AudioContext();
              [0, 0.35, 0.7].forEach((delay) => {
                const oscillator = context.createOscillator();
                const gain = context.createGain();
                oscillator.type = "square";
                oscillator.frequency.value = 880;
                gain.gain.setValueAtTime(0.18, context.currentTime + delay);
                gain.gain.exponentialRampToValueAtTime(
                  0.001, context.currentTime + delay + 0.22
                );
                oscillator.connect(gain).connect(context.destination);
                oscillator.start(context.currentTime + delay);
                oscillator.stop(context.currentTime + delay + 0.24);
              });
            }
          }
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _clear_alarm_notification() -> None:
    st.html(
        """
        <script>
          sessionStorage.setItem("livesense-alarm-active", "false");
          if (window.__livesenseAlarmNotification) {
            window.__livesenseAlarmNotification.close();
            window.__livesenseAlarmNotification = null;
          }
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _render_notification_permission() -> None:
    st.html(
        """
        <div id="livesense-alert-widget">
          <button id="alerts">Enable alarm notifications</button>
          <span id="state"></span>
        </div>
        <style>
          #livesense-alert-widget {
            margin: 0; font: 11px "Segoe UI", sans-serif; color: #52625d;
          }
          #livesense-alert-widget button {
            width: 100%; padding: 7px; border: 1px solid #d9e2de;
            border-radius: 5px; background: white; cursor: pointer;
          }
          #livesense-alert-widget #state {
            display: block; margin-top: 4px; font-size: 10px;
          }
        </style>
        <script>
          const state = document.getElementById("state");
          const button = document.getElementById("alerts");
          const show = () => {
            state.textContent = window.Notification
              ? `Notification permission: ${Notification.permission}`
              : "Browser notifications unavailable";
          };
          button.onclick = async () => {
            if (window.Notification) await Notification.requestPermission();
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) { const context = new AudioContext(); await context.resume(); }
            show();
          };
          show();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _render_local_camera_preview(active: bool) -> None:
    """Render the webcam directly in the browser without a Python round trip."""
    preview_html = """
        <div id="livesense-preview-shell">
          <video id="livesense-preview" autoplay muted playsinline></video>
          <canvas id="livesense-face-overlay"></canvas>
          <div id="livesense-detection-badge"><span></span>FACE TRACKING</div>
          <div id="livesense-preview-state">Start camera for live monitoring</div>
        </div>
        <style>
          #livesense-preview-shell {
            position: relative; width: 100%; overflow: hidden;
            border-radius: 4px; background: #17201e; aspect-ratio: 16 / 9;
          }
          #livesense-preview {
            display: block; width: 100%; height: 100%; object-fit: cover;
            transform: scaleX(-1);
          }
          #livesense-face-overlay {
            position: absolute; inset: 0; width: 100%; height: 100%;
            pointer-events: none;
          }
          #livesense-detection-badge {
            position: absolute; top: 9px; left: 9px; display: none;
            align-items: center; gap: 5px; padding: 4px 7px;
            border: 1px solid rgba(30, 226, 166, .45); border-radius: 4px;
            background: rgba(3, 16, 25, .8); color: #55efbd;
            font: 700 9px "Segoe UI", sans-serif; letter-spacing: .04em;
          }
          #livesense-detection-badge span {
            width: 6px; height: 6px; border-radius: 50%; background: #20e3a3;
            box-shadow: 0 0 7px rgba(32, 227, 163, .9);
          }
          #livesense-detection-badge.searching {
            border-color: rgba(241, 163, 31, .45); color: #ffc55d;
          }
          #livesense-detection-badge.searching span {
            background: #f1a31f; box-shadow: 0 0 7px rgba(241, 163, 31, .8);
          }
          #livesense-preview-state {
            position: absolute; inset: 0; display: grid; place-items: center;
            color: white; background: #17201e; font: 12px "Segoe UI", sans-serif;
          }
        </style>
        <script type="module">
          const preview = document.getElementById("livesense-preview");
          const overlay = document.getElementById("livesense-face-overlay");
          const overlayContext = overlay.getContext("2d");
          const detectionBadge = document.getElementById("livesense-detection-badge");
          const state = document.getElementById("livesense-preview-state");
          const active = __LIVESENSE_ACTIVE__;
          let previewStream = null;
          let faceLandmarker = null;
          let lastVideoTime = -1;
          let lastInferenceAt = 0;
          let overlayRunning = true;
          const stopPreview = () => {
            overlayRunning = false;
            if (faceLandmarker) faceLandmarker.close();
            if (previewStream) previewStream.getTracks().forEach((track) => track.stop());
          };
          const setBadge = (detected, text) => {
            detectionBadge.style.display = "flex";
            detectionBadge.classList.toggle("searching", !detected);
            detectionBadge.lastChild.textContent = text;
          };
          const syncOverlaySize = () => {
            overlay.width = Math.max(1, Math.round(preview.clientWidth));
            overlay.height = Math.max(1, Math.round(preview.clientHeight));
          };
          const drawFace = (landmarks) => {
            const width = overlay.width;
            const height = overlay.height;
            const videoWidth = preview.videoWidth || width;
            const videoHeight = preview.videoHeight || height;
            const coverScale = Math.max(width / videoWidth, height / videoHeight);
            const shownWidth = videoWidth * coverScale;
            const shownHeight = videoHeight * coverScale;
            const offsetX = (width - shownWidth) / 2;
            const offsetY = (height - shownHeight) / 2;
            const points = landmarks.map((point) => ({
              x: width - (offsetX + point.x * shownWidth),
              y: offsetY + point.y * shownHeight
            }));
            const xs = points.map((point) => point.x);
            const ys = points.map((point) => point.y);
            const paddingX = width * .025;
            const paddingY = height * .035;
            const left = Math.max(2, Math.min(...xs) - paddingX);
            const right = Math.min(width - 2, Math.max(...xs) + paddingX);
            const top = Math.max(2, Math.min(...ys) - paddingY);
            const bottom = Math.min(height - 2, Math.max(...ys) + paddingY);
            const corner = Math.min(22, (right - left) * .18);

            overlayContext.strokeStyle = "#22e5ad";
            overlayContext.lineWidth = 2;
            overlayContext.shadowColor = "rgba(34, 229, 173, .75)";
            overlayContext.shadowBlur = 5;
            const corners = [
              [left + corner, top, left, top, left, top + corner],
              [right - corner, top, right, top, right, top + corner],
              [left, bottom - corner, left, bottom, left + corner, bottom],
              [right, bottom - corner, right, bottom, right - corner, bottom]
            ];
            for (const line of corners) {
              overlayContext.beginPath();
              overlayContext.moveTo(line[0], line[1]);
              overlayContext.lineTo(line[2], line[3]);
              overlayContext.lineTo(line[4], line[5]);
              overlayContext.stroke();
            }
            overlayContext.shadowBlur = 0;
            overlayContext.fillStyle = "rgba(49, 213, 239, .72)";
            for (let index = 0; index < points.length; index += 7) {
              const point = points[index];
              overlayContext.beginPath();
              overlayContext.arc(point.x, point.y, 1.15, 0, Math.PI * 2);
              overlayContext.fill();
            }
            const keyPoints = [1, 10, 33, 61, 133, 152, 263, 291, 362];
            overlayContext.fillStyle = "#5af0ff";
            for (const index of keyPoints) {
              const point = points[index];
              if (!point) continue;
              overlayContext.beginPath();
              overlayContext.arc(point.x, point.y, 2.1, 0, Math.PI * 2);
              overlayContext.fill();
            }
            overlayContext.fillStyle = "rgba(3, 18, 27, .86)";
            overlayContext.fillRect(left, Math.max(0, top - 17), 79, 15);
            overlayContext.fillStyle = "#55efbd";
            overlayContext.font = '700 9px "Segoe UI", sans-serif';
            overlayContext.fillText("FACE DETECTED", left + 5, Math.max(11, top - 6));
          };
          const trackFace = () => {
            if (!overlayRunning) return;
            const now = performance.now();
            if (
              faceLandmarker && preview.readyState >= 2 &&
              preview.currentTime !== lastVideoTime && now - lastInferenceAt >= 110
            ) {
              lastVideoTime = preview.currentTime;
              lastInferenceAt = now;
              const result = faceLandmarker.detectForVideo(preview, now);
              overlayContext.clearRect(0, 0, overlay.width, overlay.height);
              if (result.faceLandmarks && result.faceLandmarks.length) {
                drawFace(result.faceLandmarks[0]);
                setBadge(true, "FACE DETECTED");
              } else {
                setBadge(false, "SEARCHING FOR FACE");
              }
            }
            requestAnimationFrame(trackFace);
          };
          const initialiseFaceOverlay = async () => {
            try {
              const vision = await import(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/+esm"
              );
              const files = await vision.FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm"
              );
              const options = {
                baseOptions: {
                  modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
                  delegate: "GPU"
                },
                runningMode: "VIDEO",
                numFaces: 1,
                minFaceDetectionConfidence: .55,
                minFacePresenceConfidence: .55,
                minTrackingConfidence: .55
              };
              try {
                faceLandmarker = await vision.FaceLandmarker.createFromOptions(files, options);
              } catch (gpuError) {
                options.baseOptions.delegate = "CPU";
                faceLandmarker = await vision.FaceLandmarker.createFromOptions(files, options);
              }
              setBadge(false, "SEARCHING FOR FACE");
              requestAnimationFrame(trackFace);
            } catch (error) {
              setBadge(false, "FACE OVERLAY UNAVAILABLE");
            }
          };
          if (active) {
            state.textContent = "Starting camera...";
            navigator.mediaDevices.getUserMedia({
              video: {
                width: { ideal: 640 }, height: { ideal: 360 },
                frameRate: { ideal: 24, max: 24 }, facingMode: "user"
              },
              audio: false
            }).then((stream) => {
              previewStream = stream;
              preview.srcObject = stream;
              preview.onplaying = () => {
                syncOverlaySize();
                state.style.display = "none";
                initialiseFaceOverlay();
              };
            }).catch((error) => {
              state.textContent = `Camera unavailable: ${error.message}`;
            });
          }
          window.addEventListener("pagehide", stopPreview, { once: true });
          window.addEventListener("beforeunload", stopPreview, { once: true });
          window.addEventListener("resize", syncOverlaySize);
        </script>
        """
    components.html(
        preview_html.replace("__LIVESENSE_ACTIVE__", "true" if active else "false"),
        height=260,
        scrolling=False,
    )


def _metric(
    name: str,
    value: float,
    state: str,
    color: str,
) -> str:
    displayed = int(round(value))
    return dedent(
        f"""
        <div class="metric-box">
          <div class="metric-name">{escape(name)}</div>
          <div class="metric-number" style="color:{color}">
            {displayed}<span class="metric-denominator">/100</span>
          </div>
          <div class="metric-state" style="color:{color}">{escape(state)}</div>
          <div class="progress-track">
            <div class="progress-value" style="width:{value:.0f}%;background:{color}"></div>
          </div>
        </div>
        """
    ).strip()


def _sparkline(values: list[float], color: str) -> str:
    points = values[-30:] if values else [0.0]
    if len(points) == 1:
        points = [points[0], points[0]]
    coordinates = []
    for index, value in enumerate(points):
        x = index * 100 / (len(points) - 1)
        y = 58 - max(0.0, min(100.0, value)) * 0.46
        coordinates.append(f"{x:.1f},{y:.1f}")
    return dedent(
        f"""
        <svg class="sparkline" viewBox="0 0 100 62" preserveAspectRatio="none">
          <line class="spark-grid" x1="0" y1="58" x2="100" y2="58"></line>
          <polyline fill="none" stroke="{color}" stroke-width="1.5"
            vector-effect="non-scaling-stroke" points="{" ".join(coordinates)}"></polyline>
        </svg>
        """
    ).strip()


@st.fragment(run_every=0.5)
def _render_status_banner() -> None:
    current, _, _ = _live_view()
    if current.alarm_active:
        st.markdown(
            """
            <div class="notice-banner notice-danger notice-critical">
              <span class="alarm-pulse">!</span>
              <div><strong>DANGER: PULL OVER NOW - SLEEP DETECTED</strong><br>
              Stop driving, move to a safe place, and rest before continuing.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_alarm_notification()
        return
    _clear_alarm_notification()
    if current.phone_at_ear:
        st.markdown(
            """
            <div class="notice-banner notice-danger">
              <span class="danger-icon">!</span>
              <div><strong>PHONE USE DETECTED</strong><br>
              Put the phone down. This warning clears when phone use is no longer observed.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.face_missing_warning:
        st.markdown(
            """
            <div class="notice-banner notice-danger">
              <span class="danger-icon">!</span>
              <div><strong>FACE NOT DETECTED</strong><br>
              Return your face to the camera so safety monitoring can continue.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.seatbelt_warning:
        st.markdown(
            """
            <div class="notice-banner notice-danger">
              <span class="danger-icon">!</span>
              <div><strong>SEAT BELT NOT CONFIRMED</strong><br>
              Buckle up, or adjust the camera so the belt is visible across your chest.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.drinking_detected:
        st.markdown(
            """
            <div class="notice-banner notice-danger">
              <span class="danger-icon">!</span>
              <div><strong>DRINKING DETECTED</strong><br>
              Keep your hands and attention available for driving.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.eating_detected:
        st.markdown(
            """
            <div class="notice-banner notice-danger">
              <span class="danger-icon">!</span>
              <div><strong>EATING DETECTED</strong><br>
              Avoid eating while driving and restore full attention.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.sleep_state in {"Dozing", "Drowsy"}:
        warning_title = (
            "DOZING WARNING" if current.sleep_state == "Dozing" else "DROWSINESS WARNING"
        )
        st.markdown(
            f"""
            <div class="notice-banner notice-warning">
              <span class="notice-icon">!</span>
              <div><strong>{warning_title}</strong><br>
              Pull over at the next safe place and take a break.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    quality = _quality_label(current.signal_quality)
    if current.driver_status == "Camera Ready":
        copy = "Start the camera to begin monitoring."
    elif current.driver_status == "Normal":
        copy = "No danger signal detected."
    else:
        copy = f"Live activity: {current.activity}. Keep the face visible and centered."
    st.markdown(
        f"""
        <div class="status-banner">
          <div class="status-icon">&#10003;</div>
          <div>
            <div class="status-title">Monitoring Status: {escape(current.driver_status)}</div>
            <div class="status-copy">{escape(copy)}</div>
          </div>
          <div class="quality">
            <div class="quality-row">
              <span class="quality-label">Signal Quality</span>
              <span class="quality-value">{quality} - {current.signal_quality:.0f}%</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=1.0)
def _render_metrics() -> None:
    current, _, _ = _live_view()
    sleep_state = current.sleep_state
    sleep_color = "#d94c45" if current.alarm_active else "#d59522"
    attention_state = "Stable" if current.attention >= 65 else "Needs attention"
    readiness_state = "Ready" if current.readiness >= 65 else "Building signal"
    phone_state = "Phone at ear" if current.phone_at_ear else "Clear"
    eating_state = "Detected" if current.eating_detected else "Clear"
    drinking_state = "Detected" if current.drinking_detected else "Clear"
    seatbelt_state = "Visible" if current.seatbelt_visible else "Not confirmed"
    face_state = "Visible" if current.face_detected else "Not detected"
    if current.activity == "Waiting for camera":
        recommendation = "Start camera monitoring to begin analysis."
    elif current.alarm_active:
        recommendation = "Wake the monitored person immediately and move to a safe condition."
    elif current.sleep_state in {"Dozing", "Drowsy"}:
        recommendation = "Drowsiness detected. Pause the activity and take a restorative break."
    elif current.phone_at_ear:
        recommendation = "Put the phone down and keep your attention on the road."
    elif current.drinking_detected:
        recommendation = "Put the drink down and return both attention and control to driving."
    elif current.eating_detected:
        recommendation = "Stop eating and restore full attention to the road."
    elif current.seatbelt_warning:
        recommendation = "Buckle the seat belt, or adjust the camera so the belt is visible."
    elif current.face_missing_warning:
        recommendation = "Return your face to view so safety monitoring can continue."
    elif current.activity == "Attentive":
        recommendation = "Continue monitoring. Keep your face visible and posture upright."
    elif current.activity == "No face":
        recommendation = "Move back into view so LiveSense can restore the face signal."
    elif current.activity == "Looking away":
        recommendation = "Return your attention toward the central monitoring area."
    else:
        recommendation = "Movement detected. Hold a steady position while signals settle."

    recommendation_html = dedent(
        f"""
        <div class="activity-pill"><span class="live-dot"></span>
          Live activity: {escape(current.activity)}
        </div>
        <div class="cue-grid">
          <span>Sleep: <strong>{escape(current.sleep_state)}</strong></span>
          <span>Eyes: <strong>{"Closed" if current.eyes_closed else "Open"}</strong></span>
          <span>Yawn: <strong>{"Yes" if current.yawning else "No"}</strong></span>
          <span>Phone: <strong>{"Detected" if current.phone_at_ear else "Clear"}</strong></span>
          <span>Eating: <strong>{eating_state}</strong></span>
          <span>Drinking: <strong>{drinking_state}</strong></span>
          <span>Seat belt: <strong>{seatbelt_state}</strong></span>
          <span>Face: <strong>{face_state}</strong></span>
        </div>
        <div class="recommendation">
          <div class="recommendation-icon">RA</div>
          <div>
            <div class="recommendation-title">Recommended action</div>
            <div class="recommendation-copy">{escape(recommendation)}</div>
          </div>
        </div>
        """
    ).strip()
    html = (
        '<div class="panel"><div class="panel-head">'
        '<span class="panel-title">Live Signals</span>'
        f'<span class="live-label"><span class="live-dot"></span>{current.fps:.1f} FPS</span>'
        '</div><div class="metric-grid">'
        + _metric("Drowsiness", current.drowsiness, sleep_state, sleep_color)
        + _metric("Attention", current.attention, attention_state, "#d94c45")
        + _metric("Readiness", current.readiness, readiness_state, "#d59522")
        + _metric(
            "Phone Use",
            100.0 if current.phone_at_ear else 0.0,
            phone_state,
            "#d94c45" if current.phone_at_ear else "#139d70",
        )
        + "</div>"
        + recommendation_html
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


@st.fragment(run_every=1.0)
def _render_events() -> None:
    _, _, events = _live_view()
    items = []
    for event in events[:4]:
        observed = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        event_class = " event-critical" if event.level == "critical" else ""
        items.append(
            dedent(
                f"""
            <div class="event-item">
              <div class="event-dot{event_class}"></div>
              <div>
                <div class="event-title">{escape(event.title)} · {observed}</div>
                <div class="event-copy">{escape(event.detail)}</div>
              </div>
            </div>
            """
            ).strip()
        )
    if not items:
        items.append(
            dedent(
                """
            <div class="event-empty"><strong>No active events</strong><br>
              The current frame has no actionable activity changes.</div>
            """
            ).strip()
        )
    st.markdown(
        '<div class="panel"><div class="panel-head">'
        '<span class="panel-title">Event Insights</span>'
        '<span class="trend-range">Live</span></div>' + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )


def _activity_lane_plot(
    series: list[tuple[str, str, list[float], str]],
) -> str:
    """Render independent signal lanes in one compact, readable SVG plot."""
    lane_height = 20
    plot_top = 8
    plot_left = 112.0
    plot_right = 878.0
    height = plot_top + len(series) * lane_height + 4
    elements: list[str] = []
    for lane, (label, state, raw_values, color) in enumerate(series):
        values = raw_values[-60:] if raw_values else [0.0]
        if len(values) == 1:
            values = [values[0], values[0]]
        lane_top = plot_top + lane * lane_height
        baseline = lane_top + 15
        background = "#0a1926" if lane % 2 == 0 else "#0c1c29"
        elements.append(
            f'<rect x="0" y="{lane_top}" width="1000" height="{lane_height}" fill="{background}" />'
        )
        elements.append(
            f'<line x1="{plot_left:.0f}" y1="{baseline}" x2="{plot_right:.0f}" '
            f'y2="{baseline}" stroke="#193243" stroke-width="1" />'
        )
        points = []
        for index, value in enumerate(values):
            x = plot_left + index * (plot_right - plot_left) / (len(values) - 1)
            y = baseline - max(0.0, min(100.0, value)) * 0.11
            points.append(f"{x:.1f},{y:.1f}")
        elements.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
            'stroke-width="2" vector-effect="non-scaling-stroke" />'
        )
        elements.append(
            f'<text x="8" y="{baseline - 3}" class="activity-label">{escape(label)}</text>'
        )
        elements.append(
            f'<text x="992" y="{baseline - 3}" text-anchor="end" '
            f'class="activity-state">{escape(state)}</text>'
        )
    return (
        f'<svg class="activity-plot" viewBox="0 0 1000 {height}" '
        'preserveAspectRatio="none">' + "".join(elements) + "</svg>"
    )


@st.fragment(run_every=1.0)
def _render_trends() -> None:
    current, history, _ = _live_view()
    chart_data: list[tuple[str, str, list[float], str]] = [
        (
            "Sleep risk",
            current.sleep_state,
            [point.drowsiness for point in history],
            "#d85b55",
        ),
        (
            "Eyes closed",
            "Yes" if current.eyes_closed else "No",
            [100.0 if point.eyes_closed else 0.0 for point in history],
            "#e65c55",
        ),
        (
            "Yawning",
            "Yes" if current.yawning else "No",
            [100.0 if point.yawning else 0.0 for point in history],
            "#a96bd5",
        ),
        (
            "Attention",
            f"{current.attention:.0f}%",
            [point.attention for point in history],
            "#dc982b",
        ),
        (
            "Phone",
            "Detected" if current.phone_at_ear else "Clear",
            [100.0 if point.phone_at_ear else 0.0 for point in history],
            "#db514b",
        ),
        (
            "Eating",
            "Detected" if current.eating_detected else "Clear",
            [100.0 if point.eating_detected else 0.0 for point in history],
            "#dd7b2f",
        ),
        (
            "Drinking",
            "Detected" if current.drinking_detected else "Clear",
            [100.0 if point.drinking_detected else 0.0 for point in history],
            "#3186cf",
        ),
        (
            "Seat belt warning",
            "Warning" if current.seatbelt_warning else "Clear",
            [100.0 if point.seatbelt_warning else 0.0 for point in history],
            "#cc4f49",
        ),
        (
            "Face visible",
            "Visible" if current.face_detected else "Not detected",
            [100.0 if point.face_detected else 0.0 for point in history],
            "#159b72",
        ),
    ]
    st.markdown(
        f"""
        <div class="trend-card activity-card">
          <div class="trend-meta">
            <span class="trend-title">All Activity Signals</span>
            <span class="trend-range">Last 60 observations · updates every second</span>
          </div>
          {_activity_lane_plot(chart_data)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar() -> None:
    st.markdown(
        """
        <div class="brand">
          <div class="brand-mark">LS</div>
          <div><div class="brand-title">LiveSense</div>
          <div class="brand-subtitle">Human activity & safety monitoring</div></div>
        </div>
        <div class="side-section">MONITORING</div>
        <div class="nav-item nav-active">Live Dashboard</div>
        <div class="nav-item nav-muted">Sessions</div>
        <div class="nav-item nav-muted">Reports</div>
        <div class="side-section">CAMERA</div>
        """,
        unsafe_allow_html=True,
    )

    camera_label = "Stop Camera" if st.session_state.camera_requested else "Start Camera"
    if st.button(camera_label, type="primary", use_container_width=True):
        st.session_state.camera_requested = not st.session_state.camera_requested
        st.rerun()
    if st.button("Pause Analysis", use_container_width=True):
        st.session_state.camera_requested = False
        st.rerun()
    if st.button("Calibrate (10s)", use_container_width=True):
        st.session_state.calibration_requested = True
    if st.button("Start New Session", use_container_width=True):
        st.session_state.reset_requested = True

    st.markdown('<div class="side-section">CONTEXT</div>', unsafe_allow_html=True)
    st.selectbox(
        "Mode",
        ["General", "Driver", "Desk work", "Care"],
        index=1,
        label_visibility="visible",
    )
    st.selectbox(
        "Monitoring Context",
        ["Chair", "Standing", "Vehicle", "Bed"],
        index=2,
        label_visibility="visible",
    )
    st.markdown('<div class="side-section">ALARMS</div>', unsafe_allow_html=True)
    _render_notification_permission()

    st.markdown('<div class="side-section">FEEDBACK</div>', unsafe_allow_html=True)
    feedback = st.selectbox("Latest Feedback", ["None", "Helpful", "Needs review"])
    if st.button("Save Feedback", use_container_width=True):
        st.session_state.latest_feedback = feedback
        st.toast("Feedback saved for this session.")
    st.caption("Visual estimates only — not medical or safety advice.")


def render_dashboard() -> None:
    settings = load_settings()
    st.set_page_config(
        page_title=settings.app.title,
        page_icon="LS",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    defaults = {
        "camera_requested": False,
        "calibration_requested": False,
        "reset_requested": False,
        "latest_feedback": "None",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.sidebar:
        _render_sidebar()

    st.markdown(
        '<div class="topbar"><span class="user-chip">↑ &nbsp; '
        '<span class="user-avatar"></span> Work</span></div>',
        unsafe_allow_html=True,
    )
    _render_status_banner()

    camera_column, metrics_column, events_column = st.columns([1.4, 1.18, 0.86], gap="small")
    with camera_column:
        with st.container(border=True):
            st.markdown(
                '<div class="panel-head"><span class="panel-title">Live Camera Feed</span>'
                '<span class="live-label"><span class="live-dot"></span>Live</span></div>',
                unsafe_allow_html=True,
            )
            _render_local_camera_preview(st.session_state.camera_requested)
            context = webrtc_streamer(
                key="livesense-camera",
                mode=WebRtcMode.SENDONLY,
                desired_playing_state=st.session_state.camera_requested,
                video_processor_factory=lambda: CameraProcessor(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=False,
                    dozing_seconds=settings.monitoring.dozing_seconds,
                    sleeping_seconds=settings.monitoring.sleeping_seconds,
                ),
                audio_processor_factory=None,
                media_stream_constraints={
                    "video": {
                        "width": {"ideal": settings.camera.width},
                        "height": {"ideal": settings.camera.height},
                        "frameRate": {"ideal": settings.camera.target_fps},
                    },
                    "audio": False,
                },
                video_html_attrs={"autoPlay": True, "controls": False, "muted": True},
                media_toggle_controls=False,
                video_receiver_size=1,
                sendback_audio=False,
                async_processing=True,
            )
            if context.video_processor:
                processor = context.video_processor
                st.session_state.live_processor = processor
                processor.configure(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=False,
                )
                if st.session_state.calibration_requested:
                    processor.start_calibration(10.0)
                    st.session_state.calibration_requested = False
                if st.session_state.reset_requested:
                    processor.reset_session()
                    st.session_state.reset_requested = False

    with metrics_column:
        _render_metrics()
    with events_column:
        _render_events()

    st.markdown('<div class="trend-row"></div>', unsafe_allow_html=True)
    _render_trends()
