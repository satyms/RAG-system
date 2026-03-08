"""Pydantic schemas for request / response validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Query ────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """Payload sent by the chat UI."""
    question: str = Field(..., min_length=1, max_length=5000, description="User question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class SourceChunk(BaseModel):
    """One retrieved chunk returned alongside the answer."""
    content: str
    source: str = ""
    score: float | None = None


class QueryResponse(BaseModel):
    """Payload returned to the chat UI."""
    answer: str
    sources: list[SourceChunk] = []


# ── Study Studio ───────────────────────────────────────────
ArtifactType = Literal["flashcards", "quiz", "mind_map"]


class StudyArtifactRequest(BaseModel):
    """Payload sent by the studio UI to generate a study artifact."""

    artifact_type: ArtifactType = Field(..., description="Requested artifact type")
    top_k: int = Field(default=12, ge=4, le=30, description="Number of chunks to use")


class StudyArtifactResponse(BaseModel):
    """Structured study artifact returned to the frontend studio."""

    artifact_type: ArtifactType
    title: str
    summary: str
    content: dict[str, Any]
    sources: list[SourceChunk] = []


# ── Ingestion ────────────────────────────────────────────────
class IngestResponse(BaseModel):
    """Result of a document ingestion request."""
    filename: str
    chunks: int
    message: str = "Ingested successfully"


# ── Health ───────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = ""
    version: str = ""
