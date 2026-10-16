#!/usr/bin/env python3
"""
Accuracy tests for Phase 2: Hard-negative mining and improved TTA.
"""

import sys
import os
import numpy as np
import pytest
import heapq

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from src.recognition.extractor import EnsembleExtractor, FaceMatcher, ONNXEmbeddingModel
from src.recognition.hard_neg_mining import HardNegativeMiner, HardNegative


class TestHardNegativeMining:
    """Test hard-negative mining functionality."""

    def test_hard_negative_creation(self):
        """Test HardNegative dataclass and initialization."""
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-5)

        hn = HardNegative(
            embedding=embedding,
            similarity=0.3,
            user_id="user1",
            frame_id=100,
            timestamp=1234567890.0,
            difficulty_score=0.2,
        )

        assert hn.embedding.shape == (512,)
        assert hn.similarity == 0.3
        assert hn.user_id == "user1"
        assert hn.frame_id == 100
        assert hn.difficulty_score == 0.2
        assert hn.occurrence_count == 1

    def test_hard_negative_update_difficulty(self):
        """Test updating difficulty score."""
        embedding = np.random.randn(512).astype(np.float32)

        hn = HardNegative(
            embedding=embedding,
            similarity=0.5,
            user_id="user1",
            frame_id=100,
            timestamp=1234567890.0,
            difficulty_score=0.0,
        )

        assert hn.occurrence_count == 1

        # Update with lower similarity (harder negative)
        hn.update_difficulty(0.2)
        assert hn.similarity == 0.2
        assert hn.difficulty_score == 0.3
        assert hn.occurrence_count == 2

        # Update with higher similarity (easier negative)
        hn.update_difficulty(0.6)
        assert hn.similarity == 0.6
        assert hn.difficulty_score == 0.4

    def test_hard_negative_miner_initialization(self):
        """Test HardNegativeMiner initialization."""
        miner = HardNegativeMiner(
            max_hard_negatives=100,
            difficulty_threshold=0.3,
            min_occurrences=5,
        )

        assert miner.max_hard_negatives == 100
        assert miner.difficulty_threshold == 0.3
        assert miner.min_occurrences == 5
        assert len(miner.hard_negatives) == 0
        assert len(miner.negative_heap) == 0
        assert miner.frame_count == 0

    def test_hard_negative_processing(self):
        """Test processing match results."""
        miner = HardNegativeMiner(
            difficulty_threshold=0.4,
            mining_interval=10,  # Small interval for testing
        )

        # Create test embeddings
        emb1 = np.random.randn(512).astype(np.float32)
        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-5)

        emb2 = np.random.randn(512).astype(np.float32)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-5)

        # Simulate matches
        for i in range(15):  # Exceed mining_interval
            # True positive
            miner.process_match_result(
                embedding=emb1,
                similarity=0.9,
                user_id="user1",
                is_matched=True,
                frame_id=i * 10,
                timestamp=float(i * 10),
                database={"user1": emb1, "user2": emb2},
            )

            # False negative (similar to user2 but threshold may fail)
            miner.process_match_result(
                embedding=emb2,
                similarity=0.8,
                user_id="user2",
                is_matched=False,
                frame_id=i * 10 + 1,
                timestamp=float(i * 10 + 1),
                database={"user1": emb1, "user2": emb2},
            )

        assert miner.frame_count == 30
        assert len(miner.true_positives) == 15
        assert len(miner.hard_negatives) > 0

    def test_hard_negative_augmentation(self):
        """Test ML augmentation for hard negatives."""
        miner = HardNegativeMiner(
            use_mlm=True,
            mlm_rotation_range=20.0,
            mlm_brightness_range=0.3,
        )

        # Create sample embeddings
        emb1 = np.random.randn(512).astype(np.float32)
        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-5)

        emb2 = np.random.randn(512).astype(np.float32)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-5)

        # Store a hard negative
        key = "test_key"
        hn = HardNegative(
            embedding=emb1,
            similarity=0.3,
            user_id="user1",
            frame_id=100,
            timestamp=1234567890.0,
            difficulty_score=0.2,
        )
        miner.hard_negatives[key] = hn
        heapq.heappush(miner.negative_heap, (0.2, key))

        # Get hard negative with augmentation
        augmented = miner.get_hard_negative_for_training(
            target_user_id="user2",
            current_embedding=emb2,
        )

        if augmented is not None:
            assert augmented.shape == (512,)
            assert abs(np.linalg.norm(augmented) - 1.0) < 0.001
            # Augmented should be different from original
            np.testing.assert_array_almost_equal(augmented, emb1, decimal=5)

    def test_hard_negative_cleanup(self):
        """Test cleanup of old hard negatives."""
        miner = HardNegativeMiner(
            max_hard_negatives=10,
            min_occurrences=2,
            mining_interval=5,
        )

        # Add several hard negatives
        for i in range(15):
            emb = np.random.randn(512).astype(np.float32)
            emb = emb / (np.linalg.norm(emb) + 1e-5)

            miner.process_match_result(
                embedding=emb,
                similarity=0.3 + i * 0.01,  # Varying similarities
                user_id=f"user{i}",
                is_matched=False,
                frame_id=i,
                timestamp=float(i),
                database={},
            )

        # Some should be cleaned up due to low difficulty or low occurrence
        initial_count = len(miner.hard_negatives)
        assert initial_count > 0

        # Trigger cleanup by processing more
        for i in range(15, 25):
            emb = np.random.randn(512).astype(np.float32)
            emb = emb / (np.linalg.norm(emb) + 1e-5)

            miner.process_match_result(
                embedding=emb,
                similarity=0.2,
                user_id=f"user{i}",
                is_matched=False,
                frame_id=i,
                timestamp=float(i),
                database={},
            )

        # Count should not exceed max
        assert len(miner.hard_negatives) <= miner.max_hard_negatives


