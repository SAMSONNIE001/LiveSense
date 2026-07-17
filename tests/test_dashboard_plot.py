"""Tests for the consolidated activity-lane plot."""

from inspect import getsource

from dashboard.app import _activity_lane_plot, _render_local_camera_preview


def test_activity_plot_keeps_each_signal_in_a_labelled_lane() -> None:
    plot = _activity_lane_plot(
        [
            ("Phone", "Detected", [0.0, 100.0], "#ff0000"),
            ("Face visible", "Visible", [100.0, 100.0], "#00aa00"),
        ]
    )

    assert plot.startswith('<svg class="activity-plot"')
    assert "Phone" in plot
    assert "Detected" in plot
    assert "Face visible" in plot
    assert plot.count("<polyline") == 2
    assert "{baseline}" not in plot


def test_local_preview_contains_real_face_tracking_overlay() -> None:
    source = getsource(_render_local_camera_preview)

    assert "livesense-face-overlay" in source
    assert "FaceLandmarker" in source
    assert "detectForVideo" in source
    assert "FACE DETECTED" in source
