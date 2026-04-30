"""Retrieval Service - Phase 3 filtering and candidate selection

Implements structured filtering, relaxation strategies, and candidate
reduction as specified in Phase 3 of the architecture.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, Restaurant, CandidateSet
from zomoto_ai.phase3.retrieval import retrieve_with_relaxation
from zomoto_ai.phase3.models import RetrievalResult, RelaxStep
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker


class RetrievalService:
    """Service for Phase 3 retrieval and candidate selection."""
    
    def __init__(self):
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        
        # Load restaurant data
        self._restaurants = None
        self._load_restaurants()
    
    def _load_restaurants(self):
        """Load restaurant data from parquet file."""
        try:
            from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet
            self._restaurants = load_restaurants_from_parquet("data/restaurants_processed.parquet")
            self.logger.info("retrieval_service", "restaurants_loaded", 
                           f"Loaded {len(self._restaurants)} restaurants")
        except Exception as e:
            self.logger.error("retrieval_service", "restaurants_load_failed", 
                            f"Failed to load restaurants: {e}")
            self._restaurants = []
    
    async def retrieve_candidates(
        self,
        user_preference: UserPreference,
        top_n: int = 50,
        enable_relaxation: bool = True
    ) -> RetrievalResult:
        """
        Retrieve candidate restaurants based on user preferences.
        
        This implements Phase 3 of the architecture:
        - Structured filtering by location, cuisine, budget, rating
        - Relaxation strategies when no matches found
        - Candidate reduction to manage LLM token limits
        """
        with self.performance_tracker.track_request("backend", "retrieval"):
            start_time = time.time()
            
            try:
                self.logger.info("retrieval_service", "retrieval_started",
                               f"Starting candidate retrieval for {user_preference.location}",
                               location=user_preference.location,
                               top_n=top_n,
                               enable_relaxation=enable_relaxation)
                
                # Perform retrieval with relaxation
                retrieval_result = retrieve_with_relaxation(
                    restaurants=self._restaurants,
                    pref=user_preference,
                    top_n=top_n
                )
                
                # Log retrieval statistics
                processing_time = time.time() - start_time
                candidates_found = len(retrieval_result.candidate_set.candidates)
                relaxation_steps = len(retrieval_result.relax_steps)
                
                self.logger.info("retrieval_service", "retrieval_completed",
                                f"Retrieved {candidates_found} candidates in {processing_time:.2f}s",
                                candidates_found=candidates_found,
                                relaxation_steps=relaxation_steps,
                                processing_time_seconds=processing_time)
                
                # Log relaxation steps if any
                if retrieval_result.relax_steps:
                    self.logger.info("retrieval_service", "relaxation_applied",
                                   f"Applied {len(retrieval_result.relax_steps)} relaxation steps",
                                   steps=[step.note for step in retrieval_result.relax_steps])
                
                return retrieval_result
                
            except Exception as e:
                self.logger.error("retrieval_service", "retrieval_failed",
                                f"Candidate retrieval failed: {str(e)}",
                                user_preference=user_preference.dict(),
                                exc_info=True)
                raise
    
    async def filter_by_location(
        self,
        restaurants: List[Restaurant],
        location: str,
        fuzzy_match: bool = True
    ) -> List[Restaurant]:
        """Filter restaurants by location with optional fuzzy matching."""
        location_lower = location.lower()
        filtered = []
        
        for restaurant in restaurants:
            # Check various location fields
            location_fields = [
                restaurant.location or "",
                restaurant.city or "",
                restaurant.area or ""
            ]
            
            match_found = False
            for field in location_fields:
                if field and location_lower in field.lower():
                    match_found = True
                    break
            
            if match_found:
                filtered.append(restaurant)
        
        if not filtered and fuzzy_match:
            # Try fuzzy matching - look for partial matches
            location_parts = location_lower.split()
            for restaurant in restaurants:
                for part in location_parts:
                    if len(part) >= 3:  # Only match parts with 3+ characters
                        for field in location_fields:
                            if field and part in field.lower():
                                filtered.append(restaurant)
                                break
        
        return filtered
    
    async def filter_by_cuisine(
        self,
        restaurants: List[Restaurant],
        cuisine: str,
        exact_match: bool = False
    ) -> List[Restaurant]:
        """Filter restaurants by cuisine."""
        if not cuisine:
            return restaurants
        
        cuisine_lower = cuisine.lower()
        filtered = []
        
        for restaurant in restaurants:
            for restaurant_cuisine in restaurant.cuisines:
                if exact_match:
                    if restaurant_cuisine.lower() == cuisine_lower:
                        filtered.append(restaurant)
                        break
                else:
                    if cuisine_lower in restaurant_cuisine.lower():
                        filtered.append(restaurant)
                        break
        
        return filtered
    
    async def filter_by_budget(
        self,
        restaurants: List[Restaurant],
        budget_max: Optional[int] = None,
        budget_min: Optional[int] = None
    ) -> List[Restaurant]:
        """Filter restaurants by budget range."""
        if not budget_max and not budget_min:
            return restaurants
        
        filtered = []
        
        for restaurant in restaurants:
            if restaurant.cost_for_two is None:
                continue
            
            if budget_max and restaurant.cost_for_two > budget_max:
                continue
            
            if budget_min and restaurant.cost_for_two < budget_min:
                continue
            
            filtered.append(restaurant)
        
        return filtered
    
    async def filter_by_rating(
        self,
        restaurants: List[Restaurant],
        min_rating: float = 0.0
    ) -> List[Restaurant]:
        """Filter restaurants by minimum rating."""
        if min_rating <= 0:
            return restaurants
        
        filtered = []
        
        for restaurant in restaurants:
            if restaurant.rating is None:
                continue
            
            if restaurant.rating >= min_rating:
                filtered.append(restaurant)
        
        return filtered
    
    async def apply_diversity_sampling(
        self,
        restaurants: List[Restaurant],
        target_count: int = 10
    ) -> List[Restaurant]:
        """
        Apply diversity sampling to ensure varied recommendations.
        
        Ensures diversity across:
        - Price ranges (budget, mid-range, expensive)
        - Cuisine types
        - Geographic areas
        """
        if len(restaurants) <= target_count:
            return restaurants
        
        # Group restaurants by categories for diversity
        price_groups = {"budget": [], "mid": [], "expensive": []}
        cuisine_groups = {}
        area_groups = {}
        
        for restaurant in restaurants:
            # Price grouping
            if restaurant.cost_for_two:
                if restaurant.cost_for_two <= 500:
                    price_groups["budget"].append(restaurant)
                elif restaurant.cost_for_two <= 1000:
                    price_groups["mid"].append(restaurant)
                else:
                    price_groups["expensive"].append(restaurant)
            
            # Cuisine grouping
            for cuisine in restaurant.cuisines[:2]:  # Limit to top 2 cuisines
                if cuisine not in cuisine_groups:
                    cuisine_groups[cuisine] = []
                cuisine_groups[cuisine].append(restaurant)
            
            # Area grouping
            area = restaurant.area or restaurant.location or "unknown"
            if area not in area_groups:
                area_groups[area] = []
            area_groups[area].append(restaurant)
        
        # Select diverse candidates
        selected = []
        used_restaurants = set()
        
        # First, ensure price diversity
        for price_group in price_groups.values():
            if len(selected) >= target_count:
                break
            # Sort by rating and pick top candidates
            sorted_by_rating = sorted(
                [r for r in price_group if r.id not in used_restaurants],
                key=lambda x: x.rating or 0,
                reverse=True
            )
            for restaurant in sorted_by_rating[:2]:  # Max 2 per price group
                if len(selected) < target_count:
                    selected.append(restaurant)
                    used_restaurants.add(restaurant.id)
        
        # Then, ensure cuisine diversity
        remaining_slots = target_count - len(selected)
        if remaining_slots > 0:
            cuisine_candidates = []
            for cuisine_group in cuisine_groups.values():
                sorted_by_rating = sorted(
                    [r for r in cuisine_group if r.id not in used_restaurants],
                    key=lambda x: x.rating or 0,
                    reverse=True
                )
                cuisine_candidates.extend(sorted_by_rating[:1])  # Top 1 per cuisine
            
            # Add top cuisine candidates
            for restaurant in cuisine_candidates[:remaining_slots]:
                selected.append(restaurant)
                used_restaurants.add(restaurant.id)
        
        # Fill remaining slots with highest rated
        remaining_slots = target_count - len(selected)
        if remaining_slots > 0:
            remaining_restaurants = sorted(
                [r for r in restaurants if r.id not in used_restaurants],
                key=lambda x: x.rating or 0,
                reverse=True
            )
            selected.extend(remaining_restaurants[:remaining_slots])
        
        return selected[:target_count]
    
    async def get_retrieval_statistics(self) -> Dict[str, Any]:
        """Get retrieval service statistics."""
        if not self._restaurants:
            return {"error": "No restaurants loaded"}
        
        # Calculate statistics
        locations = set()
        cuisines = set()
        price_ranges = {"budget": 0, "mid": 0, "expensive": 0}
        
        for restaurant in self._restaurants:
            # Location stats
            if restaurant.city:
                locations.add(restaurant.city)
            elif restaurant.location:
                locations.add(restaurant.location)
            
            # Cuisine stats
            for cuisine in restaurant.cuisines:
                cuisines.add(cuisine)
            
            # Price range stats
            if restaurant.cost_for_two:
                if restaurant.cost_for_two <= 500:
                    price_ranges["budget"] += 1
                elif restaurant.cost_for_two <= 1000:
                    price_ranges["mid"] += 1
                else:
                    price_ranges["expensive"] += 1
        
        return {
            "total_restaurants": len(self._restaurants),
            "unique_locations": len(locations),
            "unique_cuisines": len(cuisines),
            "price_distribution": price_ranges,
            "service_status": "healthy"
        }