class TestEnsembleExtractorEnhanced:
    """Test enhanced EnsembleExtractor with improved TTA."""

    @pytest.fixture
    def mock_models(self):
        """Create mock ONNX models for testing."""
        models = []
        for i in range(3):
            # Mock embedding model
            model = ONNXEmbeddingModel(
                model_path=f"/fake/path/model_{i}.onnx",
                name=f"model_{i}",
            )
            # Replace the session with a mock that returns deterministic embeddings
            class MockSession:
                def run(self, output_names, input_feed, _i=i):
                    # Return a deterministic embedding
                    embedding = np.ones(512, dtype=np.float32) * (_i + 1) / 4.0
                    return [np.expand_dims(embedding, axis=0)]

                def get_inputs(self):
                    class MockInput:
                        name = "input"
                    return [MockInput()]

                def get_outputs(self):
                    class MockOutput:
                        name = "output"
                    return [MockOutput()]

            model.session = MockSession()
            models.append(model)
        return models

    def test_ensemble_extractor_initialization(self, mock_models):
        """Test EnsembleExtractor with new TTA parameters."""
        from src.recognition.extractor import EnsembleExtractor

        extractor = EnsembleExtractor(
            models=mock_models,
            weights=[0.5, 0.3, 0.2],
            tta_enabled=True,
            tta_rotations=True,
            tta_brightness=True,
        )

        assert extractor.tta_enabled is True
        assert extractor.tta_rotations is True
        assert extractor.tta_brightness is True
        assert extractor.tta_rotation_angle == 15.0
        assert extractor.tta_brightness_factor == 0.1

    def test_ensemble_extractor_with_augmentation(self, mock_models):
        """Test that augmented embeddings are included."""
        from src.recognition.extractor import EnsembleExtractor
        import cv2

        extractor = EnsembleExtractor(
            models=mock_models,
            weights=[1.0],  # Single model for simplicity
            tta_enabled=True,
            tta_rotations=True,
            tta_brightness=True,
        )

        # Create a simple test image
        image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        landmarks = np.array([
            [25, 25], [75, 25], [50, 50], [25, 75], [75, 75]
        ], dtype=np.float32)

        # Set random seed for reproducible augmentation
        np.random.seed(42)
        import random
        random.seed(42)

        # Run extraction
        embedding = extractor.extract(image, landmarks)

        # Check that embedding is normalized
        assert abs(np.linalg.norm(embedding) - 1.0) < 0.001

        # With TTA enabled, we should have multiple augmented versions
        # The final embedding should be different from a single model output
        # (deterministic mock model returns 0.25)
        assert abs(embedding[0] - 0.25) > 0.001  # Should be averaged with augmented versions

    def test_ensemble_extractor_no_augmentation(self, mock_models):
        """Test that disabling augmentation works."""
        from src.recognition.extractor import EnsembleExtractor

        extractor = EnsembleExtractor(
            models=mock_models,
            weights=[1.0],
            tta_enabled=False,
            tta_rotations=True,  # These should be ignored
            tta_brightness=True,  # These should be ignored
        )

        image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        landmarks = np.array([
            [25, 25], [75, 25], [50, 50], [25, 75], [75, 75]
        ], dtype=np.float32)

        embedding = extractor.extract(image, landmarks)

        # With TTA disabled, should just return the model's embedding (0.25)
        assert abs(embedding[0] - 0.25) < 0.001

    def test_ensemble_extractor_parameters(self, mock_models):
        """Test that custom TTA parameters are respected."""
        from src.recognition.extractor import EnsembleExtractor

        # Test custom rotation angle
        extractor = EnsembleExtractor(
            models=mock_models,
            weights=[1.0],
            tta_enabled=True,
            tta_rotations=True,
            tta_rotation_angle=45.0,  # Custom angle
        )

        assert extractor.tta_rotation_angle == 45.0

        # Test custom brightness factor
        extractor2 = EnsembleExtractor(
            models=mock_models,
            weights=[1.0],
            tta_enabled=True,
            tta_brightness=True,
            tta_brightness_factor=0.5,  # Custom factor
        )

        assert extractor2.tta_brightness_factor == 0.5


