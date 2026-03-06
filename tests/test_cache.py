"""Tests for Phase 3: Redis caching layer."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.core.cache import (
    _cache_key,
    get_cached_query,
    set_cached_query,
    get_cached_embedding,
    set_cached_embedding,
    invalidate_query_cache,
    invalidate_all_cache,
)


class TestCacheKey:
    """Tests for deterministic cache key generation."""

    def test_same_input_same_key(self):
        k1 = _cache_key("query", "hello world|5")
        k2 = _cache_key("query", "hello world|5")
        assert k1 == k2

    def test_different_input_different_key(self):
        k1 = _cache_key("query", "hello world|5")
        k2 = _cache_key("query", "goodbye world|5")
        assert k1 != k2

    def test_different_prefix_different_key(self):
        k1 = _cache_key("query", "hello")
        k2 = _cache_key("embed", "hello")
        assert k1 != k2

    def test_key_format(self):
        key = _cache_key("query", "test")
        assert key.startswith("rag:query:")
        assert len(key) > len("rag:query:")


class TestCacheOperationsWithoutRedis:
    """Test cache operations gracefully degrade when Redis is unavailable."""

    @patch("app.core.cache._get_redis", return_value=None)
    def test_get_cached_query_returns_none(self, mock_redis):
        result = get_cached_query("test question")
        assert result is None

    @patch("app.core.cache._get_redis", return_value=None)
    def test_set_cached_query_no_error(self, mock_redis):
        # Should not raise
        set_cached_query("test", 5, {"answer": "test"})

    @patch("app.core.cache._get_redis", return_value=None)
    def test_get_cached_embedding_returns_none(self, mock_redis):
        result = get_cached_embedding("test text")
        assert result is None

    @patch("app.core.cache._get_redis", return_value=None)
    def test_set_cached_embedding_no_error(self, mock_redis):
        set_cached_embedding("test", [0.1, 0.2, 0.3])

    @patch("app.core.cache._get_redis", return_value=None)
    def test_invalidate_query_cache_returns_zero(self, mock_redis):
        assert invalidate_query_cache() == 0

    @patch("app.core.cache._get_redis", return_value=None)
    def test_invalidate_all_cache_returns_zero(self, mock_redis):
        assert invalidate_all_cache() == 0


class TestCacheOperationsWithMockRedis:
    """Test cache operations with a mocked Redis client."""

    def _mock_redis(self):
        """Create a mock Redis client with in-memory dict storage."""
        store = {}
        mock = MagicMock()
        mock.get = lambda key: store.get(key)
        mock.setex = lambda key, ttl, value: store.__setitem__(key, value)
        mock.delete = lambda *keys: sum(1 for k in keys if store.pop(k, None) is not None)
        mock.scan_iter = lambda pattern: (k for k in store if k.startswith(pattern.replace("*", "")))
        mock.ping.return_value = True
        return mock

    @patch("app.core.cache._get_redis")
    def test_query_cache_round_trip(self, mock_get_redis):
        mock_client = self._mock_redis()
        mock_get_redis.return_value = mock_client

        # Miss
        result = get_cached_query("What is AI?", 5)
        assert result is None

        # Set
        set_cached_query("What is AI?", 5, {"answer": "Artificial Intelligence"})

        # Hit
        result = get_cached_query("What is AI?", 5)
        assert result is not None
        assert result["answer"] == "Artificial Intelligence"

    @patch("app.core.cache._get_redis")
    def test_embedding_cache_round_trip(self, mock_get_redis):
        mock_client = self._mock_redis()
        mock_get_redis.return_value = mock_client

        vec = [0.1, 0.2, 0.3]
        set_cached_embedding("test text", vec)
        result = get_cached_embedding("test text")
        assert result == vec
