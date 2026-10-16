# AGENTS.md

Compact operating notes for this repo. See `CLAUDE.md` for the design vision and `docs/system_design.md` for full architecture. Several README/CLAUDE.md instructions are aspirational and do not match the code yet — trust this file and the code.

## Reality check (read before editing)

- This is a **Phase 1 skeleton with Phase 2/3/4/5/6 additions**. `src/camera`, `src/detection`, `src/recognition`, `src/liveness`, `src/database`, `src/pipeline` contain the running pipeline; `src/security` has `keystore.py`, `audit.py`, `tls.py`; `src/sync` has `crdt.py`, `backoff.py`, `compression.py`, `queue.py`, `signing.py`, `sync_manager.py`; `src/index` has `vector_index.py`, `hierarchical.py`, `sharding.py`, `management.py`, `matcher.py`; `src/api` has `app.py` (FastAPI factory `create_app`) + `schemas.py`; `src/dashboard` has `index.html` + `static/` (plain HTML/JS, no build). Sync is network-agnostic: `SyncQueue` is **CRDT-backed** (LWW-Element-Set), uploads are **zstd-compressed delta payloads signed with Ed25519**, but no real mTLS socket is wired (transport is injected; `NullTransport` models "offline"). `Database` takes an optional `sync_queue` and enqueues enrollment/template/delete events; `FacePipeline` builds the queue before the DB and injects it. **`faiss`/`hnswlib`/`sklearn` are NOT installed** — `src/index` falls back to a numpy `BruteForceIndex` and a numpy-SVD `PCAReducer` (FAISS backend is lazy/optional; `PipelineConfig.matcher_backend` defaults to `"linear"`).
- `config/default.yaml` / `config/local.yaml` are **not loaded anywhere**. `pipeline.py` never imports `yaml`; all runtime config comes from the `PipelineConfig` dataclass in `src/pipeline/pipeline.py`. Editing YAML has no effect today.
- `models/` is empty and gitignored, but a small **YuNet ONNX** is vendored at `src/detection/data/face_detection_yunet_2023mar.onnx` (Apache-2.0, OpenCV Zoo) — it is the model-free detection fallback. `FacePipeline.__init__` raises `RuntimeError("No recognition models loaded")` when no recognition model loads **unless `PipelineConfig.demo_mode=True`**, in which case `SyntheticEmbeddingModel` is used (see `create_demo_config()`). So `python main.py` (production) fails, but `python main.py --demo` / `--web --demo` work; `--test` is an alias for demo. `test_pipeline_creation.py` still asserts the RuntimeError.
- Detection backends (`PipelineConfig.detector_backend`): `"auto"` (SCRFD if the model loads, else YuNet, else dummy) is the default; `"scrfd"`, `"yunet"`, `"dummy"` force one. `_detect()` returns `[]` from SCRFD errors, uses `YuNetFaceDetector` (`src/detection/yunet.py`, via `cv2.FaceDetectorYN`, needs no extra dep) when available, and falls back to `_dummy_detection` (fixed centered box) only if both fail. Note: **OpenCV 5.0 here has NO `cv2.CascadeClassifier`**. Demo recognition bypasses liveness (`_check_liveness` returns live in demo mode).
- `process_frame` now **matches**: `FacePipeline._get_user_templates()` delegates to `Database.get_user_templates()`, which returns `user_id -> decrypted embedding`. Embeddings are stored **Fernet-encrypted at rest** in a `users.encrypted_embedding` column (migrated on init); the biohashed template remains the primary record. Demo uses **YuNet detection** (real tracking) and **bypasses liveness** (`_check_liveness` returns live in demo mode).
- `EnsembleExtractor.extract(image, landmarks)` **aligns internally**. The pipeline must pass the **original frame** (not a pre-aligned crop) or embeddings come out zero/garbage.
- Stale references you will not find: `scripts/download_models.py`, `scripts/quantize_model.py`, module `facial_attendance`, `tests/test_face_pipeline.py`.

## Commands

Run everything from the repo root. There is no installed package (`pyproject.toml`/`setup.py`), so `from src...` imports only work with cwd = repo root.

