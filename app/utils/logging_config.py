"""Structured JSON logging configuration with request-ID support."""

from __future__ import annotations

import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit log records as JSON lines with optional extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Inject request_id from context variable if available
        try:
            from app.middleware.request_id import request_id_ctx
            rid = request_id_ctx.get("")
            if rid:
                log_entry["request_id"] = rid
        except Exception:
            pass

        # Merge extra keys set via logger.info("msg", extra={...})
        _STANDARD = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "pathname",
            "filename", "module", "levelno", "levelname", "message",
            "msecs", "thread", "threadName", "process", "processName",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _STANDARD and key not in log_entry:
                log_entry[key] = val

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(debug: bool = False) -> None:
    """Configure root logger with JSON format."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers
    root.handlers.clear()

    # Stdout handler — all logs
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    stdout_handler.setFormatter(JSONFormatter())
    stdout_handler.addFilter(lambda r: r.levelno < logging.ERROR)
    root.addHandler(stdout_handler)

    # Stderr handler — ERROR and above
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(JSONFormatter())
    root.addHandler(stderr_handler)

    # Quiet noisy libraries
    for lib in ("httpcore", "httpx", "urllib3", "asyncio", "multipart"):
        logging.getLogger(lib).setLevel(logging.WARNING)