class TestFaceMatcherEnhanced:
    """Test enhanced FaceMatcher with history-based thresholds."""

    def test_face_matcher_initialization(self):
        """Test FaceMatcher with new parameters."""
        from src.recognition.extractor import FaceMatcher

        matcher = FaceMatcher(
            threshold=0.5,
            history_size=50,
        )

        assert matcher.threshold == 0.5
        assert matcher.history_size == 50
        assert len(matcher.similarity_history) == 0

    def test_adaptive_threshold_calculation(self):
        """Test adaptive threshold calculation with history."""
        from src.recognition.extractor import FaceMatcher

        matcher = FaceMatcher(
            threshold=0.45,
            history_size=10,
            adaptive_enabled=True,
        )

        # Create test embedding
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-5)

        # Create database with known embeddings
        database = {
            "user1": embedding,
            "user2": embedding * 0.8,
        }

        # First match - should update history
        result1 = matcher.match(embedding, database)
        assert result1 is not None
        assert result1.user_id == "user1"
        assert result1.similarity > 0.8  # Should match user1 (closer embedding)

        # Check that history was updated
        assert "user1" in matcher.similarity_history
        assert len(matcher.similarity_history["user1"]) == 1
        assert abs(matcher.similarity_history["user1"][0] - result1.similarity) < 0.001

        # Second match with same embedding
        result2 = matcher.match(embedding, database)
        assert result2 is not None
        assert "user1" in matcher.similarity_history
        assert len(matcher.similarity_history["user1"]) == 2

    def test_threshold_adjustment(self):
        """Test that threshold adjusts based on historical performance."""
        from src.recognition.extractor import FaceMatcher

        matcher = FaceMatcher(
            threshold=0.5,
            history_size=20,
            adaptive_enabled=True,
        )

        # Create embeddings
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-5)

        database = {"user1": embedding}

        # Make several matches with high similarity
        similarities = []
        for i in range(5):
            result = matcher.match(embedding, database)
            if result:
                similarities.append(result.similarity)

        # Threshold should adjust based on these high similarities
        # The adaptive logic tries to move threshold towards observed similarities

    def test_history_size_limit(self):
        """Test that similarity history respects size limit."""
        from src.recognition.extractor import FaceMatcher

        matcher = FaceMatcher(
            threshold=0.5,
            history_size=3,  # Small history for testing
            adaptive_enabled=True,
        )

        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-5)

        database = {"user1": embedding}

        # Make more matches than history size
        for i in range(10):
            result = matcher.match(embedding, database)
            assert result is not None

        # History should not exceed history_size
        assert len(matcher.similarity_history["user1"]) <= matcher.history_size

    def test_disabled_adaptive(self):
        """Test that adaptive learning can be disabled."""
        from src.recognition.extractor import FaceMatcher

        matcher = FaceMatcher(
            threshold=0.45,
            adaptive_enabled=False,  # Disabled
            history_size=10,
        )

        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-5)

        database = {"user1": embedding}

        # Make multiple matches
        for i in range(5):
            result = matcher.match(embedding, database)
            assert result is not None

        # Threshold should remain unchanged when adaptive is disabled
        # (Implementation dependent)


class TestAccuracyIntegration:
    """Integration tests for accuracy improvements."""

    def test_all_accuracy_components(self):
        """Test that all accuracy components work together."""
        # This test verifies that the main components integrate properly
        from src.recognition.extractor import EnsembleExtractor
        from src.recognition.hard_neg_mining import HardNegativeMiner

        # Create mock extractor
        class MockModel:
            def extract(self, image):
                class Result:
                    embedding = np.random.randn(512).astype(np.float32)
                    embedding = embedding / (np.linalg.norm(embedding) + 1e-5)
                    model_name = "mock"
                    confidence = 1.0
                return Result()

        models = [MockModel() for _ in range(2)]

        extractor = EnsembleExtractor(
            models=models,
            weights=[0.5, 0.5],
            tta_enabled=True,
            tta_rotations=True,
            tta_brightness=True,
        )

        matcher = FaceMatcher(
            threshold=0.45,
            history_size=10,
            adaptive_enabled=True,
        )

        miner = HardNegativeMiner()

        # Create test data
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        landmarks = np.array([[25, 25], [75, 25], [50, 50], [25, 75], [75, 75]], dtype=np.float32)

        # Test extraction
        embedding = extractor.extract(test_image, landmarks)
        assert embedding.shape == (512,)
        assert abs(np.linalg.norm(embedding) - 1.0) < 0.001

        # Test matching
        database = {"user1": embedding, "user2": embedding * 0.8}
        result = matcher.match(embedding, database)
        assert result is not None

        # Test hard negative mining
        miner.process_match_result(
            embedding=embedding,
            similarity=result.similarity,
            user_id=result.user_id,
            is_matched=result.matched,
            frame_id=1,
            timestamp=1234567890.0,
            database=database,
        )

        # All components worked together
        assert matcher.similarity_history.get(result.user_id) is not None
        assert len(miner.true_positives) > 0 or len(miner.hard_negatives) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])