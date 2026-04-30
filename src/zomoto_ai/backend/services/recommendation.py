"""Recommendation Service - Main orchestration service

Coordinates the complete recommendation pipeline including retrieval,
ranking, caching, and result formatting.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, RecommendationResult, RecommendationItem
from zomoto_ai.phase3.retrieval import retrieve_with_relaxation, load_restaurants_from_parquet
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker
from .retrieval import RetrievalService
from .ranking import RankingService
from .cache import CacheService


class RecommendationService:
    """Main recommendation service orchestrating the complete pipeline."""
    
    def __init__(self):
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        
        # Initialize sub-services
        self.retrieval_service = RetrievalService()
        self.ranking_service = RankingService()
        self.cache_service = CacheService()
        
        # Load restaurant data
        self._restaurants = None
        self._load_restaurants()
    
    def _load_restaurants(self):
        """Load restaurant data from parquet file."""
        try:
            self._restaurants = load_restaurants_from_parquet("data/restaurants_processed.parquet")
            self.logger.info("recommendation_service", "restaurants_loaded", 
                           f"Loaded {len(self._restaurants)} restaurants")
        except Exception as e:
            self.logger.error("recommendation_service", "restaurants_load_failed", 
                            f"Failed to load restaurants: {e}")
            self._restaurants = []
    
    async def generate_recommendations(
        self,
        user_preference: UserPreference,
        top_n: int = 10,
        include_explanations: bool = True,
        use_cache: bool = True
    ) -> RecommendationResult:
        """
        Generate restaurant recommendations based on user preferences.
        
        This method orchestrates the complete pipeline:
        1. Retrieval (Phase 3) - Filter and select candidates
        2. Ranking (Phase 4) - LLM-powered ranking with explanations
        3. Result formatting - Prepare final response
        """
        with self.performance_tracker.track_request("backend", "recommendations"):
            start_time = time.time()
            
            try:
                self.logger.info("recommendation_service", "generation_started",
                               f"Starting recommendation generation for {user_preference.location}",
                               location=user_preference.location,
                               top_n=top_n,
                               include_explanations=include_explanations)
                
                # Step 1: Retrieval - Get candidate restaurants
                with self.performance_tracker.track_request("backend", "retrieval"):
                    retrieval_result = await self.retrieval_service.retrieve_candidates(
                        user_preference=user_preference,
                        top_n=max(top_n * 3, 50)  # Get more candidates for better ranking
                    )
                
                if not retrieval_result.candidate_set.candidates:
                    self.logger.warning("recommendation_service", "no_candidates",
                                      "No candidates found after retrieval")
                    return RecommendationResult(
                        user_preference=user_preference,
                        items=[],
                        summary="No restaurants found matching your preferences. Try relaxing your criteria."
                    )
                
                self.logger.info("recommendation_service", "candidates_retrieved",
                                f"Retrieved {len(retrieval_result.candidate_set.candidates)} candidates")
                
                # Step 2: Ranking - LLM-powered ranking
                with self.performance_tracker.track_request("backend", "ranking"):
                    ranking_result = await self.ranking_service.rank_candidates(
                        candidate_set=retrieval_result.candidate_set,
                        top_n=top_n,
                        include_explanations=include_explanations
                    )
                
                # Step 3: Format results
                final_items = []
                for i, item in enumerate(ranking_result.items[:top_n], 1):
                    final_item = RecommendationItem(
                        restaurant_id=item.restaurant_id,
                        rank=i,
                        explanation=item.explanation if include_explanations and item.explanation else "Explanation disabled."
                    )
                    final_items.append(final_item)
                
                # Create summary
                summary = self._generate_summary(
                    user_preference=user_preference,
                    items=final_items,
                    retrieval_steps=retrieval_result.relax_steps
                )
                
                result = RecommendationResult(
                    user_preference=user_preference,
                    items=final_items,
                    summary=summary
                )
                
                processing_time = time.time() - start_time
                
                self.logger.info("recommendation_service", "generation_completed",
                                f"Generated {len(final_items)} recommendations in {processing_time:.2f}s",
                                total_recommendations=len(final_items),
                                processing_time_seconds=processing_time,
                                candidates_count=len(retrieval_result.candidate_set.candidates))
                
                return result
                
            except Exception as e:
                self.logger.error("recommendation_service", "generation_failed",
                                f"Recommendation generation failed: {str(e)}",
                                user_preference=user_preference.dict(),
                                exc_info=True)
                raise
    
    async def generate_recommendations_async(
        self,
        user_preference: UserPreference,
        top_n: int = 10,
        include_explanations: bool = True
    ) -> str:
        """
        Generate recommendations asynchronously.
        
        Returns a job ID that can be used to check status and get results.
        """
        # This would integrate with the job queue service
        # For now, we'll implement a simple async version
        job_id = f"rec_{int(time.time())}"
        
        # Submit to job queue (would be implemented in job queue service)
        # For now, just return the job ID
        return job_id
    
    def _generate_summary(
        self,
        user_preference: UserPreference,
        items: List[RecommendationItem],
        retrieval_steps: List[str]
    ) -> str:
        """Generate a human-readable summary of recommendations."""
        if not items:
            return "No restaurants found matching your preferences."
        
        location = user_preference.location
        count = len(items)
        
        # Get top cuisines
        cuisines = []
        for item in items[:5]:  # Top 5 items
            # This would need the actual restaurant data
            # For now, we'll use a generic approach
            pass
        
        summary = f"Found {count} top restaurants in {location}"
        
        if user_preference.cuisine:
            summary += f" serving {user_preference.cuisine} cuisine"
        
        if user_preference.min_rating > 0:
            summary += f" with ratings above {user_preference.min_rating}"
        
        if user_preference.budget:
            summary += f" within your budget range"
        
        if retrieval_steps:
            summary += f" (used {len(retrieval_steps)} relaxation steps)"
        
        return summary + "."
    
    async def get_recommendation_by_id(self, recommendation_id: str) -> Optional[RecommendationResult]:
        """Get a previously generated recommendation by ID."""
        # This would integrate with cache service
        return None
    
    async def validate_preferences(self, user_preference: UserPreference) -> Dict[str, Any]:
        """Validate user preferences and provide suggestions."""
        validation_result = {
            "valid": True,
            "errors": [],
            "suggestions": []
        }
        
        # Validate location
        if not user_preference.location or len(user_preference.location.strip()) < 2:
            validation_result["valid"] = False
            validation_result["errors"].append("Location is required and must be at least 2 characters")
        
        # Validate rating
        if user_preference.min_rating < 0 or user_preference.min_rating > 5:
            validation_result["valid"] = False
            validation_result["errors"].append("Rating must be between 0 and 5")
        
        # Validate budget
        if user_preference.budget:
            if user_preference.budget.max_cost_for_two and user_preference.budget.max_cost_for_two < 0:
                validation_result["valid"] = False
                validation_result["errors"].append("Budget must be positive")
        
        # Add suggestions
        if user_preference.min_rating > 4.5:
            validation_result["suggestions"].append("High rating requirement may limit results. Consider 4.0+ for more options.")
        
        if user_preference.budget and user_preference.budget.max_cost_for_two and user_preference.budget.max_cost_for_two < 300:
            validation_result["suggestions"].append("Low budget may limit options. Consider increasing to 500+ for better selection.")
        
        return validation_result
    
    async def get_popular_locations(self) -> List[str]:
        """Get list of popular locations with restaurants."""
        if not self._restaurants:
            return []
        
        # Count restaurants by location
        location_counts = {}
        for restaurant in self._restaurants:
            location = restaurant.city or restaurant.location
            if location:
                location_counts[location] = location_counts.get(location, 0) + 1
        
        # Sort by count and return top locations
        sorted_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
        return [location for location, count in sorted_locations[:20]]
    
    async def get_popular_cuisines(self, location: str = None) -> List[str]:
        """Get list of popular cuisines, optionally filtered by location."""
        if not self._restaurants:
            return []
        
        # Count cuisines
        cuisine_counts = {}
        for restaurant in self._restaurants:
            # Filter by location if specified
            if location:
                restaurant_location = restaurant.city or restaurant.location
                if not location.lower() in restaurant_location.lower():
                    continue
            
            for cuisine in restaurant.cuisines:
                cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1
        
        # Sort by count and return top cuisines
        sorted_cuisines = sorted(cuisine_counts.items(), key=lambda x: x[1], reverse=True)
        return [cuisine for cuisine, count in sorted_cuisines[:20]]
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics and health information."""
        return {
            "restaurants_loaded": len(self._restaurants) if self._restaurants else 0,
            "service_status": "healthy" if self._restaurants else "degraded",
            "last_load_time": time.time(),
            "cache_enabled": True,
            "async_enabled": True
        }
