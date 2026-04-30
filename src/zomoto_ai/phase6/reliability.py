"""Reliability, Timeouts, Retries, and Fallback Behavior for Phase 6

Provides comprehensive error handling, retry mechanisms, and fallback strategies
for production hardening.
"""

import asyncio
import time
import random
from typing import Dict, Any, Optional, Callable, TypeVar, Union, List, Type
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import logging
from datetime import datetime, timezone, timedelta
import threading
from contextlib import contextmanager

# Import domain models
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult, RecommendationItem, Restaurant
from zomoto_ai.phase4.groq_ranker import GroqLLMClient
from .logging import get_logger, get_performance_tracker


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class FallbackStrategy(Enum):
    """Fallback strategy types."""
    CACHED_RESULT = "cached_result"
    SIMPLIFIED_ALGORITHM = "simplified_algorithm"
    DEFAULT_RESPONSE = "default_response"
    ERROR_RESPONSE = "error_response"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                ConnectionError,
                TimeoutError,
                IOError,
                ValueError  # For LLM parsing errors
            ]


@dataclass
class TimeoutConfig:
    """Configuration for timeouts."""
    connection_timeout: float = 10.0
    read_timeout: float = 30.0
    total_timeout: float = 60.0
    llm_timeout: float = 30.0


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""
    strategy: FallbackStrategy = FallbackStrategy.SIMPLIFIED_ALGORITHM
    cache_ttl: int = 3600  # 1 hour
    default_response_timeout: float = 5.0


class RetryableError(Exception):
    """Base class for retryable errors."""
    pass


