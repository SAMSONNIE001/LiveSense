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
    """Emit a debounced browser notification and audible alarm."""
    st.html(
        """
        <script>
          const now = Date.now();
          const lastAlarm = Number(sessionStorage.getItem("livesense-last-alarm") || 0);
          if (now - lastAlarm > 9000) {
            sessionStorage.setItem("livesense-last-alarm", String(now));
            if (window.Notification && Notification.permission === "granted") {
              new Notification("LiveSense sleep alarm", {
                body: "Sleep detected. Pull over now and stop in a safe place.",
                requireInteraction: true
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
          #livesense-preview-state {
            position: absolute; inset: 0; display: grid; place-items: center;
            color: white; background: #17201e; font: 12px "Segoe UI", sans-serif;
          }
        </style>
        <script>
          const preview = document.getElementById("livesense-preview");
          const state = document.getElementById("livesense-preview-state");
          const active = __LIVESENSE_ACTIVE__;
          let previewStream = null;
          const stopPreview = () => {
            if (previewStream) previewStream.getTracks().forEach((track) => track.stop());
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
              preview.onplaying = () => { state.style.display = "none"; };
            }).catch((error) => {
              state.textContent = `Camera unavailable: ${error.message}`;
            });
          }
          window.addEventListener("pagehide", stopPreview, { once: true });
          window.addEventListener("beforeunload", stopPreview, { once: true });
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
            <div class="notice-banner notice-danger">
              <span class="alarm-pulse">!</span>
              <div><strong>DANGER: PULL OVER NOW - SLEEP DETECTED</strong><br>
              Stop driving, move to a safe place, and rest before continuing.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_alarm_notification()
        return
    if current.phone_at_ear:
        st.markdown(
            """
            <div class="notice-banner notice-warning">
              <span class="notice-icon">!</span>
              <div><strong>PHONE USE DETECTED</strong><br>
              Put the phone down and keep both hands available for safe driving.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if current.sleep_state in {"Dozing", "Drowsy"}:
        st.markdown(
            """
            <div class="notice-banner notice-warning">
              <span class="notice-icon">!</span>
              <div><strong>DROWSINESS WARNING</strong><br>
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
    if current.activity == "Waiting for camera":
        recommendation = "Start camera monitoring to begin analysis."
    elif current.alarm_active:
        recommendation = "Wake the monitored person immediately and move to a safe condition."
    elif current.sleep_state in {"Dozing", "Drowsy"}:
        recommendation = "Drowsiness detected. Pause the activity and take a restorative break."
    elif current.phone_at_ear:
        recommendation = "Put the phone down and keep your attention on the road."
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


@st.fragment(run_every=3.0)
def _render_trends() -> None:
    _, history, _ = _live_view()
    chart_data = [
        (
            "Drowsiness Trend",
            "Sleep risk",
            [point.drowsiness for point in history],
            "#d85b55",
        ),
        ("Attention Trend", "Attention", [point.attention for point in history], "#dc982b"),
        (
            "Phone Use",
            "Hand-at-ear warning",
            [100.0 if point.phone_at_ear else 0.0 for point in history],
            "#d85b55",
        ),
    ]
    columns = st.columns(3, gap="small")
    for column, (title, label, values, color) in zip(columns, chart_data, strict=True):
        with column:
            st.markdown(
                f"""
                <div class="trend-card">
                  <div class="trend-meta">
                    <span class="trend-title">{title}</span>
                    <span class="trend-range">Last 15 min</span>
                  </div>
                  <div class="trend-label">{label}</div>
                  {_sparkline(values, color)}
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
