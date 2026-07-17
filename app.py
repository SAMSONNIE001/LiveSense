"""LiveSense FastAPI/Uvicorn application."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from json import JSONDecodeError, loads
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from camera import CameraProcessor
from config import load_settings

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"

app = FastAPI(title="LiveSense", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

_processor: CameraProcessor | None = None
_processor_lock = Lock()
_frame_lock = asyncio.Lock()


def _get_processor() -> CameraProcessor:
    global _processor
    with _processor_lock:
        if _processor is None:
            settings = load_settings()
            _processor = CameraProcessor(
                mirrored=settings.camera.mirrored,
                show_fps=False,
                privacy_blur=False,
                dozing_seconds=settings.monitoring.dozing_seconds,
                sleeping_seconds=settings.monitoring.sleeping_seconds,
            )
        return _processor


def _decode_frame(payload: bytes) -> np.ndarray | None:
    encoded = np.frombuffer(payload, dtype=np.uint8)
    if encoded.size == 0:
        return None
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def _live_payload(processor: CameraProcessor) -> dict:
    view = processor.session.snapshot()
    return {
        "type": "signals",
        "current": asdict(view.current),
        "history": [asdict(point) for point in view.history[-120:]],
        "events": [asdict(event) for event in view.events[:12]],
    }


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/analyze")
async def analyze(websocket: WebSocket) -> None:
    await websocket.accept()
    processor = await asyncio.to_thread(_get_processor)
    await websocket.send_json(_live_payload(processor))
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            payload = message.get("bytes")
            if payload is not None:
                image = await asyncio.to_thread(_decode_frame, payload)
                if image is None:
                    await websocket.send_json({"type": "error", "detail": "Invalid frame"})
                    continue
                async with _frame_lock:
                    await asyncio.to_thread(processor.process_image, image)
                await websocket.send_json(_live_payload(processor))
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                command = loads(text)
            except JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid command"})
                continue
            action = command.get("action")
            if action == "reset":
                processor.reset_session()
            elif action == "calibrate":
                processor.start_calibration(10.0)
            await websocket.send_json(_live_payload(processor))
    except WebSocketDisconnect:
        pass
