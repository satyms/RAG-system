"""Tests for Phase 3: Metrics module."""

from __future__ import annotations

import pytest

from app.middleware.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    QUERY_COUNT,
    INGESTION_COUNT,
    CACHE_HITS,
    CACHE_MISSES,
    TOKEN_USAGE,
    CONFIDENCE_SCORE,
    PROMPT_INJECTION_BLOCKED,
    setup_metrics,
)


class TestMetricsExist:
    """Verify all expected metrics are defined and usable."""

    def test_request_count_counter(self):
        REQUEST_COUNT.labels(method="GET", endpoint="/api/health", status_code="200").inc()
        # No error = pass

    def test_request_latency_histogram(self):
        REQUEST_LATENCY.labels(method="POST", endpoint="/api/query").observe(0.5)

    def test_query_count_counter(self):
        QUERY_COUNT.labels(status="success").inc()
        QUERY_COUNT.labels(status="error").inc()
        QUERY_COUNT.labels(status="cache_hit").inc()
        QUERY_COUNT.labels(status="blocked").inc()

    def test_ingestion_count_counter(self):
        INGESTION_COUNT.labels(status="success").inc()
        INGESTION_COUNT.labels(status="error").inc()

    def test_cache_metrics(self):
        CACHE_HITS.labels(cache_type="query").inc()
        CACHE_MISSES.labels(cache_type="query").inc()
        CACHE_HITS.labels(cache_type="embedding").inc()

    def test_token_usage_counter(self):
        TOKEN_USAGE.labels(type="prompt_tokens").inc(100)
        TOKEN_USAGE.labels(type="completion_tokens").inc(50)

    def test_confidence_histogram(self):
        CONFIDENCE_SCORE.observe(0.85)

    def test_prompt_injection_blocked(self):
        PROMPT_INJECTION_BLOCKED.inc()

    def test_setup_metrics_no_error(self):
        setup_metrics("TestApp", "1.0.0")
