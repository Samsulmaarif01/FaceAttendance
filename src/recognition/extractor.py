"""
Face recognition module for embedding extraction and matching.
Supports ArcFace, CosFace, MobileFaceNet ensemble.
"""

import cv2
import numpy as np
import onnxruntime as ort
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class EmbeddingResult:
    embedding: np.ndarray  # 512-dim normalized
    model_name: str
    confidence: float


@dataclass
class MatchResult:
    user_id: str
    name: str
    similarity: float
    distance: float
    threshold: float
    matched: bool


class EmbeddingModel(ABC):
    @abstractmethod
    def extract(self, face_image: np.ndarray) -> EmbeddingResult:
        pass

    @abstractmethod
    def extract_batch(self, face_images: List[np.ndarray]) -> List[EmbeddingResult]:
        pass


class ONNXEmbeddingModel(EmbeddingModel):
    def __init__(
        self,
        model_path: str,
        name: str,
        input_size: Tuple[int, int] = (112, 112),
    ):
        self.name = name
        self.model_path = model_path
        self.input_size = input_size
        self.session = None
        self.input_name = None
        self.output_name = None
        self.load_error = None
        self._load_session()

    def _load_session(self):
        providers = ["CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
        except Exception as e:
            self.session = None
            self.load_error = e

    @property
    def is_loaded(self) -> bool:
        return self.session is not None

    def _ensure_io_names(self):
        if self.input_name is None:
            self.input_name = self.session.get_inputs()[0].name
        if self.output_name is None:
            self.output_name = self.session.get_outputs()[0].name

    def _preprocess(self, face_image: np.ndarray) -> np.ndarray:
        # Resize to 112x112
        resized = cv2.resize(face_image, self.input_size)
        # BGR -> RGB, HWC -> CHW, normalize to [-1, 1]
        input_tensor = resized[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
        input_tensor = (input_tensor - 127.5) / 127.5
        return np.expand_dims(input_tensor, axis=0)

    def _preprocess_batch(self, face_images: List[np.ndarray]) -> np.ndarray:
        tensors = [self._preprocess(img) for img in face_images]
        return np.concatenate(tensors, axis=0)

    def extract(self, face_image: np.ndarray) -> EmbeddingResult:
        self._ensure_io_names()
        input_tensor = self._preprocess(face_image)
        embedding = self.session.run([self.output_name], {self.input_name: input_tensor})[0][0]
        return EmbeddingResult(embedding=embedding, model_name=self.name, confidence=1.0)

    def extract_batch(self, face_images: List[np.ndarray]) -> List[EmbeddingResult]:
        if not face_images:
            return []
        self._ensure_io_names()
        input_tensor = self._preprocess_batch(face_images)
        embeddings = self.session.run([self.output_name], {self.input_name: input_tensor})[0]
        return [
            EmbeddingResult(embedding=emb, model_name=self.name, confidence=1.0)
            for emb in embeddings
        ]


class FaceAligner:
    def __init__(self, output_size: Tuple[int, int] = (112, 112)):
        self.output_size = output_size
        # Reference 5-point landmarks for 112x112 (ArcFace standard)
        self.ref_landmarks = np.array([
            [38.2946, 51.6963],   # left eye
            [73.5318, 51.5014],   # right eye
            [56.0252, 71.7366],   # nose
            [41.5493, 92.3655],   # left mouth
            [70.7299, 92.2041],   # right mouth
        ], dtype=np.float32)

    def align(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        # landmarks: 5 points [left_eye, right_eye, nose, left_mouth, right_mouth]
        tform = self._estimate_transform(landmarks)
        aligned = cv2.warpAffine(image, tform, self.output_size, borderValue=0.0)
        return aligned

    def _estimate_transform(self, src_landmarks: np.ndarray) -> np.ndarray:
        # Similarity transform (rotation + scale + translation)
        src = src_landmarks.astype(np.float32)
        dst = self.ref_landmarks.astype(np.float32)

        # Compute similarity transform
        # Using Umeyama algorithm
        src_mean = np.mean(src, axis=0)
        dst_mean = np.mean(dst, axis=0)
        src_centered = src - src_mean
        dst_centered = dst - dst_mean

        src_var = np.mean(np.sum(src_centered**2, axis=1))
        cov = dst_centered.T @ src_centered / 5

        U, _, Vt = np.linalg.svd(cov)
        R = U @ Vt
        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = U @ Vt

        scale = np.trace(R @ cov.T) / src_var
        t = dst_mean - scale * R @ src_mean

        M = np.eye(3)
        M[:2, :2] = scale * R
        M[:2, 2] = t
        return M[:2, :]


class EnsembleExtractor:
    def __init__(
        self,
        models: List[ONNXEmbeddingModel],
        weights: List[float],
        tta_enabled: bool = True,
        tta_rotations: bool = True,
        tta_brightness: bool = True,
        tta_rotation_angle: float = 15.0,
        tta_brightness_factor: float = 0.1,
    ):
        self.models = models
        self.weights = np.array(weights) / np.sum(weights)
        self.tta_enabled = tta_enabled
        self.tta_rotations = tta_rotations
        self.tta_brightness = tta_brightness
        self.tta_rotation_angle = tta_rotation_angle
        self.tta_brightness_factor = tta_brightness_factor
        self.aligner = FaceAligner()

    def extract(self, image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        # Align face
        aligned = self.aligner.align(image, landmarks)

        embeddings = []
        for model, weight in zip(self.models, self.weights):
            # Original
            emb1 = model.extract(aligned).embedding
            embeddings.append(emb1 * weight)

            # TTA: horizontal flip
            if self.tta_enabled:
                flipped = cv2.flip(aligned, 1)
                emb2 = model.extract(flipped).embedding
                embeddings.append(emb2 * weight)

            # TTA: rotation
            if self.tta_enabled and self.tta_rotations:
                angle = np.random.uniform(-self.tta_rotation_angle, self.tta_rotation_angle)
                center = (aligned.shape[1] // 2, aligned.shape[0] // 2)
                rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(aligned, rot_matrix, (aligned.shape[1], aligned.shape[0]),
                                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                emb_rot = model.extract(rotated).embedding
                embeddings.append(emb_rot * weight)

            # TTA: brightness variation
            if self.tta_enabled and self.tta_brightness:
                brightness_factor = np.random.uniform(1.0 - self.tta_brightness_factor,
                                                    1.0 + self.tta_brightness_factor)
                brightened = cv2.convertScaleAbs(aligned, alpha=brightness_factor, beta=0)
                emb_bright = model.extract(brightened).embedding
                embeddings.append(emb_bright * weight)

        # Average ensemble
        final_embedding = np.sum(embeddings, axis=0)
        if len(embeddings) > 1:
            final_embedding = final_embedding / (np.linalg.norm(final_embedding) + 1e-5)
        return final_embedding

    def extract_batch(
        self,
        images: List[np.ndarray],
        landmarks_list: List[np.ndarray],
    ) -> List[np.ndarray]:
        return [self.extract(img, lm) for img, lm in zip(images, landmarks_list)]


class FaceMatcher:
    def __init__(
        self,
        threshold: float = 0.45,
        adaptive_enabled: bool = True,
        min_threshold: float = 0.35,
        max_threshold: float = 0.55,
        update_rate: float = 0.05,
        history_size: int = 100,
        similarity_history: Optional[Dict[str, List[float]]] = None,
    ):
        self.threshold = threshold
        self.adaptive_enabled = adaptive_enabled
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.update_rate = update_rate
        self.history_size = history_size
        self.user_thresholds: Dict[str, float] = {}
        self.similarity_history: Dict[str, List[float]] = similarity_history or {}

    def match(
        self,
        embedding: np.ndarray,
        database: Dict[str, np.ndarray],  # user_id -> embedding
    ) -> Optional[MatchResult]:
        if not database:
            return None

        best_user = None
        best_similarity = -1.0

        for user_id, db_emb in database.items():
            similarity = float(np.dot(embedding, db_emb))
            if similarity > best_similarity:
                best_similarity = similarity
                best_user = user_id

        if best_user is None:
            return None

        # Get adaptive threshold with history-based calculation
        user_threshold = self._get_adaptive_threshold(best_user, best_similarity)

        distance = 1.0 - best_similarity
        matched = best_similarity >= user_threshold

        return MatchResult(
            user_id=best_user,
            name=best_user,  # Will be replaced with actual name
            similarity=best_similarity,
            distance=distance,
            threshold=user_threshold,
            matched=matched,
        )

    def _get_adaptive_threshold(self, user_id: str, current_similarity: float) -> float:
        # Start with base threshold
        base_threshold = self.threshold

        if not self.adaptive_enabled:
            return base_threshold

        # Get user-specific threshold
        user_threshold = self.user_thresholds.get(user_id, base_threshold)

        # Calculate statistics from history
        if user_id in self.similarity_history and len(self.similarity_history[user_id]) > 0:
            history = self.similarity_history[user_id]
            mean_similarity = np.mean(history)
            std_similarity = np.std(history)

            # Adjust threshold based on historical distribution
            if std_similarity > 0:
                z_score = (mean_similarity - current_similarity) / std_similarity
                threshold_adjust = max(0, min(0.1, -z_score * 0.02))
                user_threshold += threshold_adjust

        # Clip to valid range
        user_threshold = np.clip(user_threshold, self.min_threshold, self.max_threshold)

        # Update history
        if user_id not in self.similarity_history:
            self.similarity_history[user_id] = []
        self.similarity_history[user_id].append(current_similarity)

        # Maintain history size
        if len(self.similarity_history[user_id]) > self.history_size:
            self.similarity_history[user_id] = self.similarity_history[user_id][-self.history_size:]

        return user_threshold

    def update_threshold(self, user_id: str, similarity: float) -> None:
        # Legacy method - kept for compatibility
        if not self.adaptive_enabled:
            return
        current = self.user_thresholds.get(user_id, self.threshold)
        # Move threshold slightly towards the observed similarity
        new_threshold = current + self.update_rate * (similarity - current)
        new_threshold = np.clip(new_threshold, self.min_threshold, self.max_threshold)
        self.user_thresholds[user_id] = new_threshold

    def set_user_threshold(self, user_id: str, threshold: float) -> None:
        self.user_thresholds[user_id] = np.clip(threshold, self.min_threshold, self.max_threshold)