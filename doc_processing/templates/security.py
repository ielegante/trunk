"""Security controls and access management for template system."""

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security levels for templates and operations."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class PermissionType(Enum):
    """Permission types for template operations."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class SecurityContext:
    """Security context for template operations."""

    user_id: str
    organization: str
    security_clearance: SecurityLevel
    roles: List[str]
    permissions: List[PermissionType]
    session_token: str
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if security context is valid."""
        return datetime.now() < self.expires_at

    def has_permission(self, permission: PermissionType) -> bool:
        """Check if context has specific permission."""
        return (
            permission in self.permissions or PermissionType.ADMIN in self.permissions
        )

    def can_access_security_level(self, level: SecurityLevel) -> bool:
        """Check if context can access given security level."""
        level_hierarchy = {
            SecurityLevel.PUBLIC: 0,
            SecurityLevel.INTERNAL: 1,
            SecurityLevel.CONFIDENTIAL: 2,
            SecurityLevel.RESTRICTED: 3,
            SecurityLevel.TOP_SECRET: 4,
        }

        user_level = level_hierarchy.get(self.security_clearance, 0)
        required_level = level_hierarchy.get(level, 0)

        return user_level >= required_level


@dataclass
class AccessRule:
    """Access control rule for templates."""

    rule_id: str
    resource_pattern: str  # Regex pattern for matching resources
    required_roles: List[str]
    required_permissions: List[PermissionType]
    security_level: SecurityLevel
    conditions: Dict[str, Any]  # Additional conditions (time, IP, etc.)
    is_active: bool = True

    def matches_resource(self, resource_path: str) -> bool:
        """Check if rule matches given resource."""
        try:
            return bool(re.match(self.resource_pattern, resource_path))
        except re.error:
            logger.error(
                f"Invalid regex pattern in rule {self.rule_id}: {self.resource_pattern}"
            )
            return False

    def evaluate(self, context: SecurityContext, resource_path: str) -> bool:
        """Evaluate if context satisfies this access rule."""
        if not self.is_active:
            return False

        if not self.matches_resource(resource_path):
            return False

        # Check security level
        if not context.can_access_security_level(self.security_level):
            return False

        # Check roles
        if self.required_roles:
            if not any(role in context.roles for role in self.required_roles):
                return False

        # Check permissions
        if self.required_permissions:
            if not any(
                context.has_permission(perm) for perm in self.required_permissions
            ):
                return False

        # Check additional conditions
        if self.conditions:
            if not self._evaluate_conditions(context):
                return False

        return True

    def _evaluate_conditions(self, context: SecurityContext) -> bool:
        """Evaluate additional access conditions."""
        conditions = self.conditions

        # Time-based conditions
        if "allowed_hours" in conditions:
            current_hour = datetime.now().hour
            allowed_hours = conditions["allowed_hours"]
            if current_hour not in allowed_hours:
                return False

        # IP-based conditions
        if "allowed_ips" in conditions and context.ip_address:
            allowed_ips = conditions["allowed_ips"]
            if context.ip_address not in allowed_ips:
                return False

        # Organization-based conditions
        if "allowed_organizations" in conditions:
            allowed_orgs = conditions["allowed_organizations"]
            if context.organization not in allowed_orgs:
                return False

        return True


