"""Tests for sustained dozing and sleep decisions."""

from signals import DrowsinessMonitor


def test_continuous_eye_closure_escalates_at_two_seconds() -> None:
    monitor = DrowsinessMonitor(dozing_seconds=1.0, sleeping_seconds=2.0)
    awake = monitor.update(
        timestamp=0.0,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )
    dozing = monitor.update(
        timestamp=1.0,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )
    sleeping = monitor.update(
        timestamp=2.0,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )

    assert awake.state == "Awake"
    assert dozing.state == "Dozing"
    assert dozing.alarm_active is False
    assert sleeping.state == "Sleeping"
    assert sleeping.alarm_active is True


def test_open_eyes_do_not_trigger_alarm() -> None:
    monitor = DrowsinessMonitor()
    result = None
    for step in range(50):
        result = monitor.update(
            timestamp=step / 10,
            face_detected=True,
            eyes_closed=False,
            yawning=False,
            head_pitch=0.0,
        )

    assert result.state == "Awake"
    assert result.alarm_active is False


def test_short_eye_closure_does_not_trigger_alarm() -> None:
    monitor = DrowsinessMonitor()
    monitor.update(
        timestamp=0.0,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )
    blink = monitor.update(
        timestamp=0.4,
        face_detected=True,
        eyes_closed=False,
        yawning=False,
        head_pitch=0.0,
    )

    assert blink.eye_closure_seconds == 0.0
    assert blink.state == "Awake"
    assert blink.alarm_active is False


def test_brief_open_sample_does_not_erase_sustained_closure() -> None:
    monitor = DrowsinessMonitor(dozing_seconds=1.0, sleeping_seconds=2.0)
    monitor.update(
        timestamp=0.0,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )
    monitor.update(
        timestamp=1.1,
        face_detected=True,
        eyes_closed=False,
        yawning=False,
        head_pitch=0.0,
    )
    result = monitor.update(
        timestamp=2.1,
        face_detected=True,
        eyes_closed=True,
        yawning=False,
        head_pitch=0.0,
    )

    assert result.eye_closure_seconds == 2.1
    assert result.state == "Sleeping"
    assert result.alarm_active is True


def test_yawn_creates_drowsy_warning_without_sleep_alarm() -> None:
    monitor = DrowsinessMonitor()
    result = monitor.update(
        timestamp=1.0,
        face_detected=True,
        eyes_closed=False,
        yawning=True,
        head_pitch=0.0,
    )

    assert result.state == "Drowsy"
    assert result.alarm_active is False


def test_food_or_drink_can_clear_a_recent_yawn_warning() -> None:
    monitor = DrowsinessMonitor()
    monitor.update(
        timestamp=1.0,
        face_detected=True,
        eyes_closed=False,
        yawning=True,
        head_pitch=0.0,
    )

    monitor.suppress_yawn()
    result = monitor.update(
        timestamp=1.1,
        face_detected=True,
        eyes_closed=False,
        yawning=False,
        head_pitch=0.0,
    )

    assert result.state == "Awake"
    assert result.alarm_active is False
