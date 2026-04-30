"""Timeout Manager - Timeout enforcement for operations

Provides configurable timeout enforcement for synchronous and
asynchronous operations with proper error handling.
"""

import asyncio
import time
import signal
from contextlib import contextmanager, asynccontextmanager
from typing import Callable, Any, Optional
from functools import wraps
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger


class TimeoutError(Exception):
    """Custom timeout error."""
    pass


class TimeoutManager:
    """Manages timeout enforcement for operations."""
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self.logger = get_logger()
    
    @contextmanager
    def timeout_context(self, timeout: float, operation_name: str = "operation"):
        """Context manager for timeout enforcement."""
        start_time = time.time()
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Operation {operation_name} timed out after {timeout}s")
        
        # Set up signal handler for timeout
        old_handler = None
        if hasattr(signal, 'SIGALRM'):  # Unix-like systems
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))
        
        try:
            yield
        finally:
            # Clean up signal handler
            if hasattr(signal, 'SIGALRM') and old_handler:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self.logger.warning("timeout_manager", "timeout_exceeded",
                                  f"Operation {operation_name} exceeded timeout: {elapsed:.2f}s > {timeout}s")
    
    @asynccontextmanager
    async def timeout_context_async(self, timeout: float, operation_name: str = "operation"):
        """Async context manager for timeout enforcement."""
        start_time = time.time()
        
        try:
            async with asyncio.timeout(timeout):
                yield
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.logger.warning("timeout_manager", "timeout_exceeded_async",
                              f"Async operation {operation_name} timed out after {timeout}s")
            raise TimeoutError(f"Async operation {operation_name} timed out after {timeout}s")
        finally:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self.logger.warning("timeout_manager", "timeout_exceeded_async",
                                  f"Async operation {operation_name} exceeded timeout: {elapsed:.2f}s > {timeout}s")
    
    def execute_with_timeout(
        self,
        func: Callable,
        timeout: Optional[float] = None,
        operation_name: str = "operation",
        *args,
        **kwargs
    ) -> Any:
        """Execute function with timeout enforcement."""
        timeout = timeout or self.default_timeout
        
        try:
            with self.timeout_context(timeout, operation_name):
                return func(*args, **kwargs)
        except TimeoutError:
            self.logger.error("timeout_manager", "execution_timeout",
                            f"Function {func.__name__} timed out after {timeout}s")
            raise
        except Exception as e:
            self.logger.error("timeout_manager", "execution_error",
                            f"Function {func.__name__} failed: {str(e)}")
            raise
    
    async def execute_with_timeout_async(
        self,
        func: Callable,
        timeout: Optional[float] = None,
        operation_name: str = "operation",
        *args,
        **kwargs
    ) -> Any:
        """Execute async function with timeout enforcement."""
        timeout = timeout or self.default_timeout
        
        try:
            async with self.timeout_context_async(timeout, operation_name):
                return await func(*args, **kwargs)
        except TimeoutError:
            self.logger.error("timeout_manager", "execution_timeout_async",
                            f"Async function {func.__name__} timed out after {timeout}s")
            raise
        except Exception as e:
            self.logger.error("timeout_manager", "execution_error_async",
                            f"Async function {func.__name__} failed: {str(e)}")
            raise
    
    def run_with_timeout(
        self,
        func: Callable,
        timeout: Optional[float] = None,
        operation_name: str = "operation",
        *args,
        **kwargs
    ) -> Any:
        """Run function in separate thread with timeout."""
        timeout = timeout or self.default_timeout
        
        try:
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(func, *args, **kwargs)
                
                try:
                    result = future.result(timeout=timeout)
                    return result
                except concurrent.futures.TimeoutError:
                    self.logger.error("timeout_manager", "thread_timeout",
                                    f"Function {func.__name__} in thread timed out after {timeout}s")
                    raise TimeoutError(f"Function {func.__name__} timed out after {timeout}s")
                except Exception as e:
                    self.logger.error("timeout_manager", "thread_execution_error",
                                    f"Function {func.__name__} in thread failed: {str(e)}")
                    raise
                    
        except Exception as e:
            if not isinstance(e, TimeoutError):
                self.logger.error("timeout_manager", "thread_setup_failed",
                                f"Failed to setup thread execution: {str(e)}")
            raise
    
    def get_timeout_stats(self) -> dict:
        """Get timeout manager statistics."""
        return {
            "default_timeout": self.default_timeout,
            "supported_platforms": {
                "signal_timeout": hasattr(signal, 'SIGALRM'),
                "asyncio_timeout": True,
                "thread_timeout": True
            }
        }


# Global timeout manager instance
_timeout_manager = TimeoutManager()


def get_timeout_manager() -> TimeoutManager:
    """Get global timeout manager instance."""
    return _timeout_manager


# Decorators for easy application
def timeout(timeout: float, operation_name: str = None):
    """Decorator for adding timeout to functions."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return get_timeout_manager().execute_with_timeout(
                func, timeout, op_name, *args, **kwargs
            )
        
        return wrapper
    return decorator


def timeout_async(timeout: float, operation_name: str = None):
    """Decorator for adding timeout to async functions."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await get_timeout_manager().execute_with_timeout_async(
                func, timeout, op_name, *args, **kwargs
            )
        
        return wrapper
    return decorator


def timeout_thread(timeout: float, operation_name: str = None):
    """Decorator for adding timeout to functions via thread execution."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return get_timeout_manager().run_with_timeout(
                func, timeout, op_name, *args, **kwargs
            )
        
        return wrapper
    return decorator


# Pre-configured timeout decorators for common scenarios
def database_timeout(func: Callable) -> Callable:
    """Decorator for database operations with 10s timeout."""
    return timeout(10.0, f"database_{func.__name__}")(func)


def llm_timeout(func: Callable) -> Callable:
    """Decorator for LLM operations with 30s timeout."""
    return timeout(30.0, f"llm_{func.__name__}")(func)


def llm_timeout_async(func: Callable) -> Callable:
    """Decorator for async LLM operations with 30s timeout."""
    return timeout_async(30.0, f"llm_{func.__name__}")(func)


def cache_timeout(func: Callable) -> Callable:
    """Decorator for cache operations with 5s timeout."""
    return timeout(5.0, f"cache_{func.__name__}")(func)


def api_timeout(func: Callable) -> Callable:
    """Decorator for API operations with 15s timeout."""
    return timeout(15.0, f"api_{func.__name__}")(func)


def api_timeout_async(func: Callable) -> Callable:
    """Decorator for async API operations with 15s timeout."""
    return timeout_async(15.0, f"api_{func.__name__}")(func)


# Context manager shortcuts
def with_timeout(timeout: float, operation_name: str = "operation"):
    """Get timeout context manager."""
    return get_timeout_manager().timeout_context(timeout, operation_name)


async def with_timeout_async(timeout: float, operation_name: str = "operation"):
    """Get async timeout context manager."""
    async with get_timeout_manager().timeout_context_async(timeout, operation_name):
        yield
