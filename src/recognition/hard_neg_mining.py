"""
Hard-negative mining for face recognition.
Identifies and handles difficult-to-recognize face embeddings.
"""

import numpy as np
import heapq
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import random

@dataclass
class HardNegative:
    """Hard negative sample with metadata."""
    embedding: np.ndarray
    similarity: float
    user_id: str
    frame_id: int
    timestamp: float
    difficulty_score: float
    occurrence_count: int = 1

    def update_difficulty(self, new_similarity: float):
        """Update difficulty score based on new similarity."""
        self.difficulty_score = round(
            max(self.difficulty_score, abs(self.similarity - new_similarity)), 6
        )
        self.similarity = new_similarity
        self.occurrence_count += 1


class HardNegativeMiner:
    """
    Hard-negative mining system for face recognition.
    Tracks difficult-to-recognize faces and applies special handling.
    """

    def __init__(
        self,
        max_hard_negatives: int = 1000,
        difficulty_threshold: float = 0.4,
        min_occurrences: int = 3,
        mining_interval: int = 100,
        use_mlm: bool = True,
        mlm_rotation_range: float = 15.0,
        mlm_brightness_range: float = 0.2,
    ):
        self.max_hard_negatives = max_hard_negatives
        self.difficulty_threshold = difficulty_threshold
        self.min_occurrences = min_occurrences
        self.mining_interval = mining_interval
        self.use_mlm = use_mlm
        self.mlm_rotation_range = mlm_rotation_range
        self.mlm_brightness_range = mlm_brightness_range

        # Hard negative storage
        self.hard_negatives: Dict[str, HardNegative] = {}
        self.negative_heap: List[Tuple[float, str]] = []  # Min-heap by difficulty score

        # Tracking
        self.frame_count = 0
        self.false_negatives: List[Dict] = []
        self.true_positives: List[Dict] = []

        # ML for hard negative augmentation
        self.augmentation_cache = {}

    def process_match_result(
        self,
        embedding: np.ndarray,
        similarity: float,
        user_id: str,
        is_matched: bool,
        frame_id: int,
        timestamp: float,
        database: Dict[str, np.ndarray],
    ):
        """Process a match result to identify hard negatives."""
        self.frame_count += 1

        if is_matched:
            # True positive - record for learning
            self.true_positives.append({
                'user_id': user_id,
                'similarity': similarity,
                'frame_id': frame_id,
            })
        else:
            # False negative or unknown - check against database
            if database:
                # Find best match
                best_user = None
                best_similarity = -1.0

                for db_user_id, db_emb in database.items():
                    db_similarity = float(np.dot(embedding, db_emb))
                    if db_similarity > best_similarity:
                        best_similarity = db_similarity
                        best_user = db_user_id

                if best_user and best_similarity >= self.difficulty_threshold:
                    # This is a hard negative - store it
                    self._store_hard_negative(
                        embedding, best_similarity, best_user,
                        frame_id, timestamp
                    )
                elif best_user:
                    # False negative (similar enough but not matched due to threshold)
                    self._process_false_negative(
                        embedding, best_similarity, best_user,
                        frame_id, timestamp
                    )
            else:
                # No database - store as potential hard negative
                self._store_hard_negative(
                    embedding, similarity, user_id,
                    frame_id, timestamp
                )

        # Periodically re-index hard negatives
        if self.frame_count % self.mining_interval == 0:
            self._reindex_hard_negatives()

    def _store_hard_negative(
        self,
        embedding: np.ndarray,
        similarity: float,
        user_id: str,
        frame_id: int,
        timestamp: float,
    ):
        """Store a hard negative sample."""
        key = f"{user_id}_{frame_id}"

        if key in self.hard_negatives:
            # Update existing
            self.hard_negatives[key].update_difficulty(similarity)
            # Move in heap
            self._update_heap(key)
        else:
            # Create new hard negative
            difficulty = max(0.0, 0.5 - similarity)
            hn = HardNegative(
                embedding=embedding,
                similarity=similarity,
                user_id=user_id,
                frame_id=frame_id,
                timestamp=timestamp,
                difficulty_score=difficulty,
            )
            self.hard_negatives[key] = hn

            # Add to heap
            heapq.heappush(self.negative_heap, (difficulty, key))

        # Clean up old hard negatives if over limit
        self._cleanup_hard_negatives()

    def _process_false_negative(
        self,
        embedding: np.ndarray,
        similarity: float,
        user_id: str,
        frame_id: int,
        timestamp: float,
    ):
        """Process a false negative (similar but not matched)."""
        # Store as hard negative if similarity is borderline
        if self.difficulty_threshold <= similarity < 0.8:
            self._store_hard_negative(embedding, similarity, user_id, frame_id, timestamp)

    def _update_heap(self, key: str):
        """Update heap position for existing hard negative."""
        # Note: Heap doesn't support efficient updates, so we rebuild when needed
        pass

    def _reindex_hard_negatives(self):
        """Rebuild heap and remove outdated entries."""
        # Rebuild heap from current hard negatives
        new_heap = []
        for key, hn in self.hard_negatives.items():
            heapq.heappush(new_heap, (hn.difficulty_score, key))
        self.negative_heap = new_heap

    def _cleanup_hard_negatives(self):
        """Evict lowest-difficulty hard negatives when over capacity."""
        if len(self.hard_negatives) <= self.max_hard_negatives:
            return

        self._reindex_hard_negatives()
        while len(self.hard_negatives) > self.max_hard_negatives and self.negative_heap:
            _, key = heapq.heappop(self.negative_heap)
            self.hard_negatives.pop(key, None)

    def get_hard_negative_for_training(
        self,
        target_user_id: str,
        current_embedding: Optional[np.ndarray] = None,
    ) -> Optional[np.ndarray]:
        """Get a hard negative sample for training with augmentation."""
        if not self.hard_negatives:
            return None

        # Get hard negative with highest difficulty
        if self.negative_heap:
            difficulty, key = self.negative_heap[0]

            # Check if we can use this sample
            hn = self.hard_negatives[key]

            # Avoid using the same sample too recently
            if self.frame_count - hn.frame_id < 10:
                heapq.heappop(self.negative_heap)
                return self.get_hard_negative_for_training(target_user_id, current_embedding)

            if hn.user_id != target_user_id or current_embedding is not None:
                # Get sample and apply ML augmentation if enabled
                sample = hn.embedding.copy()

                if self.use_mlm and current_embedding is not None:
                    # Apply mixup-like augmentation
                    sample = self._apply_mlm_augmentation(sample, current_embedding)

                # Remove from heap and hard negatives
                heapq.heappop(self.negative_heap)
                del self.hard_negatives[key]

                return sample

        return None

    def _apply_mlm_augmentation(
        self,
        embedding: np.ndarray,
        reference_embedding: np.ndarray,
    ) -> np.ndarray:
        """Apply MixUp-style augmentation for hard negatives."""
        # Generate random lambda for mixup
        lambda_ = random.uniform(0.3, 0.7)

        # Mix two embeddings
        mixed = lambda_ * embedding + (1 - lambda_) * reference_embedding

        # Normalize
        mixed = mixed / (np.linalg.norm(mixed) + 1e-5)

        return mixed

    def get_hard_negative_count(self) -> int:
        """Get total number of hard negatives stored."""
        return len(self.hard_negatives)

    def get_top_difficulties(self, limit: int = 10) -> List[Tuple[str, float, int]]:
        """Get top hard negatives by difficulty score."""
        # Create list from heap and sort
        items = []
        for difficulty, key in self.negative_heap:
            hn = self.hard_negatives[key]
            items.append((hn.user_id, difficulty, hn.occurrence_count))

        # Sort by difficulty and return top N
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:limit]

    def reset(self):
        """Reset the hard negative miner."""
        self.hard_negatives.clear()
        self.negative_heap.clear()
        self.frame_count = 0
        self.false_negatives.clear()
        self.true_positives.clear()
        self.augmentation_cache.clear()

    def export_for_training(self) -> Dict:
        """Export hard negatives for external training."""
        return {
            'hard_negatives': {
                key: {
                    'embedding': hn.embedding.tolist(),
                    'similarity': hn.similarity,
                    'user_id': hn.user_id,
                    'difficulty_score': hn.difficulty_score,
                    'occurrence_count': hn.occurrence_count,
                }
                for key, hn in self.hard_negatives.items()
            },
            'statistics': {
                'total_hard_negatives': len(self.hard_negatives),
                'frame_count': self.frame_count,
                'false_negatives': len(self.false_negatives),
                'true_positives': len(self.true_positives),
            }
        }

    def import_from_training(self, data: Dict):
        """Import hard negatives from external training data."""
        self.reset()

        for key, hn_data in data.get('hard_negatives', {}).items():
            hn = HardNegative(
                embedding=np.array(hn_data['embedding']),
                similarity=hn_data['similarity'],
                user_id=hn_data['user_id'],
                frame_id=int(key.split('_')[1]),
                timestamp=0.0,  # Original training timestamp
                difficulty_score=hn_data['difficulty_score'],
                occurrence_count=hn_data['occurrence_count'],
            )
            self.hard_negatives[key] = hn
            heapq.heappush(self.negative_heap, (hn.difficulty_score, key))