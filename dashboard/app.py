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
from signals import AudioActivityDetector, AudioActivityProcessor, SignalSnapshot


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
                body: "Possible sleep detected. Wake the monitored person immediately.",
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


@st.fragment(run_every=2.0)
def _render_status_banner() -> None:
    current, _, _ = _live_view()
    quality = _quality_label(current.signal_quality)
    if current.alarm_active:
        st.markdown(
            """
            <div class="alarm-banner">
              <span class="alarm-pulse">!</span>
              <div><strong>SLEEP DETECTED — WAKE UP</strong><br>
              Sustained eye closure triggered the LiveSense alarm.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_alarm_notification()
        icon = "!"
        copy = "Critical sleep cues detected. Wake the monitored person immediately."
    elif current.sleep_state in {"Dozing", "Drowsy"}:
        icon = "!"
        copy = "Drowsiness cues are increasing. Take a break and restore alertness."
    elif current.cough_detected:
        icon = "!"
        copy = "A suspected cough audio burst was detected and added to events."
    elif current.driver_status == "Normal":
        icon = "✓"
        copy = "Person appears awake and attentive. Continue monitoring for changes."
    elif current.driver_status == "Camera Ready":
        icon = "◦"
        copy = "Start the camera to begin live human-signal monitoring."
    else:
        icon = "!"
        copy = f"Live activity: {current.activity}. Keep the face visible and centered."
    st.markdown(
        f"""
        <div class="status-banner">
            <div class="status-icon">{icon}</div>
            <div>
            <div class="status-title">Monitoring Status: {escape(current.driver_status)}</div>
            <div class="status-copy">{escape(copy)}</div>
          </div>
          <div class="quality">
            <div class="quality-row">
              <span class="quality-label">Signal Quality</span>
              <span class="quality-value">{quality} · {current.signal_quality:.0f}%</span>
            </div>
            <div class="quality-copy">Camera signal is visible and processed in memory.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=2.0)
def _render_metrics() -> None:
    current, _, _ = _live_view()
    sleep_state = current.sleep_state
    sleep_color = "#d94c45" if current.alarm_active else "#d59522"
    attention_state = "Stable" if current.attention >= 65 else "Needs attention"
    readiness_state = "Ready" if current.readiness >= 65 else "Building signal"
    audio_state = "Cough cue" if current.cough_detected else f"{current.cough_count} cough events"
    if current.activity == "Waiting for camera":
        recommendation = "Start camera and microphone monitoring to begin analysis."
    elif current.alarm_active:
        recommendation = "Wake the monitored person immediately and move to a safe condition."
    elif current.sleep_state in {"Dozing", "Drowsy"}:
        recommendation = "Drowsiness detected. Pause the activity and take a restorative break."
    elif current.cough_detected:
        recommendation = "Suspected cough detected. Continue observing frequency and wellbeing."
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
          <span>Coughs: <strong>{current.cough_count}</strong></span>
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
        + _metric("Audio Activity", current.audio_level, audio_state, "#139d70")
        + "</div>"
        + recommendation_html
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


@st.fragment(run_every=2.0)
def _render_events() -> None:
    _, _, events = _live_view()
    items = []
    for event in events[:4]:
        observed = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        event_class = " event-critical" if event.level == "critical" else ""
        items.append(
            f"""
            <div class="event-item">
              <div class="event-dot{event_class}"></div>
              <div>
                <div class="event-title">{escape(event.title)} · {observed}</div>
                <div class="event-copy">{escape(event.detail)}</div>
              </div>
            </div>
            """
        )
    if not items:
        items.append(
            """
            <div class="event-empty"><strong>No active events</strong><br>
              The current frame has no actionable activity changes.</div>
            """
        )
    st.markdown(
        '<div class="panel"><div class="panel-head">'
        '<span class="panel-title">Event Insights</span>'
        '<span class="trend-range">Live</span></div>' + "".join(items) + "</div>",
        unsafe_allow_html=True,
    )


@st.fragment(run_every=5.0)
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
            "Audio Activity",
            "Microphone level",
            [point.audio_level for point in history],
            "#159d75",
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
    st.selectbox("Mode", ["General", "Driver", "Desk work", "Care"], label_visibility="visible")
    st.selectbox(
        "Monitoring Context",
        ["Chair", "Standing", "Vehicle", "Bed"],
        label_visibility="visible",
    )
    st.toggle(
        "Privacy blur",
        key="privacy_blur",
        help="Blur the detected face after live signals are calculated.",
    )
    st.toggle(
        "Cough audio analysis",
        key="audio_analysis",
        help="Use microphone audio to flag short bursts consistent with coughing.",
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
        "privacy_blur": False,
        "audio_analysis": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not isinstance(st.session_state.get("audio_detector"), AudioActivityDetector):
        st.session_state.audio_detector = AudioActivityDetector()

    with st.sidebar:
        _render_sidebar()

    # WebRTC creates its processor outside the Streamlit script callback. Capture
    # widget state here instead of reading session_state from that worker context.
    privacy_blur = bool(st.session_state.get("privacy_blur", False))
    audio_analysis = bool(st.session_state.get("audio_analysis", True))
    audio_detector = st.session_state.audio_detector

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
            context = webrtc_streamer(
                key="livesense-camera",
                mode=WebRtcMode.SENDRECV,
                desired_playing_state=st.session_state.camera_requested,
                video_processor_factory=lambda: CameraProcessor(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=privacy_blur,
                    audio_detector=audio_detector,
                    dozing_seconds=settings.monitoring.dozing_seconds,
                    sleeping_seconds=settings.monitoring.sleeping_seconds,
                ),
                audio_processor_factory=(
                    (lambda: AudioActivityProcessor(audio_detector)) if audio_analysis else None
                ),
                media_stream_constraints={
                    "video": {
                        "width": {"ideal": settings.camera.width},
                        "height": {"ideal": settings.camera.height},
                        "frameRate": {"ideal": settings.camera.target_fps},
                    },
                    "audio": audio_analysis,
                },
                video_html_attrs={"autoPlay": True, "controls": False, "muted": True},
                media_toggle_controls=False,
                sendback_audio=False,
                async_processing=True,
            )
            if context.video_processor:
                processor = context.video_processor
                st.session_state.live_processor = processor
                processor.configure(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=privacy_blur,
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
