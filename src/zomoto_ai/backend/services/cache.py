"""Cache Service - Redis-based caching layer

Provides intelligent caching for recommendations, restaurant data,
and frequently accessed information to improve performance.
"""

import asyncio
import json
import hashlib
import time
from typing import Any, Optional, Dict, List
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, RecommendationResult
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker


class CacheService:
    """Service for managing Redis-based caching."""
    
    def __init__(self, cache_backend=None):
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self.cache_backend = cache_backend
        
        # Cache key prefixes
        self.RECOMMENDATION_PREFIX = "rec:"
        self.RESTAURANT_PREFIX = "rest:"
        self.USER_PREFIX = "user:"
        self.STATS_PREFIX = "stats:"
        
        # Default TTL values (seconds)
        self.DEFAULT_TTL = 3600  # 1 hour
        self.RECOMMENDATION_TTL = 1800  # 30 minutes
        self.RESTAURANT_TTL = 7200  # 2 hours
        self.STATS_TTL = 300  # 5 minutes
    
    def generate_cache_key(self, user_preference: UserPreference, top_n: int) -> str:
        """Generate a unique cache key for user preferences."""
        # Create a deterministic key from user preferences
        key_data = {
            "location": user_preference.location.lower().strip(),
            "cuisine": (user_preference.cuisine or "").lower().strip(),
            "min_rating": user_preference.min_rating,
            "budget_max": user_preference.budget.max_cost_for_two if user_preference.budget else None,
            "budget_min": user_preference.budget.min_cost_for_two if user_preference.budget else None,
            "top_n": top_n
        }
        
        # Remove None values and sort keys for consistency
        key_data = {k: v for k, v in key_data.items() if v is not None}
        key_string = json.dumps(key_data, sort_keys=True)
        
        # Create hash
        hash_object = hashlib.md5(key_string.encode())
        hash_hex = hash_object.hexdigest()
        
        return f"{self.RECOMMENDATION_PREFIX}{hash_hex}"
    
    async def get_recommendations(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached recommendations."""
        with self.performance_tracker.track_request("cache", "get_recommendations"):
            try:
                if not self.cache_backend:
                    return None
                
                cached_data = await self.cache_backend.get(cache_key)
                
                if cached_data:
                    self.logger.info("cache_service", "recommendation_hit",
                                   f"Cache hit for recommendations: {cache_key}",
                                   cache_key=cache_key)
                    
                    # Update cache hit statistics
                    await self._update_cache_stats("recommendations", "hit")
                    
                    return json.loads(cached_data)
                else:
                    self.logger.info("cache_service", "recommendation_miss",
                                   f"Cache miss for recommendations: {cache_key}",
                                   cache_key=cache_key)
                    
                    # Update cache miss statistics
                    await self._update_cache_stats("recommendations", "miss")
                    
                    return None
                    
            except Exception as e:
                self.logger.error("cache_service", "get_recommendations_failed",
                                f"Failed to get cached recommendations: {str(e)}",
                                cache_key=cache_key)
                return None
    
    async def set_recommendations(
        self,
        cache_key: str,
        recommendation_result: RecommendationResult,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache recommendations."""
        with self.performance_tracker.track_request("cache", "set_recommendations"):
            try:
                if not self.cache_backend:
                    return False
                
                # Convert to serializable format
                cache_data = {
                    "user_preference": recommendation_result.user_preference.dict(),
                    "items": [
                        {
                            "restaurant_id": item.restaurant_id,
                            "rank": item.rank,
                            "explanation": item.explanation
                        }
                        for item in recommendation_result.items
                    ],
                    "summary": recommendation_result.summary,
                    "timestamp": time.time()
                }
                
                # Serialize to JSON
                serialized_data = json.dumps(cache_data)
                
                # Set with TTL
                actual_ttl = ttl or self.RECOMMENDATION_TTL
                success = await self.cache_backend.set(cache_key, serialized_data, ttl=actual_ttl)
                
                if success:
                    self.logger.info("cache_service", "recommendations_cached",
                                   f"Cached recommendations: {cache_key}",
                                   cache_key=cache_key,
                                   ttl=actual_ttl)
                    
                    # Update cache set statistics
                    await self._update_cache_stats("recommendations", "set")
                
                return success
                
            except Exception as e:
                self.logger.error("cache_service", "set_recommendations_failed",
                                f"Failed to cache recommendations: {str(e)}",
                                cache_key=cache_key)
                return False
    
    async def get_restaurant(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Get cached restaurant data."""
        with self.performance_tracker.track_request("cache", "get_restaurant"):
            try:
                if not self.cache_backend:
                    return None
                
                cache_key = f"{self.RESTAURANT_PREFIX}{restaurant_id}"
                cached_data = await self.cache_backend.get(cache_key)
                
                if cached_data:
                    await self._update_cache_stats("restaurants", "hit")
                    return json.loads(cached_data)
                else:
                    await self._update_cache_stats("restaurants", "miss")
                    return None
                    
            except Exception as e:
                self.logger.error("cache_service", "get_restaurant_failed",
                                f"Failed to get cached restaurant: {str(e)}",
                                restaurant_id=restaurant_id)
                return None
    
    async def set_restaurant(
        self,
        restaurant_id: str,
        restaurant_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache restaurant data."""
        try:
            if not self.cache_backend:
                return False
            
            cache_key = f"{self.RESTAURANT_PREFIX}{restaurant_id}"
            serialized_data = json.dumps(restaurant_data)
            actual_ttl = ttl or self.RESTAURANT_TTL
            
            success = await self.cache_backend.set(cache_key, serialized_data, ttl=actual_ttl)
            
            if success:
                await self._update_cache_stats("restaurants", "set")
            
            return success
            
        except Exception as e:
            self.logger.error("cache_service", "set_restaurant_failed",
                            f"Failed to cache restaurant: {str(e)}",
                            restaurant_id=restaurant_id)
            return False
    
    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user preferences."""
        try:
            if not self.cache_backend:
                return None
            
            cache_key = f"{self.USER_PREFIX}prefs:{user_id}"
            cached_data = await self.cache_backend.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            self.logger.error("cache_service", "get_user_prefs_failed",
                            f"Failed to get cached user preferences: {str(e)}",
                            user_id=user_id)
            return None
    
    async def set_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache user preferences."""
        try:
            if not self.cache_backend:
                return False
            
            cache_key = f"{self.USER_PREFIX}prefs:{user_id}"
            serialized_data = json.dumps(preferences)
            actual_ttl = ttl or self.DEFAULT_TTL
            
            return await self.cache_backend.set(cache_key, serialized_data, ttl=actual_ttl)
            
        except Exception as e:
            self.logger.error("cache_service", "set_user_prefs_failed",
                            f"Failed to cache user preferences: {str(e)}",
                            user_id=user_id)
            return False
    
    async def invalidate_recommendations(self, user_preference: UserPreference, top_n: int) -> bool:
        """Invalidate cached recommendations for specific preferences."""
        try:
            cache_key = self.generate_cache_key(user_preference, top_n)
            
            if self.cache_backend:
                success = await self.cache_backend.delete(cache_key)
                
                if success:
                    self.logger.info("cache_service", "recommendations_invalidated",
                                   f"Invalidated recommendations: {cache_key}",
                                   cache_key=cache_key)
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error("cache_service", "invalidate_recommendations_failed",
                            f"Failed to invalidate recommendations: {str(e)}")
            return False
    
    async def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries by pattern."""
        try:
            if not self.cache_backend:
                return 0
            
            if pattern:
                # Clear by pattern
                deleted_count = await self.cache_backend.delete_pattern(pattern)
            else:
                # Clear all cache
                deleted_count = await self.cache_backend.clear()
            
            self.logger.info("cache_service", "cache_cleared",
                            f"Cleared {deleted_count} cache entries",
                            pattern=pattern or "all",
                            deleted_count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            self.logger.error("cache_service", "clear_cache_failed",
                            f"Failed to clear cache: {str(e)}")
            return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        try:
            if not self.cache_backend:
                return {
                    "hit_rate": 0.0,
                    "total_requests": 0,
                    "hits": 0,
                    "misses": 0,
                    "size": 0
                }
            
            # Get statistics from backend
            backend_stats = await self.cache_backend.get_statistics()
            
            # Get our own statistics
            stats_key = f"{self.STATS_PREFIX}performance"
            stats_data = await self.cache_backend.get(stats_key)
            
            our_stats = {}
            if stats_data:
                our_stats = json.loads(stats_data)
            else:
                our_stats = {
                    "recommendations": {"hits": 0, "misses": 0, "sets": 0},
                    "restaurants": {"hits": 0, "misses": 0, "sets": 0},
                    "total_requests": 0
                }
            
            # Calculate hit rate
            total_hits = sum(
                category_stats.get("hits", 0) 
                for category_stats in our_stats.values()
                if isinstance(category_stats, dict)
            )
            total_requests = our_stats.get("total_requests", 0)
            
            hit_rate = (total_hits / total_requests) if total_requests > 0 else 0.0
            
            return {
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "hits": total_hits,
                "misses": total_requests - total_hits,
                "size": backend_stats.get("size", 0),
                "backend_stats": backend_stats,
                "category_stats": our_stats
            }
            
        except Exception as e:
            self.logger.error("cache_service", "get_statistics_failed",
                            f"Failed to get cache statistics: {str(e)}")
            return {
                "hit_rate": 0.0,
                "total_requests": 0,
                "hits": 0,
                "misses": 0,
                "size": 0,
                "error": str(e)
            }
    
    async def _update_cache_stats(self, category: str, operation: str):
        """Update cache statistics."""
        try:
            if not self.cache_backend:
                return
            
            stats_key = f"{self.STATS_PREFIX}performance"
            
            # Get current stats
            stats_data = await self.cache_backend.get(stats_key)
            stats = json.loads(stats_data) if stats_data else {}
            
            # Update category stats
            if category not in stats:
                stats[category] = {"hits": 0, "misses": 0, "sets": 0}
            
            if operation in ["hit", "miss", "set"]:
                stats[category][operation] += 1
            
            # Update total requests
            if operation in ["hit", "miss"]:
                stats["total_requests"] = stats.get("total_requests", 0) + 1
            
            # Save updated stats
            await self.cache_backend.set(stats_key, json.dumps(stats), ttl=self.STATS_TTL)
            
        except Exception as e:
            self.logger.error("cache_service", "update_stats_failed",
                            f"Failed to update cache statistics: {str(e)}")
    
    async def warm_cache(self, popular_locations: List[str], popular_cuisines: List[str]) -> int:
        """Warm cache with popular location/cuisine combinations."""
        warmed_count = 0
        
        try:
            from zomoto_ai.phase0.domain.models import UserPreference, Budget
            
            # Generate popular combinations
            combinations = []
            
            for location in popular_locations[:5]:  # Top 5 locations
                # Base preference
                base_pref = UserPreference(location=location, min_rating=4.0)
                combinations.append((base_pref, 10))
                
                # With cuisine
                for cuisine in popular_cuisines[:3]:  # Top 3 cuisines
                    pref_with_cuisine = UserPreference(
                        location=location,
                        cuisine=cuisine,
                        min_rating=4.0
                    )
                    combinations.append((pref_with_cuisine, 10))
                
                # With budget
                for budget in [500, 1000, 1500]:
                    pref_with_budget = UserPreference(
                        location=location,
                        budget=Budget(kind="range", max_cost_for_two=budget),
                        min_rating=4.0
                    )
                    combinations.append((pref_with_budget, 10))
            
            # Generate cache keys for warming
            cache_keys = []
            for pref, top_n in combinations:
                cache_key = self.generate_cache_key(pref, top_n)
                cache_keys.append(cache_key)
            
            # In a real implementation, you would pre-generate recommendations
            # For now, we'll just log the warming process
            self.logger.info("cache_service", "cache_warming",
                            f"Cache warming initiated for {len(cache_keys)} combinations",
                            combinations_count=len(cache_keys))
            
            warmed_count = len(cache_keys)
            
        except Exception as e:
            self.logger.error("cache_service", "cache_warming_failed",
                            f"Cache warming failed: {str(e)}")
        
        return warmed_count
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get cache service health information."""
        return {
            "service_status": "healthy" if self.cache_backend else "degraded",
            "backend_available": self.cache_backend is not None,
            "cache_prefixes": {
                "recommendations": self.RECOMMENDATION_PREFIX,
                "restaurants": self.RESTAURANT_PREFIX,
                "users": self.USER_PREFIX,
                "statistics": self.STATS_PREFIX
            },
            "default_ttl_values": {
                "recommendations": self.RECOMMENDATION_TTL,
                "restaurants": self.RESTAURANT_TTL,
                "default": self.DEFAULT_TTL
            }
        }
