"""Retrieval — fetch relevant chunks from the vector store."""

from __future__ import annotations

import logging

from langchain_core.documents import Document

from app.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def retrieve_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """
    Return the top-k most similar chunks for the given query.

    Each dict contains: content, source, score.
    """
    store = get_vector_store()
    results: list[tuple[Document, float]] = store.similarity_search_with_score(
        query, k=top_k
    )

    chunks = []
    for doc, score in results:
        # Skip the bootstrap dummy document
        if doc.page_content.strip() == "__init__":
            continue
        chunks.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", ""),
                "score": round(float(score), 4),
            }
        )

    logger.info("Retrieved %d chunks for query (top_k=%d)", len(chunks), top_k)
    return chunks
