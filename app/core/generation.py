"""LLM generation — Ollama (llama3.2), with latency & token tracking."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt template ──────────────────────────────────────────
_SYSTEM = (
    "You are a precise, helpful AI assistant. "
    "Answer the user's question using ONLY the provided context below. "
    "If the context does not contain enough information to answer, "
    "clearly state that the information is not available in the provided documents.\n\n"
    "Rules:\n"
    "- Be concise and factual.\n"
    "- Cite which source/section the information comes from when possible.\n"
    "- Do not hallucinate or make up information.\n\n"
    "Context:\n{context}"
)

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    ("human", "{question}"),
])


# ── LLM singleton ───────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_llm() -> ChatOllama:
    """Instantiate Ollama LLM."""
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.3,
    )


# ── Public API ───────────────────────────────────────────────

def generate_answer(
    question: str,
    context_chunks: list[dict],
) -> dict:
    """
    Build prompt from retrieved chunks, call Ollama LLM, return result dict.

    Returns:
        {
            "answer": str,
            "latency_ms": float,
            "token_usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int},
        }
    """
    # Format context
    context_parts = []
    for i, c in enumerate(context_chunks, 1):
        source = c.get("source", "unknown")
        page = c.get("page_number", "")
        header = f"[Source {i}: {source}"
        if page:
            header += f", page {page}"
        header += "]"
        context_parts.append(f"{header}\n{c['content']}")

    context_text = "\n\n---\n\n".join(context_parts) or "No relevant context found."

    chain = _PROMPT | _get_llm()

    start = time.perf_counter()
    response = chain.invoke({"context": context_text, "question": question})
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    answer: str = response.content  # type: ignore[union-attr]

    # Extract token usage if available
    token_usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        token_usage = {
            "prompt_tokens": getattr(um, "input_tokens", 0),
            "completion_tokens": getattr(um, "output_tokens", 0),
            "total_tokens": getattr(um, "total_tokens", 0),
        }

    logger.info(
        "Generated answer (%d chars, %.0fms, tokens=%s)",
        len(answer), latency_ms, token_usage,
    )

    return {
        "answer": answer,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
    }