Windows console is `cp1252`: the root test scripts print `✓/✗/✅/❌` and crash with `UnicodeEncodeError` unless you prefix UTF-8. Use `python -X utf8 ...` (or `PYTHONIOENCODING=utf-8`).

```bash
# Hand-rolled test scripts (not pytest). test_pipeline.py is currently red.
python -X utf8 test_imports.py
python -X utf8 test_pipeline.py          # 3 pass / 2 fail (liveness kwarg + no models)
python -X utf8 test_pipeline_creation.py # fails: RuntimeError no recognition models

# Real pytest suites (phase 2 + phase 3 + phase 4 + phase 5 + phase 6). pytest must be installed first.
python -m pytest tests/ -v

# Phase 6 local web UI (no Docker, no ONNX models needed). Serves src/dashboard.
python -X utf8 main.py --web --demo      # http://127.0.0.1:8000
python -X utf8 -m src.api                 # module equivalent (--real for models/…onnx)
```

- `test_pipeline.py` failure 1: it calls `LivenessDetector(min_frames=...)` but the param is `blink_frames`. Failure 2: `FacePipeline` needs loadable recognition models (or `demo_mode`).
- `tests/` has six populated suites: `tests/recognition/test_accuracy.py` (phase 2) + `tests/recognition/test_synthetic.py` (phase 6), `tests/security/test_security.py` (phase 3), `tests/sync/test_sync.py` (phase 4), `tests/index/test_index.py` (phase 5), `tests/api/test_api.py` (phase 6), and `tests/detection/test_yunet.py` (phase 6); other `tests/*` dirs are empty (`__init__.py` only).

## Dependencies

`requirements.txt` is largely aspirational. In the default Python 3.13 env `numpy`, `onnxruntime`, `opencv-python-headless`, `PyYAML`, `cryptography`, `zstandard`, and — for phase 6 — `fastapi`, `uvicorn`, `starlette`, `pydantic`, `jinja2`, `Pillow`, `python-multipart`, and `httpx` are installed (`pytest` was added manually). `insightface`, `sqlalchemy`, and `faiss` are listed but absent — importing them fails. Note `insightface` pulls in `torch`, but inference is meant to go through ONNX Runtime.

## Architecture pointers

- Entry: `main.py` (inserts repo root on `sys.path`, then `from src.pipeline import ...`).
- Orchestrator: `src/pipeline/pipeline.py` → `FacePipeline.process_frame` runs detect → quality gate → align → embed → liveness → match.
- `EnsembleExtractor.extract()` re-aligns internally, so `pipeline.py` must pass the **original frame** to it (it still calls `aligner.align` once for display). Passing a pre-aligned crop with original-coordinate landmarks yields zero embeddings — a real bug that was fixed in phase 6.
- `src/api/app.py` exposes `create_app(config=None, pipeline=None)` (a **factory**, no import-time side effects). Endpoints: `GET /api/health`, `POST /api/recognize` (query `?log=false` to skip attendance), `POST /api/enroll` (form `name`, optional `user_id`), `GET /api/users` (includes `attendance_count`/`last_attendance`), `DELETE /api/users/{id}`, `GET /api/attendance`, `DELETE /api/attendance`, `GET /api/stats`, `POST /api/sync`; `/` serves `src/dashboard/index.html` and `/static` the assets. Attendance logging is throttled per user via `PipelineConfig.attendance_throttle_seconds` (default 60s); `FacePipeline.process_frame` returns each face with `attendance_logged` so the UI can pop a success toast. The dashboard's "Register from image" path is enroll-only (no attendance).
- `src/security/`: `KeyStore` (file/hardware backends), hash-chained `AuditLog`, and mTLS cert/context helpers. `Database` derives its Fernet key via `KeyStore` and records enrollment/verification/attendance events when an `audit_log` is passed; `FacePipeline` wires one via `PipelineConfig.audit_enabled`/`audit_log_path`.
- `.gitignore` excludes `config/local.yaml`, `models/*`, `data/*`, `logs/*`, `certs/*`, and all `*.onnx/*.db/*.pem`.
