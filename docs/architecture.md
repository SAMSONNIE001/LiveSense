# Architecture

LiveSense uses a layered, feature-oriented architecture so camera transport,
computer-vision models, signal extraction, and presentation can evolve without
becoming tightly coupled.

```text
Browser camera
      |
      v
camera/processor.py       WebRTC frame boundary, mirroring, FPS
      |
      v
vision/                   Face and pose landmarks (Milestone 2)
      |
      v
signals/ -> analytics/    Human signals and temporal interpretation
      |
      v
events/ -> reports/       Domain events and exportable summaries
      |
      v
dashboard/                Streamlit presentation and controls
```

## Design decisions

- **Browser-owned camera:** `streamlit-webrtc` captures the user's webcam in the
  browser, making local development and remote deployment behave consistently.
- **Frame processor boundary:** `CameraProcessor` is the single real-time entry
  point. Later vision pipelines can be composed here without leaking UI code.
- **Typed YAML settings:** configuration is operator-friendly while dataclasses
  give application code validated, explicit values.
- **Local-first privacy:** frames are transformed in memory and are not persisted.
- **Small domain packages:** future signal, analytics, event, and reporting work
  has an intentional home instead of accumulating in the Streamlit entry point.

## Extension point for Milestone 2

The next pipeline should expose a model-independent `LandmarkResult`, keep model
initialization outside the per-frame loop, and add overlays after inference. The
camera processor should orchestrate these components rather than implement model
details itself.
