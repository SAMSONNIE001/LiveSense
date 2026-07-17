# Architecture

LiveSense uses a layered, feature-oriented architecture so camera transport,
computer-vision models, signal extraction, and presentation can evolve without
becoming tightly coupled.

```text
Browser camera ------------------- Browser microphone
      |                                      |
      v                                      v
MediaPipe Face Landmarker            Audio burst detector
      |                                      |
      +---- eye/yawn/head cues    suspected cough cue ----+
                             |                             |
                             v                             |
                    Drowsiness state machine <-------------+
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
- **Duration-based sleep:** `DrowsinessMonitor` requires persistent cues before
  escalating from awake to dozing and sleeping. A single closed-eye frame cannot
  activate the critical alarm.
- **Separate audio heuristic:** microphone frames feed `AudioActivityDetector`.
  Only short, energetic, broadband bursts increment the suspected cough count;
  continuous sound is rejected by duration rules.
- **Frame processor boundary:** `CameraProcessor` combines current visual and
  audio cues and publishes immutable snapshots to a thread-safe session store.
- **Live session model:** `SignalSession` debounces activity events and samples
  rolling history so Streamlit can refresh metrics without blocking video frames.
- **Typed YAML settings:** configuration is operator-friendly while dataclasses
  give application code validated, explicit values.
- **Local-first privacy:** frames are transformed in memory and are not persisted.
- **Small domain packages:** future signal, analytics, event, and reporting work
  has an intentional home instead of accumulating in the Streamlit entry point.

## Alarm path

When sustained cues reach `Sleeping`, the snapshot sets `alarm_active`. The
session emits a critical event, the camera receives a red wake-up overlay, and
the dashboard emits a visual alarm plus debounced Web Audio and browser
notification signals. Notifications still require explicit browser permission.
