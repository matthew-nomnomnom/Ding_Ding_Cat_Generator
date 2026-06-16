"""Tests for cache_manager.py"""

import time
import pytest
from src.llm.cache_manager import CacheManager, RefinementResult


@pytest.fixture
def cache():
    return CacheManager(ttl_seconds=1, max_entries=10)


@pytest.fixture
def sample_result():
    return RefinementResult(
        prompt="dingdingcat holding a mooncake",
        negative_prompt="blurry, low quality",
        suggested_props=["mooncake"],
        suggested_background="full moon",
    )


class TestCacheManager:
    def test_get_miss(self, cache):
        assert cache.get("nonexistent") is None

    def test_set_and_get(self, cache, sample_result):
        cache.set("key1", sample_result)
        retrieved = cache.get("key1")
        assert retrieved is not None
        assert retrieved.prompt == sample_result.prompt
        assert retrieved.was_cached is True
        assert retrieved.latency_ms == 0

    def test_expiry(self, cache, sample_result):
        cache.set("key1", sample_result)
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_clear_expired(self, cache, sample_result):
        cache._ttl = 0.1
        cache.set("key1", sample_result)
        cache.set("key2", sample_result)
        time.sleep(0.2)

        cache._ttl = 9999
        cache.set("key3", sample_result)

        removed = cache.clear_expired()
        assert removed == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is not None

    def test_clear_all(self, cache, sample_result):
        cache.set("key1", sample_result)
        cache.set("key2", sample_result)
        cache.clear_all()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache) == 0

    def test_max_entries_eviction(self, sample_result):
        cache = CacheManager(max_entries=3)
        for i in range(5):
            cache.set(f"key{i}", sample_result)
        assert len(cache) <= 3

    def test_len(self, cache, sample_result):
        assert len(cache) == 0
        cache.set("a", sample_result)
        assert len(cache) == 1
        cache.set("b", sample_result)
        assert len(cache) == 2
