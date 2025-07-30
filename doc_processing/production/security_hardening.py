"""Security hardening for production deployment."""

import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validate and sanitize inputs for security."""

    # Patterns for dangerous content
    DANGEROUS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers
        re.compile(r"\.\.\/"),  # Path traversal
        re.compile(r"etc\/passwd"),  # System file access
        re.compile(r"cmd\.exe|powershell", re.IGNORECASE),  # Command execution
    ]

    # Safe file extensions for documents
    SAFE_EXTENSIONS = {
        ".md",
        ".txt",
        ".docx",
        ".pd",
        ".html",
        ".json",
        ".xml",
        ".csv",
    }

    # Maximum file sizes (in MB)
    MAX_FILE_SIZES = {
        ".pd": 50,
        ".docx": 25,
        ".md": 10,
        ".txt": 10,
        "default": 100,
    }

    @classmethod
    def validate_file_path(cls, file_path: str, base_path: Path) -> Tuple[bool, str]:
        """Validate file path for security.

        Args:
            file_path: Path to validate
            base_path: Base directory for validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Resolve to absolute path
            resolved = Path(file_path).resolve()
            base_resolved = base_path.resolve()

            # Check path traversal
            if not str(resolved).startswith(str(base_resolved)):
                return False, "Path traversal detected"

            # Check file extension
            if resolved.suffix.lower() not in cls.SAFE_EXTENSIONS:
                return False, f"Unsafe file extension: {resolved.suffix}"

            # Check file name for dangerous patterns
            for pattern in cls.DANGEROUS_PATTERNS:
                if pattern.search(resolved.name):
                    return False, "Dangerous pattern in filename"

            return True, ""

        except Exception as e:
            return False, f"Path validation error: {str(e)}"

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename for safe storage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)

        # Replace dangerous characters
        safe_chars = re.compile(r"[^a-zA-Z0-9._-]")
        sanitized = safe_chars.sub("_", filename)

        # Limit length
        name, ext = os.path.splitext(sanitized)
        if len(name) > 100:
            name = name[:100]

        return f"{name}{ext}"

    @classmethod
    def validate_file_size(cls, file_path: Path) -> Tuple[bool, str]:
        """Validate file size is within limits.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            max_size = cls.MAX_FILE_SIZES.get(
                file_path.suffix.lower(), cls.MAX_FILE_SIZES["default"]
            )

            if size_mb > max_size:
                return False, f"File too large: {size_mb:.1f}MB (max: {max_size}MB)"

            return True, ""

        except Exception as e:
            return False, f"Size validation error: {str(e)}"

    @classmethod
    def sanitize_content(cls, content: str) -> str:
        """Sanitize content for security.

        Args:
            content: Content to sanitize

        Returns:
            Sanitized content
        """
        # Remove dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            content = pattern.sub("", content)

        # Remove null bytes
        content = content.replace("\x00", "")

        return content

    @classmethod
    def validate_user_input(
        cls, input_data: str, max_length: int = 10000
    ) -> Tuple[bool, str]:
        """Validate user input for security.

        Args:
            input_data: User input to validate
            max_length: Maximum allowed length

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(input_data) > max_length:
            return False, f"Input too long: {len(input_data)} (max: {max_length})"

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(input_data):
                return False, "Dangerous pattern detected in input"

        # Check for SQL injection patterns
        sql_patterns = [
            re.compile(r"(union|select|insert|update|delete|drop)\s", re.IGNORECASE),
            re.compile(r"--|\||;|/\*|\*/", re.IGNORECASE),
        ]

        for pattern in sql_patterns:
            if pattern.search(input_data):
                return False, "SQL injection pattern detected"

        return True, ""


