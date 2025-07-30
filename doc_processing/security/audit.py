"""Security audit logging and monitoring."""

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"

    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"

    # Document processing events
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_CONVERTED = "document_converted"
    DOCUMENT_DELETED = "document_deleted"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    MALICIOUS_CONTENT = "malicious_content"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # System events
    SYSTEM_ERROR = "system_error"
    CONFIGURATION_CHANGE = "configuration_change"

    # Cache events
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_INVALIDATE = "cache_invalidate"


class AuditLevel(Enum):
    """Audit event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event."""

    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    level: AuditLevel = AuditLevel.INFO
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["level"] = self.level.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class SecurityAuditLogger:
    """Centralized security audit logging system."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """Initialize security audit logger.

        Args:
            log_file: Path to audit log file
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
        """
        self.log_file = log_file or Path("security_audit.log")
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.lock = threading.RLock()

        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Event counters for monitoring
        self.event_counters = {event_type: 0 for event_type in AuditEventType}

        # Recently logged events (for duplicate detection)
        self.recent_events = []
        self.max_recent_events = 1000

        # Configure file logger
        self._setup_file_logger()

    def _setup_file_logger(self):
        """Set up file logging with rotation."""
        from logging.handlers import RotatingFileHandler

        # Create file handler
        file_handler = RotatingFileHandler(
            self.log_file, maxBytes=self.max_file_size, backupCount=self.backup_count
        )

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Set up logger
        self.file_logger = logging.getLogger("security_audit")
        self.file_logger.setLevel(logging.INFO)
        self.file_logger.addHandler(file_handler)

    def log_event(self, event: AuditEvent) -> str:
        """Log an audit event.

        Args:
            event: AuditEvent to log

        Returns:
            Event ID for correlation
        """
        with self.lock:
            # Generate event ID
            event_id = self._generate_event_id(event)

            # Check for duplicate events
            if self._is_duplicate_event(event):
                logger.debug(
                    f"Duplicate audit event detected: {event.event_type.value}"
                )
                return event_id

            # Add to recent events
            self.recent_events.append(event)
            if len(self.recent_events) > self.max_recent_events:
                self.recent_events.pop(0)

            # Update counters
            self.event_counters[event.event_type] += 1

            # Log to file
            log_entry = {"event_id": event_id, "event": event.to_dict()}

            self.file_logger.info(json.dumps(log_entry))

            # Log to console for critical events
            if event.level in [AuditLevel.ERROR, AuditLevel.CRITICAL]:
                logger.error(f"Security audit: {event.message}")

            return event_id

    def _generate_event_id(self, event: AuditEvent) -> str:
        """Generate unique event ID."""
        # Use timestamp, event type, and user ID to create unique ID
        id_string = f"{event.timestamp.isoformat()}-{event.event_type.value}-{event.user_id or 'anonymous'}"
        return hashlib.sha256(id_string.encode()).hexdigest()[:16]

    def _is_duplicate_event(self, event: AuditEvent) -> bool:
        """Check if event is a duplicate of recent events."""
        # Simple duplicate detection based on event type and timestamp
        cutoff_time = datetime.now().timestamp() - 60  # 1 minute window

        for recent_event in self.recent_events[-50:]:  # Check last 50 events
            if (
                recent_event.event_type == event.event_type
                and recent_event.timestamp.timestamp() > cutoff_time
                and recent_event.user_id == event.user_id
                and recent_event.resource == event.resource
            ):
                return True

        return False

    def log_security_violation(
        self,
        violation_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """Log a security violation.

        Args:
            violation_type: Type of security violation
            user_id: User ID involved
            ip_address: IP address
            details: Additional details
        """
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            level=AuditLevel.WARNING,
            message=f"Security violation: {violation_type}",
            metadata=details,
        )

        self.log_event(event)

    def log_access_attempt(
        self,
        resource: str,
        action: str,
        user_id: Optional[str] = None,
        granted: bool = True,
        reason: Optional[str] = None,
    ):
        """Log an access attempt.

        Args:
            resource: Resource being accessed
            action: Action being performed
            user_id: User ID
            granted: Whether access was granted
            reason: Reason for denial if not granted
        """
        event_type = (
            AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED
        )
        level = AuditLevel.INFO if granted else AuditLevel.WARNING

        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=user_id,
            resource=resource,
            action=action,
            result="granted" if granted else "denied",
            level=level,
            message=f"Access {'granted' if granted else 'denied'} to {resource}",
            metadata={"reason": reason} if reason else None,
        )

        self.log_event(event)

    def log_document_operation(
        self,
        operation: str,
        document_id: str,
        user_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict] = None,
    ):
        """Log a document operation.

        Args:
            operation: Type of operation
            document_id: Document identifier
            user_id: User performing operation
            success: Whether operation was successful
            details: Additional details
        """
        event_type_map = {
            "upload": AuditEventType.DOCUMENT_UPLOADED,
            "process": AuditEventType.DOCUMENT_PROCESSED,
            "convert": AuditEventType.DOCUMENT_CONVERTED,
            "delete": AuditEventType.DOCUMENT_DELETED,
        }

        event_type = event_type_map.get(operation, AuditEventType.DOCUMENT_PROCESSED)
        level = AuditLevel.INFO if success else AuditLevel.ERROR

        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=user_id,
            resource=document_id,
            action=operation,
            result="success" if success else "failure",
            level=level,
            message=f"Document {operation}: {document_id}",
            metadata=details,
        )

        self.log_event(event)

    def log_malicious_content(
        self,
        content_type: str,
        threat_type: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """Log detection of malicious content.

        Args:
            content_type: Type of content
            threat_type: Type of threat detected
            user_id: User ID
            details: Additional details
        """
        event = AuditEvent(
            event_type=AuditEventType.MALICIOUS_CONTENT,
            timestamp=datetime.now(),
            user_id=user_id,
            level=AuditLevel.ERROR,
            message=f"Malicious content detected: {threat_type} in {content_type}",
            metadata=details,
        )

        self.log_event(event)

    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with audit summary
        """
        with self.lock:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            # Count events in time period
            recent_counts = {}
            for event in self.recent_events:
                if event.timestamp.timestamp() > cutoff_time:
                    event_type = event.event_type.value
                    recent_counts[event_type] = recent_counts.get(event_type, 0) + 1

            # Get security violations
            violations = [
                event
                for event in self.recent_events
                if (
                    event.event_type == AuditEventType.SECURITY_VIOLATION
                    and event.timestamp.timestamp() > cutoff_time
                )
            ]

            # Get failed access attempts
            failed_access = [
                event
                for event in self.recent_events
                if (
                    event.event_type == AuditEventType.ACCESS_DENIED
                    and event.timestamp.timestamp() > cutoff_time
                )
            ]

            return {
                "period_hours": hours,
                "total_events": len(
                    [
                        e
                        for e in self.recent_events
                        if e.timestamp.timestamp() > cutoff_time
                    ]
                ),
                "event_counts": recent_counts,
                "security_violations": len(violations),
                "failed_access_attempts": len(failed_access),
                "critical_events": len(
                    [
                        e
                        for e in self.recent_events
                        if e.level == AuditLevel.CRITICAL
                        and e.timestamp.timestamp() > cutoff_time
                    ]
                ),
            }

    def export_audit_log(
        self,
        output_file: Path,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
    ) -> int:
        """Export audit log to file.

        Args:
            output_file: Output file path
            start_time: Start time for export
            end_time: End time for export
            event_types: Event types to include

        Returns:
            Number of events exported
        """
        with self.lock:
            events_to_export = []

            for event in self.recent_events:
                # Filter by time range
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue

                # Filter by event types
                if event_types and event.event_type not in event_types:
                    continue

                events_to_export.append(event)

            # Write to file
            with open(output_file, "w") as f:
                for event in events_to_export:
                    f.write(event.to_json() + "\n")

            logger.info(
                f"Exported {len(events_to_export)} audit events to {output_file}"
            )
            return len(events_to_export)

    def get_suspicious_patterns(self) -> List[Dict[str, Any]]:
        """Analyze recent events for suspicious patterns.

        Returns:
            List of suspicious patterns detected
        """
        patterns = []

        # Check for repeated failed access attempts
        failed_attempts = {}
        for event in self.recent_events[-100:]:  # Check last 100 events
            if event.event_type == AuditEventType.ACCESS_DENIED:
                user_key = f"{event.user_id}:{event.ip_address}"
                failed_attempts[user_key] = failed_attempts.get(user_key, 0) + 1

        for user_key, count in failed_attempts.items():
            if count >= 5:  # 5 or more failed attempts
                patterns.append(
                    {
                        "pattern": "repeated_failed_access",
                        "details": f"User {user_key} has {count} failed access attempts",
                        "severity": "high",
                    }
                )

        # Check for multiple security violations
        violation_users = {}
        for event in self.recent_events[-100:]:
            if event.event_type == AuditEventType.SECURITY_VIOLATION:
                user_id = event.user_id or "anonymous"
                violation_users[user_id] = violation_users.get(user_id, 0) + 1

        for user_id, count in violation_users.items():
            if count >= 3:  # 3 or more violations
                patterns.append(
                    {
                        "pattern": "multiple_security_violations",
                        "details": f"User {user_id} has {count} security violations",
                        "severity": "high",
                    }
                )

        # Check for unusual activity patterns
        # (This would be more sophisticated in production)

        return patterns


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> SecurityAuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger


def audit_log(
    event_type: AuditEventType,
    message: str,
    user_id: Optional[str] = None,
    level: AuditLevel = AuditLevel.INFO,
    **kwargs,
) -> str:
    """Convenience function for logging audit events.

    Args:
        event_type: Type of audit event
        message: Event message
        user_id: User ID
        level: Event severity level
        **kwargs: Additional event fields

    Returns:
        Event ID
    """
    logger = get_audit_logger()

    event = AuditEvent(
        event_type=event_type,
        timestamp=datetime.now(),
        user_id=user_id,
        level=level,
        message=message,
        **kwargs,
    )

    return logger.log_event(event)
