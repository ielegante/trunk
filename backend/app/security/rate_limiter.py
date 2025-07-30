"""
Rate limiting middleware for API endpoints
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter for API endpoints"""

    def __init__(
        self,
        redis_client: redis.Redis,
        default_limit: int = 100,
        window_seconds: int = 3600,
    ):
        self.redis = redis_client
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def check_rate_limit(
        self, key: str, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Check if request is within rate limit

        Args:
            key: Unique identifier for rate limiting (e.g., IP address, user ID)
            limit: Custom limit override

        Returns:
            Dict with rate limit status and metadata
        """
        limit = limit or self.default_limit
        current_time = int(time.time())
        window_start = current_time - self.window_seconds

        try:
            # Clean old entries and count current requests
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, self.window_seconds)

            results = pipe.execute()
            request_count = results[1] + 1  # +1 for current request

            # Check if limit exceeded
            if request_count > limit:
                return {
                    "allowed": False,
                    "limit": limit,
                    "remaining": 0,
                    "reset_time": current_time + self.window_seconds,
                    "request_count": request_count,
                }

            return {
                "allowed": True,
                "limit": limit,
                "remaining": limit - request_count,
                "reset_time": current_time + self.window_seconds,
                "request_count": request_count,
            }

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if Redis is unavailable
            return {
                "allowed": True,
                "limit": limit,
                "remaining": limit,
                "reset_time": current_time + self.window_seconds,
                "request_count": 1,
            }


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting"""

    def __init__(self, redis_client: redis.Redis):
        self.rate_limiter = RateLimiter(redis_client)

    async def __call__(self, request: Request, call_next):
        """Process request through rate limiter"""

        # Get identifier for rate limiting
        identifier = self._get_identifier(request)

        # Check rate limit
        rate_limit_result = await self.rate_limiter.check_rate_limit(identifier)

        if not rate_limit_result["allowed"]:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": rate_limit_result["limit"],
                    "reset_time": rate_limit_result["reset_time"],
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
                    "X-RateLimit-Reset": str(rate_limit_result["reset_time"]),
                    "Retry-After": str(self.rate_limiter.window_seconds),
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limit_result["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_result["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_result["reset_time"])

        return response

    def _get_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting"""

        # Try to get user ID from auth context
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        client_ip = request.client.host
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()

        return f"ip:{client_ip}"


# Decorator for endpoint-specific rate limiting
def rate_limit(limit: int = 100, window_seconds: int = 3600):
    """
    Decorator for endpoint-specific rate limiting

    Args:
        limit: Number of requests allowed in window
        window_seconds: Time window in seconds
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented with dependency injection
            # in the actual FastAPI application
            return await func(*args, **kwargs)

        wrapper._rate_limit = limit
        wrapper._rate_window = window_seconds
        return wrapper

    return decorator


# Specific rate limiters for different endpoint types
class EndpointRateLimits:
    """Predefined rate limits for different endpoint types"""

    AUTH_ENDPOINTS = {"limit": 10, "window": 900}  # 10 requests per 15 minutes
    GIT_OPERATIONS = {"limit": 50, "window": 3600}  # 50 requests per hour
    FILE_UPLOADS = {"limit": 20, "window": 3600}  # 20 uploads per hour
    API_GENERAL = {"limit": 100, "window": 3600}  # 100 requests per hour
    POWER_USER = {"limit": 100, "window": 3600}  # 100 commands per hour
