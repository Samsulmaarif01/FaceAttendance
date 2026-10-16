"""
Main pipeline for face recognition attendance system.
Integrates camera, detection, recognition, liveness, and database.
"""

import cv2
import numpy as np
import time
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from src.camera.capture import Camera, CameraConfig
from src.detection.detector import SCRFDDetector, FaceDetection, QualityGate
from src.recognition.extractor import (
    EnsembleExtractor, FaceAligner, FaceMatcher,
    ONNXEmbeddingModel,
)
from src.recognition.synthetic import SyntheticEmbeddingModel
from src.liveness.detector import LivenessDetector, LivenessResult
from src.database.database import Database, BioHasher, User, AttendanceRecord
from src.security.audit import AuditLog


@dataclass
class PipelineConfig:
    # Camera
    camera_device_id: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_backend: str = "opencv"

    # Detection
    detection_model_path: str = "models/scrfd.onnx"
    detection_input_size: tuple = (640, 640)
    detection_conf_threshold: float = 0.5
    detection_nms_threshold: float = 0.4
    detection_max_faces: int = 10
    quality_min_face_size: int = 80
    quality_min_sharpness: float = 100.0
    quality_min_brightness: int = 40
    quality_max_brightness: int = 200

    # Recognition
    recognition_models: List[dict] = None  # List of {'path': str, 'name': str, 'weight': float}
    recognition_input_size: tuple = (112, 112)
    recognition_threshold: float = 0.45
    recognition_adaptive_enabled: bool = True
    recognition_min_threshold: float = 0.35
    recognition_max_threshold: float = 0.55
    recognition_update_rate: float = 0.05
    recognition_tta_enabled: bool = True
    recognition_tta_rotations: bool = True
    recognition_tta_brightness: bool = True
    recognition_tta_rotation_angle: float = 15.0
    recognition_tta_brightness_factor: float = 0.1

    # Liveness
    liveness_ear_threshold: float = 0.25
    liveness_blink_frames: int = 3
    liveness_head_movement_threshold: float = 10.0
    liveness_min_frames: int = 10

    # Database
    database_path: str = "data/attendance.db"
    database_encryption_key: Optional[bytes] = None
    database_biohash_token: Optional[bytes] = None

    # Security
    audit_enabled: bool = True
    audit_log_path: str = "logs/audit.log"

    # Sync (offline-first, phase 4)
    sync_enabled: bool = False
    sync_queue_path: str = "data/sync_queue.bin"
    sync_max_batch: int = 50
    sync_device_id: str = ""
    sync_queue_max_size: int = 10000
    sync_transport: Optional[object] = None  # injectable transport; NullTransport if None

    # Scalability (phase 5)
    matcher_backend: str = "linear"  # "linear" | "indexed"
    index_backend: str = "auto"      # "auto" | "brute_force" | "faiss"
    index_use_hnsw: bool = False

    # Demo / testing (phase 6). When enabled, the pipeline runs without ONNX
    # models: a synthetic embedding model is used and liveness is bypassed.
    demo_mode: bool = False

    # System
    frame_skip: int = 2  # Process every Nth frame to save CPU
    display_output: bool = True
    window_name: str = "Face Attendance"


class FacePipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.frame_count = 0
        self._init_modules()

    def _init_modules(self):
        # Camera
        camera_config = CameraConfig(
            device_id=self.config.camera_device_id,
            width=self.config.camera_width,
            height=self.config.camera_height,
            fps=self.config.camera_fps,
            backend=self.config.camera_backend,
        )
        self.camera = Camera(camera_config)

        # Detection
        try:
            self.detector = SCRFDDetector(
                model_path=self.config.detection_model_path,
                input_size=self.config.detection_input_size,
                conf_threshold=self.config.detection_conf_threshold,
                nms_threshold=self.config.detection_nms_threshold,
                max_faces=self.config.detection_max_faces,
            )
        except Exception as e:
            print(f"Warning: Could not load detection model: {e}")
            self.detector = None  # Will use dummy detection

        self.quality_gate = QualityGate(
            min_face_size=self.config.quality_min_face_size,
            min_sharpness=self.config.quality_min_sharpness,
            min_brightness=self.config.quality_min_brightness,
            max_brightness=self.config.quality_max_brightness,
        )

        # Recognition
        if self.config.recognition_models is None:
            # Default ensemble weights
            self.config.recognition_models = [
                {"path": "models/arcface_r100.onnx", "name": "arcface_r100", "weight": 0.5},
                {"path": "models/cosface_r50.onnx", "name": "cosface_r50", "weight": 0.3},
                {"path": "models/mobilefacenet.onnx", "name": "mobilefacenet", "weight": 0.2},
            ]

        recognition_models = []
        for model_info in self.config.recognition_models:
            try:
                model = ONNXEmbeddingModel(
                    model_path=model_info["path"],
                    name=model_info["name"],
                    input_size=self.config.recognition_input_size,
                )
                if model.is_loaded:
                    recognition_models.append(model)
                else:
                    print(f"Warning: Could not load recognition model {model_info['name']}: {model.load_error}")
            except Exception as e:
                print(f"Warning: Could not load recognition model {model_info['name']}: {e}")

        if not recognition_models and self.config.demo_mode:
            print("Demo mode: using SyntheticEmbeddingModel (no ONNX models loaded)")
            recognition_models = [SyntheticEmbeddingModel()]
            model_weights = [1.0]
        elif not recognition_models:
            raise RuntimeError("No recognition models loaded")
        else:
            model_weights = [m["weight"] for m in self.config.recognition_models]

        self.ensemble_extractor = EnsembleExtractor(
            models=recognition_models,
            weights=model_weights,
            tta_enabled=self.config.recognition_tta_enabled,
            tta_rotations=self.config.recognition_tta_rotations,
            tta_brightness=self.config.recognition_tta_brightness,
            tta_rotation_angle=self.config.recognition_tta_rotation_angle,
            tta_brightness_factor=self.config.recognition_tta_brightness_factor,
        )
        self.aligner = FaceAligner()
        if self.config.matcher_backend == "indexed":
            from src.index import IndexedMatcher, create_index

            index = create_index(
                self.config.index_backend,
                dim=512,  # face embedding dimensionality
                use_hnsw=self.config.index_use_hnsw,
            )
            self.matcher = IndexedMatcher(
                threshold=self.config.recognition_threshold,
                index=index,
                adaptive_enabled=self.config.recognition_adaptive_enabled,
                min_threshold=self.config.recognition_min_threshold,
                max_threshold=self.config.recognition_max_threshold,
                update_rate=self.config.recognition_update_rate,
                history_size=100,
            )
        else:
            self.matcher = FaceMatcher(
                threshold=self.config.recognition_threshold,
                adaptive_enabled=self.config.recognition_adaptive_enabled,
                min_threshold=self.config.recognition_min_threshold,
                max_threshold=self.config.recognition_max_threshold,
                update_rate=self.config.recognition_update_rate,
                history_size=100,
            )

        # Liveness
        self.liveness_detector = LivenessDetector(
            ear_threshold=self.config.liveness_ear_threshold,
            blink_frames=self.config.liveness_blink_frames,
            head_movement_threshold=self.config.liveness_head_movement_threshold,
            min_frames_for_decision=self.config.liveness_min_frames,
        )

        # Audit log
        self.audit_log = AuditLog(self.config.audit_log_path) if self.config.audit_enabled else None

        # Sync (offline-first). Optional: the pipeline runs fully offline without it.
        self.sync_queue = None
        self.sync_manager = None
        if self.config.sync_enabled:
            from src.sync import NullTransport, SyncManager, SyncQueue

            self.sync_queue = SyncQueue(
                max_size=self.config.sync_queue_max_size,
                persist_path=self.config.sync_queue_path,
            )
            transport = self.config.sync_transport or NullTransport()
            self.sync_manager = SyncManager(
                queue=self.sync_queue,
                transport=transport,
                max_batch=self.config.sync_max_batch,
            )

        # Database (enrollment/template/delete events are queued for sync when enabled)
        self.database = Database(
            db_path=self.config.database_path,
            encryption_key=self.config.database_encryption_key,
            biohash_token=self.config.database_biohash_token,
            audit_log=self.audit_log,
            sync_queue=self.sync_queue,
        )

        if self.audit_log is not None:
            self.audit_log.log(
                "pipeline_initialized",
                details={
                    "recognition_models": len(self.ensemble_extractor.models),
                    "detector_loaded": self.detector is not None,
                    "sync_enabled": self.sync_manager is not None,
                },
            )

        # State
        self.liveness_states: Dict[str, LivenessDetector] = {}  # Track liveness per face (by track ID)
        self.last_recognition_time: Dict[str, float] = {}  # Throttle recognition per user

    def start(self) -> bool:
        return self.camera.start()

    def stop(self) -> None:
        self.camera.stop()
        cv2.destroyAllWindows()

    def process_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        Process a single frame and return list of results for each detected face.
        """
        self.frame_count += 1

        # Skip frames to save CPU
        if self.frame_count % self.config.frame_skip != 0:
            return []

        # Detect faces
        detections = self._detect(frame)

        # Apply quality gate
        detections = self.quality_gate.check_batch(frame, detections)

        results = []
        for det in detections:
            x, y, w, h = det.bbox
            face_roi = frame[y:y+h, x:x+w]

            # Align face
            aligned = self.aligner.align(frame, det.landmarks)

            # Extract embedding (EnsembleExtractor aligns internally from the
            # original frame; passing an already-aligned crop would misalign)
            embedding = self.ensemble_extractor.extract(frame, det.landmarks)

            # Liveness detection (simplified: use face ROI for landmarks)
            # In a real system, we would use landmarks from a 68-point detector
            liveness_result = self._check_liveness(det.landmarks)

            # Match against database
            match_result = None
            if liveness_result.is_live:
                # Get user templates from database (this is a simplification)
                # In reality, we'd need to store encrypted embeddings or use a different approach
                user_templates = self._get_user_templates()
                if user_templates:
                    match_result = self.matcher.match(embedding, user_templates)
                    if match_result is not None:
                        user = self.database.get_user(match_result.user_id)
                        if user is not None:
                            match_result.name = user.name
                    if match_result and match_result.matched:
                        # Update adaptive threshold
                        self.matcher.update_threshold(match_result.user_id, match_result.similarity)
                        # Log attendance locally (works offline)
                        record_id = self.database.log_attendance(
                            user_id=match_result.user_id,
                            similarity=match_result.similarity,
                            liveness_score=liveness_result.score,
                        )
                        # Enqueue for sync (no-op when sync is disabled)
                        self._enqueue_sync(
                            record_id=record_id,
                            user_id=match_result.user_id,
                            similarity=match_result.similarity,
                            liveness_score=liveness_result.score,
                        )

            results.append({
                "detection": det,
                "embedding": embedding,
                "liveness": liveness_result,
                "match": match_result,
                "aligned_face": aligned,
                "face_roi": face_roi,
            })

        return results

    def _enqueue_sync(
        self,
        record_id: str,
        user_id: str,
        similarity: float,
        liveness_score: float,
    ) -> None:
        """Queue an attendance record for later sync (local autonomy: never blocks)."""
        if self.sync_queue is None:
            return
        self.sync_queue.enqueue({
            "id": record_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "similarity": similarity,
            "liveness_score": liveness_score,
            "device_id": self.config.sync_device_id,
        })

    def sync_now(self):
        """Attempt one sync cycle. Returns a SyncResult or None when disabled."""
        if self.sync_manager is None:
            return None
        return self.sync_manager.sync_once()

    def _detect(self, frame: np.ndarray) -> List[FaceDetection]:
        """Run the detector, falling back to centered dummy detection."""
        if self.detector is not None:
            try:
                return self.detector.detect(frame)
            except Exception as e:
                print(f"Detection error: {e}")
                return []
        return self._dummy_detection(frame)

    def enroll_from_frame(self, frame: np.ndarray, user_id: str, name: str) -> Optional[Dict]:
        """
        Enroll a user from a single frame (used by the web API / self-service UI).

        Returns an info dict, or None when no usable face is found.
        """
        detections = self.quality_gate.check_batch(frame, self._detect(frame))
        if not detections:
            return None

        det = max(detections, key=lambda d: d.bbox[2] * d.bbox[3])
        embedding = self.ensemble_extractor.extract(frame, det.landmarks)

        success = self.database.add_user(user_id, name, embedding)
        return {
            "success": success,
            "user_id": user_id,
            "name": name,
            "confidence": float(det.confidence),
            "embedding_dim": int(embedding.shape[0]),
        }

    def _dummy_detection(self, frame: np.ndarray) -> List[FaceDetection]:
        """Create a dummy detection for testing when no model is available."""
        h, w = frame.shape[:2]
        # Create a dummy face in the center
        face_w, face_h = w // 4, h // 4
        x1, y1 = w // 2 - face_w // 2, h // 2 - face_h // 2
        x2, y2 = x1 + face_w, y1 + face_h

        # Dummy landmarks (eyes, nose, mouth)
        landmarks = np.array([
            [x1 + face_w * 0.3, y1 + face_h * 0.3],  # left eye
            [x2 - face_w * 0.3, y1 + face_h * 0.3],  # right eye
            [x1 + face_w * 0.5, y1 + face_h * 0.5],  # nose
            [x1 + face_w * 0.3, y2 - face_h * 0.3],  # left mouth
            [x2 - face_w * 0.3, y2 - face_h * 0.3],  # right mouth
        ], dtype=np.float32)

        return [FaceDetection(
            bbox=(x1, y1, face_w, face_h),
            landmarks=landmarks,
            confidence=0.9,
            quality_score=1.0,
        )]

    def _check_liveness(self, landmarks: np.ndarray) -> LivenessResult:
        """
        Check liveness for a face.
        Note: This is simplified - in reality we'd need a sequence of landmarks.
        In demo mode liveness is bypassed so the pipeline works on single frames.
        """
        if self.config.demo_mode:
            return LivenessResult(
                is_live=True,
                score=1.0,
                blink_detected=False,
                head_movement_detected=False,
                reason="demo mode: liveness bypassed",
            )
        # In a real implementation, we would maintain a liveness detector per face track
        # For simplicity, we'll use a single detector and update it with the landmarks
        return self.liveness_detector.update(landmarks)

    def _get_user_templates(self) -> Dict[str, np.ndarray]:
        """
        Get user templates (decrypted embeddings) from the database for matching.

        Embeddings are stored Fernet-encrypted at rest and only decrypted in
        memory for comparison; the biohashed template remains the invertible-free
        primary record.
        """
        return self.database.get_user_templates()

    def run(self):
        """Run the main processing loop."""
        if not self.start():
            print("Failed to start camera")
            return

        print("Starting face recognition attendance system...")
        print("Press 'q' to quit")

        try:
            while True:
                frame = self.camera.capture()
                if frame is None:
                    print("Warning: Empty frame captured")
                    time.sleep(0.01)
                    continue

                # Process frame
                results = self.process_frame(frame)

                # Draw results on frame
                display_frame = frame.copy()
                for result in results:
                    det = result["detection"]
                    x, y, w, h = det.bbox
                    liveness = result["liveness"]
                    match = result["match"]

                    # Color based on liveness and match
                    if liveness.is_live:
                        if match and match.matched:
                            color = (0, 255, 0)  # Green for recognized live face
                            label = f"{match.name}: {match.similarity:.2f}"
                        else:
                            color = (0, 255, 255)  # Yellow for live but unknown
                            label = f"Unknown: {liveness.score:.2f}"
                    else:
                        color = (0, 0, 255)  # Red for spoof
                        label = "SPOOF"

                    # Draw bounding box
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(display_frame, label, (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                    # Draw landmarks
                    for point in det.landmarks:
                        cv2.circle(display_frame, tuple(point.astype(int)), 2, color, -1)

                # Show FPS
                fps = 1.0 / (time.time() - getattr(self, '_last_time', time.time()))
                self._last_time = time.time()
                cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                if self.config.display_output:
                    cv2.imshow(self.config.window_name, display_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    # Print results to console
                    if results:
                        print(f"Frame {self.frame_count}: {len(results)} face(s) detected")
                        for i, result in enumerate(results):
                            det = result["detection"]
                            liveness = result["liveness"]
                            match = result["match"]
                            print(f"  Face {i}: bbox={det.bbox}, conf={det.confidence:.2f}, "
                                  f"live={liveness.is_live}, score={liveness.score:.2f}")
                            if match:
                                print(f"    Matched: {match.name} (sim={match.similarity:.2f})")

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()

        print("System stopped.")


def create_default_config() -> PipelineConfig:
    """Create a default pipeline configuration."""
    return PipelineConfig()


def create_demo_config(**overrides) -> PipelineConfig:
    """
    Create a configuration for demo / local web testing.

    Runs without ONNX models (synthetic embeddings), processes every frame,
    and relaxes quality gates so webcam frames are accepted.
    """
    config = PipelineConfig(
        demo_mode=True,
        frame_skip=1,
        display_output=False,
        recognition_tta_enabled=False,
        liveness_min_frames=1,
        quality_min_face_size=40,
        quality_min_sharpness=0.0,
        quality_min_brightness=10,
        quality_max_brightness=250,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


if __name__ == "__main__":
    # Create and run pipeline
    config = create_default_config()
    pipeline = FacePipeline(config)
    pipeline.run()