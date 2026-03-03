"""Retrieval — embed query, search Qdrant, return ranked chunks."""

from __future__ import annotations

import logging

from app.config import settings
from app.core.embeddings import embed_text
from app.core.vector_store import search_vectors

logger = logging.getLogger(__name__)


def retrieve_chunks(
    query: str,
    top_k: int | None = None,
    source_filter: str | None = None,
) -> list[dict]:
    """
    Embed the query, search Qdrant, return top-k results sorted by score.

    Each result dict: id, score, content, source, chunk_index, page_number, metadata.
    """
    k = top_k or settings.TOP_K

    # Embed query
    query_vector = embed_text(query)

    # Vector search
    hits = search_vectors(query_vector, top_k=k, source_filter=source_filter)

    # Already sorted by Qdrant (descending cosine similarity)
    logger.info(
        "Retrieved %d chunks for query (top_k=%d, source_filter=%s)",
        len(hits), k, source_filter,
    )
    return hits

