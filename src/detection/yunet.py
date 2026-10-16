"""
YuNet face detector (OpenCV FaceDetectorYN) — the model-free fallback.

Used when no SCRFD ONNX model is available so the pipeline (and the local web
UI) tracks real faces instead of a fixed dummy box. YuNet is a small, CPU-only
detector shipped with OpenCV; the model file is vendored under
``src/detection/data`` (Apache-2.0, OpenCV Zoo) and runs through OpenCV's DNN
module (no extra dependency).

It returns a bounding box plus 5 landmarks (left eye, right eye, nose,
left mouth, right mouth) matching the SCRFD/aligner convention.
"""

from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from .detector import FaceDetection

_DEFAULT_MODEL = Path(__file__).resolve().parent / "data" / "face_detection_yunet_2023mar.onnx"


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        score_threshold: float = 0.7,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ):
        self.model_path = str(model_path or _DEFAULT_MODEL)
        if not Path(self.model_path).is_file():
            raise RuntimeError(f"YuNet model not found: {self.model_path}")
        self.detector = cv2.FaceDetectorYN.create(
            self.model_path, "", (320, 320), score_threshold, nms_threshold, top_k
        )

    def detect(self, image: np.ndarray) -> List[FaceDetection]:
        h, w = image.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(image)
        if faces is None:
            return []

        detections = []
        for f in faces:
            x, y, bw, bh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
            x = max(0, x)
            y = max(0, y)
            bw = min(bw, w - x)
            bh = min(bh, h - y)
            if bw <= 1 or bh <= 1:
                continue
            # YuNet: (right eye, left eye, nose, right mouth, left mouth)
            # -> reorder to (left eye, right eye, nose, left mouth, right mouth)
            landmarks = np.array([
                [f[2], f[3]],    # left eye
                [f[0], f[1]],    # right eye
                [f[4], f[5]],    # nose
                [f[12], f[13]],  # left mouth
                [f[10], f[11]],  # right mouth
            ], dtype=np.float32)
            detections.append(FaceDetection(
                bbox=(int(x), int(y), int(bw), int(bh)),
                landmarks=landmarks,
                confidence=float(f[14]),
            ))
        return detections
