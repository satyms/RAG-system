"""Unit tests for cross-encoder reranker module."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import numpy as np

from app.core.reranker import rerank


class TestRerank:
    def _make_chunks(self, n: int) -> list[dict]:
        return [
            {"id": f"c{i}", "content": f"Chunk content {i}", "source": "doc.pdf", "score": 0.9 - i * 0.05}
            for i in range(n)
        ]

    @patch("app.core.reranker.get_reranker")
    def test_reranks_by_score(self, mock_get):
        mock_model = MagicMock()
        # Return scores in reverse order so reranking should flip them
        mock_model.predict.return_value = np.array([0.1, 0.5, 0.9, 0.3, 0.7])
        mock_get.return_value = mock_model

        chunks = self._make_chunks(5)
        result, latency = rerank("test query", chunks, top_k=3)

        assert len(result) == 3
        assert result[0]["reranker_score"] >= result[1]["reranker_score"]
        assert result[1]["reranker_score"] >= result[2]["reranker_score"]
        assert latency >= 0

    @patch("app.core.reranker.get_reranker")
    def test_rerank_empty_chunks(self, mock_get):
        result, latency = rerank("test", [], top_k=5)
        assert result == []
        assert latency == 0.0
        mock_get.assert_not_called()

    @patch("app.core.reranker.settings")
    def test_rerank_disabled(self, mock_settings):
        mock_settings.RERANKER_ENABLED = False
        mock_settings.RERANKER_TOP_K = 3

        chunks = self._make_chunks(5)
        result, latency = rerank("test", chunks, top_k=3)

        assert len(result) == 3
        assert latency == 0.0
        # Should be first 3 in original order (no reranking)
        assert result[0]["id"] == "c0"

    @patch("app.core.reranker.get_reranker")
    def test_attaches_reranker_score(self, mock_get):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8, 0.2])
        mock_get.return_value = mock_model

        chunks = self._make_chunks(2)
        result, _ = rerank("query", chunks, top_k=2)

        for c in result:
            assert "reranker_score" in c
            assert isinstance(c["reranker_score"], float)
