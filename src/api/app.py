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
from fastapi.responses import FileResponse, Response
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
        "attendance_logged": bool(result.get("attendance_logged", False)),
        "attendance_duplicate": bool(result.get("attendance_duplicate", False)),
        "attendance_duplicate_at": result.get("attendance_duplicate_at"),
        "attendance_status": result.get("attendance_status", "no_match"),
        "gate_granted": bool(result.get("gate_granted", False)),
        "direction": result.get("direction", "in"),
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
        templates = pipe.database.get_user_templates()
        unreadable = list(pipe.database.unreadable_templates)
        return {
            "status": "ok",
            "demo_mode": bool(pipe.config.demo_mode),
            "recognition_models": len(pipe.ensemble_extractor.models),
            "detector_loaded": pipe.detector is not None,
            "matcher_backend": pipe.config.matcher_backend,
            "sync_enabled": pipe.sync_manager is not None,
            "templates_loaded": len(templates),
            "templates_unreadable": len(unreadable),
            "templates_unreadable_ids": unreadable[:10],
            "enroll_duplicate_threshold": pipe.config.enroll_duplicate_threshold,
        }

    @app.post("/api/recognize", response_model=schemas.RecognizeResponse)
    async def recognize(
        file: UploadFile = File(...),
        log: bool = True,
        direction: str = "in",
        gate: bool = False,
    ) -> dict:
        if direction not in ("in", "out"):
            raise HTTPException(status_code=400, detail="direction must be 'in' or 'out'")
        frame = decode_image(await file.read())
        start = time.perf_counter()
        results = pipe.process_frame(frame, log_attendance=log, direction=direction, gate=gate)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        faces = [_serialize_face(r) for r in results]
        return {"faces": faces, "count": len(faces), "elapsed_ms": round(elapsed_ms, 2)}

    @app.post("/api/enroll", response_model=schemas.EnrollResponse)
    async def enroll(
        name: str = Form(""),
        user_id: Optional[str] = Form(None),
        file: UploadFile = File(...),
    ) -> dict:
        frame = decode_image(await file.read())
        # user_id stays None when the caller did not supply one: the pipeline
        # only invents an id once it decides this really is a new user.
        info = pipe.enroll_from_frame(frame, user_id, (name or "").strip())
        if info is None:
            raise HTTPException(status_code=400, detail="No usable face detected")
        if info.get("duplicate"):
            # Not an error: the face is already registered. 200 lets the UI show
            # an informative banner instead of a red failure.
            return info
        if info.get("needs_name"):
            raise HTTPException(
                status_code=400,
                detail="Isi nama untuk mendaftarkan pengguna baru",
            )
        if not info["success"]:
            raise HTTPException(status_code=409, detail=f"User '{info['user_id']}' already exists")
        return info

    @app.get("/api/users", response_model=schemas.UsersResponse)
    def users(include_archived: bool = False) -> dict:
        people = pipe.database.get_all_users(include_archived=include_archived)
        summary = pipe.database.get_attendance_summary()
        today = pipe.database.get_today_status()
        result = []
        for u in people:
            stats = summary.get(u.id, {})
            status = today.get(u.id, {})
            result.append({
                "id": u.id,
                "name": u.name,
                "is_active": bool(u.is_active),
                "is_archived": not bool(u.is_active),
                "created_at": u.created_at.isoformat(),
                "attendance_count": int(stats.get("count", 0)),
                "last_attendance": stats.get("last"),
                "checked_in_today": bool(status.get("in", False)),
                "checked_out_today": bool(status.get("out", False)),
                "has_photo": pipe.database.get_user_photo(u.id) is not None,
            })
        return {"users": result, "count": len(result)}

    @app.get("/api/users/{user_id}/photo", include_in_schema=False)
    def user_photo(user_id: str):
        """Avatar JPEG for a user, or 404 when none is stored."""
        photo = pipe.database.get_user_photo(user_id)
        if not photo:
            raise HTTPException(status_code=404, detail="No photo for this user")
        return Response(content=photo, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=300"})

    @app.post("/api/users/{user_id}/photo", response_model=schemas.PhotoResponse)
    async def set_user_photo(user_id: str, file: UploadFile = File(...)) -> dict:
        """Attach or replace the avatar of an EXISTING user.

        Photo-only: the stored template and every attendance record are left
        untouched, so an operator can backfill an avatar for someone enrolled
        before thumbnails existed without re-registering their face.
        """
        if pipe.database.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        frame = decode_image(await file.read())
        photo = pipe.update_photo_from_frame(frame, user_id)
        if photo is None:
            raise HTTPException(status_code=400, detail="No usable face detected")
        return {"success": True, "user_id": user_id, "has_photo": True, "bytes": len(photo)}

    @app.delete("/api/users/{user_id}", response_model=schemas.DeleteResponse)
    def delete_user(user_id: str, permanent: bool = False) -> dict:
        """Archive (soft delete, default) or permanently delete a user.

        * archive   -> keeps the template and every attendance record, so the
                       face is still recognised as "already registered" and
                       re-enrolling reactivates the same user instead of
                       creating a duplicate. Restorable via /api/users/{id}/restore.
        * permanent -> removes the user, their template and all their attendance
                       records. Irreversible.
        """
        if permanent:
            deleted, attendance_deleted = pipe.database.hard_delete_user(user_id)
            if not deleted:
                raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
            return {"success": True, "id": user_id, "mode": "permanent",
                    "attendance_deleted": attendance_deleted}
        if not pipe.database.delete_user(user_id):
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        pipe.reset_attendance_throttle(user_id)
        return {"success": True, "id": user_id, "mode": "archived", "attendance_deleted": 0}

    @app.post("/api/users/{user_id}/restore", response_model=schemas.DeleteResponse)
    def restore_user(user_id: str) -> dict:
        """Restore an archived user so they show up in Data Karyawan again."""
        if not pipe.database.restore_user(user_id):
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        pipe.reset_attendance_throttle(user_id)
        return {"success": True, "id": user_id, "mode": "restored", "attendance_deleted": 0}

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
                    "direction": r.direction,
                    "name": r.name,
                }
                for r in records
            ],
            "count": len(records),
        }

    @app.delete("/api/attendance", response_model=schemas.DeleteResponse)
    def clear_attendance() -> dict:
        removed = pipe.database.clear_attendance()
        # Drop the in-memory throttle too, so the cleared day can be
        # re-attended immediately instead of being silently skipped.
        pipe.reset_attendance_throttle()
        return {"success": True, "deleted": removed}

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

    @app.middleware("http")
    async def _revalidate_dashboard(request, call_next):
        """Never serve the dashboard stale.

        Without a Cache-Control header the browser applies heuristic freshness
        to index.html, so a restart could keep serving the OLD page — which
        pins an old ``?v=`` on app.js/style.css and makes a code change look
        like it did nothing at all. API responses choose their own caching
        (avatars use max-age=300), so only the UI is touched here.
        """
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.get("/", include_in_schema=False)
    def dashboard():
        if index.is_file():
            return FileResponse(str(index))
        raise HTTPException(status_code=404, detail="Dashboard not found")
