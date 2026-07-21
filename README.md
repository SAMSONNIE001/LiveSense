# LiveSense

LiveSense is a real-time human-activity and driver-safety monitoring dashboard.
It runs with FastAPI/Uvicorn, uses the browser's camera, and performs visual
analysis with bundled MediaPipe models.

## Final capabilities

- Fast static dashboard served by FastAPI; Streamlit is not used
- One browser-owned camera stream with an immediate local preview
- Backpressure-controlled WebSocket analysis with no stale-frame queue
- Face box and shoulder/arm tracking overlay
- Fresh-frame eye analysis with a two-second continuous-closure sleep alarm
- Blink protection: cached landmark frames cannot advance the sleep timer
- Yawning based on sustained jaw-opening evidence from fresh face inference
- Hand-safety guidance without ambiguous phone-use claims
- Eating from repeated food evidence or sustained hand-to-mouth jaw movement
- Drinking from repeated cup/bottle evidence positioned near the mouth
- Independent seat-belt, missing-face, attention, and signal-quality observations
- Bold live warnings, activity record, charts, event timeline, session summary,
  and a dedicated reports page
- Browser notification and audible pull-over alarm for confirmed sleeping
- A browser refresh starts a new in-memory monitoring session
- Frames are processed in memory and are never recorded by LiveSense

## Requirements

- Python 3.11 or newer
- A webcam
- A current browser with camera and WebSocket support
- Windows PowerShell commands are shown below

## Install and run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app:app --host 127.0.0.1 --port 8501
```

Open <http://127.0.0.1:8501>, select **Start Camera**, and allow camera access.
Camera access works on localhost or an HTTPS deployment. LiveSense does not
request microphone access.

If port 8501 is already occupied, stop the previous server with `Ctrl+C` or use
another port:

```powershell
uvicorn app:app --host 127.0.0.1 --port 8502
```

## How the final observations work

| Observation | Confirmation rule |
| --- | --- |
| Sleeping | Both-eye evidence remains closed for two seconds across fresh face analyses |
| Yawning | Strong jaw opening persists across fresh face analyses |
| Eating | Repeated positioned food evidence, or sustained hand-to-mouth plus jaw movement |
| Drinking | Repeated cup/bottle evidence positioned close to the mouth |
| Hands safety | One visible hand produces advice to keep both hands available |
| Seat belt | Sustained paired diagonal belt-edge evidence across the upper torso |
| Missing face | The face remains outside a reliable camera view |

Fresh inference matters: cached face results may keep the dashboard visually
stable, but they do not advance sleep or yawning timers. This prevents a single
blink captured at low FPS from becoming a sleep alarm.

## Reports and API

- `GET /` - live dashboard
- `GET /reports` - clear session report page
- `GET /api/report` - current report data as JSON
- `GET /health` - server health
- `WS /ws/analyze` - JPEG frames in, live JSON signals out
- `GET /api/docs` - FastAPI API documentation

Session history is held only in server memory. Refreshing the dashboard sends one
session-reset command, so previous observations do not reappear after a refresh.

## Jupyter notebook

[`LiveSense_Final_Validation.ipynb`](LiveSense_Final_Validation.ipynb) documents
and demonstrates the final sleep, blink, eating, drinking, and object-position
rules without needing to start the camera.

Install the notebook extra and launch JupyterLab:

```powershell
pip install -e ".[dev,notebook]"
jupyter lab LiveSense_Final_Validation.ipynb
```

## Validate the project

```powershell
pytest
ruff check .
python -m pip check
node --check web\app.js
node --check web\reports.js
```

## Project structure

```text
app.py                          FastAPI application and analysis WebSocket
web/                            Static dashboard and reports page
camera/                         Frame processing and signal coordination
config/                         YAML configuration and typed settings
vision/                         Face, hand, object, and seat-belt analysis
signals/                        Drowsiness and temporal state machines
analytics/                      Session history and event interpretation
assets/models/                  Bundled MediaPipe/TFLite model files
tests/                          Automated regression tests
LiveSense_Final_Validation.ipynb Final behavior walkthrough
```

## Accuracy and safety scope

LiveSense uses visual estimates from a normal webcam. Lighting, camera angle,
occlusion, object size, and analysis FPS affect results. Eating, drinking, and
seat-belt observations use a general-purpose object/edge pipeline rather than a
certified automotive model.

LiveSense is a development and demonstration system. It is not a certified
driver-monitoring device, medical system, or substitute for safe driving.

## Privacy

Camera frames are compressed by the browser, analyzed in memory, and discarded.
LiveSense does not save video frames, request microphone access, or persist
session history to disk.

## License

LiveSense is available under the [MIT License](LICENSE).
