"""Job Queue Backend - Redis and in-memory job queue implementations

Provides unified interface for distributed job queue processing
with Redis support and in-memory fallback.
"""

import asyncio
import json
import time
import uuid
from typing import Any, Optional, Dict, List
from abc import ABC, abstractmethod
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger, get_performance_tracker


class JobQueueBackend(ABC):
    """Abstract base class for job queue backends."""
    
    @abstractmethod
    async def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> str:
        """Enqueue a job."""
        pass
    
    @abstractmethod
    async def dequeue(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Dequeue a job."""
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        pass
    
    @abstractmethod
    async def update_job_status(self, job_id: str, status: str, result: Any = None, error: str = None):
        """Update job status."""
        pass
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        pass


class InMemoryJobQueueBackend(JobQueueBackend):
    """In-memory job queue backend for development/testing."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self._queue = asyncio.Queue(maxsize=max_size)
        self._jobs = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0
        }
    
    async def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> str:
        """Enqueue a job."""
        with self.performance_tracker.track_request("job_queue", "enqueue"):
            async with self._lock:
                if len(self._jobs) >= self.max_size:
                    raise Exception("Queue is full")
                
                job_id = str(uuid.uuid4())
                job = {
                    "id": job_id,
                    "data": job_data,
                    "priority": priority,
                    "status": "pending",
                    "created_at": time.time(),
                    "started_at": None,
                    "completed_at": None,
                    "result": None,
                    "error": None,
                    "retry_count": 0,
                    "max_retries": 3
                }
                
                self._jobs[job_id] = job
                
                # Add to priority queue (simple implementation)
                await self._queue.put((priority, time.time(), job_id))
                
                self._stats["total_jobs"] += 1
                
                self.logger.info("in_memory_job_queue", "job_enqueued", f"Enqueued job: {job_id}",
                               job_id=job_id, priority=priority)
                
                return job_id
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Dequeue a job."""
        try:
            with self.performance_tracker.track_request("job_queue", "dequeue"):
                priority, created_at, job_id = await asyncio.wait_for(
                    self._queue.get(), timeout=timeout
                )
                
                async with self._lock:
                    job = self._jobs.get(job_id)
                    if job and job["status"] == "pending":
                        job["status"] = "running"
                        job["started_at"] = time.time()
                        return job
                    else:
                        # Job might have been cancelled or already processed
                        return None
                        
        except asyncio.TimeoutError:
            return None
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)
    
    async def update_job_status(self, job_id: str, status: str, result: Any = None, error: str = None):
        """Update job status."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job["status"] = status
                if result is not None:
                    job["result"] = result
                if error is not None:
                    job["error"] = error
                
                if status == "running":
                    job["started_at"] = time.time()
                elif status in ["completed", "failed", "cancelled"]:
                    job["completed_at"] = time.time()
                    
                    # Update stats
                    if status == "completed":
                        self._stats["completed_jobs"] += 1
                    elif status == "failed":
                        self._stats["failed_jobs"] += 1
                    elif status == "cancelled":
                        self._stats["cancelled_jobs"] += 1
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        async with self._lock:
            pending_count = sum(1 for job in self._jobs.values() if job["status"] == "pending")
            running_count = sum(1 for job in self._jobs.values() if job["status"] == "running")
            
            return {
                **self._stats,
                "queue_size": len(self._jobs),
                "pending_jobs": pending_count,
                "running_jobs": running_count,
                "max_size": self.max_size,
                "backend_type": "memory"
            }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job["status"] == "pending":
                job["status"] = "cancelled"
                job["completed_at"] = time.time()
                self._stats["cancelled_jobs"] += 1
                return True
            return False
    
    async def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        async with self._lock:
            jobs_to_remove = []
            for job_id, job in self._jobs.items():
                if (job["status"] in ["completed", "failed", "cancelled"] 
                    and job["completed_at"] and job["completed_at"] < cutoff_time):
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self._jobs[job_id]


