"""Fallback Handler - Fallback behavior when primary services fail

Provides fallback strategies for when primary services are unavailable,
ensuring system continues to function with degraded capabilities.
"""

import asyncio
import time
from typing import Any, Optional, Dict, List
from abc import ABC, abstractmethod
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult, RecommendationItem, Restaurant
from zomoto_ai.phase6.logging import get_logger


class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies."""
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute fallback strategy."""
        pass


class CacheFallbackStrategy(FallbackStrategy):
    """Fallback strategy for cache operations."""
    
    def __init__(self):
        self.logger = get_logger()
        self._memory_cache = {}
    
    async def execute(self, operation: str, key: str, value: Any = None, **kwargs) -> Any:
        """Execute cache fallback operation."""
        if operation == "get":
            return self._memory_cache.get(key)
        elif operation == "set":
            self._memory_cache[key] = value
            return True
        elif operation == "delete":
            return self._memory_cache.pop(key, None) is not None
        else:
            return None


class LLMFallbackStrategy(FallbackStrategy):
    """Fallback strategy for LLM operations."""
    
    def __init__(self):
        self.logger = get_logger()
    
    async def execute(self, candidate_set: CandidateSet, **kwargs) -> RecommendationResult:
        """Execute LLM fallback - simplified ranking."""
        self.logger.info("llm_fallback", "simplified_ranking", "Using simplified ranking fallback")
        
        # Sort candidates by rating and votes
        sorted_candidates = sorted(
            candidate_set.candidates,
            key=lambda r: (r.rating or 0, r.votes or 0),
            reverse=True
        )
        
        items = []
        for i, restaurant in enumerate(sorted_candidates[:10], 1):
            explanation = self._generate_simple_explanation(restaurant, i)
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
    
    def _generate_simple_explanation(self, restaurant: Restaurant, rank: int) -> str:
        """Generate simple explanation based on available data."""
        reasons = []
        
        if restaurant.rating and restaurant.rating >= 4.0:
            reasons.append(f"high rating of {restaurant.rating}")
        elif restaurant.rating:
            reasons.append(f"rating of {restaurant.rating}")
        
        if restaurant.votes and restaurant.votes > 100:
            reasons.append(f"popular with {restaurant.votes} reviews")
        
        if restaurant.cost_for_two:
            if restaurant.cost_for_two <= 500:
                reasons.append("affordable pricing")
            elif restaurant.cost_for_two <= 1000:
                reasons.append("moderate pricing")
            else:
                reasons.append("premium dining")
        
        if restaurant.cuisines:
            if len(restaurant.cuisines) == 1:
                reasons.append(f"specializes in {restaurant.cuisines[0]} cuisine")
            else:
                reasons.append(f"offers {', '.join(restaurant.cuisines[:2])} cuisines")
        
        if not reasons:
            reasons.append("matches your preferences")
        
        return f"Ranked #{rank} for its {', '.join(reasons)}."


class DatabaseFallbackStrategy(FallbackStrategy):
    """Fallback strategy for database operations."""
    
    def __init__(self):
        self.logger = get_logger()
        self._fallback_data = []
    
    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute database fallback operation."""
        if operation == "search":
            return self._search_fallback(**kwargs)
        elif operation == "get_by_id":
            return self._get_by_id_fallback(**kwargs)
        else:
            return None
    
    def _search_fallback(self, location: str, **kwargs) -> List[Dict[str, Any]]:
        """Fallback search using mock data."""
        self.logger.warning("database_fallback", "mock_search", "Using mock search data")
        
        # Return empty results for now
        # In a real implementation, this could use cached data or static fallback data
        return []
    
    def _get_by_id_fallback(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Fallback get by ID using mock data."""
        self.logger.warning("database_fallback", "mock_get", f"Using mock data for restaurant {restaurant_id}")
        return None


