"""Comprehensive logging system for document processing."""

import json
import logging
import logging.handlers
import sys
import threading
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union


class LogLevel(Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Log formats."""

    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"


@dataclass
class LogContext:
    """Context information for logging."""

    operation_id: Optional[str] = None
    document_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    component: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add context information if available
        if self.include_context and hasattr(record, "context"):
            log_entry["context"] = record.context.to_dict()

        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
                "context",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


class StructuredFormatter(logging.Formatter):
    """Structured log formatter."""

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record in structured format."""
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        # Base format
        parts = [
            f"[{timestamp}]",
            f"[{record.levelname}]",
            f"[{record.name}]",
            f"[{record.module}:{record.funcName}:{record.lineno}]",
        ]

        # Add context if available
        if self.include_context and hasattr(record, "context"):
            context = record.context.to_dict()
            if context:
                context_str = " ".join(f"{k}={v}" for k, v in context.items())
                parts.append(f"[{context_str}]")

        # Add message
        parts.append(record.getMessage())

        # Add exception if present
        if record.exc_info:
            parts.append(f"\nException: {record.exc_info[1]}")
            parts.append(f"Traceback: {traceback.format_exception(*record.exc_info)}")

        return " ".join(parts)


class ContextualLogger:
    """Logger with contextual information."""

    def __init__(self, logger: logging.Logger, context: Optional[LogContext] = None):
        self.logger = logger
        self.context = context or LogContext()
        self.local = threading.local()

    def _get_record_with_context(
        self, level: int, msg: str, *args, **kwargs
    ) -> logging.LogRecord:
        """Create log record with context."""
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown file)",
            0,
            msg,
            args,
            kwargs.get("exc_info"),
            kwargs.get("func"),
            kwargs.get("extra"),
            kwargs.get("stack_info"),
        )

        # Add context to record
        record.context = self.context

        return record

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        if self.logger.isEnabledFor(logging.DEBUG):
            record = self._get_record_with_context(logging.DEBUG, msg, *args, **kwargs)
            self.logger.handle(record)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        if self.logger.isEnabledFor(logging.INFO):
            record = self._get_record_with_context(logging.INFO, msg, *args, **kwargs)
            self.logger.handle(record)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        if self.logger.isEnabledFor(logging.WARNING):
            record = self._get_record_with_context(
                logging.WARNING, msg, *args, **kwargs
            )
            self.logger.handle(record)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        if self.logger.isEnabledFor(logging.ERROR):
            record = self._get_record_with_context(logging.ERROR, msg, *args, **kwargs)
            self.logger.handle(record)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message."""
        if self.logger.isEnabledFor(logging.CRITICAL):
            record = self._get_record_with_context(
                logging.CRITICAL, msg, *args, **kwargs
            )
            self.logger.handle(record)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self.error(msg, *args, **kwargs)

    def with_context(self, **context_updates) -> "ContextualLogger":
        """Create new logger with updated context."""
        new_context = LogContext(**{**asdict(self.context), **context_updates})
        return ContextualLogger(self.logger, new_context)


class LogManager:
    """Manages logging configuration and loggers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize log manager.

        Args:
            config: Logging configuration
        """
        self.config = config or {}
        self.loggers: Dict[str, logging.Logger] = {}
        self.handlers: Dict[str, logging.Handler] = {}
        self.formatters: Dict[str, logging.Formatter] = {}
        self.lock = threading.RLock()

        # Configuration
        self.log_level = self.config.get("level", "INFO")
        self.log_format = self.config.get("format", "json")
        self.log_file = self.config.get("file", "app.log")
        self.max_size_mb = self.config.get("max_size_mb", 100)
        self.backup_count = self.config.get("backup_count", 5)
        self.include_context = self.config.get("include_context", True)

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Set up logging configuration."""
        # Create formatters
        if self.log_format == "json":
            formatter = JSONFormatter(include_context=self.include_context)
        elif self.log_format == "structured":
            formatter = StructuredFormatter(include_context=self.include_context)
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        self.formatters["default"] = formatter

        # Create handlers
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.handlers["console"] = console_handler

        # File handler
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self.max_size_mb * 1024 * 1024,
                backupCount=self.backup_count,
            )
            file_handler.setFormatter(formatter)
            self.handlers["file"] = file_handler

        # Error file handler
        if self.log_file:
            error_log_path = log_path.with_suffix(".error.log")
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_path,
                maxBytes=self.max_size_mb * 1024 * 1024,
                backupCount=self.backup_count,
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            self.handlers["error"] = error_handler

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level.upper()))

        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add our handlers
        for handler in self.handlers.values():
            root_logger.addHandler(handler)

    def get_logger(
        self, name: str, context: Optional[LogContext] = None
    ) -> ContextualLogger:
        """Get a contextual logger.

        Args:
            name: Logger name
            context: Log context

        Returns:
            Contextual logger
        """
        with self.lock:
            if name not in self.loggers:
                self.loggers[name] = logging.getLogger(name)

            return ContextualLogger(self.loggers[name], context)

    def add_handler(self, name: str, handler: logging.Handler):
        """Add a logging handler.

        Args:
            name: Handler name
            handler: Logging handler
        """
        with self.lock:
            self.handlers[name] = handler

            # Add to all existing loggers
            for logger in self.loggers.values():
                logger.addHandler(handler)

    def remove_handler(self, name: str):
        """Remove a logging handler.

        Args:
            name: Handler name
        """
        with self.lock:
            if name in self.handlers:
                handler = self.handlers[name]

                # Remove from all loggers
                for logger in self.loggers.values():
                    logger.removeHandler(handler)

                # Close handler
                handler.close()
                del self.handlers[name]

    def set_level(self, level: Union[str, int]):
        """Set logging level for all loggers.

        Args:
            level: Log level
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper())

        with self.lock:
            for logger in self.loggers.values():
                logger.setLevel(level)

    def flush_all(self):
        """Flush all handlers."""
        with self.lock:
            for handler in self.handlers.values():
                if hasattr(handler, "flush"):
                    handler.flush()

    def close_all(self):
        """Close all handlers."""
        with self.lock:
            for handler in self.handlers.values():
                handler.close()

    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics.

        Returns:
            Dictionary with logging statistics
        """
        stats = {
            "total_loggers": len(self.loggers),
            "total_handlers": len(self.handlers),
            "log_level": self.log_level,
            "log_format": self.log_format,
            "handlers": {},
        }

        for name, handler in self.handlers.items():
            handler_stats = {
                "type": type(handler).__name__,
                "level": handler.level,
                "formatter": (
                    type(handler.formatter).__name__ if handler.formatter else None
                ),
            }

            # Add file-specific stats
            if hasattr(handler, "baseFilename"):
                handler_stats["file"] = handler.baseFilename
                try:
                    file_path = Path(handler.baseFilename)
                    if file_path.exists():
                        handler_stats["file_size_mb"] = file_path.stat().st_size / (
                            1024 * 1024
                        )
                except Exception:
                    pass

            stats["handlers"][name] = handler_stats

        return stats


