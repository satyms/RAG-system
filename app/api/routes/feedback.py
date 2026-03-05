"""Phase 4 API routes — feedback endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from app.config import settings
from app.models.schemas import FeedbackRequest, FeedbackResponse
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


@router.post("", response_model=FeedbackResponse)
@limiter.limit("30/minute")
async def submit_feedback(request: Request, body: FeedbackRequest):
    """Submit user feedback for a query."""
    from app.core.feedback import submit_feedback as _submit

    entry = _submit(
        query=body.query,
        answer=body.answer,
        rating=body.rating,
        correction=body.correction,
        comment=body.comment,
        confidence_score=body.confidence_score,
        faithfulness_score=body.faithfulness_score,
        metadata={},
    )
    return FeedbackResponse(
        id=entry.get("id", ""),
        message="Feedback recorded successfully",
    )


@router.get("")
@limiter.limit("60/minute")
async def get_feedback(
    request: Request,
    limit: int = 50,
    rating_filter: str | None = None,
):
    """Get feedback entries with optional rating filter."""
    from app.core.feedback import get_feedback as _get

    entries = _get(rating=rating_filter, limit=limit)
    return {
        "count": len(entries),
        "entries": entries,
    }


@router.get("/stats")
@limiter.limit("60/minute")
async def feedback_stats(request: Request):
    """Aggregated feedback statistics."""
    from app.core.feedback import get_feedback_stats
    return get_feedback_stats()


@router.post("/export-eval")
@limiter.limit("5/minute")
async def export_eval_data(request: Request):
    """Export corrections as evaluation data and expand ground-truth."""
    from app.core.feedback import (
        export_corrections_as_eval_data,
        expand_ground_truth_from_feedback,
    )

    eval_data = export_corrections_as_eval_data()
    expanded = expand_ground_truth_from_feedback()
    return {
        "eval_pairs": len(eval_data),
        "ground_truth_expanded": expanded,
    }


@router.post("/suggest-tuning")
@limiter.limit("10/minute")
async def suggest_tuning(request: Request):
    """Analyse negative feedback and suggest parameter tuning."""
    from app.core.feedback import suggest_tuning as _suggest
    return _suggest()
