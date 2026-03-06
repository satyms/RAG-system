"""System monitoring — drift detection, alerting, and autonomous health tracking."""

from __future__ import annotations

import logging
import time
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

MONITOR_DIR = settings.BASE_DIR / "evaluation" / "monitoring"
MONITOR_DIR.mkdir(parents=True, exist_ok=True)


# ── Rolling metric windows ──────────────────────────────────

_WINDOW_SIZE = 100  # Keep last N observations

_confidence_window: deque[float] = deque(maxlen=_WINDOW_SIZE)
_faithfulness_window: deque[float] = deque(maxlen=_WINDOW_SIZE)
_latency_window: deque[float] = deque(maxlen=_WINDOW_SIZE)
_retrieval_count_window: deque[int] = deque(maxlen=_WINDOW_SIZE)

# Alert state
_alerts: list[dict] = []


# ── Record metrics ───────────────────────────────────────────

def record_query_metrics(
    confidence: float | None = None,
    faithfulness: float | None = None,
    latency_ms: float | None = None,
    retrieval_count: int | None = None,
) -> None:
    """Record metrics from a query for drift detection."""
    if confidence is not None:
        _confidence_window.append(confidence)
    if faithfulness is not None:
        _faithfulness_window.append(faithfulness)
    if latency_ms is not None:
        _latency_window.append(latency_ms)
    if retrieval_count is not None:
        _retrieval_count_window.append(retrieval_count)

    # Check for anomalies after recording
    _check_drift()


# ── Drift detection ──────────────────────────────────────────

def _check_drift() -> None:
    """Check for metric drift and raise alerts."""
    now = datetime.now(timezone.utc).isoformat()

    # Confidence drift
    if len(_confidence_window) >= 20:
        recent = list(_confidence_window)[-10:]
        older = list(_confidence_window)[-20:-10]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if older_avg > 0 and (older_avg - recent_avg) / older_avg > 0.2:
            _raise_alert(
                "confidence_drift",
                f"Confidence dropped {((older_avg - recent_avg) / older_avg) * 100:.1f}%: "
                f"{older_avg:.3f} → {recent_avg:.3f}",
                severity="warning",
            )

    # Faithfulness drift
    if len(_faithfulness_window) >= 20:
        recent = list(_faithfulness_window)[-10:]
        older = list(_faithfulness_window)[-20:-10]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if older_avg > 0 and (older_avg - recent_avg) / older_avg > 0.2:
            _raise_alert(
                "faithfulness_drift",
                f"Faithfulness dropped: {older_avg:.3f} → {recent_avg:.3f}",
                severity="warning",
            )

    # Latency spike
    if len(_latency_window) >= 10:
        recent = list(_latency_window)[-5:]
        avg_latency = sum(recent) / len(recent)
        if avg_latency > 10000:  # >10s average
            _raise_alert(
                "latency_spike",
                f"Avg latency: {avg_latency:.0f}ms (last 5 queries)",
                severity="critical",
            )
        elif avg_latency > 5000:  # >5s
            _raise_alert(
                "high_latency",
                f"Avg latency: {avg_latency:.0f}ms (last 5 queries)",
                severity="warning",
            )

    # Empty retrievals
    if len(_retrieval_count_window) >= 10:
        recent = list(_retrieval_count_window)[-10:]
        zero_count = sum(1 for c in recent if c == 0)
        if zero_count >= 5:
            _raise_alert(
                "empty_retrievals",
                f"{zero_count}/10 recent queries returned 0 chunks",
                severity="warning",
            )


def _raise_alert(alert_type: str, message: str, severity: str = "info") -> None:
    """Create and store an alert."""
    # Deduplicate: don't raise same alert within 5 minutes
    recent_of_type = [
        a for a in _alerts
        if a["type"] == alert_type
        and (time.time() - a.get("_ts", 0)) < 300
    ]
    if recent_of_type:
        return

    alert = {
        "type": alert_type,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "_ts": time.time(),
    }
    _alerts.append(alert)
    logger.warning("ALERT [%s] %s: %s", severity, alert_type, message)


# ── Public API ───────────────────────────────────────────────

def get_alerts(severity: str | None = None, limit: int = 50) -> list[dict]:
    """Get recent alerts, optionally filtered by severity."""
    alerts = _alerts
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    # Remove internal timestamp
    return [
        {k: v for k, v in a.items() if not k.startswith("_")}
        for a in sorted(alerts, key=lambda x: x["timestamp"], reverse=True)[:limit]
    ]


def clear_alerts() -> int:
    """Clear all alerts. Returns count cleared."""
    count = len(_alerts)
    _alerts.clear()
    return count


def get_system_health_snapshot() -> dict:
    """Get a comprehensive snapshot of system metrics."""
    def _avg(d: deque) -> float | None:
        if not d:
            return None
        return round(sum(d) / len(d), 4)

    def _trend(d: deque) -> str:
        if len(d) < 20:
            return "insufficient_data"
        recent = sum(list(d)[-10:]) / 10
        older = sum(list(d)[-20:-10]) / 10
        if older == 0:
            return "stable"
        change = (recent - older) / older
        if change > 0.1:
            return "improving"
        if change < -0.1:
            return "degrading"
        return "stable"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": {
            "avg": _avg(_confidence_window),
            "samples": len(_confidence_window),
            "trend": _trend(_confidence_window),
        },
        "faithfulness": {
            "avg": _avg(_faithfulness_window),
            "samples": len(_faithfulness_window),
            "trend": _trend(_faithfulness_window),
        },
        "latency_ms": {
            "avg": _avg(_latency_window),
            "samples": len(_latency_window),
            "trend": _trend(_latency_window),
        },
        "retrieval": {
            "avg_chunks": _avg(_retrieval_count_window),
            "samples": len(_retrieval_count_window),
            "zero_rate": round(
                sum(1 for c in _retrieval_count_window if c == 0)
                / max(len(_retrieval_count_window), 1), 4
            ) if _retrieval_count_window else None,
        },
        "alerts": {
            "total": len(_alerts),
            "critical": sum(1 for a in _alerts if a["severity"] == "critical"),
            "warning": sum(1 for a in _alerts if a["severity"] == "warning"),
        },
    }


def save_snapshot() -> str:
    """Save current health snapshot to disk."""
    snapshot = get_system_health_snapshot()
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    path = MONITOR_DIR / f"snapshot_{ts}.json"
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
    return str(path)
