"""
Face detection module using InsightFace SCRFD model.
CPU-only inference via ONNX Runtime.
"""

import cv2
import numpy as np
import onnxruntime as ort
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FaceDetection:
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    landmarks: np.ndarray  # 5 points: left_eye, right_eye, nose, left_mouth, right_mouth
    confidence: float
    quality_score: float = 0.0


class SCRFDDetector:
    def __init__(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (640, 640),
        conf_threshold: float = 0.5,
        nms_threshold: float = 0.4,
        max_faces: int = 10,
    ):
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.max_faces = max_faces

        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)

        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        h, w = image.shape[:2]
        scale = min(self.input_size[0] / w, self.input_size[1] / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(image, (new_w, new_h))
        padded = np.full((self.input_size[1], self.input_size[0], 3), 114, dtype=np.uint8)
        padded[:new_h, :new_w] = resized

        # Normalize: BGR -> RGB, HWC -> CHW, [0,255] -> [0,1]
        input_tensor = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        input_tensor = np.expand_dims(input_tensor, axis=0)

        return input_tensor, scale

    def _postprocess(
        self,
        outputs: List[np.ndarray],
        scale: float,
        orig_shape: Tuple[int, int],
    ) -> List[FaceDetection]:
        # SCRFD outputs: [bboxes, landmarks, scores]
        # Simplified post-processing - adjust based on actual model outputs
        bboxes = outputs[0][0]  # [N, 5] - x1, y1, x2, y2, score
        landmarks = outputs[1][0] if len(outputs) > 1 else None  # [N, 10] - 5 points

        h, w = orig_shape
        detections = []

        for i in range(min(len(bboxes), self.max_faces)):
            score = bboxes[i, 4]
            if score < self.conf_threshold:
                continue

            x1, y1, x2, y2 = bboxes[i, :4] / scale
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            if landmarks is not None:
                lm = landmarks[i].reshape(5, 2) / scale
                lm[:, 0] = np.clip(lm[:, 0], 0, w)
                lm[:, 1] = np.clip(lm[:, 1], 0, h)
            else:
                # Fallback: estimate landmarks from bbox
                lm = self._estimate_landmarks(x1, y1, x2, y2)

            detections.append(FaceDetection(
                bbox=(x1, y1, x2 - x1, y2 - y1),
                landmarks=lm.astype(np.float32),
                confidence=float(score),
            ))

        # NMS
        detections = self._nms(detections)

        return detections

    def _estimate_landmarks(self, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w // 2, y1 + h // 2
        return np.array([
            [cx - w * 0.15, cy - h * 0.1],  # left eye
            [cx + w * 0.15, cy - h * 0.1],  # right eye
            [cx, cy + h * 0.05],            # nose
            [cx - w * 0.1, cy + h * 0.2],   # left mouth
            [cx + w * 0.1, cy + h * 0.2],   # right mouth
        ], dtype=np.float32)

    def _nms(self, detections: List[FaceDetection]) -> List[FaceDetection]:
        if not detections:
            return []

        boxes = np.array([d.bbox for d in detections])
        scores = np.array([d.confidence for d in detections])

        x = boxes[:, 0]
        y = boxes[:, 1]
        w = boxes[:, 2]
        h = boxes[:, 3]

        areas = w * h
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x[i], x[order[1:]])
            yy1 = np.maximum(y[i], y[order[1:]])
            xx2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]])
            yy2 = np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])

            w_int = np.maximum(0, xx2 - xx1)
            h_int = np.maximum(0, yy2 - yy1)
            inter = w_int * h_int

            iou = inter / (areas[i] + areas[order[1:]] - inter)
            order = order[1:][iou <= self.nms_threshold]

        return [detections[i] for i in keep]

    def detect(self, image: np.ndarray) -> List[FaceDetection]:
        input_tensor, scale = self._preprocess(image)
        outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
        return self._postprocess(outputs, scale, image.shape[:2])


class QualityGate:
    def __init__(
        self,
        min_face_size: int = 80,
        min_sharpness: float = 100.0,
        min_brightness: int = 40,
        max_brightness: int = 200,
    ):
        self.min_face_size = min_face_size
        self.min_sharpness = min_sharpness
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

    def check(self, image: np.ndarray, detection: FaceDetection) -> Tuple[bool, str]:
        x, y, w, h = detection.bbox

        # Size check
        if w < self.min_face_size or h < self.min_face_size:
            return False, f"face too small: {w}x{h} < {self.min_face_size}"

        # Sharpness check (Laplacian variance)
        face_roi = image[y:y+h, x:x+w]
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness < self.min_sharpness:
            return False, f"blurry: sharpness={sharpness:.1f} < {self.min_sharpness}"

        # Brightness check
        brightness = gray.mean()
        if brightness < self.min_brightness:
            return False, f"too dark: brightness={brightness:.1f} < {self.min_brightness}"
        if brightness > self.max_brightness:
            return False, f"too bright: brightness={brightness:.1f} > {self.max_brightness}"

        return True, "ok"

    def check_batch(self, image: np.ndarray, detections: List[FaceDetection]) -> List[FaceDetection]:
        filtered = []
        for det in detections:
            ok, reason = self.check(image, det)
            if ok:
                det.quality_score = 1.0
                filtered.append(det)
        return filtered