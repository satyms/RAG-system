"""Pydantic schemas for request / response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Query ────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """Payload sent by the chat UI."""
    question: str = Field(..., min_length=1, max_length=5000, description="User question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of final chunks after reranking")
    source_filter: str | None = Field(default=None, description="Filter by source filename")
    hybrid_weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Override hybrid alpha (0=BM25, 1=dense)")


class SourceChunk(BaseModel):
    """One retrieved chunk returned alongside the answer."""
    content: str
    source: str = ""
    score: float | None = None
    chunk_index: int | None = None
    page_number: int | None = None
    reranker_score: float | None = None
    hybrid_score: float | None = None


class QueryResponse(BaseModel):
    """Payload returned to the chat UI."""
    answer: str
    sources: list[SourceChunk] = []
    confidence_score: float | None = None
    latency_ms: float | None = None
    token_usage: dict = {}
    retrieval_metadata: dict = {}
    faithfulness_score: float | None = None
    is_grounded: str | None = None
    low_confidence: bool = False


# ── Ingestion ────────────────────────────────────────────────
class IngestResponse(BaseModel):
    """Result of a document ingestion request."""
    filename: str
    chunks: int
    document_id: str = ""
    message: str = "Ingested successfully"


# ── Health ───────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = ""
    version: str = ""
    qdrant: str = ""
    database: str = ""
    redis: str = ""
    llm: str = ""
