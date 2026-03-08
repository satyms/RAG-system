"""Studio endpoint — generate structured study artifacts from indexed documents."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.generation import generate_study_artifact
from app.core.retrieval import retrieve_corpus_chunks
from app.models.schemas import SourceChunk, StudyArtifactRequest, StudyArtifactResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["Studio"])


@router.post("/generate", response_model=StudyArtifactResponse)
async def generate_artifact(payload: StudyArtifactRequest):
    """Generate a flashcard set, quiz, or mind map from indexed content."""

    try:
        chunks = retrieve_corpus_chunks(limit=payload.top_k)
        if not chunks:
            raise HTTPException(status_code=400, detail="No indexed content found. Upload a document first.")

        artifact = generate_study_artifact(payload.artifact_type, chunks)
        title = str(artifact.get("title") or payload.artifact_type.replace("_", " ").title())
        summary = str(artifact.get("summary") or f"Generated {payload.artifact_type.replace('_', ' ')}")
        content = {key: value for key, value in artifact.items() if key not in {"title", "summary"}}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Studio generation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return StudyArtifactResponse(
        artifact_type=payload.artifact_type,
        title=title,
        summary=summary,
        content=content,
        sources=[SourceChunk(**chunk) for chunk in chunks],
    )