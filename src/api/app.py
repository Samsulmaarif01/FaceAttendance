"""
Local web API for the face attendance system (phase 6).

Serves a browser dashboard plus JSON endpoints for recognition, self-service
enrollment, and attendance/stats. Runs fully offline and needs no Docker: the
UI lives in ``src/dashboard`` and the server is started with uvicorn.

Create the app with :func:`create_app` (a factory, so importing this module has
no side effects). Run it with::

    python -X utf8 main.py --web --demo
    # or
    python -m uvicorn src.api.app:create_app --factory --port 8000
"""

import secrets
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.pipeline.pipeline import FacePipeline, PipelineConfig, create_demo_config
from src.api import schemas

DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"


def decode_image(data: bytes) -> np.ndarray:
    """Decode uploaded image bytes into a BGR frame."""
    if not data:
        raise HTTPException(status_code=400, detail="Empty image payload")
    buffer = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid or unsupported image")
    return frame


def _serialize_face(result: dict) -> dict:
    det = result["detection"]
    liveness = result["liveness"]
    match = result.get("match")
    x, y, w, h = det.bbox
    face = {
        "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
        "confidence": float(det.confidence),
        "liveness": {
            "is_live": bool(liveness.is_live),
            "score": float(liveness.score),
            "reason": liveness.reason,
        },
        "match": None,
    }
    if match is not None:
        face["match"] = {
            "user_id": match.user_id,
            "name": match.name,
            "similarity": float(match.similarity),
            "threshold": float(match.threshold),
            "matched": bool(match.matched),
        }
    return face


def create_app(
    config: Optional[PipelineConfig] = None,
    pipeline: Optional[FacePipeline] = None,
) -> FastAPI:
    """Build the FastAPI application (factory; no import-time side effects)."""
    app = FastAPI(title="Face Attendance API", version="0.6.0")

    pipe = pipeline or FacePipeline(config or create_demo_config())
    app.state.pipeline = pipe

    @app.get("/api/health", response_model=schemas.HealthResponse)
    def health() -> dict:
        return {
            "status": "ok",
            "demo_mode": bool(pipe.config.demo_mode),
            "recognition_models": len(pipe.ensemble_extractor.models),
            "detector_loaded": pipe.detector is not None,
            "matcher_backend": pipe.config.matcher_backend,
            "sync_enabled": pipe.sync_manager is not None,
        }

    @app.post("/api/recognize", response_model=schemas.RecognizeResponse)
    async def recognize(file: UploadFile = File(...)) -> dict:
        frame = decode_image(await file.read())
        start = time.perf_counter()
        results = pipe.process_frame(frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        faces = [_serialize_face(r) for r in results]
        return {"faces": faces, "count": len(faces), "elapsed_ms": round(elapsed_ms, 2)}

    @app.post("/api/enroll", response_model=schemas.EnrollResponse)
    async def enroll(
        name: str = Form(...),
        user_id: Optional[str] = Form(None),
        file: UploadFile = File(...),
    ) -> dict:
        frame = decode_image(await file.read())
        uid = user_id or secrets.token_urlsafe(8)
        info = pipe.enroll_from_frame(frame, uid, name)
        if info is None:
            raise HTTPException(status_code=400, detail="No usable face detected")
        if not info["success"]:
            raise HTTPException(status_code=409, detail=f"User '{uid}' already exists")
        return info

    @app.get("/api/users", response_model=schemas.UsersResponse)
    def users() -> dict:
        people = pipe.database.get_all_users()
        return {
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "is_active": bool(u.is_active),
                    "created_at": u.created_at.isoformat(),
                }
                for u in people
            ],
            "count": len(people),
        }

    @app.get("/api/attendance", response_model=schemas.AttendanceResponse)
    def attendance(limit: int = 50) -> dict:
        records = pipe.database.list_attendance(limit=max(1, min(limit, 500)))
        return {
            "records": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "timestamp": r.timestamp.isoformat(),
                    "similarity": float(r.similarity),
                    "liveness_score": float(r.liveness_score),
                    "synced": bool(r.synced),
                }
                for r in records
            ],
            "count": len(records),
        }

    @app.get("/api/stats", response_model=schemas.StatsResponse)
    def stats() -> dict:
        return pipe.database.get_attendance_stats()

    @app.post("/api/sync", response_model=schemas.SyncResponse)
    def sync() -> dict:
        result = pipe.sync_now()
        if result is None:
            return {"status": "disabled"}
        return {
            "status": "ok" if result.success else "offline",
            "success": result.success,
            "uploaded": result.uploaded,
            "synced_ids": list(result.synced_ids),
            "retry_delay": result.retry_delay,
            "error": result.error,
        }

    _mount_dashboard(app)
    return app


def _mount_dashboard(app: FastAPI) -> None:
    index = DASHBOARD_DIR / "index.html"
    static = DASHBOARD_DIR / "static"
    if static.is_dir():
        app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        if index.is_file():
            return FileResponse(str(index))
        raise HTTPException(status_code=404, detail="Dashboard not found")
