"""API Endpoints - FastAPI route definitions

Implements all API endpoints as specified in the architecture:
- POST /recommendations - Main recommendation endpoint
- GET /health - Service health check
- GET /metrics - Prometheus metrics endpoint
- GET /cache/stats - Cache statistics
- POST /cache/clear - Clear cache
- GET /jobs/{id} - Async job status
"""

import asyncio
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .models import (
    RecommendationRequest,
    RecommendationResponse,
    PreferenceRequest,
    RecommendationItem,
    RestaurantItem,
    HealthResponse,
    HealthStatus,
    MetricsResponse,
    MetricValue,
    CacheStatsResponse,
    JobResponse,
    JobStatus
)
from ..services import (
    RecommendationService,
    CacheService,
    JobQueueService,
    MonitoringService
)
from ..data import get_cache_backend, get_job_queue_backend
from zomoto_ai.phase6.logging import get_logger
from zomoto_ai.phase6.monitoring import get_monitoring_system


# Create router
router = APIRouter(prefix="/api/v1", tags=["recommendations"])

# Initialize services
recommendation_service = RecommendationService()
cache_service = CacheService(get_cache_backend())
job_queue_service = JobQueueService(get_job_queue_backend())
monitoring_service = MonitoringService()

logger = get_logger()


@router.post("/recommendations", response_model=RecommendationResponse)
async def create_recommendations(
    request: RecommendationRequest,
    correlation_id: str = None
) -> RecommendationResponse:
    """
    Generate restaurant recommendations based on user preferences.
    
    This is the main API endpoint that orchestrates the complete
    recommendation pipeline including retrieval, ranking, and caching.
    """
    start_time = time.time()
    
    try:
        # Convert request to domain model
        user_preference = request.preferences.to_domain_model()
        
        # Check cache first (if enabled)
        cache_key = None
        cached_result = None
        if request.use_cache:
            cache_key = cache_service.generate_cache_key(user_preference, request.top_n)
            cached_result = await cache_service.get_recommendations(cache_key)
        
        if cached_result:
            # Return cached result
            processing_time = (time.time() - start_time) * 1000
            return RecommendationResponse(
                recommendations=cached_result["recommendations"],
                user_preferences=request.preferences,
                summary=cached_result["summary"],
                total_candidates=cached_result["total_candidates"],
                processing_time_ms=processing_time,
                cache_hit=True
            )
        
        # Generate new recommendations
        result = await recommendation_service.generate_recommendations(
            user_preference=user_preference,
            top_n=request.top_n,
            include_explanations=request.include_explanations
        )
        
        # Cache the result
        if cache_key:
            await cache_service.set_recommendations(cache_key, result, ttl=3600)
        
        # Convert to API response
        recommendations = []
        for item in result.items:
            restaurant_domain = next((r for r in recommendation_service.retrieval_service._restaurants if r.id == item.restaurant_id), None)
            if not restaurant_domain:
                continue
                
            restaurant = RestaurantItem(
                restaurant_id=item.restaurant_id,
                name=restaurant_domain.name,
                location=restaurant_domain.location or restaurant_domain.city or "Unknown",
                cuisines=restaurant_domain.cuisines or [],
                cost_for_two=restaurant_domain.cost_for_two,
                rating=restaurant_domain.rating,
                votes=restaurant_domain.votes
            )
            
            kwargs = {
                "restaurant": restaurant,
                "rank": item.rank,
                "explanation": item.explanation or ""
            }
            score = getattr(item, 'score', None)
            if score is not None:
                kwargs["score"] = score
                
            recommendations.append(RecommendationItem(**kwargs))
        
        processing_time = (time.time() - start_time) * 1000
        
        response = RecommendationResponse(
            recommendations=recommendations,
            user_preferences=request.preferences,
            summary=result.summary,
            total_candidates=len(result.items),
            processing_time_ms=processing_time,
            cache_hit=False
        )
        
        # Log successful recommendation
        logger.info(
            "recommendations",
            "generated",
            f"Generated {len(recommendations)} recommendations",
            user_location=user_preference.location,
            top_n=request.top_n,
            processing_time_ms=processing_time,
            cache_hit=False
        )
        
        return response
        
    except ValueError as e:
        logger.error(
            "recommendations",
            "validation_error",
            f"Validation error: {str(e)}",
            correlation_id=correlation_id
        )
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(
            "recommendations",
            "generation_failed",
            f"Recommendation generation failed: {str(e)}",
            correlation_id=correlation_id,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.post("/recommendations/async")
async def create_recommendations_async(
    request: RecommendationRequest,
    correlation_id: str = None
) -> JobResponse:
    """
    Submit recommendation generation as an async job.
    
    Useful for large datasets or when immediate response is not required.
    """
    try:
        # Convert request to domain model
        user_preference = request.preferences.to_domain_model()
        
        # Submit async job
        job_id = await job_queue_service.submit_recommendation_job(
            user_preference=user_preference,
            top_n=request.top_n,
            include_explanations=request.include_explanations
        )
        
        # Get job status
        job_status = await job_queue_service.get_job_status(job_id)
        
        logger.info(
            "recommendations_async",
            "job_submitted",
            f"Async recommendation job submitted: {job_id}",
            job_id=job_id,
            correlation_id=correlation_id
        )
        
        return JobResponse(
            job=JobStatus(
                job_id=job_status.id,
                status=job_status.status.value,
                created_at=job_status.created_at,
                started_at=job_status.started_at,
                completed_at=job_status.completed_at,
                result=job_status.result,
                error=job_status.error,
                progress=job_status.retry_count / job_status.max_retries * 100
            )
        )
        
    except Exception as e:
        logger.error(
            "recommendations_async",
            "submission_failed",
            f"Async job submission failed: {str(e)}",
            correlation_id=correlation_id
        )
        raise HTTPException(status_code=500, detail="Failed to submit async job")


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    correlation_id: str = None
) -> JobResponse:
    """Get the status of an async recommendation job."""
    try:
        job_status = await job_queue_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(
            job=JobStatus(
                job_id=job_status.id,
                status=job_status.status.value,
                created_at=job_status.created_at,
                started_at=job_status.started_at,
                completed_at=job_status.completed_at,
                result=job_status.result,
                error=job_status.error,
                progress=job_status.retry_count / job_status.max_retries * 100
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "jobs",
            "status_failed",
            f"Failed to get job status: {str(e)}",
            job_id=job_id,
            correlation_id=correlation_id
        )
        raise HTTPException(status_code=500, detail="Failed to get job status")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Simple health check for the API.
    """
    try:
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=time.time(),
            components={"api": HealthStatus(status="healthy", last_check=int(time.time()))}
        )
    except Exception as e:
        logger.error("health", "check_failed", f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            uptime_seconds=0,
            components={}
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Get system metrics for monitoring.
    
    Returns performance metrics, error rates, and other operational data.
    """
    try:
        # Get metrics from monitoring system
        monitoring_system = get_monitoring_system()
        system_status = monitoring_system.get_system_status()
        
        # Convert to response format
        metrics = []
        for name, value in system_status.get("metrics", {}).items():
            if isinstance(value, (int, float)):
                metrics.append(MetricValue(
                    name=name,
                    value=float(value),
                    unit="count" if "counter" in name else "value"
                ))
        
        summary = {
            "total_requests": system_status.get("metrics", {}).get("total_requests", 0),
            "error_rate": system_status.get("metrics", {}).get("error_rate", 0),
            "avg_response_time": system_status.get("metrics", {}).get("avg_response_time", 0)
        }
        
        return MetricsResponse(
            metrics=metrics,
            summary=summary
        )
        
    except Exception as e:
        logger.error("metrics", "fetch_failed", f"Failed to fetch metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Get cache performance statistics."""
    try:
        stats = await cache_service.get_statistics()
        
        return CacheStatsResponse(
            hit_rate=stats.get("hit_rate", 0.0),
            total_requests=stats.get("total_requests", 0),
            hits=stats.get("hits", 0),
            misses=stats.get("misses", 0),
            size=stats.get("size", 0)
        )
        
    except Exception as e:
        logger.error("cache", "stats_failed", f"Failed to get cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear all cache data."""
    try:
        await cache_service.clear_cache()
        
        logger.info("cache", "cleared", "Cache cleared successfully")
        
        return {"message": "Cache cleared successfully"}
        
    except Exception as e:
        logger.error("cache", "clear_failed", f"Failed to clear cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/system/status")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status."""
    try:
        monitoring_system = get_monitoring_system()
        status = monitoring_system.get_system_status()
        
        return status
        
    except Exception as e:
        logger.error("system", "status_failed", f"Failed to get system status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


# Additional utility endpoints
@router.get("/info")
async def get_api_info() -> Dict[str, Any]:
    """Get API information and capabilities."""
    return {
        "name": "Zomoto AI Recommendation API",
        "version": "1.0.0",
        "description": "Restaurant recommendation system with LLM-powered ranking",
        "endpoints": {
            "recommendations": "/api/v1/recommendations",
            "async_recommendations": "/api/v1/recommendations/async",
            "job_status": "/api/v1/jobs/{job_id}",
            "health": "/api/v1/health",
            "metrics": "/api/v1/metrics",
            "cache_stats": "/api/v1/cache/stats"
        },
        "features": [
            "Real-time recommendations",
            "Async job processing",
            "Intelligent caching",
            "Rate limiting",
            "Health monitoring",
            "Structured logging"
        ]
    }
