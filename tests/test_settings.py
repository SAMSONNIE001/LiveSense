"""Tests for YAML configuration loading and validation."""

from pathlib import Path

import pytest

from config import load_settings


def test_default_settings_load() -> None:
    settings = load_settings()

    assert settings.app.title == "LiveSense"
    assert settings.camera.width == 1280
    assert settings.camera.mirrored is True
    assert settings.privacy.persist_frames is False


def test_invalid_camera_dimensions_are_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("camera:\n  width: 0\n  height: 720\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dimensions"):
        load_settings(config_file)
