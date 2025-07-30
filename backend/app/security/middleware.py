"""
Security middleware for FastAPI application
"""

import logging
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosnif"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=()"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS attacks"""

    def __init__(self, app, max_size: int = 100 * 1024 * 1024):  # 100MB default
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length:
            content_length = int(content_length)
            if content_length > self.max_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Request too large",
                        "max_size": self.max_size,
                        "received_size": content_length,
                    },
                )

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests for security monitoring"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Get client IP
        client_ip = request.client.host
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()

        # Get user agent
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log request details
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s "
            f"IP: {client_ip} "
            f"User-Agent: {user_agent}"
        )

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Standardize error responses and prevent information disclosure"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # Re-raise HTTP exceptions (these are expected)
            raise e
        except Exception as e:
            # Log the actual error for debugging
            logger.error(f"Unhandled error: {e}", exc_info=True)

            # Return generic error response to prevent information disclosure
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later.",
                },
            )


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Validate content types for POST/PUT requests"""

    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    }

    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "").split(";")[0].strip()

            if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": "Unsupported media type",
                        "allowed_types": list(self.ALLOWED_CONTENT_TYPES),
                    },
                )

        return await call_next(request)


class SecurityMiddlewareStack:
    """Convenience class to add all security middleware"""

    @staticmethod
    def add_to_app(app, redis_client=None, max_request_size: int = 100 * 1024 * 1024):
        """Add all security middleware to FastAPI app"""

        # Add middleware in reverse order (last added is executed first)
        app.add_middleware(ErrorHandlingMiddleware)
        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(ContentTypeValidationMiddleware)
        app.add_middleware(RequestSizeLimitMiddleware, max_size=max_request_size)
        app.add_middleware(SecurityHeadersMiddleware)

        # Add rate limiting if Redis is available
        if redis_client:
            from .rate_limiter import RateLimitMiddleware

            app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
