# LiveSense

Real-time human activity and driver-safety monitoring with a FastAPI/Uvicorn
server and a browser-owned camera.

## Capabilities

- Fast static replica dashboard served by FastAPI
- One browser camera stream; no duplicate server-side camera capture
- Backpressure-aware WebSocket analysis with no stale-frame queue
- MediaPipe eye closure, yawning, face and hand landmarks
- Rapid dozing and sleep alarm state machine
- Phone-at-ear and phone-in-hand detection
- Eating, drinking, seat-belt and missing-face observations
- Live face box, shoulder/arm overlay, charts, event timeline and session summary
- Browser notification and audible sleep alarm
- In-memory processing only; frames are not recorded or persisted

## Quick start

LiveSense requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app:app --host 127.0.0.1 --port 8501
```

Open <http://localhost:8501>, select **Start Camera**, and allow camera access.
Camera permission requires localhost or an HTTPS deployment. LiveSense does not
request microphone access.

## API

- `GET /` — dashboard
- `GET /health` — server health
- `WS /ws/analyze` — binary JPEG frames in, JSON signals out
- `GET /api/docs` — FastAPI API documentation

## Test

```powershell
pytest
```

## Project structure

```text
app.py                 FastAPI application and analysis WebSocket
web/                   Static HTML, CSS and JavaScript dashboard
camera/                Frame processing and safety-signal coordination
config/                YAML configuration and typed settings
vision/                MediaPipe face, hand and object pipelines
signals/               Drowsiness and shared signal state machines
analytics/             Session history and event interpretation
tests/                 Automated tests
```

## Safety and privacy

LiveSense processes compressed frames in memory and does not save them. Results
are automated visual estimates, not certified driver-safety or medical diagnoses.

## License

LiveSense is available under the [MIT License](LICENSE).
