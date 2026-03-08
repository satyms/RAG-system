"""LLM generation — build prompt, call model, return answer."""

from __future__ import annotations

import json
import logging
import re
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


_STUDIO_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You create structured study materials from provided document context. "
            "Respond with valid JSON only and no markdown fences. Use the requested schema exactly. "
            "Do not invent facts outside the context. Keep titles concise and educational.\n\n"
            "Artifact type: {artifact_type}\n"
            "Required JSON schema: {schema_instructions}\n\n"
            "Context:\n{context}",
        ),
        ("human", "Generate the study artifact."),
    ]
)


_ARTIFACT_SCHEMAS = {
    "flashcards": (
        '{"title": "string", "summary": "string", "cards": '
        '[{"question": "string", "answer": "string"}]}'
    ),
    "quiz": (
        '{"title": "string", "summary": "string", "questions": '
        '[{"question": "string", "options": ["string", "string", "string", "string"], '
        '"answer_index": 0, "explanation": "string", "hint": "string"}]}'
    ),
    "mind_map": (
        '{"title": "string", "summary": "string", "central_topic": "string", '
        '"branches": [{"label": "string", "children": '
        '[{"label": "string", "children": [{"label": "string"}]}]}]}'
    ),
}


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

    chain = _PROMPT | _get_llm()
    response = chain.invoke({"context": context_text, "question": question})

    answer: str = response.content  # type: ignore[union-attr]
    logger.info("Generated answer (%d chars)", len(answer))
    return answer


def _extract_json_object(raw_text: str) -> dict[str, object]:
    """Parse a JSON object from model output, tolerating markdown fences."""

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model did not return valid JSON")
        parsed = json.loads(cleaned[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object from model output")
    return parsed


def generate_study_artifact(artifact_type: str, context_chunks: list[dict[str, object]]) -> dict[str, object]:
    """Generate a structured study artifact from indexed corpus chunks."""

    if artifact_type not in _ARTIFACT_SCHEMAS:
        raise ValueError(f"Unsupported artifact type: {artifact_type}")

    context_text = "\n\n---\n\n".join(
        f"Source: {chunk.get('source', '')}\n{chunk.get('content', '')}"
        for chunk in context_chunks
    ) or "No relevant context found."

    chain = _STUDIO_PROMPT | _get_llm()
    response = chain.invoke(
        {
            "artifact_type": artifact_type,
            "schema_instructions": _ARTIFACT_SCHEMAS[artifact_type],
            "context": context_text,
        }
    )

    raw_content: str = response.content  # type: ignore[union-attr]
    parsed = _extract_json_object(raw_content)
    logger.info("Generated %s artifact", artifact_type)
    return parsed
