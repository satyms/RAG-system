"""Retrieval — fetch relevant chunks from the vector store."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from langchain_core.documents import Document

from app.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _documents_to_chunks(documents: Iterable[tuple[Document, float | None]]) -> list[dict[str, object]]:
    """Normalize vector store documents into API-friendly chunk payloads."""

    chunks: list[dict[str, object]] = []
    for doc, score in documents:
        if doc.page_content.strip() == "__init__":
            continue
        chunks.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", ""),
                "score": round(float(score), 4) if score is not None else None,
            }
        )
    return chunks


def retrieve_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """
    Return the top-k most similar chunks for the given query.

    Each dict contains: content, source, score.
    """
    store = get_vector_store()
    results: list[tuple[Document, float]] = store.similarity_search_with_score(
        query, k=top_k
    )

    chunks = _documents_to_chunks(results)

    logger.info("Retrieved %d chunks for query (top_k=%d)", len(chunks), top_k)
    return chunks


def retrieve_corpus_chunks(limit: int = 12) -> list[dict[str, object]]:
    """Return indexed chunks directly from the store for study-artifact generation."""

    store = get_vector_store()
    raw_documents = getattr(store.docstore, "_dict", {}).values()
    documents = [(doc, None) for doc in raw_documents]
    chunks = _documents_to_chunks(documents)
    limited_chunks = chunks[:limit]
    logger.info("Retrieved %d corpus chunks for studio generation", len(limited_chunks))
    return limited_chunks
