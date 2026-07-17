# LiveSense

**Real-time Human Signal Intelligence using Computer Vision.**

LiveSense is a privacy-conscious human-state monitoring dashboard that combines
a browser camera and microphone with local signal analysis. It monitors awake,
drowsy, dozing, and sleeping states, suspected cough events, attention, movement,
signal quality, session events, and rolling trends.

## Current capabilities

- Browser-based webcam capture (no server-side camera access required)
- MediaPipe face landmarks for eye closure, yawning, and head-angle cues
- Duration-based `Awake`, `Drowsy`, `Dozing`, and `Sleeping` state machine
- Suspected cough detection from short microphone audio bursts
- Critical sleep event, red visual alarm, audible beeps, and browser notification
- Camera overlays for sleep state, eyes, cough count, activity, and FPS
- Rolling drowsiness, attention, and audio-activity trends
- Camera, microphone, privacy blur, calibration, feedback, and session controls
- Configurable video and dashboard settings
- Bundled official MediaPipe Face Landmarker model for offline runtime use
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
camera and microphone access. Select **Enable alarm notifications** in the
sidebar if you want operating-system browser notifications. Camera and microphone
permissions require `localhost` or an HTTPS deployment.

Sleep timing can be adjusted in `config/settings.yaml`. The default begins a
dozing warning after 1.1 seconds of sustained closure and activates the sleep
alarm after 3 seconds.

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
vision/                MediaPipe face landmark pipeline
signals/               Drowsiness and audio-burst state machines
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

LiveSense processes video and audio frames in memory and does not record or
persist them. Sleep, drowsiness, yawning, and cough results are automated cues,
not medical diagnoses or substitutes for human supervision or certified safety
systems. A suspected cough may also be triggered by another short, loud sound.

## License

LiveSense is available under the [MIT License](LICENSE).
