"""Unit tests for the retrieval module (app.core.retrieval)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.retrieval import retrieve_chunks


class TestRetrieveChunks:
    """Test retrieval with mocked embedding + vector search."""

    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_returns_results(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [
            {"id": "a1", "score": 0.95, "content": "chunk one", "source": "doc.pdf"},
            {"id": "a2", "score": 0.88, "content": "chunk two", "source": "doc.pdf"},
        ]

        results = retrieve_chunks("What is AI?", top_k=2)

        assert len(results) == 2
        assert results[0]["score"] == 0.95
        mock_embed.assert_called_once_with("What is AI?")
        mock_search.assert_called_once_with([0.1] * 768, top_k=2, source_filter=None)

    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_source_filter_forwarded(self, mock_embed, mock_search):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []

        retrieve_chunks("test", top_k=3, source_filter="notes.txt")

        mock_search.assert_called_once_with([0.0] * 768, top_k=3, source_filter="notes.txt")

    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_empty_results(self, mock_embed, mock_search):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []

        results = retrieve_chunks("obscure query")
        assert results == []

    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_default_top_k_from_settings(self, mock_embed, mock_search):
        mock_embed.return_value = [0.0] * 768
        mock_search.return_value = []

        retrieve_chunks("hello")

        _, kwargs = mock_search.call_args
        assert kwargs["top_k"] == 5  # settings.TOP_K default
