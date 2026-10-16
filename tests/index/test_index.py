"""Tests for the scalability module (phase 5)."""

import numpy as np
import pytest

from src.index import (
    BruteForceIndex,
    FAISSIndex,
    HierarchicalMatcher,
    IndexedMatcher,
    PCAReducer,
    ShardedVectorIndex,
    SiteRegistry,
    available_backends,
    create_index,
)


def _unit(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


@pytest.fixture
def gallery():
    rng = np.random.default_rng(0)
    vectors = rng.standard_normal((100, 64)).astype(np.float32)
    return _unit(vectors)


class TestBruteForceIndex:
    def test_search_matches_exact_cosine(self, gallery):
        index = BruteForceIndex()
        index.add_batch([f"u{i}" for i in range(100)], gallery)

        hits = index.search(gallery[7], k=3)
        assert hits[0].id == "u7"
        expected = float(np.dot(gallery[7], gallery[7]))
        assert hits[0].score == pytest.approx(expected, abs=1e-5)
        assert hits[0].score >= hits[1].score >= hits[2].score

    def test_scaled_query_is_normalized(self, gallery):
        index = BruteForceIndex()
        index.add_batch([f"u{i}" for i in range(100)], gallery)
        assert index.search(gallery[3] * 17.0, k=1)[0].id == "u3"

    def test_update_replaces_existing(self, gallery):
        index = BruteForceIndex()
        index.add("u1", gallery[1])
        index.add("u1", gallery[2])
        assert len(index) == 1
        assert index.search(gallery[2], k=1)[0].id == "u1"

    def test_remove_and_clear(self, gallery):
        index = BruteForceIndex()
        index.add_batch([f"u{i}" for i in range(5)], gallery[:5])
        assert index.remove("u3") is True
        assert index.remove("missing") is False
        assert len(index) == 4
        index.clear()
        assert len(index) == 0

    def test_empty_index_returns_no_hits(self, gallery):
        assert BruteForceIndex().search(gallery[0], k=5) == []

    def test_k_larger_than_gallery(self, gallery):
        index = BruteForceIndex()
        index.add_batch(["a", "b"], gallery[:2])
        assert len(index.search(gallery[0], k=10)) == 2


class TestPCAReducer:
    def test_transform_shape_and_variance(self, gallery):
        reducer = PCAReducer(n_components=8).fit(gallery)
        projected = reducer.transform(gallery)
        assert projected.shape == (100, 8)
        ratio = reducer.explained_variance_ratio()
        assert ratio.shape == (8,)
        assert 0.0 < ratio.sum() <= 1.0 + 1e-6

    def test_transform_before_fit_raises(self):
        with pytest.raises(RuntimeError):
            PCAReducer().transform(np.ones((2, 4), dtype=np.float32))

    def test_invalid_fit(self):
        with pytest.raises(ValueError):
            PCAReducer().fit(np.empty((0, 4), dtype=np.float32))
        with pytest.raises(ValueError):
            PCAReducer(n_components=0)


class TestHierarchicalMatcher:
    def test_exact_when_gallery_within_candidates(self, gallery):
        matcher = HierarchicalMatcher(coarse_dim=16, coarse_candidates=200)
        matcher.add_batch([f"u{i}" for i in range(20)], gallery[:20])
        assert matcher.search(gallery[5], k=1)[0].id == "u5"

    def test_coarse_then_fine_returns_true_nearest(self, gallery):
        matcher = HierarchicalMatcher(coarse_dim=24, coarse_candidates=25)
        matcher.add_batch([f"u{i}" for i in range(100)], gallery)

        brute = BruteForceIndex()
        brute.add_batch([f"u{i}" for i in range(100)], gallery)

        for query_index in (0, 42, 99):
            coarse_top = matcher.search(gallery[query_index], k=1)[0]
            brute_top = brute.search(gallery[query_index], k=1)[0]
            assert coarse_top.id == brute_top.id

    def test_remove(self, gallery):
        matcher = HierarchicalMatcher(coarse_dim=8, coarse_candidates=10)
        matcher.add_batch([f"u{i}" for i in range(10)], gallery[:10])
        assert matcher.remove("u0") is True
        assert matcher.remove("u0") is False
        assert len(matcher) == 9


class TestShardedVectorIndex:
    def test_routes_per_site(self, gallery):
        sharded = ShardedVectorIndex()
        sharded.add_batch("jakarta", [f"j{i}" for i in range(30)], gallery[:30])
        sharded.add_batch("bandung", [f"b{i}" for i in range(30)], gallery[30:60])

        assert set(sharded.sites()) == {"jakarta", "bandung"}
        assert len(sharded) == 60
        hit = sharded.search(gallery[35], k=1, sites=["bandung"])[0]
        assert hit.id == "b5"

    def test_searches_all_sites_by_default(self, gallery):
        sharded = ShardedVectorIndex()
        sharded.add_batch("a", ["a0"], gallery[:1])
        sharded.add_batch("b", ["b0"], gallery[1:2])
        top = sharded.search(gallery[1], k=1)[0]
        assert top.id == "b0"

    def test_remove_and_stats(self, gallery):
        sharded = ShardedVectorIndex()
        sharded.add_batch("a", ["a0", "a1"], gallery[:2])
        assert sharded.stats() == {"a": 2}
        assert sharded.remove("a", "a0") is True
        assert sharded.stats() == {"a": 1}

    def test_custom_factory(self, gallery):
        created = []

        def factory():
            index = BruteForceIndex()
            created.append(index)
            return index

        sharded = ShardedVectorIndex(index_factory=factory)
        sharded.add("x", "v", gallery[0])
        assert len(created) == 1


class TestSiteRegistry:
    def test_register_is_idempotent(self):
        registry = SiteRegistry()
        registry.register("s1", name="HQ", model_version="v1")
        registry.register("s1", model_version="v2")
        assert len(registry) == 1
        assert registry.get("s1").name == "HQ"
        assert registry.get("s1").model_version == "v2"

    def test_activate_deactivate_and_list(self):
        registry = SiteRegistry()
        registry.register("s1")
        registry.register("s2")
        assert registry.deactivate("s2") is True
        assert registry.deactivate("missing") is False
        assert [site.site_id for site in registry.list_sites(active_only=True)] == ["s1"]
        assert registry.activate("s2") is True

    def test_heartbeat_and_model_version(self):
        registry = SiteRegistry()
        registry.register("s1")
        assert registry.heartbeat("s1", timestamp="2026-10-16T00:00:00") is True
        assert registry.get("s1").last_seen == "2026-10-16T00:00:00"
        assert registry.update_model_version("s1", "v3") is True
        assert registry.update_model_version("missing", "v3") is False

    def test_aggregate(self):
        registry = SiteRegistry()
        registry.register("s1", model_version="v1")
        registry.register("s2", model_version="v1")
        registry.register("s3", model_version="v2")
        registry.deactivate("s3")
        aggregate = registry.aggregate()
        assert aggregate["total"] == 3
        assert aggregate["active"] == 2
        assert aggregate["inactive"] == 1
        assert aggregate["by_model_version"] == {"v1": 2, "v2": 1}


class TestIndexedMatcher:
    def _database(self, gallery):
        return {f"u{i}": gallery[i] for i in range(30)}

    def test_matches_exact_user(self, gallery):
        database = self._database(gallery)
        matcher = IndexedMatcher(threshold=0.45)
        result = matcher.match(gallery[9], database)
        assert result.user_id == "u9"
        assert result.similarity > 0.9
        assert result.matched is True

    def test_empty_database_returns_none(self):
        assert IndexedMatcher().match(np.ones(64, dtype=np.float32), {}) is None

    def test_rebuilds_when_database_changes(self, gallery):
        matcher = IndexedMatcher(threshold=0.45)
        database = self._database(gallery)
        matcher.match(gallery[0], database)

        database["new"] = gallery[50]
        result = matcher.match(gallery[50], database)
        assert result.user_id == "new"

    def test_agrees_with_face_matcher_best_user(self, gallery):
        from src.recognition.extractor import FaceMatcher

        database = self._database(gallery)
        indexed = IndexedMatcher(threshold=0.45).match(gallery[17], database)
        linear = FaceMatcher(threshold=0.45).match(gallery[17], database)
        assert indexed.user_id == linear.user_id


class TestBackends:
    def test_available_backends_always_has_brute_force(self):
        assert "brute_force" in available_backends()

    def test_create_index_brute_force(self):
        assert isinstance(create_index("brute_force"), BruteForceIndex)

    def test_create_index_faiss_requires_dim(self):
        if "faiss" not in available_backends():
            with pytest.raises(RuntimeError):
                create_index("faiss", dim=64)

    @pytest.mark.skipif(
        not FAISSIndex.is_available(), reason="faiss not installed"
    )
    def test_faiss_index_round_trip(self, gallery):  # pragma: no cover - optional
        index = FAISSIndex(dim=gallery.shape[1])
        index.add_batch([f"u{i}" for i in range(100)], gallery)
        assert index.search(gallery[7], k=1)[0].id == "u7"
