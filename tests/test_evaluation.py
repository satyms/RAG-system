"""Unit tests for retrieval evaluation framework."""

from __future__ import annotations

from app.core.evaluation import precision_at_k, recall_at_k, mrr


class TestPrecisionAtK:
    def test_all_relevant(self):
        assert precision_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == 1.0

    def test_none_relevant(self):
        assert precision_at_k(["a", "b", "c"], ["x", "y", "z"], k=3) == 0.0

    def test_partial(self):
        assert precision_at_k(["a", "b", "c"], ["a", "c"], k=3) == round(2 / 3, 4)

    def test_k_smaller_than_retrieved(self):
        assert precision_at_k(["a", "b", "c", "d"], ["a"], k=2) == 0.5

    def test_empty_retrieved(self):
        assert precision_at_k([], ["a"], k=5) == 0.0


class TestRecallAtK:
    def test_all_found(self):
        assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0

    def test_none_found(self):
        assert recall_at_k(["x", "y"], ["a", "b"], k=2) == 0.0

    def test_partial(self):
        assert recall_at_k(["a", "x", "y"], ["a", "b"], k=3) == 0.5

    def test_no_relevant(self):
        assert recall_at_k(["a"], [], k=1) == 0.0


class TestMRR:
    def test_first_position(self):
        assert mrr(["a", "b", "c"], ["a"]) == 1.0

    def test_second_position(self):
        assert mrr(["x", "a", "c"], ["a"]) == 0.5

    def test_third_position(self):
        assert mrr(["x", "y", "a"], ["a"]) == round(1 / 3, 4)

    def test_not_found(self):
        assert mrr(["x", "y", "z"], ["a"]) == 0.0

    def test_first_relevant_matters(self):
        # MRR uses rank of FIRST relevant doc
        assert mrr(["x", "a", "b"], ["a", "b"]) == 0.5
