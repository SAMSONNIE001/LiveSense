"""Typed application settings loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).with_name("settings.yaml")


@dataclass(frozen=True, slots=True)
class AppSettings:
    title: str = "LiveSense"
    tagline: str = "Real-time Human Signal Intelligence"
    page_icon: str = "LS"


@dataclass(frozen=True, slots=True)
class CameraSettings:
    width: int = 1280
    height: int = 720
    target_fps: int = 30
    mirrored: bool = True
    show_fps: bool = True

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Camera dimensions must be positive")
        if self.target_fps <= 0:
            raise ValueError("Camera target_fps must be positive")


@dataclass(frozen=True, slots=True)
class PrivacySettings:
    persist_frames: bool = False


@dataclass(frozen=True, slots=True)
class MonitoringSettings:
    dozing_seconds: float = 1.1
    sleeping_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.dozing_seconds <= 0:
            raise ValueError("Monitoring dozing_seconds must be positive")
        if self.sleeping_seconds <= self.dozing_seconds:
            raise ValueError("Monitoring sleeping_seconds must exceed dozing_seconds")


@dataclass(frozen=True, slots=True)
class LiveSenseSettings:
    app: AppSettings
    camera: CameraSettings
    privacy: PrivacySettings
    monitoring: MonitoringSettings


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{key}' must be a mapping")
    return value


def load_settings(path: str | Path = DEFAULT_CONFIG_PATH) -> LiveSenseSettings:
    """Load and validate LiveSense settings from *path*."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    if not isinstance(raw, dict):
        raise ValueError("The configuration root must be a mapping")

    return LiveSenseSettings(
        app=AppSettings(**_section(raw, "app")),
        camera=CameraSettings(**_section(raw, "camera")),
        privacy=PrivacySettings(**_section(raw, "privacy")),
        monitoring=MonitoringSettings(**_section(raw, "monitoring")),
    )