# Global log manager instance
log_manager = LogManager()


def configure_logging(config: Dict[str, Any]):
    """Configure the global log manager.

    Args:
        config: Logging configuration
    """
    global log_manager
    log_manager = LogManager(config)


def get_logger(name: str, context: Optional[LogContext] = None) -> ContextualLogger:
    """Get a contextual logger from the global manager.

    Args:
        name: Logger name
        context: Log context

    Returns:
        Contextual logger
    """
    return log_manager.get_logger(name, context)


@contextmanager
def log_context(**context_updates):
    """Context manager for temporary log context.

    Args:
        **context_updates: Context updates
    """
    # This is a simplified version - in practice, you'd want to use thread-local storage
    # to maintain context across different parts of the application
    yield


def log_operation(operation_name: str, logger: Optional[ContextualLogger] = None):
    """Decorator for logging operations.

    Args:
        operation_name: Name of the operation
        logger: Logger to use
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            op_logger = logger or get_logger(func.__module__)
            operation_id = str(uuid.uuid4())

            op_logger = op_logger.with_context(
                operation_id=operation_id,
                operation_name=operation_name,
                function=func.__name__,
            )

            op_logger.info(f"Starting operation: {operation_name}")
            start_time = datetime.now()

            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                op_logger.info(
                    f"Operation completed: {operation_name} (duration: {duration:.2f}s)"
                )
                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                op_logger.error(
                    f"Operation failed: {operation_name} (duration: {duration:.2f}s)",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_performance(threshold_seconds: float = 1.0):
    """Decorator for logging performance issues.

    Args:
        threshold_seconds: Performance threshold in seconds
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = datetime.now()

            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()

                if duration > threshold_seconds:
                    logger.warning(
                        f"Slow operation: {func.__name__} took {duration:.2f}s (threshold: {threshold_seconds}s)"
                    )

                return result

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Operation failed after {duration:.2f}s: {func.__name__}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
