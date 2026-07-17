"""Reference-aligned LiveSense monitoring dashboard."""

from __future__ import annotations

from datetime import datetime
from html import escape
from textwrap import dedent

import streamlit as st
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
          const runId = `${Date.now()}-${Math.random()}`;
          window.__livesensePreviewRunId = runId;
          let previewStream = window.__livesensePreviewStream || null;
          let poseLandmarker = window.__livesensePoseLandmarker || null;
          let trackingBusy = false;
          let lastVideoTime = -1;
          let lastInferenceAt = 0;
          let overlayRunning = true;
          const stopPreview = () => {
            overlayRunning = false;
            window.__livesensePreviewRunId = null;
            if (poseLandmarker) {
              poseLandmarker.close();
              window.__livesensePoseLandmarker = null;
              poseLandmarker = null;
            }
            if (previewStream) previewStream.getTracks().forEach((track) => track.stop());
            window.__livesensePreviewStream = null;
            previewStream = null;
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
          const drawTracking = (landmarks) => {
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
              y: offsetY + point.y * shownHeight,
              visibility: point.visibility ?? 1
            }));
            const facePoints = points.slice(0, 11);
            const faceXs = facePoints.map((point) => point.x);
            const faceYs = facePoints.map((point) => point.y);
            const faceCenterX = (Math.min(...faceXs) + Math.max(...faceXs)) / 2;
            const faceCenterY = (Math.min(...faceYs) + Math.max(...faceYs)) / 2;
            const featureWidth = Math.max(24, Math.max(...faceXs) - Math.min(...faceXs));
            const boxWidth = Math.min(width * .38, featureWidth * 1.72);
            const boxHeight = boxWidth * 1.2;
            const left = Math.max(2, faceCenterX - boxWidth / 2);
            const top = Math.max(2, faceCenterY - boxHeight * .44);
            const right = Math.min(width - 2, left + boxWidth);
            const bottom = Math.min(height - 2, top + boxHeight);

            overlayContext.clearRect(0, 0, width, height);
            overlayContext.strokeStyle = "#22e5ad";
            overlayContext.lineWidth = 2;
            overlayContext.shadowColor = "rgba(34, 229, 173, .75)";
            overlayContext.shadowBlur = 4;
            overlayContext.strokeRect(left, top, right - left, bottom - top);
            overlayContext.shadowBlur = 0;

            const armConnections = [
              [11, 12], [11, 13], [13, 15], [15, 17], [15, 19],
              [12, 14], [14, 16], [16, 18], [16, 20]
            ];
            overlayContext.strokeStyle = "#29c8ef";
            overlayContext.lineWidth = 2.2;
            overlayContext.lineCap = "round";
            overlayContext.lineJoin = "round";
            for (const [start, end] of armConnections) {
              const from = points[start];
              const to = points[end];
              if (!from || !to || from.visibility < .35 || to.visibility < .35) continue;
              overlayContext.beginPath();
              overlayContext.moveTo(from.x, from.y);
              overlayContext.lineTo(to.x, to.y);
              overlayContext.stroke();
            }

            overlayContext.fillStyle = "rgba(3, 18, 27, .86)";
            overlayContext.fillRect(left, Math.max(0, top - 17), 79, 15);
            overlayContext.fillStyle = "#55efbd";
            overlayContext.font = '700 9px "Segoe UI", sans-serif';
            overlayContext.fillText("FACE DETECTED", left + 5, Math.max(11, top - 6));
          };
          const trackBody = () => {
            if (
              !overlayRunning ||
              window.__livesensePreviewRunId !== runId
            ) return;
            const now = performance.now();
            if (
              poseLandmarker && !trackingBusy && preview.readyState >= 2 &&
              preview.currentTime !== lastVideoTime && now - lastInferenceAt >= 360
            ) {
              lastVideoTime = preview.currentTime;
              lastInferenceAt = now;
              trackingBusy = true;
              poseLandmarker.detectForVideo(preview, now, (result) => {
                trackingBusy = false;
                if (result.landmarks && result.landmarks.length) {
                  drawTracking(result.landmarks[0]);
                  setBadge(true, "FACE + ARMS DETECTED");
                } else {
                  overlayContext.clearRect(0, 0, overlay.width, overlay.height);
                  setBadge(false, "SEARCHING FOR FACE + ARMS");
                }
              });
            }
            requestAnimationFrame(trackBody);
          };
          const initialiseTrackingOverlay = async () => {
            if (poseLandmarker) {
              requestAnimationFrame(trackBody);
              return;
            }
            try {
              const vision = await import(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/+esm"
              );
              const files = await vision.FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm"
              );
              const options = {
                baseOptions: {
                  modelAssetPath: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
                  delegate: "GPU"
                },
                runningMode: "VIDEO",
                numPoses: 1,
                minPoseDetectionConfidence: .5,
                minPosePresenceConfidence: .5,
                minTrackingConfidence: .5
              };
              try {
                poseLandmarker = await vision.PoseLandmarker.createFromOptions(files, options);
              } catch (gpuError) {
                options.baseOptions.delegate = "CPU";
                poseLandmarker = await vision.PoseLandmarker.createFromOptions(files, options);
              }
              window.__livesensePoseLandmarker = poseLandmarker;
              setBadge(false, "SEARCHING FOR FACE + ARMS");
              requestAnimationFrame(trackBody);
            } catch (error) {
              setBadge(false, "TRACKING OVERLAY UNAVAILABLE");
            }
          };
          const attachPreview = (stream) => {
            previewStream = stream;
            window.__livesensePreviewStream = stream;
            preview.srcObject = stream;
            preview.onplaying = () => {
              syncOverlaySize();
              state.style.display = "none";
              initialiseTrackingOverlay();
            };
            if (preview.readyState >= 2) preview.onplaying();
          };
          const streamIsLive = previewStream && previewStream.getVideoTracks().some(
            (track) => track.readyState === "live"
          );
          if (active && streamIsLive) {
            attachPreview(previewStream);
          } else if (active) {
            state.textContent = "Starting camera...";
            navigator.mediaDevices.getUserMedia({
              video: {
                width: { ideal: 640 }, height: { ideal: 360 },
                frameRate: { ideal: 24, max: 24 }, facingMode: "user"
              },
              audio: false
            }).then(attachPreview).catch((error) => {
              state.textContent = `Camera unavailable: ${error.message}`;
            });
          } else {
            stopPreview();
          }
          window.addEventListener("beforeunload", stopPreview, { once: true });
          window.addEventListener("resize", syncOverlaySize);
        </script>
        """
    st.html(
        preview_html.replace("__LIVESENSE_ACTIVE__", "true" if active else "false"),
        unsafe_allow_javascript=True,
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

    # Normal state is represented in the compact console header.  This
    # fragment only consumes vertical space when an actionable warning exists.


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


def _combined_activity_plot(
    series: list[tuple[str, str, list[float], str]],
) -> str:
    """Render all live signs as independently moving lines in one plot."""
    plot_left = 42.0
    plot_right = 985.0
    plot_top = 8.0
    plot_bottom = 148.0
    elements: list[str] = []
    for value in (0, 25, 50, 75, 100):
        y = plot_bottom - value * (plot_bottom - plot_top) / 100
        elements.append(
            f'<line x1="{plot_left:.0f}" y1="{y:.1f}" x2="{plot_right:.0f}" '
            f'y2="{y:.1f}" stroke="#193243" stroke-width="1" />'
        )
        elements.append(
            f'<text x="34" y="{y + 3:.1f}" text-anchor="end" class="plot-axis-label">{value}</text>'
        )
    for _label, _state, raw_values, color in series:
        values = raw_values[-60:] if raw_values else [0.0]
        if len(values) == 1:
            values = [values[0], values[0]]
        points = []
        for index, value in enumerate(values):
            x = plot_left + index * (plot_right - plot_left) / (len(values) - 1)
            y = plot_bottom - max(0.0, min(100.0, value)) * (plot_bottom - plot_top) / 100
            points.append(f"{x:.1f},{y:.1f}")
        elements.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
            'stroke-width="1.8" stroke-linejoin="round" '
            'vector-effect="non-scaling-stroke" />'
        )
    return (
        '<svg class="activity-plot" viewBox="0 0 1000 160" '
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
    legend = "".join(
        f'<span class="signal-legend-item"><i style="background:{color}"></i>'
        f"{escape(label)} <strong>{escape(state)}</strong></span>"
        for label, state, _values, color in chart_data
    )
    st.markdown(
        f"""
        <div class="trend-card activity-card">
          <div class="trend-meta">
            <span class="trend-title">All Signals Activity</span>
            <span class="trend-range">Live · last 60 seconds</span>
          </div>
          <div class="signal-legend">{legend}</div>
          {_combined_activity_plot(chart_data)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _duration_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _mini_line(values: list[float], color: str) -> str:
    values = values[-20:] if values else [0.0, 0.0]
    if len(values) == 1:
        values = [values[0], values[0]]
    points = []
    for index, value in enumerate(values):
        x = index * 80 / (len(values) - 1)
        y = 15 - max(0.0, min(100.0, value)) * 0.13
        points.append(f"{x:.1f},{y:.1f}")
    return (
        '<svg class="mini-line" viewBox="0 0 80 16" preserveAspectRatio="none">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
        'stroke-width="1.2" vector-effect="non-scaling-stroke" /></svg>'
    )


def _signal_card(
    label: str,
    value: float,
    state: str,
    color: str,
    history: list[float],
) -> str:
    return dedent(
        f"""
        <div class="key-signal-card">
          <div class="key-signal-head"><i style="color:{color}">&#9670;</i>{escape(label)}</div>
          <div class="key-signal-value" style="color:{color}">{value:.0f}<small>/100</small></div>
          <div class="key-signal-state">{escape(state)}</div>
          {_mini_line(history, color)}
        </div>
        """
    ).strip()


@st.fragment(run_every=1.0)
def _render_console_header() -> None:
    current, history, _ = _live_view()
    started_at = history[0].timestamp if history else current.timestamp
    uptime = _duration_text(current.timestamp - started_at)
    now = datetime.now()
    active = current.driver_status != "Camera Ready"
    status = "Monitoring Active" if active else "Monitoring Ready"
    status_copy = "All systems are running smoothly" if active else "Start camera monitoring"
    st.markdown(
        f"""
        <div class="console-header">
          <div class="system-status-card">
            <span class="system-check">&#10003;</span>
            <div><strong>{status}</strong><small>{status_copy}</small></div>
            <span class="header-pulse"></span>
          </div>
          <div class="header-stat"><i>&#128247;</i><span>Camera
            <strong>{"Live" if active else "Ready"}</strong></span></div>
          <div class="header-stat"><i>&#9635;</i><span>Resolution
            <strong>640 &times; 360</strong></span></div>
          <div class="header-stat"><i>&#9673;</i><span>FPS
            <strong>{current.fps:.0f}</strong></span></div>
          <div class="header-stat"><i>&#9684;</i><span>Uptime<strong>{uptime}</strong></span></div>
          <div class="header-time"><small>{now:%b %d, %Y}</small>
            <strong>{now:%H:%M:%S}</strong></div>
          <div class="header-user"><span></span>Work</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=1.0)
def _render_key_signals() -> None:
    current, history, _ = _live_view()
    points = list(history)
    cards = (
        _signal_card(
            "Attention",
            current.attention,
            "Focused" if current.attention >= 65 else "Low",
            "#21c9ed",
            [p.attention for p in points],
        ),
        _signal_card(
            "Drowsiness",
            current.drowsiness,
            current.sleep_state,
            "#f0a11f",
            [p.drowsiness for p in points],
        ),
        _signal_card(
            "Readiness",
            current.readiness,
            "Ready" if current.readiness >= 65 else "Building",
            "#39d98a",
            [p.readiness for p in points],
        ),
        _signal_card(
            "Stress",
            current.tension,
            "Low" if current.tension < 35 else "Elevated",
            "#a875ef",
            [p.tension for p in points],
        ),
        _signal_card(
            "Eye openness",
            0.0 if current.eyes_closed else 100.0,
            "Open" if not current.eyes_closed else "Closed",
            "#23bde5",
            [0.0 if p.eyes_closed else 100.0 for p in points],
        ),
        _signal_card(
            "Phone use",
            100.0 if current.phone_at_ear else 0.0,
            "Detected" if current.phone_at_ear else "Clear",
            "#e65c55",
            [100.0 if p.phone_at_ear else 0.0 for p in points],
        ),
        _signal_card(
            "Yawning",
            100.0 if current.yawning else 0.0,
            "Detected" if current.yawning else "None",
            "#dc8a24",
            [100.0 if p.yawning else 0.0 for p in points],
        ),
        _signal_card(
            "Face visibility",
            100.0 if current.face_detected else 0.0,
            "Visible" if current.face_detected else "Missing",
            "#c37bf1",
            [100.0 if p.face_detected else 0.0 for p in points],
        ),
    )
    st.markdown(
        '<div class="console-panel"><div class="console-panel-head">'
        "<strong>KEY SIGNALS</strong><span>Live</span></div>"
        f'<div class="key-signal-grid">{"".join(cards)}</div></div>',
        unsafe_allow_html=True,
    )


def _activity_row(label: str, active: bool, active_text: str, clear_text: str = "Clear") -> str:
    state_class = "activity-alert" if active else "activity-clear"
    state = active_text if active else clear_text
    icon = "!" if active else "&#10003;"
    return (
        f'<div class="activity-row"><span class="{state_class}">{icon}</span>'
        f'<label>{escape(label)}</label><strong class="{state_class}">'
        f"{escape(state)}</strong></div>"
    )


@st.fragment(run_every=1.0)
def _render_activity_status() -> None:
    current, _, _ = _live_view()
    rows = (
        _activity_row("Face detected", not current.face_detected, "Missing", "Yes"),
        _activity_row("Eyes closed", current.eyes_closed, "Yes", "No"),
        _activity_row("Looking away", current.activity == "Looking away", "Yes", "No"),
        _activity_row("Phone use", current.phone_at_ear, "Detected", "No"),
        _activity_row("Eating", current.eating_detected, "Detected", "No"),
        _activity_row("Drinking", current.drinking_detected, "Detected", "No"),
        _activity_row("Seat belt", current.seatbelt_warning, "Not confirmed", "Confirmed"),
        _activity_row(
            "Drowsy",
            current.sleep_state in {"Drowsy", "Dozing", "Sleeping"},
            current.sleep_state,
            "No",
        ),
    )
    st.markdown(
        '<div class="console-panel activity-panel"><div class="console-panel-head">'
        "<strong>ACTIVITY STATUS</strong><span>Live checks</span></div>"
        f'<div class="activity-status-grid">{"".join(rows)}</div></div>',
        unsafe_allow_html=True,
    )


@st.fragment(run_every=1.0)
def _render_signal_quality() -> None:
    current, _, _ = _live_view()
    quality = max(0.0, min(100.0, current.signal_quality))
    lighting = "Good" if 55 <= current.brightness <= 205 else "Adjust"
    stability = "Good" if current.tension < 35 else "Moving"
    frame_rate = "Good" if current.fps >= 8 else "Low"
    st.markdown(
        f"""
        <div class="console-panel quality-panel">
          <div class="console-panel-head"><strong>SIGNAL QUALITY</strong><span>Live</span></div>
          <div class="quality-gauge" style="--quality:{quality * 3.6:.0f}deg">
            <div><strong>{quality:.0f}%</strong><small>{_quality_label(quality)}</small></div>
          </div>
          <div class="quality-list">
            <span><i></i>Lighting<strong>{lighting}</strong></span>
            <span><i></i>Face signal
              <strong>{"Good" if current.face_detected else "Missing"}</strong></span>
            <span><i></i>Stability<strong>{stability}</strong></span>
            <span><i></i>Frame rate<strong>{frame_rate}</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=1.0)
def _render_event_timeline() -> None:
    _, _, events = _live_view()
    items = []
    for event in events[:6]:
        observed = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        level = "timeline-critical" if event.level == "critical" else "timeline-warning"
        items.append(
            f'<div class="timeline-item"><time>{observed}</time><i class="{level}"></i>'
            f"<span>{escape(event.title)}</span></div>"
        )
    if not items:
        items.append('<div class="timeline-empty">No events detected in this session</div>')
    st.markdown(
        '<div class="console-panel timeline-panel"><div class="console-panel-head">'
        "<strong>EVENT TIMELINE</strong><span>View all</span></div>"
        f'<div class="timeline-list">{"".join(items)}</div></div>',
        unsafe_allow_html=True,
    )


def _plot_legend(series: list[tuple[str, str, list[float], str]]) -> str:
    return "".join(
        f'<span class="signal-legend-item"><i style="background:{color}"></i>{escape(label)}</span>'
        for label, _state, _values, color in series
    )


def _chart_panel(title: str, series: list[tuple[str, str, list[float], str]]) -> str:
    return dedent(
        f"""
        <div class="console-panel chart-panel">
          <div class="console-panel-head"><strong>{escape(title)}</strong>
            <span>10 minutes &#9662;</span></div>
          <div class="signal-legend">{_plot_legend(series)}</div>
          {_combined_activity_plot(series)}
        </div>
        """
    ).strip()


@st.fragment(run_every=1.0)
def _render_activity_chart() -> None:
    _, history, _ = _live_view()
    points = list(history)
    series = [
        ("Attention", "", [p.attention for p in points], "#21c9ed"),
        ("Drowsiness", "", [p.drowsiness for p in points], "#f0a11f"),
        ("Readiness", "", [p.readiness for p in points], "#39d98a"),
        ("Stress", "", [p.tension for p in points], "#a875ef"),
    ]
    st.markdown(_chart_panel("ACTIVITY OVER TIME", series), unsafe_allow_html=True)


@st.fragment(run_every=1.0)
def _render_drowsiness_chart() -> None:
    _, history, _ = _live_view()
    points = list(history)
    series = [
        ("Drowsiness", "", [p.drowsiness for p in points], "#e88521"),
        ("Yawning", "", [100.0 if p.yawning else 0.0 for p in points], "#f0c11f"),
        ("Eyes closed", "", [100.0 if p.eyes_closed else 0.0 for p in points], "#e65c55"),
    ]
    st.markdown(_chart_panel("DROWSINESS & YAWNING", series), unsafe_allow_html=True)


@st.fragment(run_every=1.0)
def _render_session_summary() -> None:
    current, history, events = _live_view()
    points = list(history)
    started = points[0].timestamp if points else current.timestamp
    duration = max(0.0, current.timestamp - started)
    active_ratio = sum(1 for point in points if point.face_detected) / max(1, len(points))
    alert_count = sum(1 for event in events if event.level in {"warning", "critical"})
    average_quality = sum(point.signal_quality for point in points) / max(1, len(points))
    st.markdown(
        f"""
        <div class="console-panel summary-panel">
          <div class="console-panel-head"><strong>SESSION SUMMARY</strong>
            <span>View report</span></div>
          <div class="summary-grid">
            <div><i>&#9684;</i><span>Duration<strong>{_duration_text(duration)}</strong></span></div>
            <div><i>&#10022;</i><span>Active time
              <strong>{active_ratio * 100:.0f}%</strong></span></div>
            <div><i>&#9888;</i><span>Alerts<strong>{alert_count}</strong></span></div>
            <div><i>&#9673;</i><span>Avg. signal<strong>{average_quality:.0f}%</strong></span></div>
          </div>
          <div class="summary-bar"><i style="width:{average_quality:.0f}%"></i></div>
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
          <div class="brand-subtitle">Human Activity &amp; Safety Monitoring</div></div>
        </div>
        <div class="nav-item nav-active"><span>&#9670;</span>Dashboard</div>
        <div class="nav-item nav-muted"><span>&#9635;</span>Live Feed</div>
        <div class="nav-item nav-muted"><span>&#9719;</span>Sessions</div>
        <div class="nav-item nav-muted"><span>&#8645;</span>Analytics</div>
        <div class="nav-item nav-muted"><span>&#9888;</span>Alerts <b class="nav-badge">2</b></div>
        <div class="nav-item nav-muted"><span>&#9776;</span>Reports</div>
        <div class="nav-item nav-muted"><span>&#8682;</span>Export Data</div>
        <div class="nav-item nav-muted"><span>&#9881;</span>Settings</div>
        <div class="side-section">QUICK ACTIONS</div>
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

    st.markdown(
        """
        <div class="side-section">SYSTEM STATUS</div>
        <div class="system-online"><i></i><span>All Systems Operational</span></div>
        <div class="sidebar-user"><span class="user-avatar"></span>
          <div><strong>Admin User</strong><small>Administrator</small></div><b>&#8964;</b>
        </div>
        <div class="sidebar-disclaimer">Visual safety estimates only</div>
        """,
        unsafe_allow_html=True,
    )


def _mount_hidden_analyzer(settings) -> None:
    """Mount analysis transport after the immediate local preview and dashboard UI."""
    holder = st.session_state.setdefault("processor_holder", {"instance": None})

    def processor_factory() -> CameraProcessor:
        processor = holder.get("instance")
        if not isinstance(processor, CameraProcessor):
            processor = CameraProcessor(
                mirrored=settings.camera.mirrored,
                show_fps=settings.camera.show_fps,
                privacy_blur=False,
                dozing_seconds=settings.monitoring.dozing_seconds,
                sleeping_seconds=settings.monitoring.sleeping_seconds,
            )
            holder["instance"] = processor
        return processor

    analysis_width = min(settings.camera.width, 480)
    analysis_height = max(1, round(settings.camera.height * analysis_width / settings.camera.width))
    analysis_fps = min(settings.camera.target_fps, 15)
    context = webrtc_streamer(
        key="livesense-camera",
        mode=WebRtcMode.SENDONLY,
        desired_playing_state=st.session_state.camera_requested,
        video_processor_factory=processor_factory,
        audio_processor_factory=None,
        media_stream_constraints={
            "video": {
                "width": {"ideal": analysis_width},
                "height": {"ideal": analysis_height},
                "frameRate": {"ideal": analysis_fps, "max": analysis_fps},
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
    _render_console_header()
    _render_status_banner()

    camera_column, signals_column, quality_column = st.columns([1.05, 1.22, 0.58], gap="small")
    with camera_column:
        with st.container(border=True):
            st.markdown(
                '<div class="panel-head"><span class="panel-title">LIVE CAMERA FEED</span>'
                '<span class="live-label"><span class="live-dot"></span>Live</span></div>',
                unsafe_allow_html=True,
            )
            _render_local_camera_preview(st.session_state.camera_requested)
    with signals_column:
        _render_key_signals()
        _render_activity_status()
    with quality_column:
        _render_signal_quality()
        _render_event_timeline()

    chart_one, chart_two, summary = st.columns([1.0, 1.0, 0.55], gap="small")
    with chart_one:
        _render_activity_chart()
    with chart_two:
        _render_drowsiness_chart()
    with summary:
        _render_session_summary()

    st.markdown(
        '<div class="console-tip"><span>&#9671;</span><strong>TIP</strong> Keep good lighting '
        "and a clear view of the face, shoulders, hands, food, drink, and phone.</div>",
        unsafe_allow_html=True,
    )

    with camera_column:
        _mount_hidden_analyzer(settings)
