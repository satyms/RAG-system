"""Human-in-the-Loop validation — triggers, review queue, and feedback capture."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# ── Review status ────────────────────────────────────────────

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"


# ── Review item ──────────────────────────────────────────────

@dataclass
class ReviewItem:
    """An item queued for human review."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    query: str = ""
    answer: str = ""
    context_chunks: list[dict] = field(default_factory=list)
    confidence_score: float = 0.0
    faithfulness_score: float | None = None
    trigger_reason: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_notes: str = ""
    corrected_answer: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── In-memory review queue (swap for DB in production) ───────

_review_queue: list[ReviewItem] = []


# ── Validation triggers ─────────────────────────────────────

_SENSITIVE_DOMAINS = [
    "medical", "health", "legal", "financial", "investment",
    "tax", "insurance", "compliance", "regulation",
]


def _is_sensitive_domain(query: str) -> bool:
    """Check if the query touches a sensitive domain."""
    q = query.lower()
    return any(domain in q for domain in _SENSITIVE_DOMAINS)


def should_trigger_review(
    query: str,
    answer: str,
    confidence: float,
    faithfulness_score: float | None = None,
    is_grounded: str = "unknown",
    errors: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Decide whether a response should be flagged for human review.

    Returns (should_review: bool, reason: str).
    """
    reasons = []

    # 1. Low confidence
    if confidence < settings.CONFIDENCE_THRESHOLD:
        reasons.append(f"Low confidence: {confidence:.4f} < {settings.CONFIDENCE_THRESHOLD}")

    # 2. Faithfulness concern
    if faithfulness_score is not None and faithfulness_score < 0.5:
        reasons.append(f"Low faithfulness: {faithfulness_score:.2f}")

    # 3. Not grounded
    if is_grounded == "no":
        reasons.append("Answer not grounded in context")

    # 4. Sensitive domain
    if _is_sensitive_domain(query):
        reasons.append("Sensitive domain query")

    # 5. Processing errors
    if errors:
        reasons.append(f"{len(errors)} processing error(s)")

    # 6. Very short answer (possible hallucination or refusal)
    if len(answer.strip()) < 20:
        reasons.append("Very short answer")

    # 7. Answer contains hedging language at high rate
    hedging_phrases = ["i'm not sure", "i think", "possibly", "might be", "it seems"]
    hedge_count = sum(1 for p in hedging_phrases if p in answer.lower())
    if hedge_count >= 2:
        reasons.append(f"High hedging in answer ({hedge_count} phrases)")

    if reasons:
        return True, "; ".join(reasons)
    return False, ""


# ── Review queue operations ──────────────────────────────────

def add_to_review_queue(
    query: str,
    answer: str,
    context_chunks: list[dict],
    confidence: float,
    trigger_reason: str,
    faithfulness_score: float | None = None,
    metadata: dict | None = None,
) -> str:
    """Add a response to the human review queue. Returns the review ID."""
    item = ReviewItem(
        query=query,
        answer=answer,
        context_chunks=[
            {"content": c.get("content", "")[:500], "source": c.get("source", "")}
            for c in context_chunks[:5]
        ],
        confidence_score=confidence,
        faithfulness_score=faithfulness_score,
        trigger_reason=trigger_reason,
        metadata=metadata or {},
    )
    _review_queue.append(item)
    logger.info("Added to review queue: %s (reason: %s)", item.id, trigger_reason[:80])
    return item.id


def get_review_queue(
    status: ReviewStatus | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get items from the review queue, optionally filtered by status."""
    items = _review_queue
    if status is not None:
        items = [i for i in items if i.status == status]
    items = sorted(items, key=lambda x: x.created_at, reverse=True)[:limit]
    return [_item_to_dict(i) for i in items]


def get_review_item(review_id: str) -> dict | None:
    """Get a specific review item by ID."""
    for item in _review_queue:
        if item.id == review_id:
            return _item_to_dict(item)
    return None


def submit_review(
    review_id: str,
    action: str,  # "approve" | "reject" | "correct"
    reviewer_notes: str = "",
    corrected_answer: str = "",
) -> dict | None:
    """Submit a human review decision."""
    for item in _review_queue:
        if item.id == review_id:
            if action == "approve":
                item.status = ReviewStatus.APPROVED
            elif action == "reject":
                item.status = ReviewStatus.REJECTED
            elif action == "correct":
                item.status = ReviewStatus.CORRECTED
                item.corrected_answer = corrected_answer
            else:
                return None

            item.reviewer_notes = reviewer_notes
            item.reviewed_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Review %s: %s by reviewer (notes: %s)",
                review_id, action, reviewer_notes[:50],
            )
            return _item_to_dict(item)
    return None


def get_review_stats() -> dict:
    """Get review queue statistics."""
    total = len(_review_queue)
    by_status = {}
    for s in ReviewStatus:
        count = sum(1 for i in _review_queue if i.status == s)
        by_status[s.value] = count

    avg_confidence = 0.0
    if total:
        avg_confidence = sum(i.confidence_score for i in _review_queue) / total

    return {
        "total": total,
        "by_status": by_status,
        "avg_confidence": round(avg_confidence, 4),
    }


def _item_to_dict(item: ReviewItem) -> dict:
    """Convert a ReviewItem to a serializable dict."""
    return {
        "id": item.id,
        "query": item.query,
        "answer": item.answer,
        "context_chunks": item.context_chunks,
        "confidence_score": item.confidence_score,
        "faithfulness_score": item.faithfulness_score,
        "trigger_reason": item.trigger_reason,
        "status": item.status.value,
        "reviewer_notes": item.reviewer_notes,
        "corrected_answer": item.corrected_answer,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
        "metadata": item.metadata,
    }
