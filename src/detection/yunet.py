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

# Detection runs on an image scaled to fit this box (aspect ratio preserved,
# never upscaled). Bounds YuNet cost regardless of the webcam resolution.
_DEFAULT_WORKING_SIZE = (640, 480)


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        score_threshold: float = 0.7,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        working_size: Optional[tuple] = None,
    ):
        self.model_path = str(model_path or _DEFAULT_MODEL)
        if not Path(self.model_path).is_file():
            raise RuntimeError(f"YuNet model not found: {self.model_path}")
        self.working_size = tuple(working_size) if working_size else _DEFAULT_WORKING_SIZE
        self._last_input_size = None
        self.detector = cv2.FaceDetectorYN.create(
            self.model_path, "", (320, 320), score_threshold, nms_threshold, top_k
        )

    def detect(self, image: np.ndarray) -> List[FaceDetection]:
        h, w = image.shape[:2]

        # YuNet cost scales linearly with the input pixel count, so a 1080p
        # webcam frame costs ~6x a 640x480 one. Detection therefore runs on a
        # fixed smaller "working" image and the resulting boxes are scaled back
        # to the original coordinates.
        ww, wh = self.working_size
        scale = min(ww / w, wh / h, 1.0) if w and h else 1.0
        if scale < 1.0:
            dw, dh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
            small = cv2.resize(image, (dw, dh), interpolation=cv2.INTER_AREA)
        else:
            dw, dh, small = w, h, image

        if (dw, dh) != self._last_input_size:
            self.detector.setInputSize((dw, dh))
            self._last_input_size = (dw, dh)

        _, faces = self.detector.detect(small)
        if faces is None:
            return []

        inv = 1.0 / scale if scale else 1.0
        detections = []
        for f in faces:
            x, y, bw, bh = float(f[0]) * inv, float(f[1]) * inv, float(f[2]) * inv, float(f[3]) * inv
            x = max(0, x)
            y = max(0, y)
            bw = min(bw, w - x)
            bh = min(bh, h - y)
            if bw <= 1 or bh <= 1:
                continue
            # YuNet: (right eye, left eye, nose, right mouth, left mouth)
            # -> reorder to (left eye, right eye, nose, left mouth, right mouth)
            landmarks = np.array([
                [f[2] * inv, f[3] * inv],    # left eye
                [f[0] * inv, f[1] * inv],    # right eye
                [f[4] * inv, f[5] * inv],    # nose
                [f[12] * inv, f[13] * inv],  # left mouth
                [f[10] * inv, f[11] * inv],  # right mouth
            ], dtype=np.float32)
            detections.append(FaceDetection(
                bbox=(int(x), int(y), int(bw), int(bh)),
                landmarks=landmarks,
                confidence=float(f[14]),
            ))
        return detections
