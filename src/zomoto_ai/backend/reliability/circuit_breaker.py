"""Circuit Breaker - Prevent cascade failures

Implements the circuit breaker pattern to prevent repeated calls
to failing services and provide automatic recovery.
"""

import time
import threading
from typing import Callable, Type, Optional, Dict, Any
from functools import wraps
from enum import Enum
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        name: str = "unknown"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.logger = get_logger()
        
        # State tracking
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = threading.Lock()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator for circuit breaker protection."""
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
                    self.logger.info("circuit_breaker", "state_change", 
                                   f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                else:
                    self.logger.warning("circuit_breaker", "open_circuit", 
                                      f"Circuit breaker {self.name} is OPEN - call blocked")
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            
            with self._lock:
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self.logger.info("circuit_breaker", "state_change", 
                                   f"Circuit breaker {self.name} transitioning to CLOSED")
            
            return result
            
        except self.expected_exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                self.logger.warning("circuit_breaker", "failure", 
                                  f"Circuit breaker {self.name} recorded failure {self.failure_count}/{self.failure_threshold}: {str(e)}")
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                    self.logger.error("circuit_breaker", "state_change", 
                                    f"Circuit breaker {self.name} transitioning to OPEN after {self.failure_count} failures")
            
            raise
        except Exception as e:
            # For unexpected exceptions, don't count as circuit breaker failures
            self.logger.error("circuit_breaker", "unexpected_error", 
                            f"Circuit breaker {self.name} encountered unexpected error: {str(e)}")
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self.state
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "last_failure_time": self.last_failure_time,
                "time_until_reset": max(0, self.recovery_timeout - (time.time() - self.last_failure_time)) if self.last_failure_time else 0
            }
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            self.logger.info("circuit_breaker", "manual_reset", f"Circuit breaker {self.name} manually reset")


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers = {}
        self.logger = get_logger()
    
    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name
            )
        
        return self.circuit_breakers[name]
    
    def get_all_stats(self) -> dict:
        """Get statistics for all circuit breakers."""
        return {
            name: cb.get_stats() 
            for name, cb in self.circuit_breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()
        
        self.logger.info("circuit_breaker_manager", "reset_all", "All circuit breakers reset")


# Global circuit breaker manager
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager."""
    return _circuit_breaker_manager


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """Decorator for circuit breaker protection."""
    def decorator(func: Callable) -> Callable:
        cb = get_circuit_breaker_manager().get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception
        )
        return cb(func)
    return decorator


# Pre-configured circuit breakers for common services
LLM_CIRCUIT_BREAKER = get_circuit_breaker_manager().get_circuit_breaker(
    name="llm_service",
    failure_threshold=3,
    recovery_timeout=30.0,
    expected_exception=ConnectionError
)

DATABASE_CIRCUIT_BREAKER = get_circuit_breaker_manager().get_circuit_breaker(
    name="database_service",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)

CACHE_CIRCUIT_BREAKER = get_circuit_breaker_manager().get_circuit_breaker(
    name="cache_service",
    failure_threshold=10,
    recovery_timeout=30.0,
    expected_exception=ConnectionError
)
