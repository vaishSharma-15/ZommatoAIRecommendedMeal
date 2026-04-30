"""Async Job Queue for Phase 6 - Production Hardening

Provides asynchronous job queue for LLM calls to improve performance
and reliability under high load.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone, timedelta
import threading
from queue import Queue, Empty
import pickle
from pathlib import Path
import aiofiles
from contextlib import asynccontextmanager

# Redis is optional - import only if available
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Import domain models
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult
from zomoto_ai.phase4.groq_ranker import GroqLLMClient


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Job:
    """Job definition for async processing."""
    id: str
    job_type: str
    payload: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class LLMJob:
    """Specific job for LLM processing."""
    job_id: str
    candidate_set: CandidateSet
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "candidate_set": asdict(self.candidate_set),
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMJob":
        """Create from dictionary."""
        # Reconstruct CandidateSet
        candidate_set_data = data["candidate_set"]
        candidate_set = CandidateSet(
            user_preference=candidate_set_data["user_preference"],
            candidates=candidate_set_data["candidates"]
        )
        
        return cls(
            job_id=data["job_id"],
            candidate_set=candidate_set,
            model=data.get("model", "llama-3.3-70b-versatile"),
            temperature=data.get("temperature", 0.2),
            max_tokens=data.get("max_tokens")
        )


class JobQueue:
    """In-memory job queue with priority support."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue = Queue(maxsize=max_size)
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0
        }
    
    def enqueue(self, job: Job) -> bool:
        """Add a job to the queue."""
        with self._lock:
            if len(self._jobs) >= self.max_size:
                return False
            
            self._jobs[job.id] = job
            self._queue.put((job.priority.value, job.created_at, job.id))
            self._stats["total_jobs"] += 1
            return True
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Job]:
        """Get the next job from the queue."""
        try:
            priority, created_at, job_id = self._queue.get(timeout=timeout)
            with self._lock:
                job = self._jobs.get(job_id)
                if job and job.status == JobStatus.PENDING:
                    return job
                else:
                    # Job might have been cancelled or already processed
                    return None
        except Empty:
            return None
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: JobStatus, 
                         result: Any = None, error: str = None):
        """Update job status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                if result is not None:
                    job.result = result
                if error is not None:
                    job.error = error
                
                if status == JobStatus.RUNNING:
                    job.started_at = datetime.now(timezone.utc)
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job.completed_at = datetime.now(timezone.utc)
                    
                    # Update stats
                    if status == JobStatus.COMPLETED:
                        self._stats["completed_jobs"] += 1
                    elif status == JobStatus.FAILED:
                        self._stats["failed_jobs"] += 1
                    elif status == JobStatus.CANCELLED:
                        self._stats["cancelled_jobs"] += 1
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                self._stats["cancelled_jobs"] += 1
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            pending_count = sum(1 for job in self._jobs.values() if job.status == JobStatus.PENDING)
            running_count = sum(1 for job in self._jobs.values() if job.status == JobStatus.RUNNING)
            
            return {
                **self._stats,
                "queue_size": len(self._jobs),
                "pending_jobs": pending_count,
                "running_jobs": running_count,
                "max_size": self.max_size
            }
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        with self._lock:
            jobs_to_remove = []
            for job_id, job in self._jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] 
                    and job.completed_at and job.completed_at < cutoff_time):
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self._jobs[job_id]


class RedisJobQueue:
    """Redis-based distributed job queue."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 queue_name: str = "zomoto_jobs"):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._redis = None
        self._stats_key = f"{queue_name}:stats"
    
    async def connect(self):
        """Connect to Redis."""
        self._redis = await redis.from_url(self.redis_url)
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
    
    async def enqueue(self, job: Job) -> bool:
        """Add a job to the Redis queue."""
        if not self._redis:
            await self.connect()
        
        # Store job data
        job_data = json.dumps(asdict(job), default=str)
        await self._redis.hset(f"{self.queue_name}:jobs", job.id, job_data)
        
        # Add to priority queue
        score = f"{job.priority.value:01d}{int(job.created_at.timestamp())}"
        await self._redis.zadd(self.queue_name, {job.id: score})
        
        # Update stats
        await self._redis.hincrby(self._stats_key, "total_jobs", 1)
        
        return True
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[Job]:
        """Get the next job from the Redis queue."""
        if not self._redis:
            await self.connect()
        
        # Use BZPOPMIN for blocking dequeue with priority
        result = await self._redis.bzpopmin(self.queue_name, timeout=timeout)
        
        if result:
            job_id, score = result
            job_data = await self._redis.hget(f"{self.queue_name}:jobs", job_id)
            
            if job_data:
                job_dict = json.loads(job_data)
                job = Job(**job_dict)
                
                # Update status to running
                await self.update_job_status(job_id, JobStatus.RUNNING)
                
                return job
        
        return None
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        if not self._redis:
            await self.connect()
        
        job_data = await self._redis.hget(f"{self.queue_name}:jobs", job_id)
        if job_data:
            job_dict = json.loads(job_data)
            return Job(**job_dict)
        
        return None
    
    async def update_job_status(self, job_id: str, status: JobStatus, 
                               result: Any = None, error: str = None):
        """Update job status."""
        if not self._redis:
            await self.connect()
        
        job = await self.get_job(job_id)
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            
            if status == JobStatus.RUNNING:
                job.started_at = datetime.now(timezone.utc)
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.now(timezone.utc)
                
                # Update stats
                if status == JobStatus.COMPLETED:
                    await self._redis.hincrby(self._stats_key, "completed_jobs", 1)
                elif status == JobStatus.FAILED:
                    await self._redis.hincrby(self._stats_key, "failed_jobs", 1)
                elif status == JobStatus.CANCELLED:
                    await self._redis.hincrby(self._stats_key, "cancelled_jobs", 1)
            
            # Save updated job
            job_data = json.dumps(asdict(job), default=str)
            await self._redis.hset(f"{self.queue_name}:jobs", job_id, job_data)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self._redis:
            await self.connect()
        
        # Get basic stats
        stats = await self._redis.hgetall(self._stats_key)
        stats = {k.decode(): int(v) for k, v in stats.items()}
        
        # Get current queue size
        queue_size = await self._redis.zcard(self.queue_name)
        
        # Count jobs by status
        all_jobs = await self._redis.hgetall(f"{self.queue_name}:jobs")
        pending = running = 0
        
        for job_data in all_jobs.values():
            job_dict = json.loads(job_data)
            if job_dict["status"] == JobStatus.PENDING.value:
                pending += 1
            elif job_dict["status"] == JobStatus.RUNNING.value:
                running += 1
        
        return {
            **stats,
            "queue_size": queue_size,
            "pending_jobs": pending,
            "running_jobs": running
        }


