"""Rate Limiting for Phase 6 - Production Hardening

Provides rate limiting for API endpoints to prevent abuse and ensure fair usage.
"""

import time
import threading
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from collections import defaultdict, deque
from functools import wraps
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import json


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # Allow short bursts
    
    # LLM-specific limits (more restrictive)
    llm_requests_per_minute: int = 10
    llm_requests_per_hour: int = 100
    
    # User-specific limits
    authenticated_requests_per_minute: int = 120
    authenticated_requests_per_hour: int = 2000


class RateLimiter:
    """Token bucket rate limiter with multiple time windows."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._buckets = defaultdict(lambda: defaultdict(deque))
        self._lock = threading.Lock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_old_tokens, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_old_tokens(self):
        """Background thread to clean up old tokens."""
        while True:
            time.sleep(60)  # Clean up every minute
            current_time = time.time()
            
            with self._lock:
                # Clean each client's buckets
                for client_id, windows in self._buckets.items():
                    for window_type, tokens in windows.items():
                        # Remove tokens older than their respective windows
                        if window_type == "minute":
                            cutoff = current_time - 60
                        elif window_type == "hour":
                            cutoff = current_time - 3600
                        elif window_type == "day":
                            cutoff = current_time - 86400
                        else:
                            continue
                        
                        # Remove old tokens
                        while tokens and tokens[0] < cutoff:
                            tokens.popleft()
    
    def _get_client_id(self, request: Request, use_ip: bool = True) -> str:
        """Generate client identifier for rate limiting."""
        if use_ip:
            # Use IP address as primary identifier
            client_ip = request.client.host
            return f"ip:{client_ip}"
        
        # Try to use API key or user ID if available
        auth_header = request.headers.get("authorization")
        if auth_header:
            # Hash the auth header for privacy
            return f"auth:{hashlib.sha256(auth_header.encode()).hexdigest()[:16]}"
        
        # Fallback to IP
        return f"ip:{request.client.host}"
    
    def _check_window(self, client_id: str, window_type: str, limit: int, current_time: float) -> bool:
        """Check if client is within limit for a specific time window."""
        with self._lock:
            tokens = self._buckets[client_id][window_type]
            
            # Define window cutoff
            if window_type == "minute":
                cutoff = current_time - 60
                limit_attr = "requests_per_minute"
            elif window_type == "hour":
                cutoff = current_time - 3600
                limit_attr = "requests_per_hour"
            elif window_type == "day":
                cutoff = current_time - 86400
                limit_attr = "requests_per_day"
            elif window_type == "llm_minute":
                cutoff = current_time - 60
                limit_attr = "llm_requests_per_minute"
            elif window_type == "llm_hour":
                cutoff = current_time - 3600
                limit_attr = "llm_requests_per_hour"
            else:
                return True
            
            # Remove old tokens
            while tokens and tokens[0] < cutoff:
                tokens.popleft()
            
            # Check if under limit
            return len(tokens) < limit
    
    def _add_token(self, client_id: str, window_type: str, current_time: float):
        """Add a token for the current request."""
        with self._lock:
            self._buckets[client_id][window_type].append(current_time)
    
    def is_allowed(self, request: Request, endpoint_type: str = "general", authenticated: bool = False) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed based on rate limits."""
        current_time = time.time()
        client_id = self._get_client_id(request, use_ip=not authenticated)
        
        # Define limits based on endpoint type and authentication status
        if endpoint_type == "llm":
            minute_limit = self.config.llm_requests_per_minute
            hour_limit = self.config.llm_requests_per_hour
            minute_window = "llm_minute"
            hour_window = "llm_hour"
        elif authenticated:
            minute_limit = self.config.authenticated_requests_per_minute
            hour_limit = self.config.authenticated_requests_per_hour
            minute_window = "minute"
            hour_window = "hour"
        else:
            minute_limit = self.config.requests_per_minute
            hour_limit = self.config.requests_per_hour
            minute_window = "minute"
            hour_window = "hour"
        
        # Check all time windows
        checks = [
            (minute_window, minute_limit),
            (hour_window, hour_limit),
            ("day", self.config.requests_per_day)
        ]
        
        for window_type, limit in checks:
            if not self._check_window(client_id, window_type, limit, current_time):
                # Find which window exceeded the limit
                with self._lock:
                    tokens = self._buckets[client_id][window_type]
                    current_count = len(tokens)
                
                return False, {
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window": window_type,
                    "current_count": current_count,
                    "retry_after": self._calculate_retry_after(window_type, current_time)
                }
        
        # Add tokens for all windows
        for window_type, _ in checks:
            self._add_token(client_id, window_type, current_time)
        
        return True, {}
    
    def _calculate_retry_after(self, window_type: str, current_time: float) -> int:
        """Calculate retry-after seconds for exceeded limit."""
        if window_type == "minute":
            return int(60 - (current_time % 60))
        elif window_type == "hour":
            return int(3600 - (current_time % 3600))
        elif window_type == "day":
            return int(86400 - (current_time % 86400))
        elif window_type == "llm_minute":
            return int(60 - (current_time % 60))
        elif window_type == "llm_hour":
            return int(3600 - (current_time % 3600))
        else:
            return 60
    
    def get_client_stats(self, request: Request, authenticated: bool = False) -> Dict[str, Any]:
        """Get rate limiting statistics for a client."""
        current_time = time.time()
        client_id = self._get_client_id(request, use_ip=not authenticated)
        
        with self._lock:
            stats = {}
            
            for window_type in ["minute", "hour", "day", "llm_minute", "llm_hour"]:
                tokens = self._buckets[client_id][window_type]
                
                # Remove old tokens
                if window_type == "minute" or window_type == "llm_minute":
                    cutoff = current_time - 60
                elif window_type == "hour" or window_type == "llm_hour":
                    cutoff = current_time - 3600
                elif window_type == "day":
                    cutoff = current_time - 86400
                else:
                    continue
                
                while tokens and tokens[0] < cutoff:
                    tokens.popleft()
                
                stats[window_type] = len(tokens)
            
            return stats
    
    def reset_client(self, client_id: str):
        """Reset rate limits for a specific client."""
        with self._lock:
            if client_id in self._buckets:
                del self._buckets[client_id]


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
    
    async def __call__(self, request: Request, call_next: Callable):
        """Middleware to check rate limits before processing request."""
        # Determine endpoint type and authentication status
        endpoint_type = self._get_endpoint_type(request.url.path)
        authenticated = await self._is_authenticated(request)
        
        # Check rate limits
        allowed, limit_info = self.rate_limiter.is_allowed(
            request, 
            endpoint_type=endpoint_type, 
            authenticated=authenticated
        )
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": limit_info.get("retry_after", 60),
                    "limit": limit_info.get("limit"),
                    "window": limit_info.get("window")
                },
                headers={"Retry-After": str(limit_info.get("retry_after", 60))}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        stats = self.rate_limiter.get_client_stats(request, authenticated)
        response.headers["X-RateLimit-Limit-Minute"] = str(
            self.rate_limiter.config.requests_per_minute if not authenticated 
            else self.rate_limiter.config.authenticated_requests_per_minute
        )
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, (self.rate_limiter.config.requests_per_minute if not authenticated 
                   else self.rate_limiter.config.authenticated_requests_per_minute) - stats.get("minute", 0))
        )
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
        
        return response
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type from path."""
        if "/recommendations" in path:
            return "llm"  # Recommendations use LLM
        return "general"
    
    async def _is_authenticated(self, request: Request) -> bool:
        """Check if request is authenticated."""
        # Check for API key in headers
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In a real implementation, validate the API key
            return True
        
        # Check for session cookie or other auth mechanisms
        return False


def rate_limit(endpoint_type: str = "general", authenticated_only: bool = False):
    """Decorator for rate limiting specific endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs (FastAPI dependency injection)
            request = kwargs.get("request")
            if not request:
                # Try to get request from args
                for arg in args:
                    if hasattr(arg, 'client'):  # FastAPI Request object
                        request = arg
                        break
            
            if not request:
                return await func(*args, **kwargs)
            
            # Get rate limiter (should be injected as dependency)
            rate_limiter = kwargs.get("rate_limiter")
            if not rate_limiter:
                return await func(*args, **kwargs)
            
            # Check authentication
            is_authenticated = await _check_authentication(request)
            
            if authenticated_only and not is_authenticated:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for this endpoint"
                )
            
            # Check rate limits
            allowed, limit_info = rate_limiter.is_allowed(
                request, 
                endpoint_type=endpoint_type, 
                authenticated=is_authenticated
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "retry_after": limit_info.get("retry_after", 60)
                    },
                    headers={"Retry-After": str(limit_info.get("retry_after", 60))}
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


