"""Tests for the model-free YuNet detector (phase 6 face tracking)."""

import numpy as np

from src.detection.yunet import YuNetFaceDetector


class TestYuNetFaceDetector:
    def test_loads_vendored_model(self):
        detector = YuNetFaceDetector()
        assert detector.detector is not None

    def test_blank_image_returns_list(self):
        detector = YuNetFaceDetector()
        detections = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        assert isinstance(detections, list)
        assert detections == []

    def test_detection_landmarks_shape(self):
        # Synthetic image with a face-like gradient; assert structure, not accuracy.
        img = np.tile(np.linspace(0, 255, 320, dtype=np.uint8), (240, 1))
        img = np.stack([img] * 3, axis=-1)
        for det in YuNetFaceDetector().detect(img):
            assert det.landmarks.shape == (5, 2)
            x, y, w, h = det.bbox
            assert w > 0 and h > 0
            assert 0.0 <= det.confidence <= 1.0

    def test_missing_model_raises(self, tmp_path):
        import pytest

        with pytest.raises(RuntimeError):
            YuNetFaceDetector(model_path=str(tmp_path / "nope.onnx"))
