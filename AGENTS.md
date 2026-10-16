# AGENTS.md

Compact operating notes for this repo. See `CLAUDE.md` for the design vision and `docs/system_design.md` for full architecture. Several README/CLAUDE.md instructions are aspirational and do not match the code yet — trust this file and the code.

## Reality check (read before editing)

- This is a **Phase 1 skeleton with Phase 2/3/4 additions**. `src/camera`, `src/detection`, `src/recognition`, `src/liveness`, `src/database`, `src/pipeline` contain the running pipeline; `src/security` has `keystore.py`, `audit.py`, `tls.py`; `src/sync` now has `crdt.py`, `backoff.py`, `compression.py`, `queue.py`, `signing.py`, `sync_manager.py`. `src/api`, `src/dashboard` are still empty packages (`__init__.py` only). Sync is network-agnostic: `SyncQueue` is **CRDT-backed** (LWW-Element-Set), uploads are **zstd-compressed delta payloads signed with Ed25519**, but no real mTLS socket is wired (transport is injected; `NullTransport` models "offline"). `Database` takes an optional `sync_queue` and enqueues enrollment/template/delete events; `FacePipeline` builds the queue before the DB and injects it.
- `config/default.yaml` / `config/local.yaml` are **not loaded anywhere**. `pipeline.py` never imports `yaml`; all runtime config comes from the `PipelineConfig` dataclass in `src/pipeline/pipeline.py`. Editing YAML has no effect today.
- `models/` is empty and gitignored; no `.onnx` files exist. `FacePipeline.__init__` raises `RuntimeError("No recognition models loaded")` when none load, so `python main.py` and `python main.py --test` both fail as-is (the `--test` path sets `recognition_models = []`, which still raises).
- `process_frame` never actually matches anyone: `FacePipeline._get_user_templates()` (`src/pipeline/pipeline.py:283`) always returns `{}`.
- Stale references you will not find: `scripts/download_models.py`, `scripts/quantize_model.py`, module `facial_attendance`, `tests/test_face_pipeline.py`.

## Commands

Run everything from the repo root. There is no installed package (`pyproject.toml`/`setup.py`), so `from src...` imports only work with cwd = repo root.

Windows console is `cp1252`: the root test scripts print `✓/✗/✅/❌` and crash with `UnicodeEncodeError` unless you prefix UTF-8. Use `python -X utf8 ...` (or `PYTHONIOENCODING=utf-8`).

```bash
# Hand-rolled test scripts (not pytest). test_pipeline.py is currently red.
python -X utf8 test_imports.py
python -X utf8 test_pipeline.py          # 3 pass / 2 fail (liveness kwarg + no models)
python -X utf8 test_pipeline_creation.py # fails: RuntimeError no recognition models

# Real pytest suites (phase 2 + phase 3 + phase 4). pytest must be installed first.
python -m pytest tests/ -v
```

- `test_pipeline.py` failure 1: it calls `LivenessDetector(min_frames=...)` but the param is `blink_frames`. Failure 2: `FacePipeline` needs loadable recognition models.
- `tests/` has three populated suites: `tests/recognition/test_accuracy.py` (phase 2), `tests/security/test_security.py` (phase 3), and `tests/sync/test_sync.py` (phase 4); other `tests/*` dirs are empty (`__init__.py` only).

## Dependencies

`requirements.txt` is largely aspirational. In the default Python 3.13 env only `numpy`, `onnxruntime`, `opencv-python-headless`, `PyYAML`, and `cryptography` are installed (`pytest` was added manually). `insightface`, `sqlalchemy`, `faiss`, and `fastapi` are listed but absent — importing them fails. Note `insightface` pulls in `torch`, but inference is meant to go through ONNX Runtime.

## Architecture pointers

- Entry: `main.py` (inserts repo root on `sys.path`, then `from src.pipeline import ...`).
- Orchestrator: `src/pipeline/pipeline.py` → `FacePipeline.process_frame` runs detect → quality gate → align → embed → liveness → match.
- `EnsembleExtractor.extract()` re-aligns internally, so `pipeline.py` aligns twice (harmless, but not where you'd expect).
- `src/security/`: `KeyStore` (file/hardware backends), hash-chained `AuditLog`, and mTLS cert/context helpers. `Database` derives its Fernet key via `KeyStore` and records enrollment/verification/attendance events when an `audit_log` is passed; `FacePipeline` wires one via `PipelineConfig.audit_enabled`/`audit_log_path`.
- `.gitignore` excludes `config/local.yaml`, `models/*`, `data/*`, `logs/*`, `certs/*`, and all `*.onnx/*.db/*.pem`.