@dataclass
class AuditEvent:
    """Audit log event for template operations."""

    event_id: str
    timestamp: datetime
    user_id: str
    organization: str
    operation: str
    resource: str
    result: str  # success, failure, denied
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class SecurityManager:
    """Manages security controls for template system."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize security manager.

        Args:
            config: Security configuration options
        """
        self.config = config or {}

        # Security settings
        self.session_timeout_hours = self.config.get("session_timeout_hours", 8)
        self.max_failed_attempts = self.config.get("max_failed_attempts", 5)
        self.lockout_duration_minutes = self.config.get("lockout_duration_minutes", 30)
        self.require_mfa = self.config.get("require_mfa", False)
        self.audit_enabled = self.config.get("audit_enabled", True)

        # Storage
        self.access_rules: Dict[str, AccessRule] = {}
        self.audit_log: List[AuditEvent] = []
        self.failed_attempts: Dict[str, List[datetime]] = {}
        self.locked_users: Dict[str, datetime] = {}

        # Initialize default security rules
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Initialize default security access rules."""
        default_rules = [
            AccessRule(
                rule_id="public_read",
                resource_pattern=r"templates/public/.*",
                required_roles=[],
                required_permissions=[PermissionType.READ],
                security_level=SecurityLevel.PUBLIC,
            ),
            AccessRule(
                rule_id="internal_access",
                resource_pattern=r"templates/internal/.*",
                required_roles=["employee"],
                required_permissions=[PermissionType.READ],
                security_level=SecurityLevel.INTERNAL,
            ),
            AccessRule(
                rule_id="confidential_access",
                resource_pattern=r"templates/confidential/.*",
                required_roles=["lawyer", "paralegal", "partner"],
                required_permissions=[PermissionType.READ],
                security_level=SecurityLevel.CONFIDENTIAL,
            ),
            AccessRule(
                rule_id="admin_full_access",
                resource_pattern=r"templates/.*",
                required_roles=["admin"],
                required_permissions=[PermissionType.ADMIN],
                security_level=SecurityLevel.PUBLIC,  # Admin can access any level
            ),
        ]

        for rule in default_rules:
            self.access_rules[rule.rule_id] = rule

    def create_security_context(
        self,
        user_id: str,
        organization: str,
        security_clearance: SecurityLevel,
        roles: List[str],
        permissions: List[PermissionType],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SecurityContext:
        """Create a new security context with session token.

        Args:
            user_id: User identifier
            organization: User's organization
            security_clearance: User's security clearance level
            roles: User's roles
            permissions: User's permissions
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            SecurityContext with session token
        """
        # Check if user is locked out
        if self._is_user_locked(user_id):
            raise SecurityError(
                f"User {user_id} is temporarily locked due to failed attempts"
            )

        # Generate secure session token
        session_token = self._generate_session_token(user_id)

        # Set expiration
        expires_at = datetime.now() + timedelta(hours=self.session_timeout_hours)

        context = SecurityContext(
            user_id=user_id,
            organization=organization,
            security_clearance=security_clearance,
            roles=roles,
            permissions=permissions,
            session_token=session_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Log authentication
        self._audit_log(
            "authentication",
            "success",
            user_id,
            organization,
            {
                "security_clearance": security_clearance.value,
                "roles": roles,
                "session_expires": expires_at.isoformat(),
            },
            ip_address,
            user_agent,
        )

        return context

    def _generate_session_token(self, user_id: str) -> str:
        """Generate secure session token."""
        # Create token payload
        timestamp = datetime.now().timestamp()
        random_bytes = secrets.token_bytes(16)

        # Combine user_id, timestamp, and random data
        token_data = f"{user_id}:{timestamp}:{random_bytes.hex()}"

        # Create HMAC signature
        secret_key = self.config.get("secret_key", "default_secret_key").encode()
        signature = hmac.new(
            secret_key, token_data.encode(), hashlib.sha256
        ).hexdigest()

        return f"{token_data}:{signature}"

    def validate_session_token(self, token: str, user_id: str) -> bool:
        """Validate session token."""
        try:
            parts = token.split(":")
            if len(parts) != 4:
                return False

            token_user_id, timestamp_str, random_hex, signature = parts

            # Verify user ID matches
            if token_user_id != user_id:
                return False

            # Verify signature
            token_data = f"{token_user_id}:{timestamp_str}:{random_hex}"
            secret_key = self.config.get("secret_key", "default_secret_key").encode()
            expected_signature = hmac.new(
                secret_key, token_data.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False

            # Check token age
            token_timestamp = float(timestamp_str)
            token_age_hours = (datetime.now().timestamp() - token_timestamp) / 3600

            if token_age_hours > self.session_timeout_hours:
                return False

            return True

        except (ValueError, TypeError):
            return False

    def check_access(
        self, context: SecurityContext, resource_path: str, operation: PermissionType
    ) -> bool:
        """Check if security context has access to resource.

        Args:
            context: Security context
            resource_path: Path to resource being accessed
            operation: Operation being performed

        Returns:
            True if access is granted
        """
        # Validate context
        if not context.is_valid():
            self._audit_log(
                "access_check",
                "failure",
                context.user_id,
                context.organization,
                {
                    "resource": resource_path,
                    "operation": operation.value,
                    "reason": "expired_session",
                },
                context.ip_address,
                context.user_agent,
            )
            return False

        # Check if user is locked
        if self._is_user_locked(context.user_id):
            self._audit_log(
                "access_check",
                "failure",
                context.user_id,
                context.organization,
                {
                    "resource": resource_path,
                    "operation": operation.value,
                    "reason": "user_locked",
                },
                context.ip_address,
                context.user_agent,
            )
            return False

        # Check basic permission
        if not context.has_permission(operation):
            self._audit_log(
                "access_check",
                "denied",
                context.user_id,
                context.organization,
                {
                    "resource": resource_path,
                    "operation": operation.value,
                    "reason": "insufficient_permissions",
                },
                context.ip_address,
                context.user_agent,
            )
            return False

        # Evaluate access rules
        for rule in self.access_rules.values():
            if rule.evaluate(context, resource_path):
                self._audit_log(
                    "access_check",
                    "success",
                    context.user_id,
                    context.organization,
                    {
                        "resource": resource_path,
                        "operation": operation.value,
                        "rule": rule.rule_id,
                    },
                    context.ip_address,
                    context.user_agent,
                )
                return True

        # No matching rule found
        self._audit_log(
            "access_check",
            "denied",
            context.user_id,
            context.organization,
            {
                "resource": resource_path,
                "operation": operation.value,
                "reason": "no_matching_rule",
            },
            context.ip_address,
            context.user_agent,
        )

        return False

    def add_access_rule(self, rule: AccessRule):
        """Add a new access control rule."""
        self.access_rules[rule.rule_id] = rule

    def remove_access_rule(self, rule_id: str):
        """Remove an access control rule."""
        if rule_id in self.access_rules:
            del self.access_rules[rule_id]

    def _is_user_locked(self, user_id: str) -> bool:
        """Check if user is currently locked out."""
        if user_id not in self.locked_users:
            return False

        lock_time = self.locked_users[user_id]
        unlock_time = lock_time + timedelta(minutes=self.lockout_duration_minutes)

        if datetime.now() >= unlock_time:
            # Unlock user
            del self.locked_users[user_id]
            if user_id in self.failed_attempts:
                del self.failed_attempts[user_id]
            return False

        return True

    def record_failed_attempt(self, user_id: str):
        """Record a failed authentication attempt."""
        now = datetime.now()

        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []

        self.failed_attempts[user_id].append(now)

        # Remove old attempts (older than 1 hour)
        cutoff_time = now - timedelta(hours=1)
        self.failed_attempts[user_id] = [
            attempt
            for attempt in self.failed_attempts[user_id]
            if attempt > cutoff_time
        ]

        # Check if user should be locked
        if len(self.failed_attempts[user_id]) >= self.max_failed_attempts:
            self.locked_users[user_id] = now

            self._audit_log(
                "user_lockout",
                "locked",
                user_id,
                "",
                {
                    "failed_attempts": len(self.failed_attempts[user_id]),
                    "lockout_duration_minutes": self.lockout_duration_minutes,
                },
            )

    def _audit_log(
        self,
        operation: str,
        result: str,
        user_id: str,
        organization: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log audit event."""
        if not self.audit_enabled:
            return

        event = AuditEvent(
            event_id=secrets.token_hex(16),
            timestamp=datetime.now(),
            user_id=user_id,
            organization=organization,
            operation=operation,
            resource=details.get("resource", ""),
            result=result,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.audit_log.append(event)

        # Log to system logger as well
        logger.info(
            f"AUDIT: {operation} {result} - User: {user_id}, Resource: {event.resource}"
        )

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get filtered audit log entries.

        Args:
            user_id: Filter by user ID
            operation: Filter by operation type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of entries to return

        Returns:
            List of matching audit events
        """
        filtered_events = []

        for event in self.audit_log:
            # Apply filters
            if user_id and event.user_id != user_id:
                continue

            if operation and event.operation != operation:
                continue

            if start_time and event.timestamp < start_time:
                continue

            if end_time and event.timestamp > end_time:
                continue

            filtered_events.append(event)

            if len(filtered_events) >= limit:
                break

        return filtered_events

    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics and statistics.

        Returns:
            Dictionary with security metrics
        """
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        # Count events in last 24 hours
        recent_events = [e for e in self.audit_log if e.timestamp > last_24h]

        return {
            "active_rules": len(self.access_rules),
            "total_audit_events": len(self.audit_log),
            "events_last_24h": len(recent_events),
            "locked_users": len(self.locked_users),
            "users_with_failed_attempts": len(self.failed_attempts),
            "security_events": {
                "authentication_success": len(
                    [
                        e
                        for e in recent_events
                        if e.operation == "authentication" and e.result == "success"
                    ]
                ),
                "authentication_failure": len(
                    [
                        e
                        for e in recent_events
                        if e.operation == "authentication" and e.result == "failure"
                    ]
                ),
                "access_denied": len(
                    [
                        e
                        for e in recent_events
                        if e.operation == "access_check" and e.result == "denied"
                    ]
                ),
                "user_lockouts": len(
                    [e for e in recent_events if e.operation == "user_lockout"]
                ),
            },
        }


class SecurityError(Exception):
    """Security-related error."""

    pass


class SecureTemplateValidator:
    """Validates templates for security issues."""

    def __init__(self):
        """Initialize security validator."""
        # Patterns for detecting sensitive information
        self.sensitive_patterns = {
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            "api_key": re.compile(r"\b[A-Za-z0-9]{32,}\b"),
            "password": re.compile(r"password\s*[:=]\s*[^\s]+", re.IGNORECASE),
            "secret": re.compile(r"secret\s*[:=]\s*[^\s]+", re.IGNORECASE),
            "token": re.compile(r"token\s*[:=]\s*[^\s]+", re.IGNORECASE),
        }

        # Dangerous template constructs
        self.dangerous_patterns = {
            "script_tag": re.compile(
                r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", re.IGNORECASE
            ),
            "eval_function": re.compile(r"\beval\s*\(", re.IGNORECASE),
            "exec_function": re.compile(r"\bexec\s*\(", re.IGNORECASE),
            "import_statement": re.compile(r"\bimport\s+\w+", re.IGNORECASE),
            "file_operation": re.compile(
                r"\b(open|read|write|delete)\s*\(", re.IGNORECASE
            ),
        }

    def validate_template_content(self, content: str) -> Dict[str, Any]:
        """Validate template content for security issues.

        Args:
            content: Template content to validate

        Returns:
            Validation results with security findings
        """
        findings = {
            "is_safe": True,
            "sensitive_data": [],
            "dangerous_constructs": [],
            "warnings": [],
            "severity": "low",
        }

        # Check for sensitive information
        for pattern_name, pattern in self.sensitive_patterns.items():
            matches = pattern.findall(content)
            if matches:
                findings["sensitive_data"].append(
                    {
                        "type": pattern_name,
                        "matches": matches[:5],  # Limit to first 5 matches
                        "count": len(matches),
                    }
                )
                findings["is_safe"] = False

        # Check for dangerous constructs
        for pattern_name, pattern in self.dangerous_patterns.items():
            matches = pattern.findall(content)
            if matches:
                findings["dangerous_constructs"].append(
                    {
                        "type": pattern_name,
                        "matches": matches[:3],  # Limit to first 3 matches
                        "count": len(matches),
                    }
                )
                findings["is_safe"] = False

        # Determine severity
        if findings["dangerous_constructs"]:
            findings["severity"] = "critical"
        elif findings["sensitive_data"]:
            findings["severity"] = "high"
        elif not findings["is_safe"]:
            findings["severity"] = "medium"

        # Add warnings
        if findings["sensitive_data"]:
            findings["warnings"].append(
                "Template contains potentially sensitive information"
            )

        if findings["dangerous_constructs"]:
            findings["warnings"].append(
                "Template contains potentially dangerous constructs"
            )

        return findings

    def sanitize_template_content(self, content: str) -> Tuple[str, List[str]]:
        """Sanitize template content by removing dangerous elements.

        Args:
            content: Template content to sanitize

        Returns:
            Tuple of (sanitized_content, removed_elements)
        """
        sanitized_content = content
        removed_elements = []

        # Remove dangerous constructs
        for pattern_name, pattern in self.dangerous_patterns.items():
            matches = pattern.findall(sanitized_content)
            if matches:
                sanitized_content = pattern.sub(
                    "[REMOVED_FOR_SECURITY]", sanitized_content
                )
                removed_elements.extend(
                    [f"{pattern_name}: {match}" for match in matches]
                )

        return sanitized_content, removed_elements
