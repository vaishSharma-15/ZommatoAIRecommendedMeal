"""Monitoring Service - Health checks and system monitoring

Provides comprehensive health monitoring for all system components
including database, cache, LLM service, and external dependencies.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase6.logging import get_logger
from zomoto_ai.phase6.monitoring import get_monitoring_system, HealthStatus
from ..data import get_database_backend, get_cache_backend


class MonitoringService:
    """Service for system health monitoring and status reporting."""
    
    def __init__(self):
        self.logger = get_logger()
        self.monitoring_system = get_monitoring_system()
        
        # Component health check functions
        self.health_checkers = {
            "database": self._check_database_health,
            "cache": self._check_cache_health,
            "llm_service": self._check_llm_service_health,
            "job_queue": self._check_job_queue_health,
            "api_service": self._check_api_service_health
        }
    
    async def check_all_components(self) -> Dict[str, HealthStatus]:
        """Check health of all system components."""
        results = {}
        
        for component_name, check_function in self.health_checkers.items():
            try:
                status = await check_function()
                results[component_name] = status
            except Exception as e:
                self.logger.error("monitoring_service", "component_check_failed",
                                f"Health check failed for {component_name}: {str(e)}",
                                component=component_name)
                
                results[component_name] = HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error=str(e)
                )
        
        return results
    
    async def check_component_health(self, component_name: str) -> Optional[HealthStatus]:
        """Check health of a specific component."""
        if component_name not in self.health_checkers:
            return None
        
        try:
            return await self.health_checkers[component_name]()
        except Exception as e:
            self.logger.error("monitoring_service", "component_check_failed",
                            f"Health check failed for {component_name}: {str(e)}",
                            component=component_name)
            
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def _check_database_health(self) -> HealthStatus:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            # Get database backend
            db_backend = get_database_backend()
            
            if not db_backend:
                return HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error="Database backend not available"
                )
            
            # Test basic connectivity
            stats = db_backend.get_statistics()
            
            if "error" in stats:
                return HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error=stats["error"]
                )
            
            # Test query performance
            query_start = time.time()
            test_results = db_backend.search_by_preferences(
                location="test",
                cuisine="test",
                min_rating=0.0,
                max_cost_for_two=1000,
                limit=1
            )
            query_time = (time.time() - query_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            if query_time > 1000:  # 1 second
                status = "degraded"
            if query_time > 5000:  # 5 seconds
                status = "unhealthy"
            
            return HealthStatus(
                status=status,
                last_check=time.time(),
                response_time_ms=response_time,
                error=None
            )
            
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def _check_cache_health(self) -> HealthStatus:
        """Check cache connectivity and performance."""
        start_time = time.time()
        
        try:
            # Get cache backend
            cache_backend = get_cache_backend()
            
            if not cache_backend:
                return HealthStatus(
                    status="degraded",  # Cache is optional
                    last_check=time.time(),
                    error="Cache backend not available"
                )
            
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            test_value = "test_value"
            
            # Test set operation
            set_start = time.time()
            set_success = await cache_backend.set(test_key, test_value, ttl=60)
            set_time = (time.time() - set_start) * 1000
            
            if not set_success:
                return HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error="Cache set operation failed"
                )
            
            # Test get operation
            get_start = time.time()
            retrieved_value = await cache_backend.get(test_key)
            get_time = (time.time() - get_start) * 1000
            
            if retrieved_value != test_value:
                return HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error="Cache get operation returned incorrect value"
                )
            
            # Cleanup
            await cache_backend.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            if max(set_time, get_time) > 100:  # 100ms
                status = "degraded"
            if max(set_time, get_time) > 500:  # 500ms
                status = "unhealthy"
            
            return HealthStatus(
                status=status,
                last_check=time.time(),
                response_time_ms=response_time,
                error=None
            )
            
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def _check_llm_service_health(self) -> HealthStatus:
        """Check LLM service availability and performance."""
        start_time = time.time()
        
        try:
            from zomoto_ai.phase6.reliability import get_reliable_llm_client
            
            llm_client = get_reliable_llm_client()
            
            if not llm_client._llm_client:
                return HealthStatus(
                    status="degraded",  # LLM issues are handled by fallback
                    last_check=time.time(),
                    error="LLM client not available"
                )
            
            # Check circuit breaker status
            circuit_state = llm_client.circuit_breaker.state.value
            failure_count = llm_client.circuit_breaker.failure_count
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            if circuit_state == "open":
                status = "unhealthy"
            elif circuit_state == "half_open":
                status = "degraded"
            elif failure_count > 0:
                status = "degraded"
            
            error_msg = None
            if circuit_state == "open":
                error_msg = f"Circuit breaker is open (failures: {failure_count})"
            elif failure_count > 0:
                error_msg = f"Recent failures: {failure_count}"
            
            return HealthStatus(
                status=status,
                last_check=time.time(),
                response_time_ms=response_time,
                error=error_msg
            )
            
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def _check_job_queue_health(self) -> HealthStatus:
        """Check job queue health and performance."""
        start_time = time.time()
        
        try:
            from zomoto_ai.phase6.job_queue import get_job_processor
            
            job_processor = get_job_processor()
            
            # Get queue statistics
            queue_stats = job_processor.queue.get_stats()
            processor_stats = await job_processor.get_processor_stats()
            
            # Check if processor is running
            if not processor_stats.get("running", False):
                return HealthStatus(
                    status="unhealthy",
                    last_check=time.time(),
                    error="Job processor is not running"
                )
            
            # Check queue health
            pending_jobs = queue_stats.get("pending_jobs", 0)
            total_jobs = queue_stats.get("total_jobs", 0)
            error_rate = queue_stats.get("failed_jobs", 0) / max(total_jobs, 1)
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            error_msg = None
            
            if pending_jobs > 1000:  # Too many pending jobs
                status = "degraded"
                error_msg = f"High pending job count: {pending_jobs}"
            
            if error_rate > 0.1:  # >10% error rate
                status = "unhealthy"
                error_msg = f"High error rate: {error_rate:.2%}"
            
            return HealthStatus(
                status=status,
                last_check=time.time(),
                response_time_ms=response_time,
                error=error_msg
            )
            
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def _check_api_service_health(self) -> HealthStatus:
        """Check API service health."""
        start_time = time.time()
        
        try:
            # Check if we can import and create basic services
            from ..services import RecommendationService
            
            # Try to create service instance
            service = RecommendationService()
            
            # Check service stats
            stats = service.get_service_stats()
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            error_msg = None
            
            if stats.get("service_status") != "healthy":
                status = "degraded"
                error_msg = f"Service status: {stats.get('service_status')}"
            
            if stats.get("restaurants_loaded", 0) == 0:
                status = "unhealthy"
                error_msg = "No restaurants loaded"
            
            return HealthStatus(
                status=status,
                last_check=time.time(),
                response_time_ms=response_time,
                error=error_msg
            )
            
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                last_check=time.time(),
                error=str(e)
            )
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        try:
            # Get monitoring system status
            system_status = self.monitoring_system.get_system_status()
            
            # Get component health
            component_health = await self.check_all_components()
            
            # Calculate overall health
            healthy_count = sum(1 for status in component_health.values() if status.status == "healthy")
            total_count = len(component_health)
            health_percentage = (healthy_count / total_count) * 100 if total_count > 0 else 0
            
            # Determine overall status
            overall_status = "healthy"
            if health_percentage < 50:
                overall_status = "unhealthy"
            elif health_percentage < 80:
                overall_status = "degraded"
            
            return {
                "overall_status": overall_status,
                "health_percentage": health_percentage,
                "component_health": {
                    name: {
                        "status": status.status,
                        "last_check": status.last_check,
                        "response_time_ms": status.response_time_ms,
                        "error": status.error
                    }
                    for name, status in component_health.items()
                },
                "system_metrics": system_status.get("metrics", {}),
                "active_alerts": len(self.monitoring_system.get_active_alerts()),
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error("monitoring_service", "get_metrics_failed",
                            f"Failed to get system metrics: {str(e)}")
            return {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def run_health_check_schedule(self, interval_seconds: int = 60):
        """Run periodic health checks."""
        while True:
            try:
                await self.check_all_components()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                self.logger.error("monitoring_service", "health_check_schedule_failed",
                                f"Health check schedule failed: {str(e)}")
                await asyncio.sleep(interval_seconds)
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get monitoring service health information."""
        return {
            "service_status": "healthy",
            "monitored_components": list(self.health_checkers.keys()),
            "monitoring_system_active": True,
            "health_check_interval": 60,  # seconds
            "capabilities": [
                "component_health_checks",
                "system_metrics_collection",
                "alert_integration",
                "performance_monitoring"
            ]
        }
