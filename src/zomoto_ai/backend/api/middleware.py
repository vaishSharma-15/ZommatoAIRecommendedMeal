"""API Middleware - Custom middleware for FastAPI application

Provides logging, rate limiting, correlation ID management, and error handling.
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger
from zomoto_ai.phase6.rate_limiting import RateLimiter, RateLimitConfig


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Adds correlation ID to requests for tracing."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Add to request state for downstream use
        request.state.correlation_id = correlation_id
        
        # Add correlation ID to response headers
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured logging middleware for API requests and responses."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract request information
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        
        # Log request
        self.logger.info(
            "api_request",
            "received",
            f"API request received: {method} {path}",
            correlation_id=correlation_id,
            method=method,
            path=path,
            query_params=query_params,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            self.logger.info(
                "api_response",
                "sent",
                f"API response sent: {method} {path} -> {response.status_code}",
                correlation_id=correlation_id,
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            # Add performance header
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            self.logger.error(
                "api_error",
                "request_failed",
                f"API request failed: {method} {path} - {str(e)}",
                correlation_id=correlation_id,
                method=method,
                path=path,
                error=str(e),
                duration_ms=duration_ms
            )
            
            # Re-raise exception for error handling middleware
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""
    
    def __init__(self, app: ASGIApp, config: RateLimitConfig = None):
        super().__init__(app)
        self.rate_limiter = RateLimiter(config or RateLimitConfig())
        self.logger = get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Extract client identifier
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key")
        
        # Check rate limits
        endpoint_type = "llm" if "recommendations" in request.url.path else "api"
        allowed, info = self.rate_limiter.is_allowed(
            request,
            endpoint_type=endpoint_type
        )
        
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        
        if not allowed:
            self.logger.warning(
                "rate_limit",
                "exceeded",
                f"Rate limit exceeded for {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip,
                endpoint_type=endpoint_type,
                limit=info.get("limit"),
                remaining=info.get("remaining", 0),
                reset_time=info.get("reset_time")
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "message": "Rate limit exceeded",
                    "details": {
                        "limit": info.get("limit"),
                        "remaining": info.get("remaining", 0),
                        "reset_time": info.get("reset_time")
                    }
                }
            )
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset_time", 0))
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Centralized error handling middleware."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Handle HTTP exceptions
            self.logger.warning(
                "http_error",
                "client_error",
                f"HTTP error: {e.status_code} - {e.detail}",
                correlation_id=correlation_id,
                status_code=e.status_code,
                detail=e.detail
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": self._get_error_type(e.status_code),
                    "message": e.detail,
                    "timestamp": time.time(),
                    "request_id": correlation_id
                }
            )
            
        except Exception as e:
            # Handle unexpected errors
            self.logger.error(
                "server_error",
                "unexpected_error",
                f"Unexpected server error: {str(e)}",
                correlation_id=correlation_id,
                error=str(e),
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                    "timestamp": time.time(),
                    "request_id": correlation_id
                }
            )
    
    def _get_error_type(self, status_code: int) -> str:
        """Get error type from HTTP status code."""
        error_types = {
            400: "BadRequest",
            401: "Unauthorized",
            403: "Forbidden", 
            404: "NotFound",
            405: "MethodNotAllowed",
            422: "ValidationError",
            429: "RateLimitExceeded"
        }
        return error_types.get(status_code, "HTTPError")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to responses."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add CORS headers (can be configured based on requirements)
        response.headers["Access-Control-Allow-Origin"] = "*"  # Configure as needed
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Correlation-ID"
        
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collects metrics for API requests."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            self._record_metrics(request, response, duration)
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            self._record_error_metrics(request, e, duration)
            raise
    
    def _record_metrics(self, request: Request, response: Response, duration: float):
        """Record success metrics."""
        method = request.method
        path = request.url.path
        status_code = response.status_code
        
        # Log metrics (in production, this would go to a metrics system)
        self.logger.info(
            "metrics",
            "request_completed",
            f"Request completed: {method} {path} -> {status_code}",
            method=method,
            path=path,
            status_code=status_code,
            duration_seconds=duration
        )
    
    def _record_error_metrics(self, request: Request, error: Exception, duration: float):
        """Record error metrics."""
        method = request.method
        path = request.url.path
        error_type = type(error).__name__
        
        # Log error metrics
        self.logger.error(
            "metrics",
            "request_error",
            f"Request error: {method} {path} -> {error_type}",
            method=method,
            path=path,
            error_type=error_type,
            duration_seconds=duration
        )
