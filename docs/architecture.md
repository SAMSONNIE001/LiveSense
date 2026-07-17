# Architecture

LiveSense uses a FastAPI/Uvicorn server with a static browser dashboard.

```text
Browser camera ────────> immediate local video preview
      │
      ├── Pose Landmarker ──> face box and shoulder/arm overlay
      │
      └── latest JPEG frame (WebSocket, backpressure controlled)
                              │
                              v
                       FastAPI / Uvicorn
                              │
             ┌────────────────┼────────────────┐
             v                v                v
       Face Landmarker  Hand Landmarker  Object Detector
             └────────────────┼────────────────┘
                              v
                    Driver safety state machine
                              │
                              v
                  JSON signals over the same socket
                              │
                              v
                Metrics, warnings, charts and alarms
```

## Design decisions

- **One camera:** the browser owns a single webcam stream. The displayed video and
  compressed analysis frames come from that same stream.
- **No stale frames:** the client sends the next JPEG only after the server replies
  to the previous one. Slow inference lowers analysis FPS instead of building delay.
- **Failure isolation:** the dashboard is static HTML/CSS/JavaScript. If analysis
  reconnects, the camera and page remain visible.
- **Small inference frames:** the browser sends 480x270 JPEGs while showing a clear
  640x360 preview.
- **Hybrid detection:** hand geometry gives fast phone/hand-to-mouth cues and the
  object detector supplies supporting phone, food, cup and bottle evidence.
- **Duration-based sleep:** persistent closed-eye cues progress from dozing to the
  critical sleep alarm, avoiding ordinary short blinks where possible.
- **No microphone:** only video frames are requested or transmitted.
- **In-memory privacy:** frames and signal history are never written to disk.
- **Automatic reconnect:** a lost analysis socket reconnects without blanking or
  reloading the dashboard.

## Alarm path

When sustained eye closure reaches `Sleeping`, `alarm_active` is returned in the
current signal snapshot. The browser immediately displays a red pull-over warning,
plays a debounced Web Audio alarm and, when permitted, creates a browser notification.
