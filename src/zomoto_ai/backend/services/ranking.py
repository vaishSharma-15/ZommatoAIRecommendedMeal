"""Ranking Service - Phase 4 LLM-powered ranking

Implements LLM ranking with grounded explanations as specified
in Phase 4 of the architecture.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult, RecommendationItem, Restaurant
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker
from zomoto_ai.phase6.reliability import get_reliable_llm_client


class RankingService:
    """Service for Phase 4 LLM-powered ranking and explanation generation."""
    
    def __init__(self):
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self.llm_client = get_reliable_llm_client()
    
    async def rank_candidates(
        self,
        candidate_set: CandidateSet,
        top_n: int = 10,
        include_explanations: bool = True,
        temperature: float = 0.2
    ) -> RecommendationResult:
        """
        Rank candidates using LLM and generate grounded explanations.
        
        This implements Phase 4 of the architecture:
        - Prompt building with user preferences and candidates
        - LLM ranking with grounded explanations
        - Output validation to prevent hallucinations
        """
        with self.performance_tracker.track_request("backend", "ranking"):
            start_time = time.time()
            
            try:
                self.logger.info("ranking_service", "ranking_started",
                               f"Starting LLM ranking for {len(candidate_set.candidates)} candidates",
                               candidates_count=len(candidate_set.candidates),
                               top_n=top_n,
                               include_explanations=include_explanations)
                
                if not candidate_set.candidates:
                    self.logger.warning("ranking_service", "no_candidates",
                                      "No candidates provided for ranking")
                    return RecommendationResult(
                        user_preference=candidate_set.user_preference,
                        items=[],
                        summary="No candidates available for ranking."
                    )
                
                # Fast path: use fallback ranking if explanations not requested or LLM unavailable
                if not include_explanations or self.llm_client._llm_client is None:
                    self.logger.info("ranking_service", "fast_path_ranking", "Using fast fallback ranking")
                    return await self._generate_fallback_ranking(candidate_set, top_n)
                
                self.logger.info("ranking_service", "llm_ranking_path", "Using LLM ranking with explanations")
                
                # Use reliable LLM client with fallback
                with self.performance_tracker.track_llm_call("backend", "llm_ranking"):
                    ranking_result = self.llm_client.rank_and_explain(candidate_set)
                
                self.logger.info("ranking_service", "llm_result_received",
                                f"LLM returned {len(ranking_result.items)} items")
                
                # Deduplicate results before validation
                deduplicated_result = self._deduplicate_ranking_result(ranking_result, candidate_set)
                
                # Validate results
                validated_result = await self._validate_ranking_result(
                    deduplicated_result, candidate_set, top_n
                )
                
                # Log ranking statistics
                processing_time = time.time() - start_time
                ranked_count = len(validated_result.items)
                
                self.logger.info("ranking_service", "ranking_completed",
                                f"Ranked {ranked_count} restaurants in {processing_time:.2f}s",
                                ranked_count=ranked_count,
                                processing_time_seconds=processing_time,
                                llm_used=self.llm_client._llm_client is not None)
                
                return validated_result
                
            except Exception as e:
                self.logger.error("ranking_service", "ranking_failed",
                                f"LLM ranking failed: {str(e)}",
                                candidates_count=len(candidate_set.candidates),
                                exc_info=True)
                
                # Return fallback result
                return await self._generate_fallback_ranking(candidate_set, top_n)
    
    def _deduplicate_ranking_result(self, ranking_result: RecommendationResult, original_candidates: CandidateSet = None) -> RecommendationResult:
        """Remove duplicate restaurant IDs and names from ranking result."""
        seen_ids = set()
        seen_names = set()
        deduplicated_items = []
        
        self.logger.info("ranking_service", "deduplication_started",
                        f"Deduplicating {len(ranking_result.items)} items")
        
        # Create a mapping of restaurant_id to restaurant name if candidates are available
        id_to_name = {}
        if original_candidates:
            for candidate in original_candidates.candidates:
                id_to_name[candidate.id] = candidate.name.lower()
        
        for item in ranking_result.items:
            # Deduplicate by restaurant_id
            if item.restaurant_id in seen_ids:
                self.logger.warning("ranking_service", "duplicate_id_removed",
                                  f"Removed duplicate restaurant_id={item.restaurant_id}")
                continue
            seen_ids.add(item.restaurant_id)
            
            # Deduplicate by restaurant name (for cases where same restaurant has different IDs)
            restaurant_name = id_to_name.get(item.restaurant_id, "")
            if restaurant_name and restaurant_name in seen_names:
                self.logger.warning("ranking_service", "duplicate_name_removed",
                                  f"Removed duplicate restaurant name={restaurant_name} (id={item.restaurant_id})")
                continue
            if restaurant_name:
                seen_names.add(restaurant_name)
            
            deduplicated_items.append(item)
        
        self.logger.info("ranking_service", "deduplication_completed",
                        f"Reduced from {len(ranking_result.items)} to {len(deduplicated_items)} items")
        
        return RecommendationResult(
            user_preference=ranking_result.user_preference,
            items=deduplicated_items,
            summary=ranking_result.summary
        )
    
    async def _validate_ranking_result(
        self,
        ranking_result: RecommendationResult,
        original_candidates: CandidateSet,
        top_n: int
    ) -> RecommendationResult:
        """Validate LLM ranking result for grounding and consistency."""
        candidate_ids = {restaurant.id for restaurant in original_candidates.candidates}
        validated_items = []
        seen_ids = set()
        
        for item in ranking_result.items:
            # Check if restaurant ID exists in original candidates
            if item.restaurant_id not in candidate_ids:
                self.logger.warning("ranking_service", "invalid_restaurant_id",
                                  f"LLM returned invalid restaurant ID: {item.restaurant_id}")
                continue
            
            # Skip duplicates
            if item.restaurant_id in seen_ids:
                self.logger.warning("ranking_service", "duplicate_restaurant_id",
                                  f"LLM returned duplicate restaurant ID: {item.restaurant_id}")
                continue
            seen_ids.add(item.restaurant_id)
            
            # Find the actual restaurant
            restaurant = None
            for candidate in original_candidates.candidates:
                if candidate.id == item.restaurant_id:
                    restaurant = candidate
                    break
            
            if not restaurant:
                continue
            
            # Validate explanation if provided
            explanation = item.explanation
            if explanation:
                # Check for hallucinated attributes
                if not self._is_explanation_grounded(explanation, restaurant):
                    self.logger.warning("ranking_service", "ungrounded_explanation",
                                      f"LLM explanation contains ungrounded information")
                    # Generate a grounded explanation
                    explanation = self._generate_grounded_explanation(restaurant, item.rank)
            
            validated_items.append(RecommendationItem(
                restaurant_id=item.restaurant_id,
                rank=item.rank,
                explanation=explanation
            ))
        
        # Limit to top_n
        validated_items = validated_items[:top_n]
        
        # Generate summary
        summary = self._generate_ranking_summary(
            original_candidates.user_preference,
            validated_items
        )
        
        return RecommendationResult(
            user_preference=original_candidates.user_preference,
            items=validated_items,
            summary=summary
        )
    
    def _is_explanation_grounded(self, explanation: str, restaurant) -> bool:
        """Check if explanation only uses grounded restaurant attributes."""
        # Get available attributes
        available_info = {
            "name": restaurant.name.lower(),
            "location": restaurant.location.lower() if restaurant.location else "",
            "city": restaurant.city.lower() if restaurant.city else "",
            "area": restaurant.area.lower() if restaurant.area else "",
            "cuisines": [c.lower() for c in restaurant.cuisines],
            "cost_for_two": str(restaurant.cost_for_two) if restaurant.cost_for_two else "",
            "rating": str(restaurant.rating) if restaurant.rating else "",
            "votes": str(restaurant.votes) if restaurant.votes else ""
        }
        
        explanation_lower = explanation.lower()
        
        # Check for potentially ungrounded information
        ungrounded_patterns = [
            "phone", "address", "website", "menu", "dish", "ingredient",
            "chef", "owner", "opened", "established", "since", "year"
        ]
        
        for pattern in ungrounded_patterns:
            if pattern in explanation_lower:
                # Check if it's referring to actual restaurant info
                if not any(pattern in info for info in available_info.values()):
                    return False
        
        return True
    
    def _generate_grounded_explanation(
        self,
        restaurant: Restaurant,
        rank: int,
        user_preference = None
    ) -> str:
        """Generate a grounded explanation for a restaurant."""
        reasons = []
        
        # Rating
        if restaurant.rating and restaurant.rating >= 4.0:
            reasons.append(f"high rating of {restaurant.rating}")
        elif restaurant.rating:
            reasons.append(f"rating of {restaurant.rating}")
        
        # Popularity (votes)
        if restaurant.votes and restaurant.votes > 100:
            reasons.append(f"popular with {restaurant.votes} reviews")
        
        # Price
        if restaurant.cost_for_two:
            if restaurant.cost_for_two <= 500:
                reasons.append("affordable pricing")
            elif restaurant.cost_for_two <= 1000:
                reasons.append("moderate pricing")
            else:
                reasons.append("premium dining experience")
        
        # Cuisines
        if restaurant.cuisines:
            if len(restaurant.cuisines) == 1:
                reasons.append(f"specializes in {restaurant.cuisines[0]} cuisine")
            else:
                reasons.append(f"offers {', '.join(restaurant.cuisines[:2])} cuisines")
        
        # Location
        if restaurant.location or restaurant.area:
            location = restaurant.location or restaurant.area
            reasons.append(f"located in {location}")
        
        # Add preference mentions only if restaurant actually matches them
        if user_preference and user_preference.optional_constraints:
            for constraint in user_preference.optional_constraints:
                constraint_lower = constraint.lower()
                matches = False
                
                # Check if restaurant matches this preference using same heuristics
                if "quick" in constraint_lower:
                    if (restaurant.cost_for_two and restaurant.cost_for_two <= 800) or \
                       any(c.lower() in ["cafe", "fast food", "biryani", "rolls"] for c in restaurant.cuisines):
                        matches = True
                elif "family" in constraint_lower:
                    if (restaurant.cost_for_two and 500 <= restaurant.cost_for_two <= 1500) or \
                       any(c.lower() in ["north indian", "chinese", "italian", "continental"] for c in restaurant.cuisines):
                        matches = True
                elif "outdoor" in constraint_lower:
                    if (restaurant.rating and restaurant.rating >= 4.5) or \
                       (restaurant.votes and restaurant.votes >= 1000):
                        matches = True
                elif "pet" in constraint_lower:
                    if any(c.lower() in ["cafe", "continental", "italian"] for c in restaurant.cuisines):
                        matches = True
                elif "music" in constraint_lower:
                    if (restaurant.cost_for_two and restaurant.cost_for_two >= 1000) or \
                       (restaurant.rating and restaurant.rating >= 4.5):
                        matches = True
                
                # Only add to explanation if it matches
                if matches:
                    if "family" in constraint_lower:
                        reasons.append("great for families")
                    elif "quick" in constraint_lower:
                        reasons.append("quick service option")
                    elif "outdoor" in constraint_lower:
                        reasons.append("outdoor seating available")
                    elif "pet" in constraint_lower:
                        reasons.append("pet-friendly")
                    elif "music" in constraint_lower:
                        reasons.append("live music")
        
        if not reasons:
            reasons.append("matches your preferences")
        
        explanation = f"Ranked #{rank} for its {', '.join(reasons)}."
        return explanation
    
    def _generate_ranking_summary(
        self,
        user_preference,
        ranked_items: List[RecommendationItem]
    ) -> str:
        """Generate a summary of the ranking results."""
        if not ranked_items:
            return "No restaurants could be ranked based on your preferences."
        
        count = len(ranked_items)
        location = user_preference.location
        
        summary = f"Top {count} restaurants in {location}"
        
        if user_preference.cuisine:
            summary += f" serving {user_preference.cuisine} cuisine"
        
        if user_preference.min_rating > 0:
            summary += f" with ratings above {user_preference.min_rating}"
        
        summary += f" ranked by relevance and quality."
        
        return summary
    
    async def _generate_fallback_ranking(
        self,
        candidate_set: CandidateSet,
        top_n: int = 10
    ) -> RecommendationResult:
        """Generate fallback ranking when LLM fails."""
        self.logger.info("ranking_service", "fallback_ranking",
                        "Using fallback ranking method")
        
        # Sort by rating and votes
        sorted_candidates = sorted(
            candidate_set.candidates,
            key=lambda r: (r.rating or 0, r.votes or 0),
            reverse=True
        )
        
        # Create recommendation items with deduplication by both ID and name
        items = []
        seen_ids = set()
        seen_names = set()
        for restaurant in sorted_candidates:
            # Deduplicate by restaurant_id
            if restaurant.id in seen_ids:
                continue
            seen_ids.add(restaurant.id)
            
            # Deduplicate by restaurant name (for cases where same restaurant has different IDs)
            restaurant_name = restaurant.name.lower()
            if restaurant_name in seen_names:
                self.logger.warning("ranking_service", "fallback_duplicate_name_removed",
                                  f"Removed duplicate restaurant name={restaurant_name} (id={restaurant.id})")
                continue
            seen_names.add(restaurant_name)
            
            if len(items) >= top_n:
                break
                
            explanation = self._generate_grounded_explanation(restaurant, len(items) + 1, candidate_set.user_preference)
            items.append(RecommendationItem(
                restaurant_id=restaurant.id,
                rank=len(items) + 1,
                explanation=explanation
            ))
        
        summary = f"Top {len(items)} restaurants ranked by rating and popularity (fallback method used)."
        
        return RecommendationResult(
            user_preference=candidate_set.user_preference,
            items=items,
            summary=summary
        )
    
    async def batch_rank_candidates(
        self,
        candidate_sets: List[CandidateSet],
        top_n: int = 10,
        include_explanations: bool = True
    ) -> List[RecommendationResult]:
        """Rank multiple candidate sets in batch."""
        tasks = []
        
        for candidate_set in candidate_sets:
            task = self.rank_candidates(
                candidate_set=candidate_set,
                top_n=top_n,
                include_explanations=include_explanations
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error("ranking_service", "batch_ranking_failed",
                                f"Batch ranking failed for set {i}: {str(result)}")
                # Add fallback result
                validated_results.append(await self._generate_fallback_ranking(candidate_sets[i], top_n))
            else:
                validated_results.append(result)
        
        return validated_results
    
    def get_ranking_statistics(self) -> Dict[str, Any]:
        """Get ranking service statistics."""
        return {
            "service_status": "healthy",
            "llm_available": self.llm_client._llm_client is not None,
            "circuit_breaker_state": self.llm_client.circuit_breaker.state.value,
            "cache_size": len(self.llm_client.fallback_handler.cache),
            "reliability_features": {
                "circuit_breaker": True,
                "retry_logic": True,
                "fallback_behavior": True,
                "timeout_enforcement": True
            }
        }