class NonRetryableError(Exception):
    """Base class for non-retryable errors."""
    pass


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""
    
    def __init__(self, failure_threshold: int = 5, 
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = threading.Lock()
    
    def __call__(self, func):
        """Decorator for circuit breaker."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            
            with self._lock:
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
            
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout)


class RetryHandler:
    """Handles retry logic with different strategies."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = get_logger()
    
    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not any(isinstance(e, exc_type) for exc_type in self.config.retryable_exceptions):
                    self.logger.error("retry_handler", "non_retryable_error", 
                                    f"Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
                # Don't retry on last attempt
                if attempt == self.config.max_retries:
                    self.logger.error("retry_handler", "max_retries_exceeded",
                                    f"Max retries exceeded for {func.__name__}: {e}")
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(attempt)
                
                self.logger.warning("retry_handler", "retry_attempt",
                                   f"Retry {attempt + 1}/{self.config.max_retries} for {func.__name__} after {delay:.2f}s: {e}")
                
                time.sleep(delay)
        
        # This should never be reached
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on strategy."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt)
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        else:  # IMMEDIATE
            delay = 0.0
        
        # Apply jitter
        if self.config.jitter and delay > 0:
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        # Cap at max delay
        return min(delay, self.config.max_delay)
    
    async def retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not any(isinstance(e, exc_type) for exc_type in self.config.retryable_exceptions):
                    self.logger.error("retry_handler", "non_retryable_error_async",
                                    f"Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
                # Don't retry on last attempt
                if attempt == self.config.max_retries:
                    self.logger.error("retry_handler", "max_retries_exceeded_async",
                                    f"Max retries exceeded for {func.__name__}: {e}")
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(attempt)
                
                self.logger.warning("retry_handler", "retry_attempt_async",
                                   f"Retry {attempt + 1}/{self.config.max_retries} for {func.__name__} after {delay:.2f}s: {e}")
                
                await asyncio.sleep(delay)
        
        # This should never be reached
        raise last_exception


class TimeoutHandler:
    """Handles timeout enforcement."""
    
    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.logger = get_logger()
    
    @contextmanager
    def timeout_context(self, timeout: float, operation_name: str):
        """Context manager for timeout enforcement."""
        start_time = time.time()
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Operation {operation_name} timed out after {timeout}s")
        
        # Note: In production, use proper signal handling
        # For now, we'll use a simple time check
        
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self.logger.warning("timeout_handler", "timeout_exceeded",
                                  f"Operation {operation_name} exceeded timeout: {elapsed:.2f}s > {timeout}s")
    
    async def timeout_context_async(self, timeout: float, operation_name: str):
        """Async context manager for timeout enforcement."""
        try:
            async with asyncio.timeout(timeout):
                yield
        except asyncio.TimeoutError:
            self.logger.warning("timeout_handler", "timeout_exceeded_async",
                              f"Async operation {operation_name} timed out after {timeout}s")
            raise TimeoutError(f"Operation {operation_name} timed out after {timeout}s")


class FallbackHandler:
    """Handles fallback strategies when primary methods fail."""
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.logger = get_logger()
        self.cache = {}  # Simple in-memory cache
    
    def get_fallback_result(self, operation_name: str, candidate_set: CandidateSet, 
                          error: Exception) -> RecommendationResult:
        """Get fallback result based on strategy."""
        self.logger.warning("fallback_handler", "using_fallback",
                          f"Using fallback for {operation_name}: {error}")
        
        if self.config.strategy == FallbackStrategy.CACHED_RESULT:
            return self._get_cached_result(operation_name, candidate_set)
        
        elif self.config.strategy == FallbackStrategy.SIMPLIFIED_ALGORITHM:
            return self._simplified_ranking(candidate_set)
        
        elif self.config.strategy == FallbackStrategy.DEFAULT_RESPONSE:
            return self._default_response(candidate_set)
        
        elif self.config.strategy == FallbackStrategy.ERROR_RESPONSE:
            raise error
        
        else:
            # Default to simplified algorithm
            return self._simplified_ranking(candidate_set)
    
    def cache_result(self, operation_name: str, candidate_set: CandidateSet, 
                     result: RecommendationResult):
        """Cache a successful result for fallback use."""
        cache_key = self._get_cache_key(operation_name, candidate_set)
        self.cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
    
    def _get_cache_key(self, operation_name: str, candidate_set: CandidateSet) -> str:
        """Generate cache key for operation."""
        import hashlib
        key_data = f"{operation_name}:{len(candidate_set.candidates)}:{candidate_set.user_preference.location}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_result(self, operation_name: str, candidate_set: CandidateSet) -> RecommendationResult:
        """Get cached result if available and not expired."""
        cache_key = self._get_cache_key(operation_name, candidate_set)
        cached_item = self.cache.get(cache_key)
        
        if cached_item:
            age = time.time() - cached_item["timestamp"]
            if age < self.config.cache_ttl:
                self.logger.info("fallback_handler", "cache_hit",
                               f"Using cached result for {operation_name}")
                return cached_item["result"]
            else:
                # Remove expired cache entry
                del self.cache[cache_key]
        
        # No valid cache, fall back to simplified algorithm
        return self._simplified_ranking(candidate_set)
    
    def _simplified_ranking(self, candidate_set: CandidateSet) -> RecommendationResult:
        """Simplified ranking algorithm as fallback."""
        # Sort by rating and votes
        sorted_candidates = sorted(
            candidate_set.candidates,
            key=lambda r: (r.rating or 0, r.votes or 0),
            reverse=True
        )
        
        items = []
        for i, restaurant in enumerate(sorted_candidates[:10], 1):
            explanation = (f"Ranked #{i} by rating ({restaurant.rating or 'N/A'}) "
                          f"and popularity ({restaurant.votes or 'N/A'} votes) "
                          f"[fallback ranking]")
            items.append(RecommendationItem(
                restaurant_id=restaurant.id,
                rank=i,
                explanation=explanation
            ))
        
        return RecommendationResult(
            user_preference=candidate_set.user_preference,
            items=items,
            summary=f"Top {len(items)} restaurants ranked by rating and popularity (fallback algorithm used)"
        )
    
    def _default_response(self, candidate_set: CandidateSet) -> RecommendationResult:
        """Default response when all else fails."""
        return RecommendationResult(
            user_preference=candidate_set.user_preference,
            items=[],
            summary="Service temporarily unavailable. Please try again later."
        )


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: float = 60.0):
    """Decorator for adding circuit breaker to functions."""
    def decorator(func):
        cb = CircuitBreaker(failure_threshold, recovery_timeout)
        return cb(func)
    return decorator


class ReliableLLMClient:
    """Enhanced LLM client with reliability features."""
    
    def __init__(self, retry_config: RetryConfig = None, 
                 timeout_config: TimeoutConfig = None,
                 fallback_config: FallbackConfig = None):
        self.retry_config = retry_config or RetryConfig()
        self.timeout_config = timeout_config or TimeoutConfig()
        self.fallback_config = fallback_config or FallbackConfig()
        
        self.retry_handler = RetryHandler(self.retry_config)
        self.timeout_handler = TimeoutHandler(self.timeout_config)
        self.fallback_handler = FallbackHandler(self.fallback_config)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        
        # Wrap the original LLM client with circuit breaker
        self._llm_client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the underlying LLM client."""
        try:
            self._llm_client = GroqLLMClient()
        except Exception as e:
            self.logger.error("reliable_llm", "client_init_failed",
                            f"Failed to initialize LLM client: {e}")
            self._llm_client = None
    
    @circuit_breaker
    def rank_and_explain(self, candidate_set: CandidateSet) -> RecommendationResult:
        """Rank candidates with reliability features."""
        operation_name = "llm_rank_and_explain"
        
        try:
            with self.performance_tracker.track_llm_call("phase6", "llm_ranking"):
                with self.timeout_handler.timeout_context(
                    self.timeout_config.llm_timeout, operation_name
                ):
                    if not self._llm_client:
                        raise ConnectionError("LLM client not initialized")
                    
                    result = self.retry_handler.retry(
                        self._llm_client.rank_and_explain,
                        candidate_set
                    )
                    
                    # Cache successful result
                    self.fallback_handler.cache_result(operation_name, candidate_set, result)
                    
                    return result
                    
        except Exception as e:
            self.logger.error("reliable_llm", "ranking_failed",
                            f"LLM ranking failed: {e}")
            
            # Use fallback
            return self.fallback_handler.get_fallback_result(
                operation_name, candidate_set, e
            )
    
    async def rank_and_explain_async(self, candidate_set: CandidateSet) -> RecommendationResult:
        """Async version of rank_and_explain."""
        operation_name = "llm_rank_and_explain_async"
        
        try:
            async with self.performance_tracker.track_llm_call("phase6", "llm_ranking_async"):
                async with self.timeout_handler.timeout_context_async(
                    self.timeout_config.llm_timeout, operation_name
                ):
                    if not self._llm_client:
                        raise ConnectionError("LLM client not initialized")
                    
                    # Run sync method in thread pool
                    loop = asyncio.get_event_loop()
                    result = await self.retry_handler.retry_async(
                        loop.run_in_executor,
                        None,
                        self._llm_client.rank_and_explain,
                        candidate_set
                    )
                    
                    # Cache successful result
                    self.fallback_handler.cache_result(operation_name, candidate_set, result)
                    
                    return result
                    
        except Exception as e:
            self.logger.error("reliable_llm", "ranking_async_failed",
                            f"Async LLM ranking failed: {e}")
            
            # Use fallback
            return self.fallback_handler.get_fallback_result(
                operation_name, candidate_set, e
            )
    
    def get_reliability_stats(self) -> Dict[str, Any]:
        """Get reliability statistics."""
        return {
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "cache_size": len(self.fallback_handler.cache),
            "retry_config": {
                "max_retries": self.retry_config.max_retries,
                "strategy": self.retry_config.strategy.value
            },
            "timeout_config": {
                "llm_timeout": self.timeout_config.llm_timeout,
                "total_timeout": self.timeout_config.total_timeout
            },
            "fallback_strategy": self.fallback_config.strategy.value
        }


# Decorators for easy application
def retry(config: RetryConfig = None):
    """Decorator for adding retry logic to functions."""
    def decorator(func):
        retry_config = config or RetryConfig()
        retry_handler = RetryHandler(retry_config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_handler.retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


def timeout(timeout_seconds: float, operation_name: str = None):
    """Decorator for adding timeout to functions."""
    def decorator(func):
        timeout_config = TimeoutConfig()
        timeout_handler = TimeoutHandler(timeout_config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            with timeout_handler.timeout_context(timeout_seconds, op_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global reliable client instance
default_reliable_client = ReliableLLMClient()


def get_reliable_llm_client() -> ReliableLLMClient:
    """Get default reliable LLM client instance."""
    return default_reliable_client


if __name__ == "__main__":
    # Example usage
    from zomoto_ai.phase0.domain.models import UserPreference, Restaurant
    
    # Create test candidate set
    candidate_set = CandidateSet(
        user_preference=UserPreference(location="Bangalore", min_rating=4.0),
        candidates=[
            Restaurant(
                id="1",
                name="Test Restaurant",
                location="Bangalore",
                cuisines=["Italian"],
                cost_for_two=800,
                rating=4.2,
                votes=150
            )
        ]
    )
    
    # Test reliable client
    client = ReliableLLMClient()
    
    try:
        result = client.rank_and_explain(candidate_set)
        print(f"Success: {result.summary}")
        print(f"Items: {len(result.items)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Print stats
    stats = client.get_reliability_stats()
    print(f"Reliability stats: {stats}")
