"""Redis caching layer — query, context, and embedding cache."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Optional, Any

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False


def _get_redis():
    """Lazy-load Redis connection."""
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client

    if not settings.CACHE_ENABLED:
        _redis_available = False
        return None

    try:
        import redis
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected at %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable (caching disabled): %s", exc)
        _redis_available = False
        _redis_client = None
        return None


def is_redis_available() -> bool:
    """Check if Redis is connected and responsive."""
    _get_redis()
    return _redis_available


def _cache_key(prefix: str, data: str) -> str:
    """Generate a deterministic cache key from prefix + data hash."""
    h = hashlib.sha256(data.encode()).hexdigest()[:16]
    return f"rag:{prefix}:{h}"


# ── Query result cache ───────────────────────────────────────

def get_cached_query(question: str, top_k: int = 5) -> Optional[dict]:
    """Look up a cached query response."""
    client = _get_redis()
    if not client:
        return None

    key = _cache_key("query", f"{question}|{top_k}")
    try:
        raw = client.get(key)
        if raw:
            from app.middleware.metrics import CACHE_HITS
            CACHE_HITS.labels(cache_type="query").inc()
            logger.debug("Cache HIT for query: %s", question[:60])
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Cache read error: %s", exc)

    from app.middleware.metrics import CACHE_MISSES
    CACHE_MISSES.labels(cache_type="query").inc()
    return None


def set_cached_query(question: str, top_k: int, response: dict, ttl: Optional[int] = None) -> None:
    """Cache a query response."""
    client = _get_redis()
    if not client:
        return

    key = _cache_key("query", f"{question}|{top_k}")
    try:
        client.setex(key, ttl or settings.CACHE_TTL_SECONDS, json.dumps(response, default=str))
        logger.debug("Cached query response: %s", question[:60])
    except Exception as exc:
        logger.debug("Cache write error: %s", exc)


# ── Embedding cache ──────────────────────────────────────────

def get_cached_embedding(text: str) -> Optional[list[float]]:
    """Look up a cached embedding vector."""
    client = _get_redis()
    if not client:
        return None

    key = _cache_key("embed", text)
    try:
        raw = client.get(key)
        if raw:
            from app.middleware.metrics import CACHE_HITS
            CACHE_HITS.labels(cache_type="embedding").inc()
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Embedding cache read error: %s", exc)

    from app.middleware.metrics import CACHE_MISSES
    CACHE_MISSES.labels(cache_type="embedding").inc()
    return None


def set_cached_embedding(text: str, vector: list[float], ttl: Optional[int] = None) -> None:
    """Cache an embedding vector."""
    client = _get_redis()
    if not client:
        return

    key = _cache_key("embed", text)
    try:
        client.setex(key, ttl or settings.CACHE_TTL_SECONDS * 4, json.dumps(vector))
    except Exception as exc:
        logger.debug("Embedding cache write error: %s", exc)


# ── LLM response cache ──────────────────────────────────────

def get_cached_llm_response(question: str, context_hash: str) -> Optional[dict]:
    """Look up a cached LLM response for a specific question + context pair."""
    client = _get_redis()
    if not client:
        return None

    key = _cache_key("llm", f"{question}|{context_hash}")
    try:
        raw = client.get(key)
        if raw:
            from app.middleware.metrics import CACHE_HITS
            CACHE_HITS.labels(cache_type="llm").inc()
            return json.loads(raw)
    except Exception as exc:
        logger.debug("LLM cache read error: %s", exc)

    from app.middleware.metrics import CACHE_MISSES
    CACHE_MISSES.labels(cache_type="llm").inc()
    return None


def set_cached_llm_response(question: str, context_hash: str, response: dict, ttl: Optional[int] = None) -> None:
    """Cache an LLM response."""
    client = _get_redis()
    if not client:
        return

    key = _cache_key("llm", f"{question}|{context_hash}")
    try:
        client.setex(key, ttl or settings.CACHE_TTL_SECONDS, json.dumps(response, default=str))
    except Exception as exc:
        logger.debug("LLM cache write error: %s", exc)


# ── Cache invalidation ───────────────────────────────────────

def invalidate_query_cache() -> int:
    """Invalidate all cached query results (e.g., after ingestion)."""
    client = _get_redis()
    if not client:
        return 0

    try:
        keys = list(client.scan_iter("rag:query:*"))
        if keys:
            client.delete(*keys)
        logger.info("Invalidated %d query cache entries", len(keys))
        return len(keys)
    except Exception as exc:
        logger.warning("Cache invalidation error: %s", exc)
        return 0


def invalidate_all_cache() -> int:
    """Invalidate all RAG cache entries."""
    client = _get_redis()
    if not client:
        return 0

    try:
        keys = list(client.scan_iter("rag:*"))
        if keys:
            client.delete(*keys)
        logger.info("Invalidated all %d cache entries", len(keys))
        return len(keys)
    except Exception as exc:
        logger.warning("Full cache invalidation error: %s", exc)
        return 0