class RedisJobQueueBackend(JobQueueBackend):
    """Redis-based distributed job queue backend."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, database: int = 0,
                 password: Optional[str] = None, queue_name: str = "zomoto_jobs"):
        self.host = host
        self.port = port
        self.database = database
        self.password = password
        self.queue_name = queue_name
        
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
                password=self.password
            )
            
            self._redis = aioredis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._redis.ping()
            
            self.logger.info("redis_job_queue", "connected", 
                           f"Connected to Redis: {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error("redis_job_queue", "connect_failed", f"Failed to connect: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._redis = None
            self.logger.info("redis_job_queue", "disconnected", "Disconnected from Redis")
    
    async def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> str:
        """Enqueue a job."""
        if not self._redis:
            raise Exception("Not connected to Redis")
        
        try:
            with self.performance_tracker.track_request("job_queue", "enqueue"):
                job_id = str(uuid.uuid4())
                
                job = {
                    "id": job_id,
                    "data": job_data,
                    "priority": priority,
                    "status": "pending",
                    "created_at": time.time(),
                    "started_at": None,
                    "completed_at": None,
                    "result": None,
                    "error": None,
                    "retry_count": 0,
                    "max_retries": 3
                }
                
                # Store job data
                job_key = f"{self.queue_name}:jobs:{job_id}"
                await self._redis.hset(job_key, mapping={k: json.dumps(v) for k, v in job.items()})
                
                # Add to priority queue
                score = f"{priority:01d}{int(job['created_at'])}"
                await self._redis.zadd(f"{self.queue_name}:queue", {job_id: score})
                
                # Update stats
                await self._redis.hincrby(f"{self.queue_name}:stats", "total_jobs", 1)
                
                self.logger.info("redis_job_queue", "job_enqueued", f"Enqueued job: {job_id}",
                               job_id=job_id, priority=priority)
                
                return job_id
                
        except Exception as e:
            self.logger.error("redis_job_queue", "enqueue_failed", f"Failed to enqueue job: {str(e)}")
            raise
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Dequeue a job."""
        if not self._redis:
            return None
        
        try:
            with self.performance_tracker.track_request("job_queue", "dequeue"):
                # Use BZPOPMIN for blocking dequeue with priority
                result = await self._redis.bzpopmin(f"{self.queue_name}:queue", timeout=timeout)
                
                if result:
                    job_id, score = result
                    
                    # Get job data
                    job_key = f"{self.queue_name}:jobs:{job_id}"
                    job_data = await self._redis.hgetall(job_key)
                    
                    if job_data:
                        # Parse job data
                        job = {}
                        for field, value in job_data.items():
                            try:
                                job[field.decode()] = json.loads(value.decode())
                            except:
                                job[field.decode()] = value.decode()
                        
                        # Update status to running
                        await self.update_job_status(job_id, "running")
                        
                        return job
                
                return None
                
        except Exception as e:
            self.logger.error("redis_job_queue", "dequeue_failed", f"Failed to dequeue job: {str(e)}")
            return None
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        if not self._redis:
            return None
        
        try:
            job_key = f"{self.queue_name}:jobs:{job_id}"
            job_data = await self._redis.hgetall(job_key)
            
            if job_data:
                job = {}
                for field, value in job_data.items():
                    try:
                        job[field.decode()] = json.loads(value.decode())
                    except:
                        job[field.decode()] = value.decode()
                return job
            
            return None
            
        except Exception as e:
            self.logger.error("redis_job_queue", "get_job_failed", f"Failed to get job: {str(e)}")
            return None
    
    async def update_job_status(self, job_id: str, status: str, result: Any = None, error: str = None):
        """Update job status."""
        if not self._redis:
            return
        
        try:
            job_key = f"{self.queue_name}:jobs:{job_id}"
            
            # Update job fields
            updates = {"status": json.dumps(status)}
            
            if status == "running":
                updates["started_at"] = json.dumps(time.time())
            elif status in ["completed", "failed", "cancelled"]:
                updates["completed_at"] = json.dumps(time.time())
                
                # Update stats
                if status == "completed":
                    await self._redis.hincrby(f"{self.queue_name}:stats", "completed_jobs", 1)
                elif status == "failed":
                    await self._redis.hincrby(f"{self.queue_name}:stats", "failed_jobs", 1)
                elif status == "cancelled":
                    await self._redis.hincrby(f"{self.queue_name}:stats", "cancelled_jobs", 1)
            
            if result is not None:
                updates["result"] = json.dumps(result)
            
            if error is not None:
                updates["error"] = json.dumps(error)
            
            await self._redis.hset(job_key, mapping=updates)
            
        except Exception as e:
            self.logger.error("redis_job_queue", "update_status_failed", 
                            f"Failed to update job status: {str(e)}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self._redis:
            return {"error": "Not connected"}
        
        try:
            # Get basic stats
            stats = await self._redis.hgetall(f"{self.queue_name}:stats")
            stats_dict = {}
            for field, value in stats.items():
                stats_dict[field.decode()] = int(value.decode())
            
            # Get current queue size
            queue_size = await self._redis.zcard(f"{self.queue_name}:queue")
            
            # Count jobs by status
            all_jobs = await self._redis.keys(f"{self.queue_name}:jobs:*")
            pending = running = 0
            
            for job_key in all_jobs:
                job_data = await self._redis.hget(job_key, "status")
                if job_data:
                    status = json.loads(job_data.decode())
                    if status == "pending":
                        pending += 1
                    elif status == "running":
                        running += 1
            
            return {
                **stats_dict,
                "queue_size": queue_size,
                "pending_jobs": pending,
                "running_jobs": running,
                "backend_type": "redis",
                "host": self.host,
                "port": self.port,
                "database": self.database
            }
            
        except Exception as e:
            self.logger.error("redis_job_queue", "get_stats_failed", f"Failed to get statistics: {str(e)}")
            return {"error": str(e)}
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        if not self._redis:
            return False
        
        try:
            # Remove from queue
            await self._redis.zrem(f"{self.queue_name}:queue", job_id)
            
            # Update status
            await self.update_job_status(job_id, "cancelled")
            
            return True
            
        except Exception as e:
            self.logger.error("redis_job_queue", "cancel_job_failed", f"Failed to cancel job: {str(e)}")
            return False


# Factory functions and global instances
_job_queue_backend = None


def create_memory_job_queue(max_size: int = 1000) -> InMemoryJobQueueBackend:
    """Create in-memory job queue backend."""
    return InMemoryJobQueueBackend(max_size)


def create_redis_job_queue(
    host: str = "localhost",
    port: int = 6379,
    database: int = 0,
    password: Optional[str] = None,
    queue_name: str = "zomoto_jobs"
) -> RedisJobQueueBackend:
    """Create Redis job queue backend."""
    return RedisJobQueueBackend(host, port, database, password, queue_name)


def get_job_queue_backend() -> Optional[JobQueueBackend]:
    """Get default job queue backend instance."""
    global _job_queue_backend
    
    if _job_queue_backend is None:
        # Try to determine which backend to use from environment
        import os
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"
        
        if redis_enabled:
            _job_queue_backend = create_redis_job_queue(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                database=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD"),
                queue_name=os.getenv("JOB_QUEUE_NAME", "zomoto_jobs")
            )
            
            # Try to connect
            if not _job_queue_backend.connect():
                # Fallback to memory queue
                _job_queue_backend = create_memory_job_queue()
        else:
            _job_queue_backend = create_memory_job_queue()
    
    return _job_queue_backend
