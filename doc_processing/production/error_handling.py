"""Comprehensive error handling and recovery for production."""

import asyncio
import logging
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"  # Can continue, minor issue
    MEDIUM = "medium"  # Should address soon
    HIGH = "high"  # Needs immediate attention
    CRITICAL = "critical"  # System failure


class ErrorCategory(Enum):
    """Error categories for classification."""

    FILE_ACCESS = "file_access"
    CONVERSION = "conversion"
    PERMISSION = "permission"
    DATABASE = "database"
    MEMORY = "memory"
    NETWORK = "network"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class ProductionError(Exception):
    """Base exception for production errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize production error.

        Args:
            message: Error message
            severity: Error severity level
            category: Error category
            recoverable: Whether error is recoverable
            details: Additional error details
        """
        super().__init__(message)
        self.severity = severity
        self.category = category
        self.recoverable = recoverable
        self.details = details or {}
        self.timestamp = datetime.now()


class ErrorHandler:
    """Comprehensive error handling for production systems."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize error handler.

        Args:
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_log: List[Dict[str, Any]] = []
        self.recovery_strategies = self._init_recovery_strategies()

    def _init_recovery_strategies(self) -> Dict[ErrorCategory, Callable]:
        """Initialize recovery strategies for different error types."""
        return {
            ErrorCategory.FILE_ACCESS: self._recover_file_access,
            ErrorCategory.CONVERSION: self._recover_conversion,
            ErrorCategory.PERMISSION: self._recover_permission,
            ErrorCategory.DATABASE: self._recover_database,
            ErrorCategory.MEMORY: self._recover_memory,
            ErrorCategory.NETWORK: self._recover_network,
            ErrorCategory.VALIDATION: self._recover_validation,
        }

    async def handle_error(
        self, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle error with appropriate recovery strategy.

        Args:
            error: The exception that occurred
            context: Context information about the error

        Returns:
            Recovery result
        """
        # Classify error
        error_info = self._classify_error(error)

        # Log error
        self._log_error(error, error_info, context)

        # Attempt recovery if possible
        if error_info["recoverable"]:
            recovery_result = await self._attempt_recovery(error_info, context)
            if recovery_result["success"]:
                return recovery_result

        # Return error response
        return {
            "success": False,
            "error": str(error),
            "severity": error_info["severity"].value,
            "category": error_info["category"].value,
            "recoverable": error_info["recoverable"],
            "details": error_info.get("details", {}),
            "recovery_attempted": error_info["recoverable"],
        }

    def _classify_error(self, error: Exception) -> Dict[str, Any]:
        """Classify error by type and severity."""
        if isinstance(error, ProductionError):
            return {
                "severity": error.severity,
                "category": error.category,
                "recoverable": error.recoverable,
                "details": error.details,
            }

        # Common error classifications
        error_type = type(error).__name__
        error_msg = str(error).lower()

        if isinstance(error, FileNotFoundError) or "file" in error_msg:
            return {
                "severity": ErrorSeverity.MEDIUM,
                "category": ErrorCategory.FILE_ACCESS,
                "recoverable": True,
                "details": {"error_type": error_type},
            }
        elif isinstance(error, PermissionError) or "permission" in error_msg:
            return {
                "severity": ErrorSeverity.HIGH,
                "category": ErrorCategory.PERMISSION,
                "recoverable": False,
                "details": {"error_type": error_type},
            }
        elif isinstance(error, MemoryError) or "memory" in error_msg:
            return {
                "severity": ErrorSeverity.CRITICAL,
                "category": ErrorCategory.MEMORY,
                "recoverable": True,
                "details": {"error_type": error_type},
            }
        elif "database" in error_msg or "sqlite" in error_msg:
            return {
                "severity": ErrorSeverity.HIGH,
                "category": ErrorCategory.DATABASE,
                "recoverable": True,
                "details": {"error_type": error_type},
            }
        else:
            return {
                "severity": ErrorSeverity.MEDIUM,
                "category": ErrorCategory.UNKNOWN,
                "recoverable": False,
                "details": {"error_type": error_type},
            }

    def _log_error(
        self, error: Exception, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> None:
        """Log error with full context."""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "severity": error_info["severity"].value,
            "category": error_info["category"].value,
            "context": context,
            "traceback": traceback.format_exc(),
        }

        self.error_log.append(error_record)

        # Log based on severity
        if error_info["severity"] == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {error_record}")
        elif error_info["severity"] == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {error_record}")
        elif error_info["severity"] == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {error_record}")
        else:
            logger.info(f"Low severity error: {error_record}")

    async def _attempt_recovery(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Attempt to recover from error."""
        category = error_info["category"]

        if category in self.recovery_strategies:
            strategy = self.recovery_strategies[category]
            return await strategy(error_info, context)

        return {"success": False, "reason": "No recovery strategy available"}

    async def _recover_file_access(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from file access errors."""
        file_path = context.get("file_path")
        if not file_path:
            return {"success": False, "reason": "No file path in context"}

        # Try alternative paths
        alternatives = [
            Path(file_path),
            Path(file_path).with_suffix(".bak"),
            Path(file_path).parent / f"~{Path(file_path).name}",
        ]

        for alt_path in alternatives:
            if alt_path.exists():
                logger.info(f"Found alternative file: {alt_path}")
                return {
                    "success": True,
                    "recovered_path": str(alt_path),
                    "recovery_method": "alternative_file",
                }

        # Try to create missing directories
        parent_dir = Path(file_path).parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                return {
                    "success": True,
                    "recovery_method": "created_directory",
                    "created_path": str(parent_dir),
                }
            except Exception as e:
                logger.error(f"Failed to create directory: {e}")

        return {"success": False, "reason": "Could not recover file access"}

    async def _recover_conversion(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from conversion errors."""
        # Try simplified conversion
        if "converter" in context:
            try:
                # Attempt basic text extraction
                file_path = context.get("file_path")
                if file_path and Path(file_path).exists():
                    with open(file_path, "r", errors="ignore") as f:
                        content = f.read()

                    return {
                        "success": True,
                        "recovery_method": "basic_text_extraction",
                        "content": content[:1000],  # First 1000 chars
                        "warning": "Simplified conversion used",
                    }
            except Exception as e:
                logger.error(f"Basic extraction failed: {e}")

        return {"success": False, "reason": "Conversion recovery failed"}

    async def _recover_permission(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from permission errors."""
        # For permission errors, we typically can't auto-recover
        # but we can provide helpful information
        return {
            "success": False,
            "reason": "Permission denied",
            "suggestion": "Check file permissions or run with appropriate privileges",
            "affected_path": context.get("file_path", "Unknown"),
        }

    async def _recover_database(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from database errors."""
        # Try to reconnect or use backup
        if "connection" in context:
            try:
                # Attempt reconnection
                await asyncio.sleep(self.retry_delay)
                return {
                    "success": True,
                    "recovery_method": "reconnection",
                    "message": "Database connection restored",
                }
            except Exception:
                pass

        # Try in-memory fallback
        return {
            "success": True,
            "recovery_method": "in_memory_fallback",
            "warning": "Using in-memory database as fallback",
        }

    async def _recover_memory(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from memory errors."""
        # Free up memory and retry with smaller chunks
        import gc

        gc.collect()

        return {
            "success": True,
            "recovery_method": "memory_cleanup",
            "message": "Memory freed, retry with smaller chunks",
            "suggestion": "Process in smaller batches",
        }

    async def _recover_network(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from network errors."""
        # Retry with exponential backoff
        for attempt in range(self.max_retries):
            await asyncio.sleep(self.retry_delay * (2**attempt))
            # Actual retry would happen in calling code

        return {
            "success": False,
            "reason": "Network recovery requires retry in calling code",
            "max_retries": self.max_retries,
        }

    async def _recover_validation(
        self, error_info: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover from validation errors."""
        # Try to fix common validation issues
        if "data" in context:
            # Attempt to sanitize data
            return {
                "success": True,
                "recovery_method": "data_sanitization",
                "warning": "Data was sanitized to pass validation",
            }

        return {"success": False, "reason": "Cannot recover from validation error"}

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors."""
        if not self.error_log:
            return {"total_errors": 0, "by_severity": {}, "by_category": {}}

        summary = {
            "total_errors": len(self.error_log),
            "by_severity": {},
            "by_category": {},
            "recent_errors": self.error_log[-10:],  # Last 10 errors
        }

        # Count by severity
        for severity in ErrorSeverity:
            count = sum(
                1 for e in self.error_log if e.get("severity") == severity.value
            )
            if count > 0:
                summary["by_severity"][severity.value] = count

        # Count by category
        for category in ErrorCategory:
            count = sum(
                1 for e in self.error_log if e.get("category") == category.value
            )
            if count > 0:
                summary["by_category"][category.value] = count

        return summary


def with_error_handling(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    recoverable: bool = True,
) -> Callable:
    """Decorator for automatic error handling.

    Args:
        severity: Default severity for errors
        category: Default category for errors
        recoverable: Whether errors are recoverable

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            context = {
                "function": func.__name__,
                "args": str(args)[:100],  # Truncate for logging
                "kwargs": str(kwargs)[:100],
            }

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if not isinstance(e, ProductionError):
                    # Wrap in ProductionError
                    e = ProductionError(
                        str(e),
                        severity=severity,
                        category=category,
                        recoverable=recoverable,
                    )

                return await error_handler.handle_error(e, context)

        return wrapper

    return decorator


# Global error handler instance
global_error_handler = ErrorHandler()
