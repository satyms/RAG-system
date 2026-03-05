"""Evaluation endpoints — run retrieval metrics, manage ground truth, metric history."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.evaluation import run_evaluation, load_ground_truth, save_ground_truth
from app.core.scheduler import run_scheduled_evaluation, get_metric_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Evaluation"])


class GroundTruthEntry(BaseModel):
    query: str
    relevant_chunk_ids: list[str]


class EvalRequest(BaseModel):
    k: int = Field(default=5, ge=1, le=20)


@router.post("/evaluate")
async def evaluate(payload: EvalRequest) -> dict[str, Any]:
    """Run retrieval evaluation against ground truth dataset."""
    try:
        results = run_evaluation(k=payload.k)
    except Exception as exc:
        logger.exception("Evaluation failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return results


@router.post("/evaluate/scheduled")
async def evaluate_scheduled(payload: EvalRequest) -> dict[str, Any]:
    """Run scheduled evaluation with drift tracking and metric history."""
    try:
        results = run_scheduled_evaluation(k=payload.k)
    except Exception as exc:
        logger.exception("Scheduled evaluation failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return results


@router.get("/evaluate/history")
async def get_history() -> list[dict]:
    """Return metric history for trend analysis and drift detection."""
    return get_metric_history()


@router.get("/evaluate/ground-truth")
async def get_ground_truth() -> list[dict]:
    """Return the current ground truth evaluation dataset."""
    return load_ground_truth()


@router.post("/evaluate/ground-truth")
async def set_ground_truth(entries: list[GroundTruthEntry]) -> dict:
    """Upload/replace the ground truth evaluation dataset."""
    data = [e.model_dump() for e in entries]
    save_ground_truth(data)
    return {"saved": len(data)}
