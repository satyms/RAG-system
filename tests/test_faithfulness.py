"""Unit tests for faithfulness evaluation module."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from app.core.faithfulness import evaluate_faithfulness


class TestEvaluateFaithfulness:
    """Test LLM-as-judge faithfulness evaluation with mocked Gemini."""

    def _mock_response(self, content: str):
        resp = MagicMock()
        resp.content = content
        return resp

    @patch("app.core.faithfulness._get_judge_llm")
    def test_returns_parsed_result(self, mock_get_llm):
        judge_output = json.dumps({
            "faithfulness_score": 0.95,
            "is_grounded": "yes",
            "reason": "Fully supported by context.",
        })
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.faithfulness._JUDGE_PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response(judge_output)
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = evaluate_faithfulness(
                question="What is AI?",
                answer="AI is artificial intelligence.",
                context_chunks=[{"content": "AI stands for artificial intelligence."}],
            )

        assert result["faithfulness_score"] == 0.95
        assert result["is_grounded"] == "yes"
        assert "latency_ms" in result

    @patch("app.core.faithfulness._get_judge_llm")
    def test_handles_code_fenced_json(self, mock_get_llm):
        judge_output = '```json\n{"faithfulness_score": 0.8, "is_grounded": "partial", "reason": "Mostly supported."}\n```'
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.faithfulness._JUDGE_PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response(judge_output)
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = evaluate_faithfulness(
                question="test",
                answer="answer",
                context_chunks=[{"content": "context"}],
            )

        assert result["faithfulness_score"] == 0.8
        assert result["is_grounded"] == "partial"

    @patch("app.core.faithfulness._get_judge_llm")
    def test_handles_unparseable_response(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.faithfulness._JUDGE_PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response("This is not JSON at all.")
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = evaluate_faithfulness(
                question="test",
                answer="answer",
                context_chunks=[{"content": "context"}],
            )

        assert result["faithfulness_score"] is None
        assert result["is_grounded"] == "unknown"
        assert "latency_ms" in result

    @patch("app.core.faithfulness._get_judge_llm")
    def test_empty_context(self, mock_get_llm):
        judge_output = json.dumps({
            "faithfulness_score": 0.0,
            "is_grounded": "no",
            "reason": "No context available.",
        })
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.faithfulness._JUDGE_PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response(judge_output)
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = evaluate_faithfulness(
                question="test",
                answer="some answer",
                context_chunks=[],
            )

        assert result["faithfulness_score"] == 0.0
        assert result["is_grounded"] == "no"

    @patch("app.core.faithfulness._get_judge_llm")
    def test_latency_recorded(self, mock_get_llm):
        judge_output = json.dumps({
            "faithfulness_score": 0.5,
            "is_grounded": "partial",
            "reason": "Partially supported.",
        })
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.faithfulness._JUDGE_PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response(judge_output)
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = evaluate_faithfulness(
                question="q", answer="a", context_chunks=[{"content": "c"}],
            )

        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0
