"""Composition of the LiveSense Streamlit dashboard."""

from __future__ import annotations

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from camera import CameraProcessor
from config import load_settings
from dashboard.theme import THEME_CSS


def _metric_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="ls-card">
          <div class="ls-card-label">{label}</div>
          <div class="ls-card-value">{value}</div>
          <div class="ls-card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    settings = load_settings()
    st.set_page_config(
        page_title=settings.app.title,
        page_icon=settings.app.page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### Camera controls")
        mirrored = st.toggle("Mirror camera", value=settings.camera.mirrored)
        show_fps = st.toggle("Show FPS overlay", value=settings.camera.show_fps)
        st.divider()
        st.caption("PRIVACY")
        st.markdown("Frames are processed in memory and are not saved.")
        st.caption("MILESTONE 1 · FOUNDATION + CAMERA")

    st.markdown(
        '<div class="ls-eyebrow">Computer vision · Local first</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<h1 class="ls-title">See the signals.<br><span>Understand the moment.</span></h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ls-subtitle">'
        f"{settings.app.tagline}. Start the camera to establish the live visual pipeline."
        "</div>",
        unsafe_allow_html=True,
    )

    camera_column, info_column = st.columns([2.25, 1], gap="large")
    with camera_column:
        context = webrtc_streamer(
            key="livesense-camera",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=lambda: CameraProcessor(
                mirrored=mirrored,
                show_fps=show_fps,
            ),
            media_stream_constraints={
                "video": {
                    "width": {"ideal": settings.camera.width},
                    "height": {"ideal": settings.camera.height},
                    "frameRate": {"ideal": settings.camera.target_fps},
                },
                "audio": False,
            },
            async_processing=True,
        )
        if context.video_processor:
            context.video_processor.configure(mirrored=mirrored, show_fps=show_fps)

    with info_column:
        status = "Camera active" if context.state.playing else "Camera ready"
        st.markdown(
            f'<div class="ls-status"><span class="ls-dot"></span>{status}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### Live pipeline")
        st.caption("The foundation for face, pose, and behavioral signal models.")
        _metric_card("Input", "Browser webcam", "Secure peer-to-peer stream")
        st.write("")
        _metric_card("Processing", "In memory", "No frame persistence")
        st.write("")
        _metric_card("Next", "Face + pose", "MediaPipe landmark pipeline")

    st.divider()
    st.caption("LiveSense · Human signal intelligence with privacy by design")
