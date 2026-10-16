"""Tests for the synthetic embedding model (phase 6 demo mode)."""

import cv2
import numpy as np

from src.recognition.synthetic import SyntheticEmbeddingModel


def _image(seed: int, size=(112, 112)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (*size, 3), dtype=np.uint8)


class TestSyntheticEmbeddingModel:
    def test_is_loaded(self):
        assert SyntheticEmbeddingModel().is_loaded is True

    def test_embedding_shape_and_unit_norm(self):
        model = SyntheticEmbeddingModel()
        emb = model.extract(_image(0)).embedding
        assert emb.shape == (512,)
        assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-5

    def test_deterministic_same_image(self):
        model = SyntheticEmbeddingModel()
        img = _image(1)
        a = model.extract(img).embedding
        b = model.extract(img).embedding
        assert float(np.dot(a, b)) > 0.999

    def test_similar_images_correlate_more_than_noise(self):
        model = SyntheticEmbeddingModel()
        base = _image(2)
        noisy = np.clip(base.astype(np.int16) + 5, 0, 255).astype(np.uint8)
        unrelated = _image(3)

        v_base = model.extract(base).embedding
        v_noisy = model.extract(noisy).embedding
        v_unrelated = model.extract(unrelated).embedding

        assert float(np.dot(v_base, v_noisy)) > float(np.dot(v_base, v_unrelated))

    def test_extract_batch(self):
        model = SyntheticEmbeddingModel()
        results = model.extract_batch([_image(4), _image(5)])
        assert len(results) == 2
        assert all(r.embedding.shape == (512,) for r in results)


class TestDegenerateInputs:
    def test_blank_image_still_produces_vector(self):
        model = SyntheticEmbeddingModel()
        emb = model.extract(np.zeros((112, 112, 3), dtype=np.uint8)).embedding
        assert emb.shape == (512,)
        assert np.isfinite(emb).all()

    def test_grayscale_input_supported(self):
        model = SyntheticEmbeddingModel()
        gray = cv2.cvtColor(_image(7), cv2.COLOR_BGR2GRAY)
        emb = model.extract(gray).embedding
        assert emb.shape == (512,)
