"""Tests for the FastAPI/Uvicorn dashboard entry point and static client."""

from pathlib import Path

from app import WEB_ROOT, _decode_frame, app


def test_fastapi_application_exposes_livesense() -> None:
    assert app.title == "LiveSense"
    assert any(route.path == "/ws/analyze" for route in app.routes)
    assert any(route.path == "/health" for route in app.routes)


def test_static_dashboard_contains_camera_and_live_signal_client() -> None:
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="camera"' in html
    assert 'id="activity-chart"' in html
    assert "/ws/analyze" in javascript
    assert "getUserMedia" in javascript
    assert "PoseLandmarker" in javascript
    assert "if (cameraActive) scheduleFrame()" in javascript


def test_invalid_image_payload_is_rejected() -> None:
    assert _decode_frame(b"") is None
    assert _decode_frame(b"not-an-image") is None


def test_web_assets_exist() -> None:
    assert {path.name for path in Path(WEB_ROOT).iterdir()} >= {
        "index.html",
        "styles.css",
        "app.js",
        "favicon.svg",
    }
