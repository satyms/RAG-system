"""BM25 keyword search service — in-memory index built from Qdrant payloads."""

from __future__ import annotations

import logging
import re
import threading
from functools import lru_cache

from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.vector_store import get_qdrant_client

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_bm25_index: BM25Okapi | None = None
_corpus_docs: list[dict] = []  # parallel list of payload dicts


# ── Tokeniser ────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokeniser."""
    return re.findall(r"\w+", text.lower())


# ── Index management ─────────────────────────────────────────

def build_bm25_index() -> int:
    """
    Rebuild the BM25 index from all Qdrant payloads.

    Call this after ingestion or on startup.
    Returns number of documents indexed.
    """
    global _bm25_index, _corpus_docs

    client = get_qdrant_client()
    all_docs: list[dict] = []
    offset = None

    while True:
        records, next_offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            limit=500,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for r in records:
            all_docs.append({
                "id": str(r.id),
                "content": r.payload.get("content", ""),
                "source": r.payload.get("source", ""),
                "chunk_index": r.payload.get("chunk_index"),
                "page_number": r.payload.get("page_number"),
                "metadata": r.payload,
            })
        if next_offset is None:
            break
        offset = next_offset

    if not all_docs:
        logger.warning("BM25: no documents found in Qdrant — index is empty")
        with _lock:
            _bm25_index = None
            _corpus_docs = []
        return 0

    tokenized = [_tokenize(d["content"]) for d in all_docs]

    with _lock:
        _bm25_index = BM25Okapi(tokenized)
        _corpus_docs = all_docs

    logger.info("BM25 index built with %d documents", len(all_docs))
    return len(all_docs)


def get_bm25_ready() -> bool:
    """Check if the BM25 index is populated."""
    return _bm25_index is not None and len(_corpus_docs) > 0


# ── Search ───────────────────────────────────────────────────

def bm25_search(
    query: str,
    top_k: int | None = None,
    source_filter: str | None = None,
) -> list[dict]:
    """
    Run BM25 keyword search over the in-memory corpus.

    Returns list of dicts with: id, bm25_score, content, source, etc.
    Sorted descending by BM25 score.
    """
    k = top_k or settings.TOP_K_BM25

    with _lock:
        index = _bm25_index
        docs = _corpus_docs

    if index is None or not docs:
        logger.warning("BM25 index not ready — returning empty results")
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = index.get_scores(tokens)

    # Pair docs with scores, apply source filter
    scored = []
    for doc, score in zip(docs, scores):
        if source_filter and doc.get("source") != source_filter:
            continue
        scored.append({**doc, "bm25_score": round(float(score), 4)})

    # Sort descending by BM25 score, take top_k
    scored.sort(key=lambda x: x["bm25_score"], reverse=True)
    return scored[:k]
