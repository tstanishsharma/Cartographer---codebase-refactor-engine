"""
Cartographer — Structured Logging Configuration.

Uses Structlog for structured, context-aware logging throughout the app.
In production, emits JSON. In development, emits colorized console output.

Usage:
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("event.name", key="value", another_key=123)
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "console"] = "json",
) -> None:
    """
    Configure structlog and stdlib logging globally.

    Must be called once at application startup before any log calls.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        fmt:   Output format — "json" for production, "console" for dev.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if fmt == "json":
        # Production: machine-readable JSON
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Development: human-readable colored output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # stdlib logging integration (for third-party libraries)
    formatter = structlog.stdlib.ProcessorFormatter(
        # Processors applied only to events coming from stdlib logging
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Convenience wrapper to get a bound structlog logger.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)  # type: ignore[return-value]
