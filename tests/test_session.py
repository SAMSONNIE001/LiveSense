"""Tests for live history and event generation."""

from dataclasses import replace

from analytics import SignalSession
from signals import SignalSnapshot


def test_session_records_history_and_activity_event() -> None:
    session = SignalSession(sample_interval=1.0)
    snapshot = replace(
        SignalSnapshot.waiting(),
        timestamp=10.0,
        activity="No face",
        driver_status="Signal Interrupted",
    )

    session.update(snapshot)
    view = session.snapshot()

    assert view.current.activity == "No face"
    assert view.history == (snapshot,)
    assert view.events[0].title == "No face"


def test_session_reset_clears_history_and_events() -> None:
    session = SignalSession(sample_interval=0.0)
    session.update(replace(SignalSnapshot.waiting(), timestamp=10.0, activity="Looking away"))

    session.reset()
    view = session.snapshot()

    assert view.current.activity == "Waiting for camera"
    assert view.history == ()
    assert view.events == ()
