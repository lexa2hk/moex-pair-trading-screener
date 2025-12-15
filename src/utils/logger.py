"""Logging configuration and setup."""

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog


def _get_console_renderer():
    """Return a human-readable console renderer with colors."""
    return structlog.dev.ConsoleRenderer(
        colors=True,
        exception_formatter=structlog.dev.rich_traceback,
        pad_event=40,  # Align events for readability
    )


def _get_file_renderer():
    """Return a plain text renderer for file logging (no colors)."""
    return structlog.dev.ConsoleRenderer(
        colors=False,
        exception_formatter=structlog.dev.plain_traceback,
        pad_event=40,
    )


def _get_shared_processors():
    """Return shared processors for structlog."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
) -> structlog.stdlib.BoundLogger:
    """
    Set up structured logging using stdlib integration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file

    Returns:
        Configured structlog logger instance
    """
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)
    shared_processors = _get_shared_processors()

    # Console formatter with colors
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=_get_console_renderer(),
        foreign_pre_chain=shared_processors,
    )

    # File formatter without colors
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=_get_file_renderer(),
        foreign_pre_chain=shared_processors,
    )

    # Set up handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    handlers = [console_handler]

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        handlers=handlers,
        level=level,
        force=True,  # Reset handlers each time to allow test isolation
    )

    # Silence noisy third-party loggers that don't play well with structlog
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    # Configure structlog to use stdlib logger factory
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name

    Returns:
        Logger instance
    """
    return structlog.get_logger(name)

