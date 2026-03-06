"""Unit tests for the retrieval module (app.core.retrieval).

Updated for Phase 2 hybrid retrieval — retrieve_chunks now returns
a dict with 'chunks' and 'metadata' keys.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.retrieval import retrieve_chunks


class TestRetrieveChunks:
    """Test retrieval with mocked dense + BM25 + reranker pipeline."""

    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.get_bm25_ready", return_value=False)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_returns_results(self, mock_embed, mock_search, mock_bm25_ready, mock_rerank):
        mock_embed.return_value = [0.1] * 768
        dense_hits = [
            {"id": "a1", "score": 0.95, "content": "chunk one", "source": "doc.pdf"},
            {"id": "a2", "score": 0.88, "content": "chunk two", "source": "doc.pdf"},
        ]
        mock_search.return_value = dense_hits
        mock_rerank.return_value = (
            [
                {"id": "a1", "score": 0.95, "content": "chunk one", "source": "doc.pdf",
                 "reranker_score": 0.92, "hybrid_score": 0.95},
                {"id": "a2", "score": 0.88, "content": "chunk two", "source": "doc.pdf",
                 "reranker_score": 0.80, "hybrid_score": 0.88},
            ],
            10.0,
        )

        result = retrieve_chunks("What is AI?", top_k=2)

        assert "chunks" in result
        assert "metadata" in result
        assert len(result["chunks"]) == 2
        mock_embed.assert_called_once_with("What is AI?")

    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.get_bm25_ready", return_value=False)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_source_filter_forwarded(self, mock_embed, mock_search, mock_bm25_ready, mock_rerank):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []
        mock_rerank.return_value = ([], 0.0)

        retrieve_chunks("test", top_k=3, source_filter="notes.txt")

        mock_search.assert_called_once()
        _, kwargs = mock_search.call_args
        assert kwargs["source_filter"] == "notes.txt"

    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.get_bm25_ready", return_value=False)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_empty_results(self, mock_embed, mock_search, mock_bm25_ready, mock_rerank):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []
        mock_rerank.return_value = ([], 0.0)

        result = retrieve_chunks("obscure query")
        assert result["chunks"] == []

    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.get_bm25_ready", return_value=False)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_default_top_k_from_settings(self, mock_embed, mock_search, mock_bm25_ready, mock_rerank):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []
        mock_rerank.return_value = ([], 0.0)

        retrieve_chunks("hello")

        _, kwargs = mock_search.call_args
        assert kwargs["top_k"] == 20  # settings.TOP_K_DENSE default
