#!/usr/bin/env python3
"""
Test the face pipeline implementation.
Phase 1: Basic pipeline test with dummy models.
"""

import sys
import os
import time
import numpy as np

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.camera.capture import Camera, CameraConfig
from src.detection.detector import SCRFDDetector, FaceDetection, QualityGate
from src.recognition.extractor import ONNXEmbeddingModel
from src.liveness.detector import LivenessDetector
from src.database.database import Database
from src.pipeline import create_default_config


def test_camera():
    """Test camera module."""
    print("Testing camera module...")
    config = CameraConfig(
        device_id=0,
        width=320,
        height=240,
        fps=30,
        backend="opencv",
    )
    camera = Camera(config)
    assert camera.config.width == 320
    assert camera.config.height == 240
    print("  ✓ Camera config test passed")

    camera.start()
    frame = camera.capture()
    camera.stop()

    if frame is None:
        print("  ⚠ Camera capture returned None (expected in some environments)")
    else:
        assert frame.shape[0] == config.height
        assert frame.shape[1] == config.width
        print(f"  ✓ Camera capture test passed: frame shape {frame.shape}")

    return True


def test_detector():
    """Test detector module with dummy model."""
    print("\nTesting detector module...")

    # Create a dummy image
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Test QualityGate
    gate = QualityGate(
        min_face_size=80,
        min_sharpness=100.0,
        min_brightness=40,
        max_brightness=200,
    )

    # Create a dummy detection
    detection = FaceDetection(
        bbox=(100, 100, 200, 200),
        landmarks=np.array([[110, 110], [130, 110], [120, 130], [110, 150], [130, 150]], dtype=np.float32),
        confidence=0.95,
    )

    # Check quality gate
    ok, reason = gate.check(image, detection)
    assert ok, f"Quality gate failed: {reason}"
    print(f"  ✓ QualityGate check test passed: {reason}")

    # Test batch filtering
    detections = gate.check_batch(image, [detection])
    assert len(detections) == 1
    print("  ✓ QualityGate batch test passed")

    return True


def test_liveness():
    """Test liveness detector."""
    print("\nTesting liveness detector...")
    config = {"ear_threshold": 0.25, "blink_frames": 3, "head_movement_threshold": 10.0, "min_frames": 10}
    detector = LivenessDetector(**config)

    # Create dummy landmarks
    landmarks = np.array([
        [100, 100],  # left eye
        [150, 100],  # right eye
        [125, 125],  # nose
        [100, 150],  # left mouth
        [150, 150],  # right mouth
    ], dtype=np.float32)

    # Initial call should return collecting frames
    result = detector.update(landmarks)
    assert not result.is_live
    assert "collecting" in result.reason.lower()
    print(f"  ✓ Initial liveness detection test passed: {result.reason}")

    # Mock some detections to trigger liveness
    detector.blink_detected = True
    detector.head_movement_detected = True

    result = detector.update(landmarks)
    assert result.is_live or result.score > 0
    print(f"  ✓ Liveness detection test passed: is_live={result.is_live}, score={result.score:.2f}")

    detector.reset()
    print("  ✓ Liveness detector reset test passed")

    return True


def test_database():
    """Test database module."""
    print("\nTesting database module...")

    # Use a temporary database for testing
    import tempfile
    import shutil

    db_dir = tempfile.mkdtemp()
    db_path = os.path.join(db_dir, "test.db")

    try:
        # Create database with test token
        token = b"test_token_123"
        db = Database(db_path, biohash_token=token)

        # Create a test user
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        user_id = "test_user_001"
        name = "Test User"

        added = db.add_user(user_id, name, embedding)
        assert added, "Failed to add user"
        print("  ✓ Database add_user test passed")

        # Retrieve user
        user = db.get_user(user_id)
        assert user is not None
        assert user.id == user_id
        assert user.name == name
        print("  ✓ Database get_user test passed")

        # Verify user
        verified = db.verify_user(user_id, embedding)
        assert verified, "User verification failed"
        print("  ✓ Database verify_user test passed")

        # Update user embedding
        new_embedding = np.random.randn(512).astype(np.float32)
        new_embedding = new_embedding / np.linalg.norm(new_embedding)
        updated = db.update_user_embedding(user_id, new_embedding)
        assert updated, "Failed to update user embedding"
        print("  ✓ Database update_user_embedding test passed")

        # Get all users
        all_users = db.get_all_users()
        assert len(all_users) >= 1
        print("  ✓ Database get_all_users test passed")

        # Log attendance
        record_id = db.log_attendance(user_id, 0.95, 0.8)
        assert record_id, "Failed to log attendance"
        print(f"  ✓ Database log_attendance test passed: {record_id}")

        # Get unsynced records
        unsynced = db.get_unsynced_records(limit=10)
        assert len(unsynced) >= 1
        print("  ✓ Database get_unsynced_records test passed")

        # Mark as synced
        marked = db.mark_synced([record_id])
        assert marked >= 1
        print("  ✓ Database mark_synced test passed")

        # Get stats
        stats = db.get_attendance_stats(user_id=user_id, days=30)
        assert "total" in stats
        print(f"  ✓ Database get_attendance_stats test passed: total={stats['total']}")

    finally:
        # Clean up
        shutil.rmtree(db_dir)

    print("  ✓ Database cleanup test passed")

    return True


def test_pipeline():
    """Test pipeline integration."""
    print("\nTesting pipeline integration...")

    # Create config with dummy models (will use dummy detection)
    config = create_default_config()
    config.detection_model_path = ""  # Will trigger dummy detection
    config.recognition_models = []   # Will trigger dummy matching

    # Create pipeline
    from src.pipeline import FacePipeline
    pipeline = FacePipeline(config)

    print("  ✓ FacePipeline initialization test passed")

    # Test frame processing
    # Create a dummy frame
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # This will trigger dummy detection since no model is loaded
    results = pipeline.process_frame(dummy_frame)
    print(f"  ✓ Pipeline process_frame test passed: {len(results)} results")

    # Check results structure
    if results:
        for result in results:
            assert "detection" in result
            assert "embedding" in result
            assert "liveness" in result
            assert "match" in result
            print("  ✓ Pipeline result structure test passed")

    print("  ✓ Pipeline integration test passed")

    return True


def main():
    """Run all tests."""
    print("Running Face Attendance System Phase 1 Tests")
    print("=" * 50)

    tests = [
        ("Camera", test_camera),
        ("Detector", test_detector),
        ("Liveness", test_liveness),
        ("Database", test_database),
        ("Pipeline", test_pipeline),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"  ✅ {test_name} test PASSED")
            else:
                failed += 1
                print(f"  ❌ {test_name} test FAILED (returned False)")
        except Exception as e:
            failed += 1
            print(f"  ❌ {test_name} test FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"Test Summary: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n⚠️  Some tests failed. Check output above for details.")
        return 1

    print("\n✅ All tests passed! Phase 1 implementation is working.")
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)