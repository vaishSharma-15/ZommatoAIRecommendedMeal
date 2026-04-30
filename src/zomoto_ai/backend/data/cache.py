"""Cache Backend - Redis and memory cache implementations

Provides unified interface for Redis-based distributed caching
and in-memory fallback caching.
"""

import asyncio
import json
import time
from typing import Any, Optional, Dict, List
from abc import ABC, abstractmethod
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger, get_performance_tracker


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key."""
        pass
    
    @abstractmethod
    async def clear(self) -> int:
        """Clear all keys."""
        pass
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend for development/testing."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self._cache = {}
        self._ttl_cache = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        with self.performance_tracker.track_request("cache", "get"):
            async with self._lock:
                # Check TTL
                if key in self._ttl_cache:
                    if time.time() > self._ttl_cache[key]:
                        # Expired
                        del self._cache[key]
                        del self._ttl_cache[key]
                        self._stats["misses"] += 1
                        return None
                
                if key in self._cache:
                    self._stats["hits"] += 1
                    return self._cache[key]
                else:
                    self._stats["misses"] += 1
                    return None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL."""
        with self.performance_tracker.track_request("cache", "set"):
            async with self._lock:
                # Check size limit
                if len(self._cache) >= self.max_size and key not in self._cache:
                    # Remove oldest item (simple LRU)
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    if oldest_key in self._ttl_cache:
                        del self._ttl_cache[oldest_key]
                
                self._cache[key] = value
                
                if ttl:
                    self._ttl_cache[key] = time.time() + ttl
                elif key in self._ttl_cache:
                    del self._ttl_cache[key]
                
                self._stats["sets"] += 1
                return True
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        async with self._lock:
            deleted = False
            
            if key in self._cache:
                del self._cache[key]
                deleted = True
            
            if key in self._ttl_cache:
                del self._ttl_cache[key]
                deleted = True
            
            if deleted:
                self._stats["deletes"] += 1
            
            return deleted
    
    async def clear(self) -> int:
        """Clear all keys."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._ttl_cache.clear()
            return count
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests) if total_requests > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "sets": self._stats["sets"],
                "deletes": self._stats["deletes"],
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "backend_type": "memory"
            }
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        # Simple pattern matching for memory cache
        import fnmatch
        
        async with self._lock:
            keys_to_delete = []
            for key in self._cache:
                if fnmatch.fnmatch(key, pattern):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
                if key in self._ttl_cache:
                    del self._ttl_cache[key]
                self._stats["deletes"] += 1
            
            return len(keys_to_delete)


class RedisCacheBackend(CacheBackend):
    """Redis-based distributed cache backend."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, database: int = 0,
                 password: Optional[str] = None, max_connections: int = 20):
        self.host = host
        self.port = port
        self.database = database
        self.password = password
        self.max_connections = max_connections
        
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self._redis = None
        self._pool = None
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            import aioredis
            
            self._pool = await aioredis.ConnectionPool.from_url(
                f"redis://{self.host}:{self.port}/{self.database}",
                password=self.password,
                max_connections=self.max_connections
            )
            
            self._redis = aioredis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._redis.ping()
            
            self.logger.info("redis_cache_backend", "connected", 
                           f"Connected to Redis: {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error("redis_cache_backend", "connect_failed", f"Failed to connect: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._redis = None
            self.logger.info("redis_cache_backend", "disconnected", "Disconnected from Redis")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._redis:
            return None
        
        try:
            with self.performance_tracker.track_request("cache", "get"):
                value = await self._redis.get(key)
                return value.decode('utf-8') if value else None
                
        except Exception as e:
            self.logger.error("redis_cache_backend", "get_failed", f"Failed to get key {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL."""
        if not self._redis:
            return False
        
        try:
            with self.performance_tracker.track_request("cache", "set"):
                if ttl:
                    return await self._redis.setex(key, ttl, value)
                else:
                    return await self._redis.set(key, value)
                    
        except Exception as e:
            self.logger.error("redis_cache_backend", "set_failed", f"Failed to set key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self._redis:
            return False
        
        try:
            result = await self._redis.delete(key)
            return result > 0
            
        except Exception as e:
            self.logger.error("redis_cache_backend", "delete_failed", f"Failed to delete key {key}: {str(e)}")
            return False
    
    async def clear(self) -> int:
        """Clear all keys."""
        if not self._redis:
            return 0
        
        try:
            # Get all keys and delete them
            keys = await self._redis.keys("*")
            if keys:
                return await self._redis.delete(*keys)
            return 0
            
        except Exception as e:
            self.logger.error("redis_cache_backend", "clear_failed", f"Failed to clear cache: {str(e)}")
            return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._redis:
            return {"error": "Not connected"}
        
        try:
            info = await self._redis.info()
            
            return {
                "size": info.get("db0", {}).get("keys", 0),
                "memory_used": info.get("used_memory", 0),
                "memory_human": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "backend_type": "redis",
                "host": self.host,
                "port": self.port,
                "database": self.database
            }
            
        except Exception as e:
            self.logger.error("redis_cache_backend", "stats_failed", f"Failed to get statistics: {str(e)}")
            return {"error": str(e)}
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        if not self._redis:
            return 0
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
            return 0
            
        except Exception as e:
            self.logger.error("redis_cache_backend", "delete_pattern_failed", 
                            f"Failed to delete pattern {pattern}: {str(e)}")
            return 0
    
    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """Calculate hit rate from Redis info."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        return (hits / total) if total > 0 else 0.0


# Factory functions and global instances
_cache_backend = None


def create_memory_cache(max_size: int = 10000) -> MemoryCacheBackend:
    """Create memory cache backend."""
    return MemoryCacheBackend(max_size)


def create_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    database: int = 0,
    password: Optional[str] = None,
    max_connections: int = 20
) -> RedisCacheBackend:
    """Create Redis cache backend."""
    return RedisCacheBackend(host, port, database, password, max_connections)


def get_cache_backend() -> Optional[CacheBackend]:
    """Get default cache backend instance."""
    global _cache_backend
    
    if _cache_backend is None:
        # Try to determine which backend to use from environment
        import os
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"
        
        if redis_enabled:
            _cache_backend = create_redis_cache(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                database=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD"),
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
            )
            
            # Try to connect
            if not _cache_backend.connect():
                # Fallback to memory cache
                _cache_backend = create_memory_cache()
        else:
            _cache_backend = create_memory_cache()
    
    return _cache_backend
