"""Structured logging configuration for the Knowledge Graph system.

This module configures structlog for consistent, machine-readable logging
across all components with proper context management and performance optimization.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict


def add_app_context(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application-specific context to log events."""
    event_dict["service"] = "kg-backend"
    event_dict["component"] = event_dict.get("logger", "unknown")
    return event_dict


def add_correlation_id(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add correlation ID for request tracing."""
    # Extract correlation ID from structlog context variables
    try:
        import structlog

        context_vars = structlog.contextvars.get_contextvars()
        correlation_id = context_vars.get("correlation_id")
        if correlation_id:
            event_dict["correlation_id"] = correlation_id
    except Exception:
        # If context extraction fails, just continue without correlation ID
        pass
    return event_dict


def configure_logging(
    environment: str = "development", log_level: str = "INFO", json_logs: bool = False
) -> None:
    """Configure structured logging for the application.

    Args:
        environment: Application environment (development/production)
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR)
        json_logs: Whether to output JSON format logs
    """
    # Configure stdlib logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Disable noisy loggers in production
    if environment == "production":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    # Determine output format based on environment
    if json_logs or environment == "production":
        # JSON output for production/monitoring systems
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-readable output for development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog processors
    processors = [
        # Built-in processors
        structlog.stdlib.filter_by_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        # Custom processors
        add_app_context,
        add_correlation_id,
        # Format and render
        structlog.processors.format_exc_info,
        renderer,
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured structured logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger instance
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables for request tracing.

    Args:
        **kwargs: Context variables to bind (e.g., correlation_id, user_id)
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


class StructlogMiddleware:
    """FastAPI middleware for request logging and context management."""

    def __init__(self, app: Any, logger_name: str = "kg.api.requests"):
        self.app = app
        self.logger = get_logger(logger_name)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Process request with logging context."""
        if scope["type"] == "http":
            # Generate correlation ID for request tracking
            import uuid

            correlation_id = str(uuid.uuid4())[:8]

            # Bind request context
            bind_context(
                correlation_id=correlation_id,
                method=scope["method"],
                path=scope["path"],
            )

            # Log request start
            self.logger.info(
                "Request started",
                method=scope["method"],
                path=scope["path"],
                correlation_id=correlation_id,
            )

            try:
                await self.app(scope, receive, send)

                # Log successful completion
                self.logger.info(
                    "Request completed",
                    correlation_id=correlation_id,
                )

            except Exception as e:
                # Log request failure
                self.logger.error(
                    "Request failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=correlation_id,
                )
                raise
            finally:
                # Clean up context
                clear_context()
        else:
            await self.app(scope, receive, send)


# Performance logging helpers for storage operations
class StorageOperationLogger:
    """Helper for logging storage operation performance and context."""

    def __init__(self, logger: structlog.stdlib.BoundLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time: float | None = None

    def __enter__(self) -> "StorageOperationLogger":
        import time

        self.start_time = time.perf_counter()
        self.logger.debug(
            "Storage operation started",
            operation=self.operation,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            import time

            duration = time.perf_counter() - self.start_time

            if exc_type is None:
                self.logger.info(
                    "Storage operation completed",
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                )
            else:
                self.logger.error(
                    "Storage operation failed",
                    operation=self.operation,
                    duration_ms=round(duration * 1000, 2),
                    error=str(exc_val),
                    error_type=exc_type.__name__ if exc_type else None,
                )

    def log_progress(self, message: str, **kwargs: Any) -> None:
        """Log operation progress with context."""
        self.logger.debug(
            message,
            operation=self.operation,
            **kwargs,
        )
