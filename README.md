# LiveSense

**Real-time Human Signal Intelligence using Computer Vision.**

LiveSense is a privacy-conscious computer-vision dashboard that turns a live
browser camera feed into useful visual activity signals. Its interface follows
an operational driver-monitoring layout with a live camera, scored signals,
event insights, and rolling session trends.

## Current capabilities

- Browser-based webcam capture (no server-side camera access required)
- Live face-presence, eye-visibility, motion, attention, and quality analysis
- Camera overlays for face state, activity, signal stability, and FPS
- Live fatigue, attention, readiness, and tension visual proxies
- Activity events and rolling fatigue, attention, and quality trends
- Camera, calibration, feedback, and new-session controls
- Configurable video and dashboard settings
- Modular architecture ready for MediaPipe landmark enhancement
- Automated unit tests

## Quick start

LiveSense requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
streamlit run app.py
```

Open the local URL displayed by Streamlit, select **Start camera**, and allow
camera access in the browser. Browser camera permissions require `localhost`
or an HTTPS deployment.

## Test

```powershell
pytest
```

## Project structure

```text
app.py                 Streamlit entry point
camera/                Browser video processing and camera state
dashboard/             UI composition and visual theme
config/                YAML configuration and typed settings
vision/                Future face and pose pipelines
signals/               Human-signal extraction
analytics/             Signal aggregation and interpretation
events/                Application event models
reports/               Report generation
utils/                 Shared utilities such as FPS measurement
tests/                 Automated tests
docs/                  Architecture and roadmap documentation
```

See [docs/architecture.md](docs/architecture.md) for the design and extension
points, and [docs/roadmap.md](docs/roadmap.md) for upcoming milestones.

## Privacy

LiveSense processes video frames in memory and does not record or persist camera
images. Current scores are visual estimates for interface feedback; they are not
medical diagnoses or substitutes for vehicle safety systems.

## License

LiveSense is available under the [MIT License](LICENSE).
