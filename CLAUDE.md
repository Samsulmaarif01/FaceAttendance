# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Real-time face recognition attendance system for CPU-only edge devices (Raspberry Pi 4, Intel NUC). No GPU required. Target: <1s recognition latency, offline-first, anti-spoofing liveness detection, twin discrimination.

**Current state**: Design phase — `system_design.md` is the authoritative architecture document covering all components, optimization strategies, and improvement roadmaps.

## Common Commands

```bash
# Dependencies
pip install -r requirements.txt

# Run
python main.py
python -m facial_attendance

# Test
pytest                          # all tests
pytest tests/test_face_pipeline.py -v   # single module

# Lint / format
flake8 src/
black --check src/
black src/                      # auto-format

# Model management (future)
python scripts/download_models.py    # pull ONNX models
python scripts/quantize_model.py     # FP32 → INT8
```

## Architecture at a Glance

```
Camera → Preprocess → Detect → Align → Extract Embedding → Match → Log Attendance
                ↓              ↓            ↓
         Quality Gate   Liveness Check   Sync Queue (offline)
```

### Core Modules (planned structure)

| Module | Responsibility | Key Libraries |
|--------|---------------|---------------|
| `src/camera/` | Frame capture, resolution control | OpenCV, PiCamera |
| `src/detection/` | Face detection, landmark extraction | InsightFace, ONNX |
| `src/recognition/` | Embedding extraction, matching | ArcFace/CosFace/MobileFaceNet ensemble |
| `src/liveness/` | Anti-spoofing (passive CNN + active challenge) | MiniFASNet, rPPG |
| `src/database/` | Encrypted SQLite, vector index | SQLAlchemy, FAISS/HNSW |
| `src/sync/` | Offline queue, CRDT-based sync, delta upload | Custom CRDT, zstd |
| `src/security/` | Template protection (biohashing), mTLS, audit log | cryptography, Ed25519 |
| `src/api/` | REST endpoints, webhook notifications | FastAPI |
| `src/dashboard/` | Web UI for attendance reports, self-enrollment | React/Vue (TBD) |

### Data Flow

1. **Enrollment**: Capture multi-shot (5–10 photos) → extract embeddings → compute adaptive threshold → store biohashed template in encrypted DB
2. **Recognition loop**: Capture frame → quality gate → detect face → align → extract embedding → HNSW search → liveness check → log attendance + enqueue for sync
3. **Sync cycle**: Poll queue → compress delta → sign payload → mTLS upload → apply server response → mark synced

## Key Technical Decisions (from system_design.md §13)

- **Accuracy**: Ensemble of ArcFace + CosFace + MobileFaceNet with TTA and per-user adaptive thresholds (§13.1)
- **Security**: Cancelable biometrics (biohashing), TPM/secure element key storage, mTLS, RBAC, immutable audit log (§13.2)
- **Scalability**: FAISS HNSW index for O(log n) search; sharding per site; hierarchical coarse→fine matching (§13.3)
- **Offline**: CRDT (LWW-Element-Set) for conflict-free merge; backpressure on queue; opportunistic sync with exponential backoff (§13.4)
- **Liveness**: Passive CNN (MiniFASNet) + active random challenges + optional rPPG + monocular depth estimation (§13.5)
- **UX**: Real-time overlay feedback, self-service enrollment via web, dashboard with export, walk-by recognition mode (§13.6)

## Development Guidelines

1. **CPU-first every decision** — profile with `cProfile` or `py-spy` before optimizing; prefer ONNX Runtime over PyTorch inference
2. **Never store raw embeddings** — always apply biohashing before persisting (see §13.2)
3. **Quality gate before inference** — reject blurry/small/poorly-lit faces early to save CPU cycles
4. **Test liveness thoroughly** — build a test suite with photo/video replay samples; target APCER < 1%
5. **Offline is not an edge case** — design every write path as if network may be down indefinitely
6. **Modular boundaries are strict** — each module must be testable in isolation with mocked dependencies
7. **Hardware abstraction** — wrap Pi-specific code (CSI camera, GPIO) behind interfaces so NUC path works without it

## File Conventions

- Config: YAML in `config/` (default: `config/default.yaml`, override: `config/local.yaml`)
- Models: ONNX files in `models/` (quantized INT8 variants preferred)
- Tests: `tests/` mirroring `src/` structure
- Migrations: `migrations/` for SQLite schema changes
- Logs: `logs/` (rotating, JSON format)

## Priority Roadmap (from system_design.md §13.7)

| Priority | Area | Why |
|----------|------|-----|
| **P0** | Security (template protection, TPM) | Biometric templates are irreplaceable — compromise is permanent |
| **P0** | Liveness (passive CNN + active challenge) | System is useless if spoofed |
| **P1** | Accuracy (ensemble, adaptive threshold) | Core value proposition |
| **P1** | Offline (CRDT, backpressure) | Core requirement from spec |
| **P2** | Scalability (FAISS, sharding) | Needed only after ~5K users |
| **P2** | UX (dashboard, self-enrollment) | Adoption enabler, not blocker |

## References

- Full architecture: `system_design.md`
- Improvement areas with detailed strategies: `system_design.md` §13 (Area yang Bisa Ditingkatkan)
