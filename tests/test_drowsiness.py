"""Tests for sustained dozing and sleep decisions."""

from signals import DrowsinessMonitor


def test_sustained_eye_closure_escalates_from_dozing_to_sleeping() -> None:
    monitor = DrowsinessMonitor(dozing_seconds=1.0, sleeping_seconds=3.0)
    dozing = None
    sleeping = None
    for step in range(33):
        result = monitor.update(
            timestamp=step / 10,
            face_detected=True,
            eyes_closed=True,
            yawning=False,
            head_pitch=0.0,
        )
        if step == 12:
            dozing = result
        sleeping = result

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


def test_default_monitor_alarms_within_one_second_of_eye_closure() -> None:
    monitor = DrowsinessMonitor()
    result = None
    for step in range(9):
        result = monitor.update(
            timestamp=step / 10,
            face_detected=True,
            eyes_closed=True,
            yawning=False,
            head_pitch=0.0,
        )

    assert result.eye_closure_seconds >= 0.70
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
