"""API Backend for Phase 5 - Option B

FastAPI backend providing recommendation endpoints.
"""

import os
import sys
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import Budget, UserPreference, RecommendationResult
from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet, retrieve_with_relaxation
from zomoto_ai.phase4.groq_ranker import GroqLLMClient


# Pydantic models for API
class BudgetRequest(BaseModel):
    kind: str = Field(..., description="Budget type: 'bucket' or 'range'")
    bucket: Optional[str] = Field(None, description="Budget bucket: 'low', 'medium', 'high'")
    min_cost_for_two: Optional[int] = Field(None, ge=0)
    max_cost_for_two: Optional[int] = Field(None, ge=0)


class UserPreferenceRequest(BaseModel):
    location: str = Field(..., min_length=1, description="Location for restaurant search")
    budget: Optional[BudgetRequest] = Field(None, description="Budget constraints")
    cuisine: Optional[str] = Field(None, description="Preferred cuisine")
    min_rating: float = Field(0.0, ge=0, le=5, description="Minimum rating requirement")
    optional_constraints: list[str] = Field(default_factory=list, description="Specific restaurant names")


class RecommendationRequest(BaseModel):
    preferences: UserPreferenceRequest
    top_n: int = Field(10, ge=1, le=50, description="Number of recommendations to return")


class RecommendationItemResponse(BaseModel):
    restaurant_id: str
    rank: int
    explanation: str
    restaurant_name: Optional[str] = None
    location: Optional[str] = None
    cuisines: Optional[list[str]] = None
    cost_for_two: Optional[int] = None
    rating: Optional[float] = None
    votes: Optional[int] = None


class RecommendationResponse(BaseModel):
    success: bool
    summary: Optional[str] = None
    recommendations: list[RecommendationItemResponse]
    total_candidates: int
    relaxation_steps: list[Dict[str, str]] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    restaurants_loaded: int
    llm_available: bool
    cache_enabled: bool


