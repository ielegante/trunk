"""Comprehensive error handling and production hardening for document processing."""

import logging
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from .security.audit import AuditEventType, AuditLevel, audit_log

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    VALIDATION = "validation"
    CONVERSION = "conversion"
    SECURITY = "security"
    PERFORMANCE = "performance"
    NETWORK = "network"
    SYSTEM = "system"
    USER = "user"
    CONFIGURATION = "configuration"


@dataclass
class ErrorContext:
    """Context information for error handling."""

    operation: str
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.context = context
        self.recoverable = recoverable
        self.timestamp = datetime.now()


class ValidationError(DocumentProcessingError):
    """Error in input validation."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.VALIDATION, **kwargs)
        self.field = field
        self.value = value


class ConversionError(DocumentProcessingError):
    """Error in document conversion."""

    def __init__(
        self,
        message: str,
        source_format: Optional[str] = None,
        target_format: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.CONVERSION, **kwargs)
        self.source_format = source_format
        self.target_format = target_format


class SecurityError(DocumentProcessingError):
    """Security-related error."""

    def __init__(self, message: str, threat_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SECURITY,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
        self.threat_type = threat_type


class PerformanceError(DocumentProcessingError):
    """Performance-related error."""

    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        threshold: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.PERFORMANCE, **kwargs)
        self.resource = resource
        self.threshold = threshold


class NetworkError(DocumentProcessingError):
    """Network-related error."""

    def __init__(self, message: str, endpoint: Optional[str] = None, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)
        self.endpoint = endpoint


class ErrorHandler:
    """Centralized error handling and recovery system."""

    def __init__(self, enable_audit: bool = True):
        """Initialize error handler.

        Args:
            enable_audit: Whether to enable audit logging
        """
        self.enable_audit = enable_audit
        self.error_stats = {
            "total_errors": 0,
            "by_category": {},
            "by_severity": {},
            "recovery_attempts": 0,
            "successful_recoveries": 0,
        }
        self.recovery_strategies = {}
        self._setup_default_strategies()

    def _setup_default_strategies(self):
        """Set up default recovery strategies."""
        self.recovery_strategies = {
            ValidationError: self._handle_validation_error,
            ConversionError: self._handle_conversion_error,
            SecurityError: self._handle_security_error,
            PerformanceError: self._handle_performance_error,
            NetworkError: self._handle_network_error,
        }

    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        suppress: bool = False,
    ) -> Optional[Any]:
        """Handle an error with appropriate strategy.

        Args:
            error: Exception to handle
            context: Error context
            suppress: Whether to suppress the error after handling

        Returns:
            Recovery result if applicable
        """
        # Update statistics
        self.error_stats["total_errors"] += 1

        # Determine error details
        if isinstance(error, DocumentProcessingError):
            category = error.category
            severity = error.severity
            if error.context:
                context = error.context
        else:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.MEDIUM

        # Update category and severity stats
        cat_key = category.value
        sev_key = severity.value
        self.error_stats["by_category"][cat_key] = (
            self.error_stats["by_category"].get(cat_key, 0) + 1
        )
        self.error_stats["by_severity"][sev_key] = (
            self.error_stats["by_severity"].get(sev_key, 0) + 1
        )

        # Log error details
        error_details = {
            "error_type": type(error).__name__,
            "message": str(error),
            "category": category.value,
            "severity": severity.value,
            "context": context.__dict__ if context else None,
            "traceback": traceback.format_exc(),
        }

        logger.error(f"Error handled: {error_details}")

        # Audit log for security and critical errors
        if self.enable_audit and severity in [
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
        ]:
            audit_log(
                AuditEventType.SYSTEM_ERROR,
                f"Error: {str(error)}",
                user_id=context.user_id if context else None,
                level=AuditLevel.ERROR,
                metadata=error_details,
            )

        # Try recovery
        recovery_result = None
        if isinstance(error, DocumentProcessingError) and error.recoverable:
            recovery_result = self._attempt_recovery(error, context)

        # Handle specific error types
        error_type = type(error)
        if error_type in self.recovery_strategies:
            try:
                self.recovery_strategies[error_type](error, context)
            except Exception as recovery_error:
                logger.error(f"Recovery strategy failed: {recovery_error}")

        # Re-raise if not suppressed
        if not suppress:
            raise error

        return recovery_result

    def _attempt_recovery(
        self, error: DocumentProcessingError, context: Optional[ErrorContext]
    ) -> Optional[Any]:
        """Attempt to recover from an error.

        Args:
            error: Error to recover from
            context: Error context

        Returns:
            Recovery result if successful
        """
        self.error_stats["recovery_attempts"] += 1

        try:
            # Implement recovery logic based on error type
            if isinstance(error, ConversionError):
                return self._recover_conversion_error(error, context)
            elif isinstance(error, ValidationError):
                return self._recover_validation_error(error, context)
            elif isinstance(error, NetworkError):
                return self._recover_network_error(error, context)

            return None

        except Exception as recovery_error:
            logger.error(f"Recovery failed: {recovery_error}")
            return None

    def _recover_conversion_error(
        self, error: ConversionError, context: Optional[ErrorContext]
    ) -> Optional[Any]:
        """Recover from conversion error."""
        # Try alternative conversion methods
        if error.source_format == "pd" and error.target_format == "markdown":
            logger.info("Attempting PDF recovery with alternative method")
            # Switch to different PDF library or OCR
            # This would integrate with the actual conversion logic
            return "recovery_attempted"

        return None

    def _recover_validation_error(
        self, error: ValidationError, context: Optional[ErrorContext]
    ) -> Optional[Any]:
        """Recover from validation error."""
        # Try to sanitize and re-validate
        if hasattr(error, "value") and error.value:
            from .security.sanitizer import DocumentSanitizer

            sanitized = DocumentSanitizer.sanitize_text(str(error.value))
            return sanitized

        return None

    def _recover_network_error(
        self, error: NetworkError, context: Optional[ErrorContext]
    ) -> Optional[Any]:
        """Recover from network error."""
        # Implement retry logic
        if hasattr(error, "endpoint"):
            logger.info(f"Attempting network recovery for {error.endpoint}")
            # This would implement actual retry logic
            return "retry_scheduled"

        return None

    def _handle_validation_error(
        self, error: ValidationError, context: Optional[ErrorContext]
    ):
        """Handle validation error."""
        logger.warning(f"Validation error: {error.message}")

        # Additional validation error handling
        if error.field:
            logger.info(f"Field validation failed: {error.field}")

    def _handle_conversion_error(
        self, error: ConversionError, context: Optional[ErrorContext]
    ):
        """Handle conversion error."""
        logger.error(f"Conversion error: {error.message}")

        # Log conversion failure details
        if error.source_format and error.target_format:
            logger.info(
                f"Failed conversion: {error.source_format} -> {error.target_format}"
            )

    def _handle_security_error(
        self, error: SecurityError, context: Optional[ErrorContext]
    ):
        """Handle security error."""
        logger.critical(f"Security error: {error.message}")

        # Additional security logging
        if self.enable_audit:
            audit_log(
                AuditEventType.SECURITY_VIOLATION,
                f"Security error: {error.message}",
                user_id=context.user_id if context else None,
                level=AuditLevel.CRITICAL,
                metadata={"threat_type": error.threat_type},
            )

    def _handle_performance_error(
        self, error: PerformanceError, context: Optional[ErrorContext]
    ):
        """Handle performance error."""
        logger.warning(f"Performance error: {error.message}")

        # Performance monitoring
        if error.resource and error.threshold:
            logger.info(
                f"Resource {error.resource} exceeded threshold {error.threshold}"
            )

    def _handle_network_error(
        self, error: NetworkError, context: Optional[ErrorContext]
    ):
        """Handle network error."""
        logger.error(f"Network error: {error.message}")

        # Network error handling
        if error.endpoint:
            logger.info(f"Network error for endpoint: {error.endpoint}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        return self.error_stats.copy()

    def reset_statistics(self):
        """Reset error statistics."""
        self.error_stats = {
            "total_errors": 0,
            "by_category": {},
            "by_severity": {},
            "recovery_attempts": 0,
            "successful_recoveries": 0,
        }


# Global error handler instance
_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return _error_handler


@contextmanager
def error_context(
    operation: str,
    user_id: Optional[str] = None,
    document_id: Optional[str] = None,
    **kwargs,
):
    """Context manager for error handling.

    Args:
        operation: Operation being performed
        user_id: User ID
        document_id: Document ID
        **kwargs: Additional context
    """
    context = ErrorContext(
        operation=operation, user_id=user_id, document_id=document_id, metadata=kwargs
    )

    try:
        yield context
    except Exception as e:
        _error_handler.handle_error(e, context, suppress=False)


def handle_errors(
    operation: str, suppress_errors: bool = False, recovery_attempts: int = 1
):
    """Decorator for automatic error handling.

    Args:
        operation: Operation name
        suppress_errors: Whether to suppress errors
        recovery_attempts: Number of recovery attempts
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_error = None

            while attempts <= recovery_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    attempts += 1

                    # Create context
                    context = ErrorContext(operation=operation)

                    # Try to extract user and document info from args/kwargs
                    if "user_id" in kwargs:
                        context.user_id = kwargs["user_id"]
                    if "document_id" in kwargs:
                        context.document_id = kwargs["document_id"]

                    # Handle error
                    if attempts > recovery_attempts:
                        _error_handler.handle_error(
                            e, context, suppress=suppress_errors
                        )
                        if not suppress_errors:
                            raise
                    else:
                        # Try recovery
                        recovery_result = _error_handler.handle_error(
                            e, context, suppress=True
                        )
                        if recovery_result is None:
                            # No recovery possible, fail
                            break
                        else:
                            # Recovery attempted, retry
                            time.sleep(0.1 * attempts)  # Brief delay before retry
                            continue

            # If we get here and suppress_errors is True, return None
            if suppress_errors:
                return None
            else:
                raise last_error

        return wrapper

    return decorator


