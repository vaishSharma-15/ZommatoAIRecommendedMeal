"""Retry Handler - Exponential backoff and retry logic

Implements various retry strategies with configurable backoff
patterns for handling transient failures.
"""

import asyncio
import time
import random
from typing import Callable, Type, List, Optional, Union, Any, Dict
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1  # 10% jitter by default
    retryable_exceptions: List[Type[Exception]] = None
    non_retryable_exceptions: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                ConnectionError,
                TimeoutError,
                IOError,
                ValueError,
                KeyError,
                RuntimeError
            ]
        
        if self.non_retryable_exceptions is None:
            self.non_retryable_exceptions = [
                KeyboardInterrupt,
                SystemExit,
                MemoryError,
                AssertionError
            ]


class RetryHandler:
    """Handles retry logic with different strategies."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.logger = get_logger()
    
    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is non-retryable
                if any(isinstance(e, exc_type) for exc_type in self.config.non_retryable_exceptions):
                    self.logger.error("retry_handler", "non_retryable_error",
                                    f"Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
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
    
    async def retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is non-retryable
                if any(isinstance(e, exc_type) for exc_type in self.config.non_retryable_exceptions):
                    self.logger.error("retry_handler", "non_retryable_error_async",
                                    f"Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
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
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on strategy."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt)
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = self.config.base_delay * self._fibonacci(attempt + 1)
        else:  # IMMEDIATE
            delay = 0.0
        
        # Apply jitter
        if self.config.jitter and delay > 0:
            jitter_amount = delay * self.config.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        # Cap at max delay
        return min(delay, self.config.max_delay)
    
    def _fibonacci(self, n: int) -> int:
        """Calculate Fibonacci number."""
        if n <= 1:
            return n
        
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        
        return b
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry handler statistics."""
        return {
            "config": {
                "max_retries": self.config.max_retries,
                "strategy": self.config.strategy.value,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "backoff_multiplier": self.config.backoff_multiplier,
                "jitter": self.config.jitter,
                "retryable_exceptions": [exc.__name__ for exc in self.config.retryable_exceptions],
                "non_retryable_exceptions": [exc.__name__ for exc in self.config.non_retryable_exceptions]
            }
        }


# Decorators for easy application
def retry(config: RetryConfig = None):
    """Decorator for adding retry logic to functions."""
    def decorator(func: Callable) -> Callable:
        retry_handler = RetryHandler(config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_handler.retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


def retry_async(config: RetryConfig = None):
    """Decorator for adding retry logic to async functions."""
    def decorator(func: Callable) -> Callable:
        retry_handler = RetryHandler(config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_handler.retry_async(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Pre-configured retry handlers for common scenarios
DATABASE_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=[ConnectionError, TimeoutError, IOError]
)

LLM_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=[ConnectionError, TimeoutError, ValueError]
)

CACHE_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    strategy=RetryStrategy.LINEAR_BACKOFF,
    base_delay=0.1,
    max_delay=1.0,
    retryable_exceptions=[ConnectionError, TimeoutError]
)

API_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=0.2,
    max_delay=5.0,
    retryable_exceptions=[ConnectionError, TimeoutError, IOError]
)

# Pre-configured retry handlers
database_retry_handler = RetryHandler(DATABASE_RETRY_CONFIG)
llm_retry_handler = RetryHandler(LLM_RETRY_CONFIG)
cache_retry_handler = RetryHandler(CACHE_RETRY_CONFIG)
api_retry_handler = RetryHandler(API_RETRY_CONFIG)


def retry_database(func: Callable) -> Callable:
    """Decorator for database operations retry."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return database_retry_handler.retry(func, *args, **kwargs)
    return wrapper


def retry_llm(func: Callable) -> Callable:
    """Decorator for LLM operations retry."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return llm_retry_handler.retry(func, *args, **kwargs)
    return wrapper


def retry_llm_async(func: Callable) -> Callable:
    """Decorator for async LLM operations retry."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await llm_retry_handler.retry_async(func, *args, **kwargs)
    return wrapper


def retry_cache(func: Callable) -> Callable:
    """Decorator for cache operations retry."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return cache_retry_handler.retry(func, *args, **kwargs)
    return wrapper


def retry_api(func: Callable) -> Callable:
    """Decorator for API operations retry."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return api_retry_handler.retry(func, *args, **kwargs)
    return wrapper


def retry_api_async(func: Callable) -> Callable:
    """Decorator for async API operations retry."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await api_retry_handler.retry_async(func, *args, **kwargs)
    return wrapper
