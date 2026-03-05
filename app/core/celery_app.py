"""Celery application — background task queue for ingestion pipeline."""

from __future__ import annotations

import os
import logging

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# ── Celery app ───────────────────────────────────────────────
celery_app = Celery(
    "rag_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,
    # Beat schedule (periodic tasks)
    beat_schedule={
        "periodic-evaluation": {
            "task": "app.core.tasks.run_periodic_evaluation",
            "schedule": int(os.environ.get("EVAL_INTERVAL_SECONDS", 86400)),
        },
    },
)
