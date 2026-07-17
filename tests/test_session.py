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


def test_session_emits_critical_sleep_alarm() -> None:
    session = SignalSession()
    session.update(
        replace(
            SignalSnapshot.waiting(),
            timestamp=20.0,
            activity="Sleeping",
            sleep_state="Sleeping",
            alarm_active=True,
        )
    )

    event = session.snapshot().events[0]

    assert event.level == "critical"
    assert event.title == "Sleep alarm"


def test_session_records_new_cough_count() -> None:
    session = SignalSession()
    session.update(
        replace(
            SignalSnapshot.waiting(),
            timestamp=20.0,
            activity="Coughing",
            cough_detected=True,
            cough_count=1,
        )
    )

    assert session.snapshot().events[0].title == "Suspected cough"
