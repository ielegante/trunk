"""SQLite-based rate limiter to replace Redis dependencies."""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from app.database import database_manager
from app.models import RateLimitEntry
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SQLiteRateLimiter:
    """SQLite-based rate limiter."""

    def __init__(self, default_limit: int = 100, window_seconds: int = 3600):
        """Initialize rate limiter.

        Args:
            default_limit: Default number of requests per window
            window_seconds: Window size in seconds
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.db = database_manager
        self.local_cache = {}  # Local cache for performance
        self.lock = threading.RLock()

        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired_entries, daemon=True
        )
        self.cleanup_thread.start()

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        category: str = "general",
    ) -> Tuple[bool, Dict[str, int]]:
        """Check if request is allowed and increment counter.

        Args:
            identifier: Unique identifier (IP address, user ID, etc.)
            limit: Custom limit for this check
            window: Custom window size in seconds
            category: Category for organization

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        limit = limit or self.default_limit
        window = window or self.window_seconds

        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=window)

        try:
            with self.db.get_session() as session:
                # Find or create rate limit entry
                entry = (
                    session.query(RateLimitEntry)
                    .filter_by(identifier=identifier, category=category)
                    .first()
                )

                if entry:
                    # Check if window has expired
                    if current_time > entry.window_end:
                        # Reset the window
                        entry.window_start = current_time
                        entry.window_end = current_time + timedelta(seconds=window)
                        entry.request_count = 1
                        session.commit()

                        info = {
                            "requests_made": 1,
                            "requests_remaining": limit - 1,
                            "reset_time": int(entry.window_end.timestamp()),
                            "window_seconds": window,
                        }

                        return True, info

                    # Check if within limit
                    if entry.request_count >= limit:
                        info = {
                            "requests_made": entry.request_count,
                            "requests_remaining": 0,
                            "reset_time": int(entry.window_end.timestamp()),
                            "window_seconds": window,
                        }

                        return False, info

                    # Increment counter
                    entry.request_count += 1
                    session.commit()

                    info = {
                        "requests_made": entry.request_count,
                        "requests_remaining": limit - entry.request_count,
                        "reset_time": int(entry.window_end.timestamp()),
                        "window_seconds": window,
                    }

                    return True, info

                else:
                    # Create new entry
                    entry = RateLimitEntry(
                        identifier=identifier,
                        request_count=1,
                        window_start=current_time,
                        window_end=current_time + timedelta(seconds=window),
                        category=category,
                    )

                    session.add(entry)
                    session.commit()

                    info = {
                        "requests_made": 1,
                        "requests_remaining": limit - 1,
                        "reset_time": int(entry.window_end.timestamp()),
                        "window_seconds": window,
                    }

                    return True, info

        except Exception as e:
            logger.error(f"Rate limiter error: {str(e)}")
            # In case of error, allow the request
            return True, {"error": str(e)}

    def get_status(self, identifier: str, category: str = "general") -> Dict[str, int]:
        """Get current rate limit status for an identifier.

        Args:
            identifier: Unique identifier
            category: Category

        Returns:
            Dictionary with rate limit information
        """
        try:
            with self.db.get_session() as session:
                entry = (
                    session.query(RateLimitEntry)
                    .filter_by(identifier=identifier, category=category)
                    .first()
                )

                if entry:
                    current_time = datetime.utcnow()

                    if current_time > entry.window_end:
                        # Window has expired
                        return {
                            "requests_made": 0,
                            "requests_remaining": self.default_limit,
                            "reset_time": int(
                                (
                                    current_time
                                    + timedelta(seconds=self.window_seconds)
                                ).timestamp()
                            ),
                            "window_seconds": self.window_seconds,
                        }

                    return {
                        "requests_made": entry.request_count,
                        "requests_remaining": max(
                            0, self.default_limit - entry.request_count
                        ),
                        "reset_time": int(entry.window_end.timestamp()),
                        "window_seconds": self.window_seconds,
                    }

                return {
                    "requests_made": 0,
                    "requests_remaining": self.default_limit,
                    "reset_time": int(
                        (
                            datetime.utcnow() + timedelta(seconds=self.window_seconds)
                        ).timestamp()
                    ),
                    "window_seconds": self.window_seconds,
                }

        except Exception as e:
            logger.error(f"Rate limiter status error: {str(e)}")
            return {"error": str(e)}

    def reset_limit(self, identifier: str, category: str = "general") -> bool:
        """Reset rate limit for an identifier.

        Args:
            identifier: Unique identifier
            category: Category

        Returns:
            True if reset successful, False otherwise
        """
        try:
            with self.db.get_session() as session:
                entry = (
                    session.query(RateLimitEntry)
                    .filter_by(identifier=identifier, category=category)
                    .first()
                )

                if entry:
                    session.delete(entry)
                    session.commit()
                    logger.info(f"Rate limit reset for {identifier}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Rate limiter reset error: {str(e)}")
            return False

    def get_statistics(self) -> Dict[str, int]:
        """Get rate limiter statistics."""
        try:
            with self.db.get_session() as session:
                # Total entries
                total_entries = session.query(RateLimitEntry).count()

                # Active entries (within window)
                current_time = datetime.utcnow()
                active_entries = (
                    session.query(RateLimitEntry)
                    .filter(RateLimitEntry.window_end > current_time)
                    .count()
                )

                # Entries by category
                categories = session.query(RateLimitEntry.category).distinct().all()
                category_counts = {}

                for (category,) in categories:
                    count = (
                        session.query(RateLimitEntry)
                        .filter_by(category=category)
                        .count()
                    )
                    category_counts[category] = count

                return {
                    "total_entries": total_entries,
                    "active_entries": active_entries,
                    "expired_entries": total_entries - active_entries,
                    "categories": category_counts,
                }

        except Exception as e:
            logger.error(f"Rate limiter statistics error: {str(e)}")
            return {"error": str(e)}

    def _cleanup_expired_entries(self):
        """Background thread to clean up expired entries."""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes

                with self.db.get_session() as session:
                    expired_entries = (
                        session.query(RateLimitEntry)
                        .filter(RateLimitEntry.window_end < datetime.utcnow())
                        .all()
                    )

                    if expired_entries:
                        count = len(expired_entries)
                        for entry in expired_entries:
                            session.delete(entry)

                        session.commit()
                        logger.info(f"Cleaned up {count} expired rate limit entries")

            except Exception as e:
                logger.error(f"Rate limiter cleanup error: {str(e)}")
                time.sleep(300)  # Wait before retrying


class SQLiteRateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app,
        calls_per_hour: int = 100,
        per_ip: bool = True,
        per_user: bool = False,
        exclude_paths: Optional[list] = None,
    ):
        """Initialize rate limit middleware.

        Args:
            app: FastAPI application
            calls_per_hour: Number of calls allowed per hour
            per_ip: Enable rate limiting per IP address
            per_user: Enable rate limiting per user
            exclude_paths: List of paths to exclude from rate limiting
        """
        super().__init__(app)
        self.rate_limiter = SQLiteRateLimiter(
            default_limit=calls_per_hour, window_seconds=3600
        )
        self.per_ip = per_ip
        self.per_user = per_user
        self.exclude_paths = exclude_paths or []
        self.calls_per_hour = calls_per_hour

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz", "/status"]:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host

        # Check rate limit
        if self.per_ip:
            allowed, info = self.rate_limiter.is_allowed(
                identifier=client_ip, limit=self.calls_per_hour, category="ip"
            )

            if not allowed:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")

                # Create rate limit response
                response = Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                )

                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(self.calls_per_hour)
                response.headers["X-RateLimit-Remaining"] = str(
                    info.get("requests_remaining", 0)
                )
                response.headers["X-RateLimit-Reset"] = str(info.get("reset_time", 0))
                response.headers["Retry-After"] = str(info.get("window_seconds", 3600))

                return response

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        if self.per_ip:
            status = self.rate_limiter.get_status(client_ip, "ip")
            response.headers["X-RateLimit-Limit"] = str(self.calls_per_hour)
            response.headers["X-RateLimit-Remaining"] = str(
                status.get("requests_remaining", 0)
            )
            response.headers["X-RateLimit-Reset"] = str(status.get("reset_time", 0))

        return response


# Global rate limiter instance
sqlite_rate_limiter = SQLiteRateLimiter()
