"""Phase 4 API routes -- adversarial stress testing endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/adversarial", tags=["Adversarial Testing"])


@router.post("/injection")
@limiter.limit("5/minute")
async def run_injection_tests(request: Request):
    """Run prompt-injection stress tests against the RAG pipeline."""
    from app.core.adversarial import run_injection_tests as _run
    # Execute synchronous test suite off the event loop
    results = await asyncio.to_thread(_run)
    return {"tests": results, "count": len(results)}


@router.post("/bias")
@limiter.limit("5/minute")
async def run_bias_tests(request: Request):
    """Run bias detection tests."""
    from app.core.adversarial import run_bias_tests as _run
    results = await asyncio.to_thread(_run)
    return {"tests": results, "count": len(results)}


@router.post("/safety")
@limiter.limit("5/minute")
async def run_safety_tests(request: Request):
    """Run safety & boundary tests."""
    from app.core.adversarial import run_safety_tests as _run
    results = await asyncio.to_thread(_run)
    return {"tests": results, "count": len(results)}


@router.post("/full")
@limiter.limit("2/minute")
async def run_full_stress(request: Request):
    """Run all adversarial test suites and save a report."""
    from app.core.adversarial import run_full_stress_test as _run
    report = await asyncio.to_thread(_run)
    return report
