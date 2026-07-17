# Model assets

`face_landmarker.task` is the official MediaPipe Face Landmarker float16 model
bundle used by `vision/face_landmarks.py`.

- Source: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task`
- SHA-256: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- Runtime: MediaPipe Tasks Vision, CPU

`hand_landmarker.task` is the official MediaPipe Hand Landmarker float16 model
bundle used by `vision/hand_phone.py`.

- Source: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`
- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Runtime: MediaPipe Tasks Vision, CPU

The model is bundled so LiveSense does not download executable model data when
the dashboard starts.
