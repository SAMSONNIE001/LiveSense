"""Tests for the consolidated activity-lane plot."""

from inspect import getsource

from dashboard.app import _combined_activity_plot, _render_local_camera_preview


def test_activity_plot_keeps_each_signal_in_one_combined_plot() -> None:
    plot = _combined_activity_plot(
        [
            ("Phone", "Detected", [0.0, 100.0], "#ff0000"),
            ("Face visible", "Visible", [100.0, 100.0], "#00aa00"),
        ]
    )

    assert plot.startswith('<svg class="activity-plot"')
    assert plot.count("<polyline") == 2
    assert "{baseline}" not in plot


def test_local_preview_contains_real_face_tracking_overlay() -> None:
    source = getsource(_render_local_camera_preview)

    assert "livesense-face-overlay" in source
    assert "PoseLandmarker" in source
    assert "detectForVideo" in source
    assert "FACE DETECTED" in source
    assert "armConnections" in source
    assert "overlayContext.arc" not in source
    assert "components.html" in source
    assert "host.__livesensePreviewStream" in source
    assert "host.__livesensePoseLandmarker" in source