async def _check_authentication(request: Request) -> bool:
    """Check if request is authenticated."""
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # In a real implementation, validate the token against a database
        # For now, just check if it looks like a valid token
        token = auth_header[7:]  # Remove "Bearer "
        return len(token) > 10  # Simple validation
    
    return False


class APIKeyAuthenticator:
    """API key authentication for rate limiting."""
    
    def __init__(self, api_keys: Dict[str, Dict[str, Any]]):
        self.api_keys = api_keys  # {key: {tier: "premium", requests_per_minute: 1000}}
    
    async def authenticate(self, request: Request) -> Optional[Dict[str, Any]]:
        """Authenticate request using API key."""
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        api_key = auth_header[7:]
        key_info = self.api_keys.get(api_key)
        
        if not key_info:
            return None
        
        return key_info
    
    def get_rate_limits(self, key_info: Dict[str, Any]) -> RateLimitConfig:
        """Get rate limits based on API key tier."""
        tier = key_info.get("tier", "basic")
        
        if tier == "premium":
            return RateLimitConfig(
                requests_per_minute=200,
                requests_per_hour=5000,
                requests_per_day=50000,
                llm_requests_per_minute=50,
                llm_requests_per_hour=1000
            )
        elif tier == "pro":
            return RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=2000,
                requests_per_day=20000,
                llm_requests_per_minute=25,
                llm_requests_per_hour=500
            )
        else:  # basic
            return RateLimitConfig()


# Global rate limiter instance
default_rate_limiter = RateLimiter(RateLimitConfig())


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return default_rate_limiter


def create_rate_limiter(config: RateLimitConfig) -> RateLimiter:
    """Create new rate limiter with custom config."""
    return RateLimiter(config)


if __name__ == "__main__":
    # Example usage
    rate_limiter = RateLimiter(RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100
    ))
    
    # Mock request for testing
    class MockRequest:
        def __init__(self, client_host: str = "127.0.0.1"):
            self.client = type('Client', (), {'host': client_host})()
    
    request = MockRequest()
    
    # Test rate limiting
    for i in range(15):
        allowed, info = rate_limiter.is_allowed(request)
        print(f"Request {i+1}: {'Allowed' if allowed else 'Blocked'}")
        if not allowed:
            print(f"  Limit info: {info}")
            break
    
    # Get stats
    stats = rate_limiter.get_client_stats(request)
    print(f"Client stats: {stats}")
