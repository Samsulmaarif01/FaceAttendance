"""
Synthetic embedding model for offline demos and tests.

This is NOT a real face recognizer. It maps an image to a deterministic,
L2-normalised vector via a fixed random projection of low-resolution grayscale
pixels, so visually similar crops yield correlated vectors. It exists so the
full pipeline (detect -> align -> embed -> match -> log) can be exercised
without any ONNX models installed.
"""

from typing import List

import cv2
import numpy as np

from .extractor import EmbeddingModel, EmbeddingResult

_GRID = 24  # 24x24 grayscale -> 576 features


class SyntheticEmbeddingModel(EmbeddingModel):
    """Deterministic pseudo-embedding model (demo/testing only)."""

    def __init__(self, name: str = "synthetic", dim: int = 512, seed: int = 1337):
        self.name = name
        self.dim = dim
        self.seed = seed
        rng = np.random.default_rng(seed)
        self._projection = rng.standard_normal((dim, _GRID * _GRID)).astype(np.float32)

    @property
    def is_loaded(self) -> bool:
        return True

    def _features(self, face_image: np.ndarray) -> np.ndarray:
        if face_image is None or face_image.size == 0:
            return np.zeros(_GRID * _GRID, dtype=np.float32)
        gray = face_image
        if gray.ndim == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (_GRID, _GRID)).astype(np.float32)
        small = small - small.mean()
        std = small.std()
        if std > 1e-6:
            small = small / std
        return small.flatten()

    def _embed(self, face_image: np.ndarray) -> np.ndarray:
        vec = self._projection @ self._features(face_image)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec.astype(np.float32)

    def extract(self, face_image: np.ndarray) -> EmbeddingResult:
        return EmbeddingResult(
            embedding=self._embed(face_image),
            model_name=self.name,
            confidence=1.0,
        )

    def extract_batch(self, face_images: List[np.ndarray]) -> List[EmbeddingResult]:
        return [self.extract(img) for img in face_images]
