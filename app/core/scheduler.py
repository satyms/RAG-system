"""Background evaluation scheduler — periodic metric computation & drift tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.core.evaluation import run_evaluation, EVAL_DIR

logger = logging.getLogger(__name__)

# ── Metric history file ──────────────────────────────────────
_HISTORY_PATH = EVAL_DIR / "metric_history.json"


def _load_history() -> list[dict]:
    """Load metric history from disk."""
    if _HISTORY_PATH.exists():
        with open(_HISTORY_PATH) as f:
            return json.load(f)
    return []


def _save_history(history: list[dict]) -> None:
    """Persist metric history to disk."""
    with open(_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def _detect_drift(history: list[dict], window: int = 5, threshold: float = 0.1) -> dict | None:
    """
    Detect metric drift by comparing latest result against rolling average.

    Args:
        history: Full metric history list.
        window: Number of past runs to average.
        threshold: Minimum absolute drop to flag as drift.

    Returns:
        Drift report dict if drift detected, else None.
    """
    if len(history) < window + 1:
        return None

    latest = history[-1]
    past = history[-(window + 1):-1]

    drift_report: dict = {"timestamp": latest.get("timestamp"), "drifts": []}

    for metric in ("avg_precision_at_k", "avg_recall_at_k", "avg_mrr"):
        current_val = latest.get(metric, 0)
        avg_val = sum(h.get(metric, 0) for h in past) / len(past)

        if avg_val - current_val >= threshold:
            drift_report["drifts"].append({
                "metric": metric,
                "current": round(current_val, 4),
                "rolling_avg": round(avg_val, 4),
                "drop": round(avg_val - current_val, 4),
            })

    if drift_report["drifts"]:
        return drift_report
    return None


def run_scheduled_evaluation(k: int = 5) -> dict:
    """
    Run evaluation, append to metric history, check for drift.

    Returns:
        {
            "evaluation": <eval_results>,
            "drift_detected": bool,
            "drift_report": <report> | None,
            "history_length": int,
        }
    """
    logger.info("Scheduled evaluation starting …")

    try:
        results = run_evaluation(k=k)
    except Exception as exc:
        logger.exception("Scheduled evaluation failed")
        return {"error": str(exc)}

    if "error" in results:
        return results

    # Append summary to history
    history = _load_history()
    summary = {
        "timestamp": results["timestamp"],
        "avg_precision_at_k": results["avg_precision_at_k"],
        "avg_recall_at_k": results["avg_recall_at_k"],
        "avg_mrr": results["avg_mrr"],
        "num_queries": results["num_queries"],
        "k": results["k"],
        "config": results.get("config", {}),
    }
    history.append(summary)
    _save_history(history)

    # Drift detection
    drift_report = _detect_drift(history)
    if drift_report:
        logger.warning("METRIC DRIFT DETECTED: %s", json.dumps(drift_report, indent=2))

    logger.info(
        "Scheduled evaluation complete: P@%d=%.4f, R@%d=%.4f, MRR=%.4f (history=%d runs)",
        k, results["avg_precision_at_k"],
        k, results["avg_recall_at_k"],
        results["avg_mrr"],
        len(history),
    )

    return {
        "evaluation": results,
        "drift_detected": drift_report is not None,
        "drift_report": drift_report,
        "history_length": len(history),
    }


# ── Background loop ─────────────────────────────────────────

_scheduler_task: asyncio.Task | None = None


async def _eval_loop(interval_seconds: int, k: int) -> None:
    """Async loop that runs evaluation at fixed intervals."""
    logger.info("Background evaluation scheduler started (interval=%ds)", interval_seconds)

    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Background evaluation scheduler stopped.")
            break

        try:
            # Run evaluation in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_scheduled_evaluation, k)
            if result.get("drift_detected"):
                logger.warning("Drift alert — consider reviewing retrieval config.")
        except Exception:
            logger.exception("Background evaluation iteration failed")


def start_scheduler(interval_seconds: int = 86400, k: int = 5) -> None:
    """
    Start the background evaluation scheduler.

    Args:
        interval_seconds: Seconds between runs (default: 86400 = 24 hours).
        k: The K value for Precision@K / Recall@K.
    """
    global _scheduler_task

    if _scheduler_task and not _scheduler_task.done():
        logger.warning("Scheduler already running — skipping duplicate start.")
        return

    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_eval_loop(interval_seconds, k))
    logger.info("Background evaluation scheduler registered (every %ds)", interval_seconds)


def stop_scheduler() -> None:
    """Cancel the background evaluation scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Background evaluation scheduler cancelled.")


def get_metric_history() -> list[dict]:
    """Return the full metric history."""
    return _load_history()