# Global state
restaurants = []
llm_client = None
recommendation_cache = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application state on startup."""
    global restaurants, llm_client
    
    try:
        # Load restaurants
        data_path = os.getenv("ZOMOTO_DATASET_PATH", "data/restaurants_processed.parquet")
        print(f"Loading {len(restaurants)} restaurants from {data_path}")
        restaurants = load_restaurants_from_parquet(data_path)
        print(f"Loaded {len(restaurants)} restaurants")
        
        # Initialize LLM client
        if os.getenv("GROQ_API_KEY"):
            llm_client = GroqLLMClient()
            print("LLM client initialized")
        else:
            print("LLM client not available (no GROQ_API_KEY)")
        
        yield
        
    except Exception as e:
        print(f"Failed to initialize: {e}")
        raise


# Create FastAPI app
app = FastAPI(
    title="Zomoto AI Recommendation API",
    description="AI-powered restaurant recommendations with LLM ranking",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_cache_key(preferences: UserPreferenceRequest, candidate_ids: list[str]) -> str:
    """Generate cache key for recommendation requests."""
    key_data = f"{preferences.location}_{preferences.budget}_{preferences.cuisine}_{preferences.min_rating}_{sorted(preferences.optional_constraints)}_{sorted(candidate_ids)}"
    return hashlib.md5(key_data.encode()).hexdigest()


def convert_budget_request(budget_req: Optional[BudgetRequest]) -> Optional[Budget]:
    """Convert API budget request to domain model."""
    if not budget_req:
        return None
    
    return Budget(
        kind=budget_req.kind,
        bucket=budget_req.bucket,
        min_cost_for_two=budget_req.min_cost_for_two,
        max_cost_for_two=budget_req.max_cost_for_two
    )


def create_restaurant_lookup(candidate_set) -> Dict[str, Dict[str, Any]]:
    """Create lookup dictionary for restaurant details."""
    lookup = {}
    for restaurant in candidate_set.candidates:
        lookup[restaurant.id] = {
            "name": restaurant.name,
            "location": restaurant.location or restaurant.city,
            "cuisines": restaurant.cuisines,
            "cost_for_two": restaurant.cost_for_two,
            "rating": restaurant.rating,
            "votes": restaurant.votes
        }
    return lookup


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        restaurants_loaded=len(restaurants),
        llm_available=llm_client is not None,
        cache_enabled=bool(recommendation_cache)
    )


@app.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest, background_tasks: BackgroundTasks):
    """Generate restaurant recommendations based on user preferences."""
    import time
    
    start_time = time.time()
    
    try:
        # Convert request to domain model
        user_pref = UserPreference(
            location=request.preferences.location,
            budget=convert_budget_request(request.preferences.budget),
            cuisine=request.preferences.cuisine,
            min_rating=request.preferences.min_rating,
            optional_constraints=request.preferences.optional_constraints
        )
        
        # Phase 3: Retrieval with relaxation
        retrieval_result = retrieve_with_relaxation(restaurants, user_pref, top_n=request.top_n)
        
        if not retrieval_result.candidate_set.candidates:
            return RecommendationResponse(
                success=True,
                summary="No restaurants found matching your preferences. Try relaxing your criteria!",
                recommendations=[],
                total_candidates=0,
                relaxation_steps=[{"action": step.action, "note": step.note} for step in retrieval_result.relax_steps],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Check cache for LLM results
        candidate_ids = [r.id for r in retrieval_result.candidate_set.candidates]
        cache_key = get_cache_key(request.preferences, candidate_ids)
        
        if cache_key in recommendation_cache:
            cached_result = recommendation_cache[cache_key]
            processing_time = int((time.time() - start_time) * 1000)
        else:
            # Phase 4: LLM ranking (if available)
            if llm_client:
                try:
                    recommendation_result = llm_client.rank_and_explain(retrieval_result.candidate_set)
                    # Cache the result
                    recommendation_cache[cache_key] = recommendation_result
                except Exception as e:
                    # Fallback ranking
                    recommendation_result = fallback_ranking(retrieval_result.candidate_set)
            else:
                # Fallback ranking
                recommendation_result = fallback_ranking(retrieval_result.candidate_set)
            
            processing_time = int((time.time() - start_time) * 1000)
        
        # Create restaurant lookup
        restaurant_lookup = create_restaurant_lookup(retrieval_result.candidate_set)
        
        # Convert to response format
        response_items = []
        for item in recommendation_result.items:
            restaurant_info = restaurant_lookup.get(item.restaurant_id, {})
            response_items.append(RecommendationItemResponse(
                restaurant_id=item.restaurant_id,
                rank=item.rank,
                explanation=item.explanation,
                restaurant_name=restaurant_info.get("name"),
                location=restaurant_info.get("location"),
                cuisines=restaurant_info.get("cuisines"),
                cost_for_two=restaurant_info.get("cost_for_two"),
                rating=restaurant_info.get("rating"),
                votes=restaurant_info.get("votes")
            ))
        
        return RecommendationResponse(
            success=True,
            summary=recommendation_result.summary,
            recommendations=response_items,
            total_candidates=len(retrieval_result.candidate_set.candidates),
            relaxation_steps=[{"action": step.action, "note": step.note} for step in retrieval_result.relax_steps],
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")


@app.delete("/cache")
async def clear_cache():
    """Clear recommendation cache."""
    global recommendation_cache
    recommendation_cache.clear()
    return {"message": "Cache cleared"}


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    return {
        "cache_size": len(recommendation_cache),
        "cache_enabled": True
    }


def fallback_ranking(candidate_set):
    """Fallback ranking when LLM is not available."""
    from zomoto_ai.phase0.domain.models import RecommendationResult, RecommendationItem
    
    # Simple ranking by rating and votes
    sorted_candidates = sorted(
        candidate_set.candidates,
        key=lambda r: (r.rating or 0, r.votes or 0),
        reverse=True
    )
    
    items = []
    for i, restaurant in enumerate(sorted_candidates[:10], 1):
        explanation = f"Ranked #{i} by rating ({restaurant.rating or 'N/A'}) and popularity ({restaurant.votes or 'N/A'} votes)"
        items.append(RecommendationItem(
            restaurant_id=restaurant.id,
            rank=i,
            explanation=explanation
        ))
    
    return RecommendationResult(
        user_preference=candidate_set.user_preference,
        items=items,
        summary=f"Top {len(items)} restaurants ranked by rating and popularity (no AI ranking available)"
    )


class RecommendationAPI:
    """Wrapper class for running the API server."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
    
    def run(self, reload: bool = False):
        """Run the API server."""
        uvicorn.run(
            "zomoto_ai.phase5.api:app",
            host=self.host,
            port=self.port,
            reload=reload,
            log_level="info"
        )


def main():
    """Main entry point for API server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zomoto AI Recommendation API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    api = RecommendationAPI(host=args.host, port=args.port)
    api.run(reload=args.reload)


if __name__ == "__main__":
    main()
