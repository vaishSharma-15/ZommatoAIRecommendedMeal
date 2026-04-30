"""Data Layer - Database backends and repositories

Provides unified interface for SQLite and PostgreSQL databases,
along with caching and job queue backends.
"""

from .database import (
    DatabaseBackend,
    create_sqlite_backend,
    create_postgresql_backend,
    RestaurantRepository,
    get_database_backend
)
from .cache import (
    CacheBackend,
    RedisCacheBackend,
    MemoryCacheBackend,
    get_cache_backend
)
from .job_queue import (
    JobQueueBackend,
    RedisJobQueueBackend,
    InMemoryJobQueueBackend,
    get_job_queue_backend
)

__all__ = [
    "DatabaseBackend",
    "create_sqlite_backend",
    "create_postgresql_backend",
    "RestaurantRepository",
    "get_database_backend",
    "CacheBackend",
    "RedisCacheBackend",
    "MemoryCacheBackend",
    "get_cache_backend",
    "JobQueueBackend",
    "RedisJobQueueBackend",
    "InMemoryJobQueueBackend",
    "get_job_queue_backend"
]

# Global instances
_database_backend = None
_cache_backend = None
_job_queue_backend = None


async def initialize_backends():
    """Initialize all data backends."""
    global _database_backend, _cache_backend, _job_queue_backend
    
    # Initialize database backend
    _database_backend = get_database_backend()
    await _database_backend.connect()
    
    # Initialize cache backend
    _cache_backend = get_cache_backend()
    await _cache_backend.connect()
    
    # Initialize job queue backend
    _job_queue_backend = get_job_queue_backend()
    await _job_queue_backend.connect()
