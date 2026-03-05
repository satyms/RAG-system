"""Prometheus metrics — custom counters, histograms, and FastAPI instrumentation."""

from __future__ import annotations

import logging
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# ── Application info ─────────────────────────────────────────
APP_INFO = Info("rag_app", "RAG application metadata")

# ── Request metrics ──────────────────────────────────────────
REQUEST_COUNT = Counter(
    "rag_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# ── RAG pipeline metrics ────────────────────────────────────
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "Retrieval pipeline latency",
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
)
GENERATION_LATENCY = Histogram(
    "rag_generation_duration_seconds",
    "LLM generation latency",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)
QUERY_COUNT = Counter(
    "rag_queries_total",
    "Total RAG queries processed",
    ["status"],  # success / error / low_confidence
)
INGESTION_COUNT = Counter(
    "rag_ingestions_total",
    "Total documents ingested",
    ["status"],  # success / error
)
CHUNKS_INGESTED = Counter(
    "rag_chunks_ingested_total",
    "Total chunks created during ingestion",
)

# ── Token usage ──────────────────────────────────────────────
TOKEN_USAGE = Counter(
    "rag_token_usage_total",
    "LLM token usage",
    ["type"],  # prompt_tokens / completion_tokens / total_tokens
)

# ── Cache metrics ────────────────────────────────────────────
CACHE_HITS = Counter("rag_cache_hits_total", "Cache hits", ["cache_type"])
CACHE_MISSES = Counter("rag_cache_misses_total", "Cache misses", ["cache_type"])

# ── Retrieval quality ───────────────────────────────────────
CONFIDENCE_SCORE = Histogram(
    "rag_confidence_score",
    "Distribution of query confidence scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
FAITHFULNESS_SCORE = Histogram(
    "rag_faithfulness_score",
    "Distribution of faithfulness scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── System ───────────────────────────────────────────────────
ACTIVE_TASKS = Gauge("rag_active_background_tasks", "Number of active Celery tasks")
PROMPT_INJECTION_BLOCKED = Counter(
    "rag_prompt_injection_blocked_total",
    "Queries blocked by prompt injection defense",
)


def setup_metrics(app_name: str, app_version: str) -> None:
    """Set initial application info labels."""
    APP_INFO.info({"app_name": app_name, "version": app_version})
    logger.info("Prometheus metrics initialised")