def validate_input(validator: Callable, error_message: str = "Validation failed"):
    """Decorator for input validation.

    Args:
        validator: Validation function
        error_message: Error message for validation failure
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Validate arguments
                if not validator(*args, **kwargs):
                    raise ValidationError(error_message)

                return func(*args, **kwargs)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f"Validation error: {str(e)}")

        return wrapper

    return decorator


def timeout_handler(timeout_seconds: float):
    """Decorator for handling operation timeouts.

    Args:
        timeout_seconds: Timeout in seconds
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def timeout_handler(signum, frame):
                raise PerformanceError(
                    f"Operation timed out after {timeout_seconds} seconds",
                    resource="time",
                    threshold=timeout_seconds,
                )

            # Set up timeout
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Reset alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        return wrapper

    return decorator


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: float = 60):
    """Circuit breaker pattern for error handling.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time before attempting recovery
    """

    def decorator(func):
        # Circuit breaker state
        state = {"failures": 0, "last_failure": None, "is_open": False}

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if circuit is open
            if state["is_open"]:
                if (
                    state["last_failure"]
                    and (time.time() - state["last_failure"]) > recovery_timeout
                ):
                    # Try to close circuit
                    state["is_open"] = False
                    state["failures"] = 0
                else:
                    # Circuit still open
                    raise PerformanceError(
                        "Circuit breaker is open - service unavailable",
                        resource="circuit_breaker",
                    )

            try:
                result = func(*args, **kwargs)
                # Reset failure count on success
                state["failures"] = 0
                return result
            except Exception as e:
                # Increment failure count
                state["failures"] += 1
                state["last_failure"] = time.time()

                # Open circuit if threshold exceeded
                if state["failures"] >= failure_threshold:
                    state["is_open"] = True
                    logger.warning(f"Circuit breaker opened for {func.__name__}")

                raise

        return wrapper

    return decorator
