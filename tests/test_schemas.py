"""Unit tests for Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    SourceChunk,
    IngestResponse,
    HealthResponse,
)


class TestQueryRequest:
    def test_valid_minimal(self):
        q = QueryRequest(question="Hello?")
        assert q.question == "Hello?"
        assert q.top_k == 5
        assert q.source_filter is None

    def test_valid_with_all_fields(self):
        q = QueryRequest(question="test", top_k=10, source_filter="doc.pdf")
        assert q.top_k == 10
        assert q.source_filter == "doc.pdf"

    def test_empty_question_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest(question="")

    def test_top_k_bounds(self):
        with pytest.raises(ValidationError):
            QueryRequest(question="test", top_k=0)
        with pytest.raises(ValidationError):
            QueryRequest(question="test", top_k=21)


class TestSourceChunk:
    def test_defaults(self):
        c = SourceChunk(content="text")
        assert c.source == ""
        assert c.score is None
        assert c.chunk_index is None
        assert c.page_number is None


class TestQueryResponse:
    def test_full_response(self):
        r = QueryResponse(
            answer="Hi",
            sources=[SourceChunk(content="c1")],
            confidence_score=0.91,
            latency_ms=123.4,
            token_usage={"total_tokens": 200},
        )
        assert r.answer == "Hi"
        assert r.confidence_score == 0.91
        assert r.token_usage["total_tokens"] == 200


class TestIngestResponse:
    def test_fields(self):
        r = IngestResponse(filename="doc.pdf", chunks=42, document_id="abc-123")
        assert r.filename == "doc.pdf"
        assert r.chunks == 42


class TestHealthResponse:
    def test_defaults(self):
        h = HealthResponse()
        assert h.status == "ok"
