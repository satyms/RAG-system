"""Integration tests — full API endpoints via HTTPX/TestClient.

These tests mock the heavy external dependencies (Qdrant, Postgres, LLM)
so they can run without Docker.
"""

from __future__ import annotations

import io
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.session import get_db


# ── Helpers ──────────────────────────────────────────────────

async def _mock_db():
    """Yield a mock async session."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.rollback = AsyncMock()
    yield mock_session


@pytest.fixture(autouse=True)
def override_db():
    """Replace the real DB dependency with a mock for all tests."""
    app.dependency_overrides[get_db] = _mock_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    """Async HTTPX client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/health returns 200 with status field."""
    with (
        patch("app.core.vector_store.get_qdrant_client") as mock_qdrant,
        patch("app.db.session.async_session") as mock_async_session,
    ):
        mock_qc = MagicMock()
        mock_qc.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant.return_value = mock_qc

        # Mock Postgres session context manager
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_async_session.return_value = mock_cm

        resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


# ── Query ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_endpoint(client):
    """POST /api/query returns structured answer."""
    with (
        patch("app.api.routes.query.retrieve_chunks") as mock_ret,
        patch("app.api.routes.query.generate_answer") as mock_gen,
    ):
        mock_ret.return_value = {
            "chunks": [
                {"id": "c1", "score": 0.92, "content": "Chunk content", "source": "doc.pdf",
                 "chunk_index": 0, "page_number": 1, "hybrid_score": 0.9,
                 "reranker_score": 0.88, "dense_score_norm": 0.92, "bm25_score": 0, "bm25_score_norm": 0},
            ],
            "metadata": {
                "dense_count": 1,
                "bm25_count": 0,
                "pre_rerank_count": 1,
                "post_rerank_count": 1,
                "dense_scores": [0.92],
                "bm25_scores": [],
                "reranker_scores": [0.88],
                "hybrid_scores": [0.9],
                "latency": {"dense_ms": 5.0, "bm25_ms": 0.0, "rerank_ms": 3.0, "total_retrieval_ms": 8.0},
            },
        }
        mock_gen.return_value = {
            "answer": "Test answer from Gemini.",
            "latency_ms": 120.5,
            "token_usage": {"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110},
        }

        resp = await client.post("/api/query", json={"question": "What is RAG?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Test answer from Gemini."
    assert data["latency_ms"] >= 0  # mocked calls may complete in <0.1ms
    assert len(data["sources"]) == 1


@pytest.mark.asyncio
async def test_query_empty_question(client):
    """POST /api/query with empty question returns 422."""
    resp = await client.post("/api/query", json={"question": ""})
    assert resp.status_code == 422


# ── Ingest ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_wrong_extension(client):
    """Uploading a .exe file should be rejected."""
    file_content = b"dummy binary"
    resp = await client.post(
        "/api/ingest",
        files={"file": ("malware.exe", io.BytesIO(file_content), "application/octet-stream")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ingest_empty_file(client):
    """Uploading an empty .txt file should be rejected."""
    resp = await client.post(
        "/api/ingest",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert resp.status_code == 400


# ── Root (static) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root_returns_html(client):
    """GET / should return the Ruixen AI UI."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
