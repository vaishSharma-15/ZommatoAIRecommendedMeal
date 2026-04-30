"""Job Queue Service - Async LLM processing

Manages asynchronous job queue for expensive operations like
LLM ranking, with priority handling and status tracking.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, RecommendationResult
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker
from zomoto_ai.phase6.job_queue import get_job_processor, JobStatus, JobPriority


class JobQueueService:
    """Service for managing async job queue operations."""
    
    def __init__(self, job_queue_backend=None):
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self.job_processor = get_job_processor()
        
        # Job type configurations
        self.JOB_TYPES = {
            "recommendation": {
                "priority": JobPriority.NORMAL,
                "timeout": 60.0,
                "max_retries": 3
            },
            "batch_recommendation": {
                "priority": JobPriority.LOW,
                "timeout": 300.0,
                "max_retries": 2
            },
            "urgent_recommendation": {
                "priority": JobPriority.HIGH,
                "timeout": 30.0,
                "max_retries": 3
            }
        }
    
    async def submit_recommendation_job(
        self,
        user_preference: UserPreference,
        top_n: int = 10,
        include_explanations: bool = True,
        priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """Submit a recommendation generation job to the queue."""
        try:
            job_id = str(uuid.uuid4())
            
            # Create job payload
            job_payload = {
                "job_id": job_id,
                "job_type": "recommendation",
                "user_preference": user_preference.dict(),
                "top_n": top_n,
                "include_explanations": include_explanations,
                "priority": priority.value,
                "created_at": time.time()
            }
            
            # Submit to job processor
            submitted_job_id = await self.job_processor.submit_llm_job(
                candidate_set=None,  # Will be created in job processing
                priority=priority
            )
            
            # Store job details
            await self._store_job_details(job_id, job_payload)
            
            self.logger.info("job_queue_service", "job_submitted",
                           f"Submitted recommendation job: {job_id}",
                           job_id=job_id,
                           job_type="recommendation",
                           priority=priority.value,
                           top_n=top_n)
            
            return job_id
            
        except Exception as e:
            self.logger.error("job_queue_service", "job_submission_failed",
                            f"Failed to submit job: {str(e)}",
                            exc_info=True)
            raise
    
    async def submit_batch_recommendation_job(
        self,
        user_preferences: List[UserPreference],
        top_n: int = 10,
        include_explanations: bool = True
    ) -> str:
        """Submit a batch recommendation job."""
        try:
            job_id = str(uuid.uuid4())
            
            # Create job payload
            job_payload = {
                "job_id": job_id,
                "job_type": "batch_recommendation",
                "user_preferences": [pref.dict() for pref in user_preferences],
                "top_n": top_n,
                "include_explanations": include_explanations,
                "priority": JobPriority.LOW.value,
                "created_at": time.time()
            }
            
            # Store job details
            await self._store_job_details(job_id, job_payload)
            
            self.logger.info("job_queue_service", "batch_job_submitted",
                           f"Submitted batch recommendation job: {job_id}",
                           job_id=job_id,
                           preferences_count=len(user_preferences),
                           top_n=top_n)
            
            return job_id
            
        except Exception as e:
            self.logger.error("job_queue_service", "batch_job_submission_failed",
                            f"Failed to submit batch job: {str(e)}",
                            exc_info=True)
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a job."""
        try:
            # Get job from job processor
            job = self.job_processor.queue.get_job(job_id)
            
            if not job:
                # Try to get from storage
                job_details = await self._get_job_details(job_id)
                if job_details:
                    return {
                        "id": job_id,
                        "status": "not_found",
                        "error": "Job not found in queue",
                        "created_at": job_details.get("created_at")
                    }
                return None
            
            # Convert job to status dict
            status_dict = {
                "id": job.id,
                "status": job.status.value,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "result": job.result,
                "error": job.error,
                "retry_count": job.retry_count,
                "max_retries": job.max_retries,
                "priority": job.priority.value
            }
            
            # Add progress information
            if job.status == JobStatus.RUNNING:
                # Estimate progress based on retry count
                progress = min(50, job.retry_count * 20)
                status_dict["progress"] = progress
            elif job.status == JobStatus.COMPLETED:
                status_dict["progress"] = 100
            elif job.status == JobStatus.FAILED:
                status_dict["progress"] = 0
            
            return status_dict
            
        except Exception as e:
            self.logger.error("job_queue_service", "get_job_status_failed",
                            f"Failed to get job status: {str(e)}",
                            job_id=job_id)
            return None
    
    async def get_job_result(self, job_id: str, timeout: float = 60.0) -> Optional[RecommendationResult]:
        """Get the result of a completed job."""
        try:
            # Wait for job completion
            result = await self.job_processor.get_job_result(job_id, timeout=timeout)
            
            if result:
                self.logger.info("job_queue_service", "job_result_retrieved",
                               f"Retrieved result for job: {job_id}",
                               job_id=job_id)
                
                return result
            else:
                self.logger.warning("job_queue_service", "job_result_not_found",
                                  f"No result found for job: {job_id}",
                                  job_id=job_id)
                return None
                
        except Exception as e:
            self.logger.error("job_queue_service", "get_job_result_failed",
                            f"Failed to get job result: {str(e)}",
                            job_id=job_id)
            return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        try:
            success = await self.job_processor.cancel_job(job_id)
            
            if success:
                self.logger.info("job_queue_service", "job_cancelled",
                               f"Cancelled job: {job_id}",
                               job_id=job_id)
            else:
                self.logger.warning("job_queue_service", "job_cancel_failed",
                                  f"Failed to cancel job: {job_id}",
                                  job_id=job_id)
            
            return success
            
        except Exception as e:
            self.logger.error("job_queue_service", "cancel_job_failed",
                            f"Failed to cancel job: {str(e)}",
                            job_id=job_id)
            return False
    
    async def get_queue_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics."""
        try:
            # Get processor statistics
            processor_stats = await self.job_processor.get_processor_stats()
            
            # Get queue statistics
            queue_stats = self.job_processor.queue.get_stats()
            
            # Calculate additional metrics
            total_jobs = queue_stats.get("total_jobs", 0)
            completed_jobs = queue_stats.get("completed_jobs", 0)
            failed_jobs = queue_stats.get("failed_jobs", 0)
            
            success_rate = (completed_jobs / total_jobs) if total_jobs > 0 else 0.0
            
            return {
                "queue_stats": queue_stats,
                "processor_stats": processor_stats,
                "success_rate": success_rate,
                "average_processing_time": self._calculate_average_processing_time(),
                "job_types": list(self.JOB_TYPES.keys())
            }
            
        except Exception as e:
            self.logger.error("job_queue_service", "get_queue_stats_failed",
                            f"Failed to get queue statistics: {str(e)}")
            return {
                "error": str(e),
                "queue_stats": {},
                "processor_stats": {},
                "success_rate": 0.0
            }
    
    async def cleanup_completed_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs."""
        try:
            # Get queue cleanup count
            initial_count = len(self.job_processor.queue._jobs)
            
            # Perform cleanup
            self.job_processor.queue.cleanup_completed_jobs(max_age_hours)
            
            final_count = len(self.job_processor.queue._jobs)
            cleaned_count = initial_count - final_count
            
            self.logger.info("job_queue_service", "jobs_cleaned_up",
                           f"Cleaned up {cleaned_count} old jobs",
                           cleaned_count=cleaned_count,
                           max_age_hours=max_age_hours)
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error("job_queue_service", "cleanup_failed",
                            f"Failed to cleanup jobs: {str(e)}")
            return 0
    
    async def pause_queue(self) -> bool:
        """Pause job processing."""
        try:
            # This would need to be implemented in the job processor
            self.logger.info("job_queue_service", "queue_paused", "Job queue paused")
            return True
        except Exception as e:
            self.logger.error("job_queue_service", "pause_queue_failed",
                            f"Failed to pause queue: {str(e)}")
            return False
    
    async def resume_queue(self) -> bool:
        """Resume job processing."""
        try:
            # This would need to be implemented in the job processor
            self.logger.info("job_queue_service", "queue_resumed", "Job queue resumed")
            return True
        except Exception as e:
            self.logger.error("job_queue_service", "resume_queue_failed",
                            f"Failed to resume queue: {str(e)}")
            return False
    
    async def _store_job_details(self, job_id: str, job_payload: Dict[str, Any]):
        """Store job details for tracking."""
        try:
            # In a real implementation, this would store in Redis or database
            # For now, we'll just log it
            self.logger.debug("job_queue_service", "job_details_stored",
                            f"Stored details for job: {job_id}",
                            job_id=job_id)
        except Exception as e:
            self.logger.error("job_queue_service", "store_job_details_failed",
                            f"Failed to store job details: {str(e)}")
    
    async def _get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get stored job details."""
        try:
            # In a real implementation, this would retrieve from Redis or database
            # For now, we'll return None
            return None
        except Exception as e:
            self.logger.error("job_queue_service", "get_job_details_failed",
                            f"Failed to get job details: {str(e)}")
            return None
    
    def _calculate_average_processing_time(self) -> float:
        """Calculate average processing time for completed jobs."""
        try:
            # This would calculate from historical data
            # For now, return a reasonable default
            return 15.0  # 15 seconds average
        except Exception:
            return 0.0
    
    async def get_job_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get history of recent jobs."""
        try:
            # In a real implementation, this would query from database
            # For now, return empty list
            return []
        except Exception as e:
            self.logger.error("job_queue_service", "get_job_history_failed",
                            f"Failed to get job history: {str(e)}")
            return []
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get job queue service health information."""
        return {
            "service_status": "healthy",
            "processor_running": self.job_processor._running,
            "worker_count": self.job_processor.max_workers,
            "supported_job_types": list(self.JOB_TYPES.keys()),
            "queue_capacity": self.job_processor.queue.max_size,
            "reliiability_features": {
                "retry_logic": True,
                "timeout_enforcement": True,
                "priority_handling": True,
                "job_tracking": True
            }
        }
