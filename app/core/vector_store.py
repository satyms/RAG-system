"""Qdrant vector store service — singleton client."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return a cached Qdrant client."""
    client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    logger.info("Connected to Qdrant at %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT)
    return client


def ensure_collection() -> None:
    """Create the Qdrant collection if it does not exist."""
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if settings.QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", settings.QDRANT_COLLECTION)
    else:
        logger.info("Qdrant collection already exists: %s", settings.QDRANT_COLLECTION)


def upsert_embeddings(
    embeddings: list[list[float]],
    payloads: list[dict],
) -> list[str]:
    """
    Upsert embedding vectors with metadata payloads into Qdrant.

    Returns list of point IDs (UUID strings).
    """
    client = get_qdrant_client()
    point_ids = [str(uuid.uuid4()) for _ in embeddings]

    points = [
        PointStruct(id=pid, vector=vec, payload=payload)
        for pid, vec, payload in zip(point_ids, embeddings, payloads)
    ]

    # Batch in groups of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=batch)

    logger.info("Upserted %d vectors into Qdrant", len(points))
    return point_ids


def search_vectors(
    query_vector: list[float],
    top_k: int = 5,
    source_filter: str | None = None,
) -> list[dict]:
    """
    Search Qdrant for the top-k most similar vectors.

    Returns list of dicts with: id, score, content, source, metadata.
    """
    client = get_qdrant_client()

    query_filter = None
    if source_filter:
        query_filter = Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source_filter))]
        )

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        query_filter=query_filter,
        with_payload=True,
    )

    hits = []
    for r in results:
        hits.append({
            "id": str(r.id),
            "score": round(float(r.score), 4),
            "content": r.payload.get("content", ""),
            "source": r.payload.get("source", ""),
            "chunk_index": r.payload.get("chunk_index"),
            "page_number": r.payload.get("page_number"),
            "metadata": r.payload,
        })

    logger.info("Qdrant search returned %d results (top_k=%d)", len(hits), top_k)
    return hits


def delete_document_vectors(source: str) -> int:
    """Delete all vectors for a given source filename. Returns count deleted."""
    client = get_qdrant_client()

    # Use scroll to find all points with this source
    points_to_delete = []
    offset = None
    while True:
        records, next_offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source))]
            ),
            limit=100,
            offset=offset,
        )
        points_to_delete.extend([r.id for r in records])
        if next_offset is None:
            break
        offset = next_offset

    if points_to_delete:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=points_to_delete,
        )

    logger.info("Deleted %d vectors for source=%s", len(points_to_delete), source)
    return len(points_to_delete)