class FallbackHandler:
    """Main fallback handler that manages multiple fallback strategies."""
    
    def __init__(self):
        self.logger = get_logger()
        self.strategies = {
            "cache": CacheFallbackStrategy(),
            "llm": LLMFallbackStrategy(),
            "database": DatabaseFallbackStrategy()
        }
        self._fallback_counts = {}
    
    async def execute_fallback(
        self,
        service_name: str,
        operation: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute fallback for a service operation."""
        start_time = time.time()
        
        try:
            if service_name not in self.strategies:
                self.logger.error("fallback_handler", "no_strategy",
                                f"No fallback strategy for service: {service_name}")
                raise ValueError(f"No fallback strategy for {service_name}")
            
            strategy = self.strategies[service_name]
            
            self.logger.warning("fallback_handler", "executing",
                              f"Executing fallback for {service_name}.{operation}",
                              service=service_name,
                              operation=operation)
            
            # Track fallback usage
            key = f"{service_name}.{operation}"
            self._fallback_counts[key] = self._fallback_counts.get(key, 0) + 1
            
            # Execute fallback strategy
            result = await strategy.execute(operation, *args, **kwargs)
            
            execution_time = time.time() - start_time
            
            self.logger.info("fallback_handler", "completed",
                           f"Fallback completed for {service_name}.{operation} in {execution_time:.2f}s",
                           service=service_name,
                           operation=operation,
                           execution_time=execution_time)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error("fallback_handler", "failed",
                            f"Fallback failed for {service_name}.{operation}: {str(e)}",
                            service=service_name,
                            operation=operation,
                            execution_time=execution_time,
                            exc_info=True)
            raise
    
    def register_strategy(self, service_name: str, strategy: FallbackStrategy):
        """Register a custom fallback strategy."""
        self.strategies[service_name] = strategy
        self.logger.info("fallback_handler", "strategy_registered",
                        f"Registered fallback strategy for {service_name}")
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback usage statistics."""
        return {
            "fallback_counts": self._fallback_counts.copy(),
            "total_fallbacks": sum(self._fallback_counts.values()),
            "registered_strategies": list(self.strategies.keys())
        }
    
    def reset_stats(self):
        """Reset fallback usage statistics."""
        self._fallback_counts.clear()
        self.logger.info("fallback_handler", "stats_reset", "Fallback statistics reset")


# Global fallback handler instance
_fallback_handler = FallbackHandler()


def get_fallback_handler() -> FallbackHandler:
    """Get global fallback handler instance."""
    return _fallback_handler


# Decorator for automatic fallback
def fallback_on_failure(service_name: str, operation: str = None):
    """Decorator for automatic fallback on failure."""
    def decorator(func):
        op_name = operation or func.__name__
        fallback_handler = get_fallback_handler()
        
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                fallback_handler.logger.warning("fallback_decorator", "primary_failed",
                                             f"Primary function failed, using fallback: {str(e)}")
                return await fallback_handler.execute_fallback(service_name, op_name, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                fallback_handler.logger.warning("fallback_decorator", "primary_failed",
                                             f"Primary function failed, using fallback: {str(e)}")
                # For sync functions, we need to run the async fallback in an event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        fallback_handler.execute_fallback(service_name, op_name, *args, **kwargs)
                    )
                finally:
                    loop.close()
        
        # Determine if function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Pre-configured fallback decorators
def fallback_cache(func):
    """Decorator with cache fallback."""
    return fallback_on_failure("cache")(func)


def fallback_llm(func):
    """Decorator with LLM fallback."""
    return fallback_on_failure("llm")(func)


def fallback_database(func):
    """Decorator with database fallback."""
    return fallback_on_failure("database")(func)


# Utility functions for common fallback scenarios
async def get_cached_recommendations(user_preference_hash: str) -> Optional[Dict[str, Any]]:
    """Get recommendations from cache with fallback."""
    try:
        # Try primary cache first
        from ..data import get_cache_backend
        cache_backend = get_cache_backend()
        
        if cache_backend:
            cached_data = await cache_backend.get(f"rec:{user_preference_hash}")
            if cached_data:
                import json
                return json.loads(cached_data)
    except Exception:
        pass
    
    # Fallback to memory cache
    fallback_handler = get_fallback_handler()
    return await fallback_handler.execute_fallback("cache", "get", f"rec:{user_preference_hash}")


async def get_simple_ranking(candidates: List[Restaurant]) -> List[RecommendationItem]:
    """Get simple ranking without LLM."""
    fallback_handler = get_fallback_handler()
    
    # Create candidate set
    from zomoto_ai.phase0.domain.models import UserPreference
    candidate_set = CandidateSet(
        user_preference=UserPreference(location="fallback"),
        candidates=candidates
    )
    
    result = await fallback_handler.execute_fallback("llm", "rank", candidate_set)
    return result.items
