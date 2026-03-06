"""Unit tests for Qdrant vector store service."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.core.vector_store import (
    ensure_collection,
    upsert_embeddings,
    search_vectors,
    delete_document_vectors,
    EmbeddingDimensionMismatchError,
)


class TestEnsureCollection:
    @patch("app.core.vector_store.get_qdrant_client")
    def test_creates_collection_if_missing(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_client_fn.return_value = mock_client

        ensure_collection()

        mock_client.create_collection.assert_called_once()

    @patch("app.core.vector_store.get_qdrant_client")
    def test_skips_if_exists(self, mock_client_fn):
        existing = MagicMock()
        existing.name = "rag_chunks"
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[existing])
        mock_client_fn.return_value = mock_client

        ensure_collection()

        mock_client.create_collection.assert_not_called()


class TestUpsertEmbeddings:
    @patch("app.core.vector_store.get_qdrant_client")
    def test_upserts_and_returns_ids(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        embeddings = [[0.1] * 768, [0.2] * 768]
        payloads = [{"content": "a"}, {"content": "b"}]

        ids = upsert_embeddings(embeddings, payloads)

        assert len(ids) == 2
        assert all(isinstance(i, str) for i in ids)
        mock_client.upsert.assert_called_once()

    @patch("app.core.vector_store.get_qdrant_client")
    def test_batches_large_sets(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        # 250 embeddings should be batched in 3 upsert calls (100+100+50)
        embeddings = [[0.1] * 768 for _ in range(250)]
        payloads = [{"content": f"doc_{i}"} for i in range(250)]

        ids = upsert_embeddings(embeddings, payloads)

        assert len(ids) == 250
        assert mock_client.upsert.call_count == 3

    def test_dimension_mismatch_raises(self):
        """Upsert with wrong vector dimension should raise."""
        embeddings = [[0.1, 0.2, 0.3]]  # 3 != 768
        payloads = [{"content": "a"}]

        with pytest.raises(EmbeddingDimensionMismatchError, match="dimension 3.*expected 768"):
            upsert_embeddings(embeddings, payloads)


class TestSearchVectors:
    @patch("app.core.vector_store.get_qdrant_client")
    def test_returns_formatted_hits(self, mock_client_fn):
        mock_result = MagicMock()
        mock_result.id = "point-1"
        mock_result.score = 0.95
        mock_result.payload = {
            "content": "chunk text",
            "source": "doc.pdf",
            "chunk_index": 0,
            "page_number": 1,
        }

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_result]
        mock_client_fn.return_value = mock_client

        hits = search_vectors([0.1] * 768, top_k=5)

        assert len(hits) == 1
        assert hits[0]["id"] == "point-1"
        assert hits[0]["score"] == 0.95
        assert hits[0]["content"] == "chunk text"
        assert hits[0]["source"] == "doc.pdf"

    @patch("app.core.vector_store.get_qdrant_client")
    def test_empty_results(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_client_fn.return_value = mock_client

        hits = search_vectors([0.1] * 768, top_k=5)

        assert hits == []

    @patch("app.core.vector_store.get_qdrant_client")
    def test_source_filter_applied(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_client_fn.return_value = mock_client

        search_vectors([0.1] * 768, top_k=5, source_filter="notes.pdf")

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs.get("query_filter") is not None

    def test_search_dimension_mismatch_raises(self):
        """Search with wrong query vector dimension should raise."""
        with pytest.raises(EmbeddingDimensionMismatchError, match="dimension 3.*expected 768"):
            search_vectors([0.1, 0.2, 0.3], top_k=5)


class TestDeleteDocumentVectors:
    @patch("app.core.vector_store.get_qdrant_client")
    def test_deletes_matching_vectors(self, mock_client_fn):
        record = MagicMock()
        record.id = "point-1"

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record], None)
        mock_client_fn.return_value = mock_client

        count = delete_document_vectors("doc.pdf")

        assert count == 1
        mock_client.delete.assert_called_once()

    @patch("app.core.vector_store.get_qdrant_client")
    def test_no_matching_vectors(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([], None)
        mock_client_fn.return_value = mock_client

        count = delete_document_vectors("nonexistent.pdf")

        assert count == 0
        mock_client.delete.assert_not_called()
