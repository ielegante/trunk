import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional, Set

import jwt
from app.config import settings
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions"""

    READ_TEMPLATES = "read_templates"
    CREATE_TEMPLATES = "create_templates"
    MODIFY_TEMPLATES = "modify_templates"
    DELETE_TEMPLATES = "delete_templates"
    INSTANTIATE_TEMPLATES = "instantiate_templates"
    READ_REPOSITORIES = "read_repositories"
    CREATE_REPOSITORIES = "create_repositories"
    MODIFY_REPOSITORIES = "modify_repositories"
    DELETE_REPOSITORIES = "delete_repositories"
    ADMIN_ACCESS = "admin_access"
    UPLOAD_FILES = "upload_files"
    PROCESS_DOCUMENTS = "process_documents"
    MERGE_CONFLICTS = "merge_conflicts"


class Role(Enum):
    """User roles with associated permissions"""

    GUEST = "guest"
    USER = "user"
    POWER_USER = "power_user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class RateLimitRule:
    """Rate limiting rule definition"""

    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_allowance: int = 5


@dataclass
class SecurityPolicy:
    """Security policy configuration"""

    require_mfa: bool = False
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    session_timeout_minutes: int = 30
    password_min_length: int = 8
    require_password_complexity: bool = True
    allowed_file_types: List[str] = None
    max_file_size_mb: int = 50
    rate_limit_rules: Dict[str, RateLimitRule] = None

    def __post_init__(self):
        if self.allowed_file_types is None:
            self.allowed_file_types = [".pd", ".docx", ".md", ".txt"]
        if self.rate_limit_rules is None:
            self.rate_limit_rules = {
                "default": RateLimitRule(60, 1000, 10000),
                "upload": RateLimitRule(10, 100, 500),
                "admin": RateLimitRule(120, 2000, 20000),
            }


class AccessControlManager:
    """Manages access control, permissions, and security policies"""

    def __init__(self):
        self.role_permissions = self._setup_role_permissions()
        self.security_policy = SecurityPolicy()
        self.rate_limit_cache = {}
        self.failed_login_attempts = {}
        self.active_sessions = {}

    def _setup_role_permissions(self) -> Dict[Role, Set[Permission]]:
        """Define permissions for each role"""
        return {
            Role.GUEST: {
                Permission.READ_TEMPLATES,
            },
            Role.USER: {
                Permission.READ_TEMPLATES,
                Permission.INSTANTIATE_TEMPLATES,
                Permission.READ_REPOSITORIES,
                Permission.CREATE_REPOSITORIES,
                Permission.MODIFY_REPOSITORIES,
                Permission.UPLOAD_FILES,
                Permission.PROCESS_DOCUMENTS,
            },
            Role.POWER_USER: {
                Permission.READ_TEMPLATES,
                Permission.CREATE_TEMPLATES,
                Permission.MODIFY_TEMPLATES,
                Permission.INSTANTIATE_TEMPLATES,
                Permission.READ_REPOSITORIES,
                Permission.CREATE_REPOSITORIES,
                Permission.MODIFY_REPOSITORIES,
                Permission.DELETE_REPOSITORIES,
                Permission.UPLOAD_FILES,
                Permission.PROCESS_DOCUMENTS,
                Permission.MERGE_CONFLICTS,
            },
            Role.ADMIN: {
                Permission.READ_TEMPLATES,
                Permission.CREATE_TEMPLATES,
                Permission.MODIFY_TEMPLATES,
                Permission.DELETE_TEMPLATES,
                Permission.INSTANTIATE_TEMPLATES,
                Permission.READ_REPOSITORIES,
                Permission.CREATE_REPOSITORIES,
                Permission.MODIFY_REPOSITORIES,
                Permission.DELETE_REPOSITORIES,
                Permission.ADMIN_ACCESS,
                Permission.UPLOAD_FILES,
                Permission.PROCESS_DOCUMENTS,
                Permission.MERGE_CONFLICTS,
            },
            Role.SUPER_ADMIN: set(Permission),  # All permissions
        }

    def check_permission(
        self, user_role: Role, required_permission: Permission
    ) -> bool:
        """Check if user role has required permission"""
        user_permissions = self.role_permissions.get(user_role, set())
        return required_permission in user_permissions

    def require_permission(self, permission: Permission):
        """Decorator to require specific permission"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user info from request context
                # This would be integrated with your auth system
                request = kwargs.get("request") or (
                    args[0] if args and hasattr(args[0], "headers") else None
                )

                if not request:
                    raise HTTPException(
                        status_code=401, detail="Authentication required"
                    )

                user_role = self._get_user_role_from_request(request)

                if not self.check_permission(user_role, permission):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied. Required: {permission.value}",
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def _get_user_role_from_request(self, request: Request) -> Role:
        """Extract user role from request (placeholder implementation)"""
        # This would integrate with your JWT token validation
        # For now, return a default role
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return Role.GUEST

        try:
            token = auth_header.replace("Bearer ", "")
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            role_str = payload.get("role", "user")
            return Role(role_str)
        except Exception:
            return Role.GUEST

    def validate_rate_limit(
        self, user_id: str, endpoint: str, request_type: str = "default"
    ) -> Dict[str, Any]:
        """Validate rate limiting for user requests"""
        current_time = datetime.utcnow()
        rate_rule = self.security_policy.rate_limit_rules.get(
            request_type, self.security_policy.rate_limit_rules["default"]
        )

        # Create cache key
        cache_key = f"{user_id}:{endpoint}:{request_type}"

        # Initialize or get existing rate limit data
        if cache_key not in self.rate_limit_cache:
            self.rate_limit_cache[cache_key] = {
                "requests": [],
                "burst_count": 0,
                "last_reset": current_time,
            }

        rate_data = self.rate_limit_cache[cache_key]

        # Clean old requests
        minute_ago = current_time - timedelta(minutes=1)
        hour_ago = current_time - timedelta(hours=1)
        day_ago = current_time - timedelta(days=1)

        # Filter recent requests
        recent_requests = [
            req_time for req_time in rate_data["requests"] if req_time > day_ago
        ]
        rate_data["requests"] = recent_requests

        # Count requests in different time windows
        requests_last_minute = len([req for req in recent_requests if req > minute_ago])
        requests_last_hour = len([req for req in recent_requests if req > hour_ago])
        requests_last_day = len(recent_requests)

        # Check rate limits
        if requests_last_minute >= rate_rule.requests_per_minute:
            return {
                "allowed": False,
                "reason": "Rate limit exceeded (per minute)",
                "retry_after": 60,
                "current_count": requests_last_minute,
                "limit": rate_rule.requests_per_minute,
            }

        if requests_last_hour >= rate_rule.requests_per_hour:
            return {
                "allowed": False,
                "reason": "Rate limit exceeded (per hour)",
                "retry_after": 3600,
                "current_count": requests_last_hour,
                "limit": rate_rule.requests_per_hour,
            }

        if requests_last_day >= rate_rule.requests_per_day:
            return {
                "allowed": False,
                "reason": "Rate limit exceeded (per day)",
                "retry_after": 86400,
                "current_count": requests_last_day,
                "limit": rate_rule.requests_per_day,
            }

        # Check burst allowance
        if rate_data["burst_count"] >= rate_rule.burst_allowance:
            if (current_time - rate_data["last_reset"]).seconds < 60:
                return {
                    "allowed": False,
                    "reason": "Burst limit exceeded",
                    "retry_after": 60,
                    "current_count": rate_data["burst_count"],
                    "limit": rate_rule.burst_allowance,
                }
            else:
                rate_data["burst_count"] = 0
                rate_data["last_reset"] = current_time

        # Record this request
        rate_data["requests"].append(current_time)
        rate_data["burst_count"] += 1

        return {
            "allowed": True,
            "remaining_minute": rate_rule.requests_per_minute
            - requests_last_minute
            - 1,
            "remaining_hour": rate_rule.requests_per_hour - requests_last_hour - 1,
            "remaining_day": rate_rule.requests_per_day - requests_last_day - 1,
        }

    def rate_limit(self, request_type: str = "default"):
        """Decorator for rate limiting"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request = kwargs.get("request") or (
                    args[0] if args and hasattr(args[0], "headers") else None
                )

                if request:
                    # Extract user ID from request
                    user_id = self._get_user_id_from_request(request)
                    endpoint = request.url.path

                    rate_check = self.validate_rate_limit(
                        user_id, endpoint, request_type
                    )

                    if not rate_check["allowed"]:
                        raise HTTPException(
                            status_code=429,
                            detail={
                                "error": "Rate limit exceeded",
                                "reason": rate_check["reason"],
                                "retry_after": rate_check["retry_after"],
                            },
                        )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def _get_user_id_from_request(self, request: Request) -> str:
        """Extract user ID from request"""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return request.client.host if request.client else "anonymous"

        try:
            token = auth_header.replace("Bearer ", "")
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            return payload.get("user_id", "unknown")
        except Exception:
            return request.client.host if request.client else "anonymous"

    def validate_file_upload(
        self, filename: str, file_size: int, content_type: str
    ) -> Dict[str, Any]:
        """Validate file upload against security policy"""
        validation_result = {"allowed": True, "issues": []}

        # Check file extension
        file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
        if file_ext not in self.security_policy.allowed_file_types:
            validation_result["allowed"] = False
            validation_result["issues"].append(f"File type {file_ext} not allowed")

        # Check file size
        max_size_bytes = self.security_policy.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            validation_result["allowed"] = False
            validation_result["issues"].append(
                f"File size ({file_size} bytes) exceeds maximum ({max_size_bytes} bytes)"
            )

        # Check content type
        dangerous_types = [
            "application/x-executable",
            "application/x-msdownload",
            "application/x-msdos-program",
            "application/x-msi",
            "application/x-bat",
            "application/x-sh",
        ]

        if content_type in dangerous_types:
            validation_result["allowed"] = False
            validation_result["issues"].append(
                f"Dangerous content type: {content_type}"
            )

        return validation_result

    def track_login_attempt(
        self, user_id: str, success: bool, ip_address: str
    ) -> Dict[str, Any]:
        """Track login attempts for security monitoring"""
        current_time = datetime.utcnow()

        if user_id not in self.failed_login_attempts:
            self.failed_login_attempts[user_id] = {
                "count": 0,
                "last_attempt": current_time,
                "locked_until": None,
                "attempts": [],
            }

        attempt_data = self.failed_login_attempts[user_id]

        # Add attempt record
        attempt_data["attempts"].append(
            {"timestamp": current_time, "success": success, "ip_address": ip_address}
        )

        # Keep only recent attempts (last 24 hours)
        day_ago = current_time - timedelta(days=1)
        attempt_data["attempts"] = [
            attempt
            for attempt in attempt_data["attempts"]
            if attempt["timestamp"] > day_ago
        ]

        if success:
            # Reset failed attempts on successful login
            attempt_data["count"] = 0
            attempt_data["locked_until"] = None
            return {
                "locked": False,
                "attempts_remaining": self.security_policy.max_login_attempts,
            }
        else:
            # Increment failed attempts
            attempt_data["count"] += 1
            attempt_data["last_attempt"] = current_time

            # Check if account should be locked
            if attempt_data["count"] >= self.security_policy.max_login_attempts:
                lockout_duration = timedelta(
                    minutes=self.security_policy.lockout_duration_minutes
                )
                attempt_data["locked_until"] = current_time + lockout_duration

                return {
                    "locked": True,
                    "locked_until": attempt_data["locked_until"].isoformat(),
                    "attempts_remaining": 0,
                }

            return {
                "locked": False,
                "attempts_remaining": self.security_policy.max_login_attempts
                - attempt_data["count"],
            }

    def is_account_locked(self, user_id: str) -> bool:
        """Check if account is currently locked"""
        if user_id not in self.failed_login_attempts:
            return False

        attempt_data = self.failed_login_attempts[user_id]
        locked_until = attempt_data.get("locked_until")

        if locked_until and datetime.utcnow() < locked_until:
            return True

        # Clear lock if time has passed
        if locked_until and datetime.utcnow() >= locked_until:
            attempt_data["locked_until"] = None
            attempt_data["count"] = 0

        return False

    def create_secure_session(
        self, user_id: str, user_role: Role, ip_address: str
    ) -> Dict[str, Any]:
        """Create secure session with tracking"""
        session_id = secrets.token_urlsafe(32)
        current_time = datetime.utcnow()

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "user_role": user_role.value,
            "created_at": current_time,
            "last_activity": current_time,
            "ip_address": ip_address,
            "expires_at": current_time
            + timedelta(minutes=self.security_policy.session_timeout_minutes),
        }

        self.active_sessions[session_id] = session_data

        # Clean expired sessions
        self._cleanup_expired_sessions()

        return {
            "session_id": session_id,
            "expires_at": session_data["expires_at"].isoformat(),
            "timeout_minutes": self.security_policy.session_timeout_minutes,
        }

    def validate_session(self, session_id: str) -> Dict[str, Any]:
        """Validate and update session"""
        if session_id not in self.active_sessions:
            return {"valid": False, "reason": "Session not found"}

        session_data = self.active_sessions[session_id]
        current_time = datetime.utcnow()

        # Check if session expired
        if current_time > session_data["expires_at"]:
            del self.active_sessions[session_id]
            return {"valid": False, "reason": "Session expired"}

        # Update last activity and extend expiration
        session_data["last_activity"] = current_time
        session_data["expires_at"] = current_time + timedelta(
            minutes=self.security_policy.session_timeout_minutes
        )

        return {
            "valid": True,
            "user_id": session_data["user_id"],
            "user_role": session_data["user_role"],
            "expires_at": session_data["expires_at"].isoformat(),
        }

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False

    def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.utcnow()
        expired_sessions = [
            session_id
            for session_id, session_data in self.active_sessions.items()
            if current_time > session_data["expires_at"]
        ]

        for session_id in expired_sessions:
            del self.active_sessions[session_id]

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        if session_id not in self.active_sessions:
            raise ValueError("Invalid session")

        session_data = self.active_sessions[session_id]
        user_id = session_data["user_id"]
        timestamp = str(int(datetime.utcnow().timestamp()))

        # Create CSRF token using HMAC
        message = f"{session_id}:{user_id}:{timestamp}"
        csrf_token = hmac.new(
            settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return f"{timestamp}.{csrf_token}"

    def validate_csrf_token(self, session_id: str, csrf_token: str) -> bool:
        """Validate CSRF token"""
        try:
            if session_id not in self.active_sessions:
                return False

            session_data = self.active_sessions[session_id]
            user_id = session_data["user_id"]

            # Parse token
            timestamp_str, token_hash = csrf_token.split(".", 1)

            # Check token age (max 1 hour)
            token_time = datetime.fromtimestamp(int(timestamp_str))
            if datetime.utcnow() - token_time > timedelta(hours=1):
                return False

            # Verify token
            message = f"{session_id}:{user_id}:{timestamp_str}"
            expected_hash = hmac.new(
                settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(token_hash, expected_hash)

        except Exception:
            return False

    def get_security_audit_log(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Get security audit log"""
        audit_entries = []

        # Add login attempts
        for uid, attempt_data in self.failed_login_attempts.items():
            if user_id and uid != user_id:
                continue

            for attempt in attempt_data["attempts"][-limit:]:
                audit_entries.append(
                    {
                        "timestamp": attempt["timestamp"].isoformat(),
                        "user_id": uid,
                        "event_type": "login_attempt",
                        "success": attempt["success"],
                        "ip_address": attempt["ip_address"],
                    }
                )

        # Add active sessions
        for session_id, session_data in self.active_sessions.items():
            if user_id and session_data["user_id"] != user_id:
                continue

            audit_entries.append(
                {
                    "timestamp": session_data["created_at"].isoformat(),
                    "user_id": session_data["user_id"],
                    "event_type": "session_created",
                    "session_id": session_id,
                    "ip_address": session_data["ip_address"],
                }
            )

        # Sort by timestamp (most recent first)
        audit_entries.sort(key=lambda x: x["timestamp"], reverse=True)

        return audit_entries[:limit]


# Global access control manager instance
access_control = AccessControlManager()
