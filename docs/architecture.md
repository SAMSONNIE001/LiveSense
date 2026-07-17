# Architecture

LiveSense uses a layered, feature-oriented architecture so camera transport,
computer-vision models, signal extraction, and presentation can evolve without
becoming tightly coupled.

```text
Browser camera
      |
      v
Reduced inference frame
      |
      +---- MediaPipe Face Landmarker ---- eye/yawn/head cues
      |
      +---- MediaPipe Hand Landmarker ---- hand-at-ear cue
                             |
                             v
                    Driver state machine
                             |
                             v
                 Session history and critical events
                             |
                             v
                    Streamlit dashboard + alarms
```

## Design decisions

- **Browser-owned camera:** `streamlit-webrtc` captures the user's webcam in the
  browser, making local development and remote deployment behave consistently.
- **MediaPipe landmarks:** the bundled Face Landmarker model produces eye blink,
  mouth/yawn, face geometry, and head-angle cues. Inference runs inside the video
  processor and falls back to OpenCV face/eye detection if model creation fails.
- **Low-latency sampling:** the browser captures 640x360 video while inference
  uses a smaller frame. Face and hand models run at separate sampling intervals;
  the original output frame remains clear and responsive.
- **Phone-use cue:** the hand model checks for a sustained palm position beside
  either ear and raises a top-of-page phone warning.
- **Duration-based sleep:** `DrowsinessMonitor` requires persistent cues before
  escalating from awake to dozing and sleeping. A single closed-eye frame cannot
  activate the critical alarm.
- **No microphone track:** WebRTC captures video only, reducing transport and
  processing overhead while avoiding unnecessary microphone permission.
- **Frame processor boundary:** `CameraProcessor` combines current visual cues
  and publishes immutable snapshots to a thread-safe session store.
- **Live session model:** `SignalSession` debounces activity events and samples
  rolling history so Streamlit can refresh metrics without blocking video frames.
- **Typed YAML settings:** configuration is operator-friendly while dataclasses
  give application code validated, explicit values.
- **Local-first privacy:** frames are transformed in memory and are not persisted.
- **Small domain packages:** future signal, analytics, event, and reporting work
  has an intentional home instead of accumulating in the Streamlit entry point.

## Alarm path

When sustained cues reach `Sleeping`, the snapshot sets `alarm_active`. The
session emits a critical event, and the dashboard displays a red **Pull over now**
warning plus debounced Web Audio and browser notification signals. The camera
frame remains unobstructed. Notifications still require explicit permission.
