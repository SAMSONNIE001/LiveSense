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
    return f"""
      <svg class="sparkline" viewBox="0 0 100 62" preserveAspectRatio="none">
        <line class="spark-grid" x1="0" y1="58" x2="100" y2="58"></line>
        <polyline fill="none" stroke="{color}" stroke-width="1.5"
          vector-effect="non-scaling-stroke" points="{" ".join(coordinates)}"></polyline>
      </svg>
    """


@st.fragment(run_every=2.0)
def _render_status_banner() -> None:
    current, _, _ = _live_view()
    quality = _quality_label(current.signal_quality)
    if current.driver_status == "Normal":
        icon = "✓"
        copy = "Camera signal is stable. Continue monitoring for changes."
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
            <div class="status-title">Driver Status: {escape(current.driver_status)}</div>
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
    fatigue_state = "Low" if current.fatigue < 35 else "Monitor"
    attention_state = "Stable" if current.attention >= 65 else "Needs attention"
    readiness_state = "Ready" if current.readiness >= 65 else "Building signal"
    tension_state = "Low" if current.tension < 35 else "Movement elevated"
    if current.activity == "Waiting for camera":
        recommendation = "Start the camera to begin a new live monitoring session."
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
        + _metric("Fatigue", current.fatigue, fatigue_state, "#139d70")
        + _metric("Attention", current.attention, attention_state, "#d94c45")
        + _metric("Readiness", current.readiness, readiness_state, "#d59522")
        + _metric("Tension", current.tension, tension_state, "#139d70")
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
        items.append(
            f"""
            <div class="event-item">
              <div class="event-dot"></div>
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
        ("Fatigue Trend", "Fatigue", [point.fatigue for point in history], "#d85b55"),
        ("Attention Trend", "Attention", [point.attention for point in history], "#dc982b"),
        (
            "Signal Quality",
            "Signal Quality",
            [point.signal_quality for point in history],
            "#d1ad31",
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
          <div class="brand-subtitle">Driver wellness & observation</div></div>
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
    st.selectbox("Mode", ["Driver", "Desk work", "General"], label_visibility="visible")
    st.selectbox("Care Context", ["Chair", "Standing", "Vehicle"], label_visibility="visible")
    st.toggle(
        "Privacy blur",
        value=False,
        key="privacy_blur",
        help="Blur the detected face after live signals are calculated.",
    )

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
            context = webrtc_streamer(
                key="livesense-camera",
                mode=WebRtcMode.SENDRECV,
                desired_playing_state=st.session_state.camera_requested,
                video_processor_factory=lambda: CameraProcessor(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=st.session_state.privacy_blur,
                ),
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
                async_processing=True,
            )
            if context.video_processor:
                processor = context.video_processor
                st.session_state.live_processor = processor
                processor.configure(
                    mirrored=settings.camera.mirrored,
                    show_fps=settings.camera.show_fps,
                    privacy_blur=st.session_state.privacy_blur,
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
