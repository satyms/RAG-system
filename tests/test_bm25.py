"""Unit tests for BM25 keyword search module."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.bm25_search import _tokenize, build_bm25_index, bm25_search, get_bm25_ready


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_punctuation(self):
        assert _tokenize("it's a test!") == ["it", "s", "a", "test"]

    def test_empty(self):
        assert _tokenize("") == []

    def test_numbers(self):
        assert _tokenize("page 42") == ["page", "42"]


class TestBM25Index:
    @patch("app.core.bm25_search.get_qdrant_client")
    def test_build_index_empty(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([], None)
        mock_client_fn.return_value = mock_client

        count = build_bm25_index()
        assert count == 0
        assert not get_bm25_ready()

    @patch("app.core.bm25_search.get_qdrant_client")
    def test_build_index_with_docs(self, mock_client_fn):
        record1 = MagicMock()
        record1.id = "id1"
        record1.payload = {"content": "machine learning basics", "source": "doc.pdf"}

        record2 = MagicMock()
        record2.id = "id2"
        record2.payload = {"content": "deep learning neural networks", "source": "doc.pdf"}

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record1, record2], None)
        mock_client_fn.return_value = mock_client

        count = build_bm25_index()
        assert count == 2
        assert get_bm25_ready()

    @patch("app.core.bm25_search.get_qdrant_client")
    def test_bm25_search_returns_results(self, mock_client_fn):
        record1 = MagicMock()
        record1.id = "id1"
        record1.payload = {"content": "machine learning basics", "source": "a.pdf"}

        record2 = MagicMock()
        record2.id = "id2"
        record2.payload = {"content": "deep learning neural networks", "source": "a.pdf"}

        record3 = MagicMock()
        record3.id = "id3"
        record3.payload = {"content": "cooking recipes for dinner", "source": "b.pdf"}

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record1, record2, record3], None)
        mock_client_fn.return_value = mock_client

        build_bm25_index()
        results = bm25_search("machine learning", top_k=2)

        assert len(results) <= 2
        assert results[0]["bm25_score"] >= results[-1]["bm25_score"]

    @patch("app.core.bm25_search.get_qdrant_client")
    def test_bm25_search_source_filter(self, mock_client_fn):
        record1 = MagicMock()
        record1.id = "id1"
        record1.payload = {"content": "machine learning", "source": "a.pdf"}

        record2 = MagicMock()
        record2.id = "id2"
        record2.payload = {"content": "machine learning too", "source": "b.pdf"}

        mock_client = MagicMock()
        mock_client.scroll.return_value = ([record1, record2], None)
        mock_client_fn.return_value = mock_client

        build_bm25_index()
        results = bm25_search("machine learning", source_filter="a.pdf")

        for r in results:
            assert r["source"] == "a.pdf"

    def test_bm25_search_no_index(self):
        """Search before index is built returns empty."""
        # Reset module state
        import app.core.bm25_search as mod
        mod._bm25_index = None
        mod._corpus_docs = []

        results = bm25_search("test query")
        assert results == []
