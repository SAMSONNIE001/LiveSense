"""Tests for the consolidated activity-lane plot."""

from dashboard.app import _activity_lane_plot


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
