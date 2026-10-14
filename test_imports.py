#!/usr/bin/env python3
"""
Test script to verify imports work.
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test key imports."""
    try:
        from src.camera.capture import Camera, CameraConfig
        print("✓ src.camera.capture imported successfully")
    except ImportError as e:
        print(f"✗ src.camera.capture import failed: {e}")
        return False

    try:
        from src.detection.detector import SCRFDDetector, FaceDetection, QualityGate
        print("✓ src.detection.detector imported successfully")
    except ImportError as e:
        print(f"✗ src.detection.detector import failed: {e}")
        return False

    try:
        from src.recognition.extractor import (
            EnsembleExtractor, FaceAligner, FaceMatcher,
            ONNXEmbeddingModel,
        )
        print("✓ src.recognition.extractor imported successfully")
    except ImportError as e:
        print(f"✗ src.recognition.extractor import failed: {e}")
        return False

    try:
        from src.liveness.detector import LivenessDetector, LivenessResult
        print("✓ src.liveness.detector imported successfully")
    except ImportError as e:
        print(f"✗ src.liveness.detector import failed: {e}")
        return False

    try:
        from src.database.database import Database, BioHasher, User, AttendanceRecord
        print("✓ src.database.database imported successfully")
    except ImportError as e:
        print(f"✗ src.database.database import failed: {e}")
        return False

    try:
        from src.pipeline import create_default_config, FacePipeline
        print("✓ src.pipeline imported successfully")
    except ImportError as e:
        print(f"✗ src.pipeline import failed: {e}")
        return False

    print("\nAll imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)