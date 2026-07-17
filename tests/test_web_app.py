"""Tests for the FastAPI/Uvicorn dashboard entry point and static client."""

from pathlib import Path

from app import WEB_ROOT, _decode_frame, _report_payload, app


def test_fastapi_application_exposes_livesense() -> None:
    assert app.title == "LiveSense"
    assert any(route.path == "/ws/analyze" for route in app.routes)
    assert any(route.path == "/health" for route in app.routes)
    assert any(route.path == "/reports" for route in app.routes)
    assert any(route.path == "/api/report" for route in app.routes)


def test_static_dashboard_contains_camera_and_live_signal_client() -> None:
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="camera"' in html
    assert 'id="activity-record"' in html
    assert 'id="activity-chart"' not in html
    assert "/ws/analyze" in javascript
    assert "getUserMedia" in javascript
    assert "PoseLandmarker" in javascript
    assert '["sleeping",colors.purple,"Sleeping"]' in javascript
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
        "reports.html",
        "reports.css",
        "reports.js",
    }


def test_report_payload_is_clear_before_monitoring_starts() -> None:
    report = _report_payload()

    assert report["current"]["activity"]
    assert set(report["averages"]) == {
        "attention",
        "drowsiness",
        "readiness",
        "signal_quality",
        "tension",
    }
    assert report["alert_count"] >= 0


def test_report_page_has_bold_findings_and_navigation() -> None:
    html = (WEB_ROOT / "reports.html").read_text(encoding="utf-8")
    dashboard = (WEB_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'href="/reports"' in dashboard
    assert "Current Safety Observations" in html
    assert "Average Signal Analysis" in html
    assert "Alerts and Event History" in html
    assert "Print / Save PDF" in html