class AccessControl:
    """Access control and authorization."""

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize access control.

        Args:
            secret_key: Secret key for token generation
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.session_timeout = timedelta(hours=8)  # 8 hour sessions
        self.max_failed_attempts = 5
        self.lockout_duration = timedelta(minutes=30)

        # Track failed attempts
        self.failed_attempts: Dict[str, List[datetime]] = {}

    def generate_session_token(self, user_id: str) -> str:
        """Generate secure session token.

        Args:
            user_id: User identifier

        Returns:
            Secure session token
        """
        # Create token data
        token_data = f"{user_id}:{datetime.now().isoformat()}"

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(), token_data.encode(), hashlib.sha256
        ).hexdigest()

        # Combine data and signature
        token = f"{token_data}:{signature}"

        # Encode for URL safety
        return secrets.token_urlsafe(32) + ":" + token

    def validate_session_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """Validate session token.

        Args:
            token: Session token to validate

        Returns:
            Tuple of (is_valid, user_id)
        """
        try:
            # Parse token
            parts = token.split(":")
            if len(parts) < 4:
                return False, None

            # Extract components
            user_id = parts[1]
            timestamp_str = parts[2]
            provided_signature = parts[3]

            # Verify signature
            token_data = f"{user_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key.encode(), token_data.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(provided_signature, expected_signature):
                return False, None

            # Check expiration
            timestamp = datetime.fromisoformat(timestamp_str)
            if datetime.now() - timestamp > self.session_timeout:
                return False, None

            return True, user_id

        except Exception:
            return False, None

    def check_rate_limit(self, user_id: str) -> Tuple[bool, str]:
        """Check if user is rate limited.

        Args:
            user_id: User identifier

        Returns:
            Tuple of (is_allowed, message)
        """
        now = datetime.now()

        # Clean old attempts
        if user_id in self.failed_attempts:
            self.failed_attempts[user_id] = [
                attempt
                for attempt in self.failed_attempts[user_id]
                if now - attempt < self.lockout_duration
            ]

        # Check lockout
        attempts = self.failed_attempts.get(user_id, [])
        if len(attempts) >= self.max_failed_attempts:
            lockout_end = attempts[0] + self.lockout_duration
            if now < lockout_end:
                minutes_left = (lockout_end - now).seconds // 60
                return False, f"Account locked. Try again in {minutes_left} minutes."

        return True, ""

    def record_failed_attempt(self, user_id: str) -> None:
        """Record failed login attempt.

        Args:
            user_id: User identifier
        """
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []

        self.failed_attempts[user_id].append(datetime.now())

    def clear_failed_attempts(self, user_id: str) -> None:
        """Clear failed attempts after successful login.

        Args:
            user_id: User identifier
        """
        if user_id in self.failed_attempts:
            del self.failed_attempts[user_id]


class EncryptionService:
    """Handle encryption for sensitive data."""

    def __init__(self):
        """Initialize encryption service."""
        # In production, use proper key management service
        self.encryption_key = self._derive_key()

    def _derive_key(self) -> bytes:
        """Derive encryption key."""
        # In production, load from secure storage
        return hashlib.sha256(os.urandom(32)).digest()

    def encrypt_sensitive_field(self, data: str) -> str:
        """Encrypt sensitive field (simplified for demo).

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data (base64 encoded)
        """
        # In production, use proper encryption library like cryptography
        # This is a simplified version for demonstration
        import base64

        # Simple XOR encryption (NOT secure - use proper encryption in production)
        encrypted = bytes(
            b ^ self.encryption_key[i % len(self.encryption_key)]
            for i, b in enumerate(data.encode())
        )

        return base64.b64encode(encrypted).decode()

    def decrypt_sensitive_field(self, encrypted_data: str) -> str:
        """Decrypt sensitive field.

        Args:
            encrypted_data: Encrypted data (base64 encoded)

        Returns:
            Decrypted data
        """
        import base64

        encrypted = base64.b64decode(encrypted_data.encode())

        # Reverse XOR encryption
        decrypted = bytes(
            b ^ self.encryption_key[i % len(self.encryption_key)]
            for i, b in enumerate(encrypted)
        )

        return decrypted.decode()


class SecurityAuditor:
    """Audit security events and violations."""

    def __init__(self, audit_log_path: Optional[Path] = None):
        """Initialize security auditor.

        Args:
            audit_log_path: Path to audit log file
        """
        self.audit_log_path = audit_log_path or Path("security_audit.log")
        self.audit_events: List[Dict[str, Any]] = []

    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str],
        details: Dict[str, Any],
        severity: str = "info",
    ) -> None:
        """Log security event.

        Args:
            event_type: Type of security event
            user_id: User involved
            details: Event details
            severity: Event severity
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "details": details,
        }

        self.audit_events.append(event)

        # Log to file
        if severity in ["warning", "error", "critical"]:
            logger.warning(f"Security event: {event}")
        else:
            logger.info(f"Security event: {event}")

        # Write to audit file
        self._write_to_audit_log(event)

    def _write_to_audit_log(self, event: Dict[str, Any]) -> None:
        """Write event to audit log file."""
        try:
            with open(self.audit_log_path, "a") as f:
                f.write(f"{datetime.now().isoformat()} - {event}\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_security_report(self) -> Dict[str, Any]:
        """Generate security report."""
        report = {
            "total_events": len(self.audit_events),
            "by_type": {},
            "by_severity": {},
            "recent_warnings": [],
        }

        # Count by type and severity
        for event in self.audit_events:
            event_type = event["event_type"]
            severity = event["severity"]

            report["by_type"][event_type] = report["by_type"].get(event_type, 0) + 1
            report["by_severity"][severity] = report["by_severity"].get(severity, 0) + 1

            # Collect recent warnings
            if severity in ["warning", "error", "critical"]:
                report["recent_warnings"].append(event)

        # Keep only last 10 warnings
        report["recent_warnings"] = report["recent_warnings"][-10:]

        return report


# Security configuration for production
SECURITY_CONFIG = {
    "session_timeout_hours": 8,
    "max_failed_login_attempts": 5,
    "lockout_duration_minutes": 30,
    "max_file_size_mb": 100,
    "allowed_file_extensions": [".md", ".txt", ".docx", ".pd"],
    "audit_logging_enabled": True,
    "encryption_enabled": True,
    "rate_limiting_enabled": True,
}
