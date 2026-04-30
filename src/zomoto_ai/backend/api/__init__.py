"""API Layer - FastAPI Application

Provides RESTful endpoints for the restaurant recommendation system
with comprehensive error handling, validation, and documentation.
"""

from .app import app
from .endpoints import router
from .middleware import (
    LoggingMiddleware,
    RateLimitMiddleware,
    CorrelationIDMiddleware,
    ErrorHandlingMiddleware
)
from .models import (
    RecommendationRequest,
    RecommendationResponse,
    HealthResponse,
    MetricsResponse
)

__all__ = [
    "app",
    "router",
    "LoggingMiddleware",
    "RateLimitMiddleware", 
    "CorrelationIDMiddleware",
    "ErrorHandlingMiddleware",
    "RecommendationRequest",
    "RecommendationResponse",
    "HealthResponse",
    "MetricsResponse"
]
