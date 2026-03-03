"""Pydantic schemas for request / response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Query ────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """Payload sent by the chat UI."""
    question: str = Field(..., min_length=1, max_length=5000, description="User question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    source_filter: str | None = Field(default=None, description="Filter by source filename")


class SourceChunk(BaseModel):
    """One retrieved chunk returned alongside the answer."""
    content: str
    source: str = ""
    score: float | None = None
    chunk_index: int | None = None
    page_number: int | None = None


class QueryResponse(BaseModel):
    """Payload returned to the chat UI."""
    answer: str
    sources: list[SourceChunk] = []
    confidence_score: float | None = None
    latency_ms: float | None = None
    token_usage: dict = {}


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

