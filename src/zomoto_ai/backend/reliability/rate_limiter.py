"""Rate Limiter - Token bucket algorithm for API protection

Implements rate limiting with multiple time windows and user tiers
to prevent abuse and ensure fair usage.
"""

import time
import threading
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger


class RateLimitTier(Enum):
    """Rate limit tiers for different user types."""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    ADMIN = "admin"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # Anonymous user limits
    anonymous_rpm: int = 60    # requests per minute
    anonymous_rph: int = 1000  # requests per hour
    anonymous_rpd: int = 10000 # requests per day
    
    # Authenticated user limits
    authenticated_rpm: int = 120
    authenticated_rph: int = 2000
    authenticated_rpd: int = 20000
    
    # Premium user limits
    premium_rpm: int = 300
    premium_rph: int = 5000
    premium_rpd: int = 50000
    
    # Admin user limits
    admin_rpm: int = 1000
    admin_rph: int = 20000
    admin_rpd: int = 200000
    
    # LLM-specific limits (more restrictive)
    llm_rpm: int = 20
    llm_rph: int = 100
    llm_rpd: int = 1000


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens if available."""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def get_state(self) -> Dict[str, Any]:
        """Get bucket state."""
        with self._lock:
            self._refill()
            return {
                "tokens": self.tokens,
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "last_refill": self.last_refill
            }


class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.logger = get_logger()
        
        # User buckets: {identifier: {window: TokenBucket}}
        self.user_buckets = {}
        self._lock = threading.Lock()
        
        # Window configurations (in seconds)
        self.windows = {
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
    
    def is_allowed(
        self,
        identifier: str,
        tier: RateLimitTier = RateLimitTier.ANONYMOUS,
        endpoint_type: str = "api"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed."""
        with self._lock:
            # Get or create user buckets
            if identifier not in self.user_buckets:
                self.user_buckets[identifier] = self._create_user_buckets(tier)
            
            user_buckets = self.user_buckets[identifier]
            
            # Check each window
            for window_name, window_seconds in self.windows.items():
                bucket = user_buckets[window_name]
                
                if not bucket.consume(1):
                    # Rate limit exceeded
                    reset_time = self._calculate_reset_time(bucket, window_seconds)
                    
                    self.logger.warning("rate_limiter", "limit_exceeded",
                                      f"Rate limit exceeded for {identifier} in {window_name}",
                                      identifier=identifier,
                                      tier=tier.value,
                                      window=window_name,
                                      endpoint_type=endpoint_type)
                    
                    return False, {
                        "allowed": False,
                        "limit": bucket.capacity,
                        "remaining": 0,
                        "reset_time": reset_time,
                        "window": window_name,
                        "retry_after": int(reset_time - time.time())
                    }
            
            # Request allowed
            return True, {
                "allowed": True,
                "limit": user_buckets["minute"].capacity,
                "remaining": int(user_buckets["minute"].tokens),
                "reset_time": time.time() + 60,
                "window": "minute",
                "retry_after": 0
            }
    
    def _create_user_buckets(self, tier: RateLimitTier) -> Dict[str, TokenBucket]:
        """Create token buckets for a user tier."""
        buckets = {}
        
        if tier == RateLimitTier.ANONYMOUS:
            rpm = self.config.anonymous_rpm
            rph = self.config.anonymous_rph
            rpd = self.config.anonymous_rpd
        elif tier == RateLimitTier.AUTHENTICATED:
            rpm = self.config.authenticated_rpm
            rph = self.config.authenticated_rph
            rpd = self.config.authenticated_rpd
        elif tier == RateLimitTier.PREMIUM:
            rpm = self.config.premium_rpm
            rph = self.config.premium_rph
            rpd = self.config.premium_rpd
        elif tier == RateLimitTier.ADMIN:
            rpm = self.config.admin_rpm
            rph = self.config.admin_rph
            rpd = self.config.admin_rpd
        else:
            rpm = self.config.anonymous_rpm
            rph = self.config.anonymous_rph
            rpd = self.config.anonymous_rpd
        
        # Create buckets for each window
        buckets["minute"] = TokenBucket(rpm, rpm / 60)
        buckets["hour"] = TokenBucket(rph, rph / 3600)
        buckets["day"] = TokenBucket(rpd, rpd / 86400)
        
        return buckets
    
    def _calculate_reset_time(self, bucket: TokenBucket, window_seconds: int) -> float:
        """Calculate when the bucket will be full again."""
        tokens_needed = bucket.capacity - bucket.tokens
        if tokens_needed <= 0:
            return time.time()
        
        seconds_to_refill = tokens_needed / bucket.refill_rate
        return time.time() + min(seconds_to_refill, window_seconds)
    
    def get_user_stats(self, identifier: str) -> Dict[str, Any]:
        """Get rate limiting statistics for a user."""
        with self._lock:
            if identifier not in self.user_buckets:
                return {"error": "User not found"}
            
            user_buckets = self.user_buckets[identifier]
            
            return {
                "identifier": identifier,
                "buckets": {
                    window: bucket.get_state()
                    for window, bucket in user_buckets.items()
                }
            }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Get global rate limiting statistics."""
        with self._lock:
            total_users = len(self.user_buckets)
            active_users = sum(
                1 for buckets in self.user_buckets.values()
                if any(bucket.tokens > 0 for bucket in buckets.values())
            )
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "config": {
                    "anonymous": {"rpm": self.config.anonymous_rpm, "rph": self.config.anonymous_rph},
                    "authenticated": {"rpm": self.config.authenticated_rpm, "rph": self.config.authenticated_rph},
                    "premium": {"rpm": self.config.premium_rpm, "rph": self.config.premium_rph},
                    "admin": {"rpm": self.config.admin_rpm, "rph": self.config.admin_rph}
                }
            }
    
    def cleanup_expired_users(self, max_age_hours: int = 24):
        """Clean up inactive user buckets."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self._lock:
            users_to_remove = []
            
            for identifier, buckets in self.user_buckets.items():
                # Check if all buckets have been inactive
                oldest_activity = min(
                    bucket.last_refill for bucket in buckets.values()
                )
                
                if oldest_activity < cutoff_time:
                    users_to_remove.append(identifier)
            
            for identifier in users_to_remove:
                del self.user_buckets[identifier]
            
            self.logger.info("rate_limiter", "cleanup_completed",
                           f"Cleaned up {len(users_to_remove)} inactive users",
                           cleaned_users=len(users_to_remove))
    
    def reset_user(self, identifier: str):
        """Reset rate limiting for a specific user."""
        with self._lock:
            if identifier in self.user_buckets:
                tier = self._determine_user_tier(identifier)
                self.user_buckets[identifier] = self._create_user_buckets(tier)
                
                self.logger.info("rate_limiter", "user_reset",
                               f"Reset rate limiting for user: {identifier}",
                               identifier=identifier)
    
    def _determine_user_tier(self, identifier: str) -> RateLimitTier:
        """Determine user tier (simplified implementation)."""
        # In a real implementation, this would check user roles, API keys, etc.
        if identifier.startswith("admin_"):
            return RateLimitTier.ADMIN
        elif identifier.startswith("premium_"):
            return RateLimitTier.PREMIUM
        elif identifier.startswith("auth_"):
            return RateLimitTier.AUTHENTICATED
        else:
            return RateLimitTier.ANONYMOUS


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter


def check_rate_limit(
    identifier: str,
    tier: RateLimitTier = RateLimitTier.ANONYMOUS,
    endpoint_type: str = "api"
) -> Tuple[bool, Dict[str, Any]]:
    """Check rate limit for a request."""
    return get_rate_limiter().is_allowed(identifier, tier, endpoint_type)
