"""Backend Architecture for Zomoto AI Recommendation System

Production-ready backend with API layer, service layer, data layer,
and reliability components as specified in PhaseWiseArchitecture.md.
"""

from .api import app
from .services import (
    RecommendationService,
    RetrievalService,
    RankingService,
    CacheService,
    JobQueueService,
    MonitoringService
)
from .data import (
    DatabaseBackend,
    RestaurantRepository,
    CacheBackend,
    JobQueueBackend
)
from .reliability import (
    CircuitBreaker,
    RateLimiter,
    RetryHandler,
    TimeoutManager,
    FallbackHandler
)

__version__ = "1.0.0"
__all__ = [
    "app",
    "RecommendationService",
    "RetrievalService", 
    "RankingService",
    "CacheService",
    "JobQueueService",
    "MonitoringService",
    "DatabaseBackend",
    "RestaurantRepository",
    "CacheBackend",
    "JobQueueBackend",
    "CircuitBreaker",
    "RateLimiter",
    "RetryHandler",
    "TimeoutManager",
    "FallbackHandler"
]