class LLMJobProcessor:
    """Processor for LLM jobs."""
    
    def __init__(self, queue: Union[JobQueue, RedisJobQueue], 
                 max_workers: int = 3, timeout: float = 30.0):
        self.queue = queue
        self.max_workers = max_workers
        self.timeout = timeout
        self.llm_client = GroqLLMClient()
        self._workers = []
        self._running = False
    
    async def start(self):
        """Start the job processor."""
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
    
    async def stop(self):
        """Stop the job processor."""
        self._running = False
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Close Redis connection if needed
        if isinstance(self.queue, RedisJobQueue):
            await self.queue.disconnect()
    
    async def _worker(self, worker_id: str):
        """Worker task that processes jobs."""
        while self._running:
            try:
                # Get next job
                if isinstance(self.queue, RedisJobQueue):
                    job = await self.queue.dequeue(timeout=1.0)
                else:
                    job = self.queue.dequeue(timeout=1.0)
                    # Convert synchronous call to async
                    if job:
                        await asyncio.sleep(0)  # Yield control
                
                if not job:
                    continue
                
                # Process job with timeout
                try:
                    await asyncio.wait_for(
                        self._process_job(job), 
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    await self._handle_job_error(job, "Job timed out")
                except Exception as e:
                    await self._handle_job_error(job, str(e))
                
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
    
    async def _process_job(self, job: Job):
        """Process a single job."""
        if job.job_type == "llm_ranking":
            await self._process_llm_job(job)
        else:
            await self._handle_job_error(job, f"Unknown job type: {job.job_type}")
    
    async def _process_llm_job(self, job: Job):
        """Process LLM ranking job."""
        try:
            # Parse LLM job
            llm_job = LLMJob.from_dict(job.payload)
            
            # Process with LLM client
            result = self.llm_client.rank_and_explain(llm_job.candidate_set)
            
            # Update job with result
            await self._update_job_result(job, result)
            
        except Exception as e:
            await self._handle_job_error(job, str(e))
    
    async def _update_job_result(self, job: Job, result: RecommendationResult):
        """Update job with successful result."""
        if isinstance(self.queue, RedisJobQueue):
            await self.queue.update_job_status(job.id, JobStatus.COMPLETED, result=result)
        else:
            self.queue.update_job_status(job.id, JobStatus.COMPLETED, result=result)
    
    async def _handle_job_error(self, job: Job, error_message: str):
        """Handle job processing error."""
        job.retry_count += 1
        
        if job.retry_count <= job.max_retries:
            # Retry the job
            if isinstance(self.queue, RedisJobQueue):
                await self.queue.update_job_status(job.id, JobStatus.PENDING, error=error_message)
                # Re-queue with lower priority
                await self.queue.enqueue(job)
            else:
                self.queue.update_job_status(job.id, JobStatus.PENDING, error=error_message)
                self.queue.enqueue(job)
        else:
            # Mark as failed
            if isinstance(self.queue, RedisJobQueue):
                await self.queue.update_job_status(job.id, JobStatus.FAILED, error=error_message)
            else:
                self.queue.update_job_status(job.id, JobStatus.FAILED, error=error_message)
    
    async def submit_llm_job(self, candidate_set: CandidateSet, 
                           priority: JobPriority = JobPriority.NORMAL) -> str:
        """Submit an LLM ranking job."""
        job_id = str(uuid.uuid4())
        
        llm_job = LLMJob(job_id=job_id, candidate_set=candidate_set)
        
        job = Job(
            id=job_id,
            job_type="llm_ranking",
            payload=llm_job.to_dict(),
            priority=priority
        )
        
        if isinstance(self.queue, RedisJobQueue):
            await self.queue.enqueue(job)
        else:
            self.queue.enqueue(job)
        
        return job_id
    
    async def get_job_result(self, job_id: str, timeout: float = 60.0) -> Optional[RecommendationResult]:
        """Get job result, waiting if necessary."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if isinstance(self.queue, RedisJobQueue):
                job = await self.queue.get_job(job_id)
            else:
                job = self.queue.get_job(job_id)
            
            if not job:
                return None
            
            if job.status == JobStatus.COMPLETED:
                return job.result
            elif job.status == JobStatus.FAILED:
                raise Exception(f"Job failed: {job.error}")
            elif job.status == JobStatus.CANCELLED:
                raise Exception("Job was cancelled")
            
            # Wait before checking again
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        if isinstance(self.queue, RedisJobQueue):
            # Remove from queue and update status
            await self.queue._redis.zrem(self.queue.queue_name, job_id)
            await self.queue.update_job_status(job_id, JobStatus.CANCELLED)
            return True
        else:
            return self.queue.cancel_job(job_id)
    
    async def get_processor_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        queue_stats = {}
        if isinstance(self.queue, RedisJobQueue):
            queue_stats = await self.queue.get_stats()
        else:
            queue_stats = self.queue.get_stats()
        
        return {
            "workers": self.max_workers,
            "running": self._running,
            "queue_stats": queue_stats
        }


# Global instances
default_job_queue = JobQueue()
default_processor = LLMJobProcessor(default_job_queue)


def get_job_queue() -> JobQueue:
    """Get default job queue instance."""
    return default_job_queue


def get_job_processor() -> LLMJobProcessor:
    """Get default job processor instance."""
    return default_processor


async def submit_llm_ranking_job(candidate_set: CandidateSet, 
                                priority: JobPriority = JobPriority.NORMAL) -> str:
    """Submit LLM ranking job to default processor."""
    return await default_processor.submit_llm_job(candidate_set, priority)


async def get_llm_ranking_result(job_id: str, timeout: float = 60.0) -> RecommendationResult:
    """Get LLM ranking result from default processor."""
    return await default_processor.get_job_result(job_id, timeout)


if __name__ == "__main__":
    # Example usage
    async def main():
        # Create and start processor
        processor = LLMJobProcessor(JobQueue(), max_workers=2)
        await processor.start()
        
        try:
            # Submit a test job
            from zomoto_ai.phase0.domain.models import UserPreference, Restaurant
            
            # Create test candidate set
            candidate_set = CandidateSet(
                user_preference=UserPreference(location="Bangalore", min_rating=4.0),
                candidates=[
                    Restaurant(
                        id="1",
                        name="Test Restaurant",
                        location="Bangalore",
                        cuisines=["Italian"],
                        cost_for_two=800,
                        rating=4.2,
                        votes=150
                    )
                ]
            )
            
            job_id = await processor.submit_llm_job(candidate_set)
            print(f"Submitted job: {job_id}")
            
            # Wait for result
            try:
                result = await processor.get_job_result(job_id, timeout=30)
                print(f"Job completed: {result.summary}")
            except Exception as e:
                print(f"Job failed: {e}")
            
            # Print stats
            stats = await processor.get_processor_stats()
            print(f"Processor stats: {json.dumps(stats, indent=2, default=str)}")
            
        finally:
            await processor.stop()
    
    asyncio.run(main())
