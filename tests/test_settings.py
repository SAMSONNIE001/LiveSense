"""Tests for YAML configuration loading and validation."""

from pathlib import Path

import pytest

from config import load_settings


def test_default_settings_load() -> None:
    settings = load_settings()

    assert settings.app.title == "LiveSense"
    assert settings.camera.width == 640
    assert settings.camera.height == 360
    assert settings.camera.target_fps == 24
    assert settings.camera.mirrored is True
    assert settings.privacy.persist_frames is False
    assert settings.monitoring.dozing_seconds == 1.1
    assert settings.monitoring.sleeping_seconds == 3.0


def test_invalid_camera_dimensions_are_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("camera:\n  width: 0\n  height: 720\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dimensions"):
        load_settings(config_file)


def test_sleep_threshold_must_exceed_dozing_threshold(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid-monitoring.yaml"
    config_file.write_text(
        "monitoring:\n  dozing_seconds: 3\n  sleeping_seconds: 2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exceed"):
        load_settings(config_file)
