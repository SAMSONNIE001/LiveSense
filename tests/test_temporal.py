"""Tests for stable activation and clearing of live observations."""

from signals import StableObservation


def test_observation_activates_only_after_confirmation_time() -> None:
    observation = StableObservation(activate_seconds=2.0, clear_seconds=1.0)

    assert observation.update(True, 10.0) is False
    assert observation.update(True, 11.9) is False
    assert observation.update(True, 12.0) is True


def test_observation_remains_active_during_brief_dropout() -> None:
    observation = StableObservation(activate_seconds=1.0, clear_seconds=1.5)
    observation.update(True, 10.0)
    assert observation.update(True, 11.0) is True

    assert observation.update(False, 11.1) is True
    assert observation.update(False, 12.5) is True
    assert observation.update(False, 12.6) is False


def test_observation_rejects_a_short_positive_blip() -> None:
    observation = StableObservation(activate_seconds=1.0, clear_seconds=1.0)

    assert observation.update(True, 5.0) is False
    assert observation.update(False, 5.4) is False
    assert observation.update(True, 6.0) is False
