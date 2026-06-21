"""Structured logging setup used by all services."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from shared.config import settings


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format ``record`` as JSON.

        Includes timestamp, level, logger name, message, and any extra fields
        attached to the record.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}",
        }

        # Merge extra fields added via logging.LoggerAdapter or extra=...
        for key in ("service", "trace_id", "request_id", "user_id", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger for the application.

    Args:
        level: Optional override log level. Defaults to ``settings.log_level``.
    """
    effective_level = (level or settings.log_level).upper()

    root = logging.getLogger()
    root.setLevel(effective_level)

    # Remove existing handlers to avoid duplicate logs during reconfiguration.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(effective_level)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)

    # Keep third-party libraries less chatty in production.
    if settings.is_production:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for the application.

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A standard library logger.
    """
    return logging.getLogger(name)
