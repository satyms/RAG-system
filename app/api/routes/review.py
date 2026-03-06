"""Phase 4 API routes -- human-in-the-loop review endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from app.models.schemas import ReviewActionRequest
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["Human Review"])


@router.get("")
@limiter.limit("60/minute")
async def list_review_queue(
    request: Request,
    status: str | None = None,
    limit: int = 50,
):
    """List items in the human review queue."""
    from app.core.human_review import get_review_queue, ReviewStatus

    status_enum = None
    if status:
        try:
            status_enum = ReviewStatus(status)
        except ValueError:
            pass
    items = get_review_queue(status=status_enum, limit=limit)
    return {
        "count": len(items),
        "items": items,
    }


@router.get("/stats")
@limiter.limit("60/minute")
async def review_stats(request: Request):
    """Get review queue statistics."""
    from app.core.human_review import get_review_stats
    return get_review_stats()


@router.get("/{review_id}")
@limiter.limit("60/minute")
async def get_review_item(request: Request, review_id: str):
    """Get full detail for a single review item."""
    from app.core.human_review import get_review_item as _get

    item = _get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/{review_id}")
@limiter.limit("30/minute")
async def submit_review(
    request: Request,
    review_id: str,
    body: ReviewActionRequest,
):
    """Approve or reject a review item."""
    from app.core.human_review import submit_review as _submit

    result = _submit(
        review_id=review_id,
        action=body.action,
        corrected_answer=body.corrected_answer,
        reviewer_notes=body.reviewer_notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return {"message": f"Review {body.action}d", "review_id": review_id}
