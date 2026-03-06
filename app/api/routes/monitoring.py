"""Phase 4 API routes — system monitoring & alerting endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/health")
@limiter.limit("60/minute")
async def system_health(request: Request):
    """Get detailed system health snapshot with trend analysis."""
    from app.core.monitoring import get_system_health_snapshot
    return get_system_health_snapshot()


@router.get("/alerts")
@limiter.limit("60/minute")
async def list_alerts(request: Request, limit: int = 50):
    """Get recent system alerts."""
    from app.core.monitoring import get_alerts
    alerts = get_alerts(limit=limit)
    return {
        "count": len(alerts),
        "alerts": alerts,
    }


@router.delete("/alerts")
@limiter.limit("10/minute")
async def clear_alerts(request: Request):
    """Clear all alerts."""
    from app.core.monitoring import clear_alerts as _clear
    count = _clear()
    return {"cleared": count}
