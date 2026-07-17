# LiveSense

**Real-time Human Signal Intelligence using Computer Vision.**

LiveSense is a privacy-conscious driver-state monitoring dashboard that performs
low-latency local camera analysis. It monitors awake, drowsy, dozing, sleeping,
attention, movement, object-assisted phone use, eating, drinking, seat-belt,
and missing-face signals.

## Current capabilities

- Browser-based webcam capture (no server-side camera access required)
- MediaPipe face landmarks for eye closure, yawning, and head-angle cues
- Duration-based `Awake`, `Drowsy`, `Dozing`, and `Sleeping` state machine
- MediaPipe hand landmarks plus EfficientDet-Lite0 for steadier phone-at-ear warnings
- Eating, drinking, seat-belt-not-confirmed, and missing-face observations
- Critical sleep event with a red pull-over warning, audible alarm, and notification
- Zero-round-trip browser preview with conditions shown in the top warning banner
- Rolling drowsiness, attention, and phone-use trends
- Camera, calibration, feedback, and session controls
- Configurable video and dashboard settings
- Bundled official MediaPipe face and hand landmarker models for offline runtime use
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

Open the local URL displayed by Streamlit, select **Start Camera**, and allow
camera access. Select **Enable alarm notifications** in the sidebar if you want
operating-system browser notifications. Camera permission requires `localhost`
or an HTTPS deployment. LiveSense does not request microphone access.

Sleep timing can be adjusted in `config/settings.yaml`. The default begins a
yellow dozing warning after 1.1 seconds of sustained closure and activates the
red sleep alarm after 3 seconds.

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
vision/                MediaPipe face and hand landmark pipelines
signals/               Drowsiness and shared signal state machines
analytics/             Session history, events, and interpretation
events/                Application event models
reports/               Report generation
utils/                 Shared utilities such as FPS measurement
tests/                 Automated tests
docs/                  Architecture and roadmap documentation
```

See [docs/architecture.md](docs/architecture.md) for the design and extension
points, and [docs/roadmap.md](docs/roadmap.md) for upcoming milestones.

## Privacy

LiveSense processes video frames in memory and does not record or persist them.
Sleep, drowsiness, yawning, phone-use, eating, drinking, and seat-belt results
are automated visual cues, not definitive safety or medical diagnoses or
substitutes for human supervision or certified safety systems.

## License

LiveSense is available under the [MIT License](LICENSE).
