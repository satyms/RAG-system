"""LLM generation — build prompt, call model, return answer."""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────
_SYSTEM = (
    "You are a helpful AI assistant. Use the following context to answer the "
    "user's question. If the context does not contain enough information, say "
    "so honestly but still try your best.\n\n"
    "Context:\n{context}"
)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        ("human", "{question}"),
    ]
)


# ── LLM factory ─────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_llm() -> BaseChatModel:
    """Instantiate the configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )

    if provider == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.3,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.3,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


# ── Public API ───────────────────────────────────────────────
def generate_answer(question: str, context_chunks: list[dict[str, object]]) -> str:
    """Build a prompt from retrieved chunks and call the LLM."""
    context_text = "\n\n---\n\n".join(
        c["content"] for c in context_chunks
    ) or "No relevant context found."

    try:
        chain = _PROMPT | _get_llm()
        response = chain.invoke({"context": context_text, "question": question})
        answer: str = response.content  # type: ignore[union-attr]
        logger.info("Generated answer (%d chars)", len(answer))
        return answer
    except Exception as exc:
        logger.warning("LLM generation failed; using extractive fallback answer: %s", exc)
        return _fallback_answer(question, context_chunks)


def _fallback_answer(question: str, context_chunks: list[dict[str, object]]) -> str:
    """Return a grounded fallback answer when the configured LLM is unavailable."""
    if not context_chunks:
        return (
            "The LLM backend is currently unavailable, and no relevant context was found in the vector store. "
            "Try again after the model service is back online."
        )

    snippets = []
    for chunk in context_chunks[:3]:
        content = str(chunk.get("content", "")).strip().replace("\n", " ")
        source = str(chunk.get("source", "")).strip() or "retrieved source"
        if content:
            snippets.append(f"- {source}: {content[:280]}")

    if not snippets:
        return (
            "The LLM backend is currently unavailable. Relevant chunks were retrieved, but they did not contain "
            "usable text for a fallback answer."
        )

    return (
        "The LLM backend is currently unavailable, so this is a retrieval-only fallback based on the top matching chunks "
        f"for the question: '{question}'.\n\n"
        "Relevant excerpts:\n"
        + "\n".join(snippets)
    )
