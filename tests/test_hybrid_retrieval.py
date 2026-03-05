"""Unit tests for hybrid retrieval pipeline."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.retrieval import _min_max_normalize, _merge_results, retrieve_chunks


class TestMinMaxNormalize:
    def test_basic(self):
        assert _min_max_normalize([1, 2, 3]) == [0.0, 0.5, 1.0]

    def test_all_same(self):
        assert _min_max_normalize([5, 5, 5]) == [1.0, 1.0, 1.0]

    def test_empty(self):
        assert _min_max_normalize([]) == []

    def test_two_values(self):
        result = _min_max_normalize([0.3, 0.9])
        assert abs(result[0] - 0.0) < 0.001
        assert abs(result[1] - 1.0) < 0.001


class TestMergeResults:
    def test_merge_deduplicates(self):
        dense = [
            {"id": "a", "score": 0.9, "content": "chunk a"},
            {"id": "b", "score": 0.7, "content": "chunk b"},
        ]
        bm25 = [
            {"id": "a", "bm25_score": 5.0, "content": "chunk a"},
            {"id": "c", "bm25_score": 3.0, "content": "chunk c"},
        ]
        merged = _merge_results(dense, bm25, alpha=0.5)

        ids = [m["id"] for m in merged]
        assert len(ids) == 3  # a, b, c deduplicated
        assert len(set(ids)) == 3

    def test_alpha_1_favours_dense(self):
        dense = [{"id": "a", "score": 0.9, "content": "d"}]
        bm25 = [{"id": "b", "bm25_score": 10.0, "content": "b"}]
        merged = _merge_results(dense, bm25, alpha=1.0)

        # With alpha=1.0, dense gets full weight, bm25 gets 0
        a = next(m for m in merged if m["id"] == "a")
        b = next(m for m in merged if m["id"] == "b")
        assert a["hybrid_score"] > b["hybrid_score"]

    def test_alpha_0_favours_bm25(self):
        dense = [{"id": "a", "score": 0.9, "content": "d"}]
        bm25 = [{"id": "b", "bm25_score": 10.0, "content": "b"}]
        merged = _merge_results(dense, bm25, alpha=0.0)

        a = next(m for m in merged if m["id"] == "a")
        b = next(m for m in merged if m["id"] == "b")
        assert b["hybrid_score"] > a["hybrid_score"]


class TestRetrieveChunks:
    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.bm25_search")
    @patch("app.core.retrieval.get_bm25_ready", return_value=True)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_full_pipeline_returns_dict(self, mock_embed, mock_search, mock_bm25_ready, mock_bm25, mock_rerank):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [
            {"id": "d1", "score": 0.95, "content": "dense chunk", "source": "a.pdf"},
        ]
        mock_bm25.return_value = [
            {"id": "b1", "bm25_score": 4.5, "content": "bm25 chunk", "source": "a.pdf"},
        ]
        mock_rerank.return_value = (
            [{"id": "d1", "content": "dense chunk", "reranker_score": 0.88, "hybrid_score": 0.9, "score": 0.95, "source": "a.pdf"}],
            15.0,
        )

        result = retrieve_chunks("test query", top_k=5)

        assert "chunks" in result
        assert "metadata" in result
        assert isinstance(result["metadata"]["latency"], dict)

    @patch("app.core.retrieval.rerank")
    @patch("app.core.retrieval.get_bm25_ready", return_value=False)
    @patch("app.core.retrieval.search_vectors")
    @patch("app.core.retrieval.embed_text")
    def test_dense_only_fallback(self, mock_embed, mock_search, mock_bm25_ready, mock_rerank):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [
            {"id": "d1", "score": 0.9, "content": "chunk", "source": "a.pdf"},
        ]
        mock_rerank.return_value = (
            [{"id": "d1", "content": "chunk", "score": 0.9, "hybrid_score": 0.9, "source": "a.pdf"}],
            10.0,
        )

        result = retrieve_chunks("test")

        assert result["metadata"]["bm25_count"] == 0
        assert result["metadata"]["latency"]["bm25_ms"] == 0.0
