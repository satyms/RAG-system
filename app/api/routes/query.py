"""Query endpoint — ask a question against the RAG pipeline."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.retrieval import retrieve_chunks
from app.core.generation import generate_answer
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Query"])


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    """Retrieve relevant chunks and generate an LLM answer."""
    try:
        chunks = retrieve_chunks(payload.question, top_k=payload.top_k)
        answer = generate_answer(payload.question, chunks)
    except Exception as exc:
        logger.exception("Query pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return QueryResponse(
        answer=answer,
        sources=[SourceChunk(**c) for c in chunks],
    )
