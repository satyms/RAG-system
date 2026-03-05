"""Unit tests for background evaluation scheduler module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.scheduler import (
    _detect_drift,
    _load_history,
    _save_history,
    run_scheduled_evaluation,
    get_metric_history,
)


class TestDriftDetection:
    def _make_history(self, precisions: list[float]) -> list[dict]:
        return [
            {"avg_precision_at_k": p, "avg_recall_at_k": p, "avg_mrr": p}
            for p in precisions
        ]

    def test_no_drift_when_stable(self):
        history = self._make_history([0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
        assert _detect_drift(history) is None

    def test_detects_drift_on_drop(self):
        # 5 runs at 0.8, then sudden drop to 0.5
        history = self._make_history([0.8, 0.8, 0.8, 0.8, 0.8, 0.5])
        result = _detect_drift(history, window=5, threshold=0.1)
        assert result is not None
        assert len(result["drifts"]) > 0
        assert result["drifts"][0]["metric"] == "avg_precision_at_k"

    def test_no_drift_with_small_drop(self):
        history = self._make_history([0.8, 0.8, 0.8, 0.8, 0.8, 0.75])
        result = _detect_drift(history, window=5, threshold=0.1)
        assert result is None

    def test_not_enough_history(self):
        history = self._make_history([0.8, 0.5])
        assert _detect_drift(history, window=5) is None


class TestMetricHistory:
    def test_save_and_load(self, tmp_path):
        history_path = tmp_path / "metric_history.json"
        data = [{"avg_precision_at_k": 0.8, "timestamp": "2026-01-01"}]

        with patch("app.core.scheduler._HISTORY_PATH", history_path):
            _save_history(data)
            loaded = _load_history()

        assert loaded == data

    def test_load_empty(self, tmp_path):
        history_path = tmp_path / "nonexistent.json"
        with patch("app.core.scheduler._HISTORY_PATH", history_path):
            assert _load_history() == []


class TestRunScheduledEvaluation:
    @patch("app.core.scheduler._save_history")
    @patch("app.core.scheduler._load_history", return_value=[])
    @patch("app.core.scheduler.run_evaluation")
    def test_appends_to_history(self, mock_eval, mock_load, mock_save):
        mock_eval.return_value = {
            "avg_precision_at_k": 0.85,
            "avg_recall_at_k": 0.80,
            "avg_mrr": 0.90,
            "num_queries": 10,
            "k": 5,
            "timestamp": "2026-01-01T00:00:00Z",
            "config": {},
            "per_query": [],
        }

        result = run_scheduled_evaluation(k=5)

        assert result["history_length"] == 1
        assert not result["drift_detected"]
        mock_save.assert_called_once()

    @patch("app.core.scheduler.run_evaluation")
    def test_handles_eval_error(self, mock_eval):
        mock_eval.return_value = {"error": "No ground truth data."}

        result = run_scheduled_evaluation()
        assert "error" in result

    @patch("app.core.scheduler.run_evaluation")
    def test_handles_exception(self, mock_eval):
        mock_eval.side_effect = RuntimeError("DB down")

        result = run_scheduled_evaluation()
        assert "error" in result


class TestGetMetricHistory:
    @patch("app.core.scheduler._load_history")
    def test_returns_history(self, mock_load):
        mock_load.return_value = [{"avg_precision_at_k": 0.8}]
        assert get_metric_history() == [{"avg_precision_at_k": 0.8}]
