"""Faithfulness evaluation — LLM-as-judge for groundedness checking."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt for faithfulness evaluation ───────────────────────
_JUDGE_SYSTEM = """You are a strict factual evaluator. Your job is to judge whether an AI answer is faithfully supported by the provided context.

Context:
{context}

Answer being evaluated:
{answer}

Question that was asked:
{question}

Evaluate the answer using ONLY the provided context. Return a JSON object with exactly these fields:
- "faithfulness_score": a float from 0.0 to 1.0 (1.0 = perfectly supported, 0.0 = completely unsupported)
- "is_grounded": one of "yes", "no", or "partial"
- "reason": a brief one-sentence explanation

Return ONLY the JSON object, no other text."""

_JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _JUDGE_SYSTEM),
    ("human", "Evaluate now."),
])


@lru_cache(maxsize=1)
def _get_judge_llm() -> ChatOllama:
    """Lightweight LLM for evaluation — Ollama with low temperature."""
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
    )


def evaluate_faithfulness(
    question: str,
    answer: str,
    context_chunks: list[dict],
) -> dict:
    """
    Use LLM-as-judge to evaluate whether the answer is grounded in context.

    Returns:
        {
            "faithfulness_score": float (0-1),
            "is_grounded": "yes" | "no" | "partial",
            "reason": str,
            "latency_ms": float,
        }
    """
    import json as _json

    context_text = "\n\n---\n\n".join(
        c.get("content", "") for c in context_chunks
    ) or "No context provided."

    chain = _JUDGE_PROMPT | _get_judge_llm()

    start = time.perf_counter()
    response = chain.invoke({
        "context": context_text,
        "answer": answer,
        "question": question,
    })
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    raw = response.content.strip()  # type: ignore[union-attr]

    # Parse JSON from response
    try:
        # Handle code-fenced JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = _json.loads(raw)
    except (_json.JSONDecodeError, IndexError):
        logger.warning("Faithfulness judge returned unparseable response: %s", raw[:200])
        parsed = {
            "faithfulness_score": None,
            "is_grounded": "unknown",
            "reason": "Failed to parse judge response",
        }

    parsed["latency_ms"] = latency_ms

    logger.info(
        "Faithfulness eval: score=%.2f, grounded=%s (%.0fms)",
        parsed.get("faithfulness_score") or 0,
        parsed.get("is_grounded", "unknown"),
        latency_ms,
    )
    return parsed
