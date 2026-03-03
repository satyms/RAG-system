"""Unit tests for the generation module (app.core.generation)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.generation import generate_answer


class TestGenerateAnswer:
    """Test LLM generation with mocked Gemini."""

    def _mock_response(self, content: str = "Test answer", usage=None):
        resp = MagicMock()
        resp.content = content
        if usage:
            resp.usage_metadata = usage
        else:
            resp.usage_metadata = None
        return resp

    @patch("app.core.generation._get_llm")
    def test_basic_generation(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.__or__ = MagicMock()  # for | operator
        mock_get_llm.return_value = mock_llm

        # Mock the chain invocation
        with patch("app.core.generation._PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response("The answer is 42.")
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = generate_answer(
                "What is the answer?",
                [{"content": "The answer is 42.", "source": "guide.pdf"}],
            )

        assert "answer" in result
        assert "latency_ms" in result
        assert "token_usage" in result

    @patch("app.core.generation._get_llm")
    def test_token_usage_extraction(self, mock_get_llm):
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.total_tokens = 150

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.generation._PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response("answer", usage)
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = generate_answer("q", [{"content": "ctx", "source": "f.pdf"}])

        assert result["token_usage"]["prompt_tokens"] == 100
        assert result["token_usage"]["completion_tokens"] == 50
        assert result["token_usage"]["total_tokens"] == 150

    @patch("app.core.generation._get_llm")
    def test_empty_context(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.generation._PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response("No info available.")
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = generate_answer("question", [])

        assert result["answer"] == "No info available."

    @patch("app.core.generation._get_llm")
    def test_latency_recorded(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        with patch("app.core.generation._PROMPT") as mock_prompt:
            chain = MagicMock()
            chain.invoke.return_value = self._mock_response("resp")
            mock_prompt.__or__ = MagicMock(return_value=chain)

            result = generate_answer("q", [{"content": "c", "source": "s"}])

        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0
