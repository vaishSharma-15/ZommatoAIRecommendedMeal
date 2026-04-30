"""API Models - Pydantic models for request/response validation

Defines the data structures for API endpoints with proper validation
and serialization.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, Budget


class BudgetRequest(BaseModel):
    """Budget model for API requests."""
    kind: str = Field(..., description="Budget type: 'range' or 'exact'")
    max_cost_for_two: Optional[int] = Field(None, description="Maximum cost for two people")
    min_cost_for_two: Optional[int] = Field(None, description="Minimum cost for two people")
    
    @validator('kind')
    def validate_kind(cls, v):
        if v not in ['range', 'exact']:
            raise ValueError("Budget kind must be 'range' or 'exact'")
        return v


class PreferenceRequest(BaseModel):
    """User preference model for API requests."""
    location: str = Field(..., description="Location for restaurant search")
    budget: Optional[BudgetRequest] = Field(None, description="Budget constraints")
    cuisine: Optional[str] = Field(None, description="Preferred cuisine type")
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Minimum rating")
    optional_constraints: List[str] = Field(default_factory=list, description="Optional constraints")
    
    def to_domain_model(self) -> UserPreference:
        """Convert to domain UserPreference model."""
        budget = None
        if self.budget:
            budget = Budget(
                kind=self.budget.kind,
                max_cost_for_two=self.budget.max_cost_for_two,
                min_cost_for_two=self.budget.min_cost_for_two
            )
        
        return UserPreference(
            location=self.location,
            budget=budget,
            cuisine=self.cuisine,
            min_rating=self.min_rating,
            optional_constraints=self.optional_constraints
        )


class RecommendationRequest(BaseModel):
    """Main recommendation request model."""
    preferences: PreferenceRequest = Field(..., description="User preferences")
    top_n: int = Field(default=10, ge=1, le=50, description="Number of recommendations to return")
    include_explanations: bool = Field(default=True, description="Include explanations for recommendations")
    use_cache: bool = Field(default=True, description="Use cached results if available")


class RestaurantItem(BaseModel):
    """Restaurant item in recommendations."""
    restaurant_id: str = Field(..., description="Restaurant ID")
    name: str = Field(..., description="Restaurant name")
    location: str = Field(..., description="Restaurant location")
    cuisines: List[str] = Field(..., description="Available cuisines")
    cost_for_two: Optional[int] = Field(None, description="Cost for two people")
    rating: Optional[float] = Field(None, description="Restaurant rating")
    votes: Optional[int] = Field(None, description="Number of votes")


class RecommendationItem(BaseModel):
    """Individual recommendation item."""
    restaurant: RestaurantItem = Field(..., description="Restaurant information")
    rank: int = Field(..., description="Rank in recommendations")
    explanation: Optional[str] = Field(None, description="Explanation for recommendation")
    score: Optional[float] = Field(None, description="Confidence score")


class RecommendationResponse(BaseModel):
    """Recommendation response model."""
    recommendations: List[RecommendationItem] = Field(..., description="List of recommendations")
    user_preferences: PreferenceRequest = Field(..., description="User preferences used")
    summary: str = Field(..., description="Summary of recommendations")
    total_candidates: int = Field(..., description="Total candidates considered")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    cache_hit: bool = Field(..., description="Whether result was served from cache")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class HealthStatus(BaseModel):
    """Health status for a component."""
    status: str = Field(..., description="Health status: healthy, unhealthy, degraded")
    last_check: datetime = Field(..., description="Last health check timestamp")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    components: Dict[str, HealthStatus] = Field(..., description="Component health statuses")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class MetricValue(BaseModel):
    """Individual metric value."""
    name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Metric unit")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metric timestamp")


class MetricsResponse(BaseModel):
    """Metrics response."""
    metrics: List[MetricValue] = Field(..., description="List of metrics")
    summary: Dict[str, Any] = Field(..., description="Metrics summary")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    hit_rate: float = Field(..., description="Cache hit rate")
    total_requests: int = Field(..., description="Total cache requests")
    hits: int = Field(..., description="Cache hits")
    misses: int = Field(..., description="Cache misses")
    size: int = Field(..., description="Cache size")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class JobStatus(BaseModel):
    """Job status model."""
    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    progress: Optional[float] = Field(None, description="Progress percentage")


class JobResponse(BaseModel):
    """Job response model."""
    job: JobStatus = Field(..., description="Job status information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for correlation")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response."""
    validation_errors: List[Dict[str, Any]] = Field(..., description="Field validation errors")
