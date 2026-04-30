"""Structured Logging and Observability for Phase 6

Provides comprehensive logging, metrics collection, and observability
for the restaurant recommendation system.
"""

import json
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from pathlib import Path
import traceback
from contextlib import contextmanager


@dataclass
class LogEvent:
    """Structured log event."""
    timestamp: datetime
    level: str
    service: str
    component: str
    action: str
    message: str
    metadata: Dict[str, Any]
    trace_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class MetricPoint:
    """Metric data point."""
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str]


@dataclass
class PerformanceMetrics:
    """Performance tracking metrics."""
    request_count: int = 0
    error_count: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    llm_calls: int = 0
    llm_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


class StructuredLogger:
    """Structured logger with JSON formatting and correlation IDs."""
    
    def __init__(self, service_name: str = "zomoto-ai", log_level: str = "INFO"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Configure JSON formatter
        handler = logging.StreamHandler()
        formatter = JsonFormatter()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Thread-local storage for trace context
        self._local = threading.local()
    
    def _get_trace_id(self) -> Optional[str]:
        """Get current trace ID from thread-local storage."""
        return getattr(self._local, 'trace_id', None)
    
    def _get_user_id(self) -> Optional[str]:
        """Get current user ID from thread-local storage."""
        return getattr(self._local, 'user_id', None)
    
    def set_trace_context(self, trace_id: str, user_id: Optional[str] = None):
        """Set trace context for current thread."""
        self._local.trace_id = trace_id
        self._local.user_id = user_id
    
    def clear_trace_context(self):
        """Clear trace context for current thread."""
        self._local.trace_id = None
        self._local.user_id = None
    
    def _log(self, level: str, component: str, action: str, message: str, **metadata):
        """Internal logging method."""
        event = LogEvent(
            timestamp=datetime.now(timezone.utc),
            level=level,
            service=self.service_name,
            component=component,
            action=action,
            message=message,
            metadata=metadata,
            trace_id=self._get_trace_id(),
            user_id=self._get_user_id()
        )
        
        getattr(self.logger, level.lower())(json.dumps(asdict(event), default=str))
    
    def info(self, component: str, action: str, message: str, **metadata):
        """Log info level event."""
        self._log("INFO", component, action, message, **metadata)
    
    def warning(self, component: str, action: str, message: str, **metadata):
        """Log warning level event."""
        self._log("WARNING", component, action, message, **metadata)
    
    def error(self, component: str, action: str, message: str, **metadata):
        """Log error level event."""
        self._log("ERROR", component, action, message, **metadata)
    
    def debug(self, component: str, action: str, message: str, **metadata):
        """Log debug level event."""
        self._log("DEBUG", component, action, message, **metadata)
    
    def log_request_start(self, component: str, request_id: str, **metadata):
        """Log request start."""
        self.info(component, "request_start", f"Request {request_id} started", 
                 request_id=request_id, **metadata)
    
    def log_request_end(self, component: str, request_id: str, duration: float, **metadata):
        """Log request completion."""
        self.info(component, "request_end", f"Request {request_id} completed",
                 request_id=request_id, duration_ms=duration*1000, **metadata)
    
    def log_llm_call(self, component: str, model: str, prompt_tokens: int, 
                    response_tokens: int, duration: float, success: bool, **metadata):
        """Log LLM API call."""
        self.info(component, "llm_call", f"LLM call to {model}",
                 model=model, prompt_tokens=prompt_tokens, response_tokens=response_tokens,
                 duration_ms=duration*1000, success=success, **metadata)
    
    def log_cache_operation(self, component: str, operation: str, cache_key: str, 
                          hit: bool, **metadata):
        """Log cache operation."""
        self.info(component, "cache_operation", f"Cache {operation}: {cache_key}",
                 operation=operation, cache_key=cache_key, hit=hit, **metadata)
    
    def log_error_with_traceback(self, component: str, action: str, message: str, 
                               exception: Exception, **metadata):
        """Log error with full traceback."""
        self.error(component, action, message,
                  error_type=type(exception).__name__,
                  error_message=str(exception),
                  traceback=traceback.format_exc(),
                  **metadata)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        if isinstance(record.msg, str):
            try:
                # Try to parse as JSON event
                log_data = json.loads(record.msg)
                return json.dumps(log_data, default=str)
            except json.JSONDecodeError:
                # Fall back to standard formatting
                log_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "message": record.msg,
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                return json.dumps(log_data, default=str)
        return super().format(record)


class ObservabilityMetrics:
    """Metrics collection and aggregation for observability."""
    
    def __init__(self, retention_minutes: int = 60):
        self.retention_minutes = retention_minutes
        self.metrics = defaultdict(lambda: deque(maxlen=1000))
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(lambda: defaultdict(int))
        self._lock = threading.RLock()
    
    def record_metric(self, metric_name: str, value: float, unit: str = "", **tags):
        """Record a metric point."""
        with self._lock:
            point = MetricPoint(
                timestamp=datetime.now(timezone.utc),
                metric_name=metric_name,
                value=value,
                unit=unit,
                tags=tags
            )
            self.metrics[metric_name].append(point)
            
            # Update counters and gauges
            if unit == "count":
                self.counters[metric_name] += int(value)
            elif unit == "gauge":
                self.gauges[metric_name] = value
    
    def increment_counter(self, metric_name: str, value: int = 1, **tags):
        """Increment a counter metric."""
        self.record_metric(metric_name, value, "count", **tags)
    
    def set_gauge(self, metric_name: str, value: float, **tags):
        """Set a gauge metric."""
        self.record_metric(metric_name, value, "gauge", **tags)
    
    def record_histogram(self, metric_name: str, value: float, **tags):
        """Record histogram metric."""
        with self._lock:
            # Create bucket key from tags
            bucket_key = f"{metric_name}:{hash(frozenset(tags.items()))}"
            self.histograms[bucket_key][metric_name] = value
            self.record_metric(metric_name, value, "histogram", **tags)
    
    def get_metric_summary(self, metric_name: str, minutes: int = 5) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            recent_points = [
                point for point in self.metrics[metric_name]
                if point.timestamp >= cutoff_time
            ]
            
            if not recent_points:
                return {"count": 0, "min": 0, "max": 0, "avg": 0, "sum": 0}
            
            values = [point.value for point in recent_points]
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "sum": sum(values),
                "latest": recent_points[-1].value,
                "unit": recent_points[-1].unit
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "metric_summaries": {
                    name: self.get_metric_summary(name)
                    for name in self.metrics.keys()
                }
            }
    
    def cleanup_old_metrics(self):
        """Clean up metrics older than retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.retention_minutes)
        
        with self._lock:
            for metric_name, points in self.metrics.items():
                # Filter old points
                self.metrics[metric_name] = deque(
                    [point for point in points if point.timestamp >= cutoff_time],
                    maxlen=1000
                )


class PerformanceTracker:
    """Track performance metrics for operations."""
    
    def __init__(self, metrics: ObservabilityMetrics, logger: StructuredLogger):
        self.metrics = metrics
        self.logger = logger
        self.performance_data = defaultdict(PerformanceMetrics)
        self._lock = threading.Lock()
    
    @contextmanager
    def track_request(self, component: str, operation: str, **metadata):
        """Context manager for tracking request performance."""
        start_time = time.time()
        request_id = metadata.get("request_id", f"req_{int(start_time * 1000)}")
        
        self.logger.log_request_start(component, request_id, **metadata)
        
        try:
            with self._lock:
                self.performance_data[component].request_count += 1
            
            yield
            
            duration = time.time() - start_time
            self.metrics.record_histogram(f"{component}_request_duration", duration, 
                                        component=component, operation=operation)
            
            with self._lock:
                perf = self.performance_data[component]
                perf.total_response_time += duration
                perf.min_response_time = min(perf.min_response_time, duration)
                perf.max_response_time = max(perf.max_response_time, duration)
            
            self.logger.log_request_end(component, request_id, duration, **metadata)
            
        except Exception as e:
            duration = time.time() - start_time
            with self._lock:
                self.performance_data[component].error_count += 1
            
            self.metrics.increment_counter(f"{component}_errors", 
                                        component=component, operation=operation)
            self.logger.log_error_with_traceback(component, operation, 
                                               f"Request {request_id} failed", e, 
                                               duration_ms=duration*1000, **metadata)
            raise
    
    @contextmanager
    def track_llm_call(self, component: str, model: str, **metadata):
        """Context manager for tracking LLM calls."""
        start_time = time.time()
        
        try:
            yield
            
            duration = time.time() - start_time
            self.metrics.record_histogram("llm_duration", duration, model=model)
            
            with self._lock:
                self.performance_data[component].llm_calls += 1
            
            self.logger.log_llm_call(component, model, 0, 0, duration, True, **metadata)
            
        except Exception as e:
            duration = time.time() - start_time
            with self._lock:
                self.performance_data[component].llm_errors += 1
            
            self.metrics.increment_counter("llm_errors", model=model)
            self.logger.log_llm_call(component, model, 0, 0, duration, False, **metadata)
            raise
    
    def record_cache_hit(self, component: str, cache_key: str):
        """Record cache hit."""
        self.metrics.increment_counter("cache_hits", component=component)
        with self._lock:
            self.performance_data[component].cache_hits += 1
        self.logger.log_cache_operation(component, "get", cache_key, True)
    
    def record_cache_miss(self, component: str, cache_key: str):
        """Record cache miss."""
        self.metrics.increment_counter("cache_misses", component=component)
        with self._lock:
            self.performance_data[component].cache_misses += 1
        self.logger.log_cache_operation(component, "get", cache_key, False)
    
    def get_performance_summary(self, component: str) -> Dict[str, Any]:
        """Get performance summary for a component."""
        with self._lock:
            perf = self.performance_data[component]
            
            if perf.request_count == 0:
                return {"error": "No requests recorded"}
            
            avg_response_time = perf.total_response_time / perf.request_count
            error_rate = perf.error_count / perf.request_count
            
            cache_total = perf.cache_hits + perf.cache_misses
            cache_hit_rate = perf.cache_hits / cache_total if cache_total > 0 else 0
            
            return {
                "request_count": perf.request_count,
                "error_count": perf.error_count,
                "error_rate": error_rate,
                "avg_response_time_ms": avg_response_time * 1000,
                "min_response_time_ms": perf.min_response_time * 1000,
                "max_response_time_ms": perf.max_response_time * 1000,
                "llm_calls": perf.llm_calls,
                "llm_errors": perf.llm_errors,
                "cache_hit_rate": cache_hit_rate,
                "cache_hits": perf.cache_hits,
                "cache_misses": perf.cache_misses
            }


# Global instances
structured_logger = StructuredLogger()
observability_metrics = ObservabilityMetrics()
performance_tracker = PerformanceTracker(observability_metrics, structured_logger)


def get_logger() -> StructuredLogger:
    """Get global structured logger instance."""
    return structured_logger


def get_metrics() -> ObservabilityMetrics:
    """Get global observability metrics instance."""
    return observability_metrics


def get_performance_tracker() -> PerformanceTracker:
    """Get global performance tracker instance."""
    return performance_tracker


# Decorator for automatic performance tracking
def track_performance(component: str, operation: str):
    """Decorator for automatic performance tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with performance_tracker.track_request(component, operation):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Context manager for trace context
def trace_context(trace_id: str, user_id: Optional[str] = None):
    """Context manager for setting trace context."""
    return TraceContext(trace_id, user_id)


class TraceContext:
    """Context manager for trace context."""
    
    def __init__(self, trace_id: str, user_id: Optional[str] = None):
        self.trace_id = trace_id
        self.user_id = user_id
    
    def __enter__(self):
        structured_logger.set_trace_context(self.trace_id, self.user_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        structured_logger.clear_trace_context()


if __name__ == "__main__":
    # Example usage
    logger = get_logger()
    metrics = get_metrics()
    tracker = get_performance_tracker()
    
    # Test structured logging
    with trace_context("test-trace-123", "user-456"):
        logger.info("test_component", "test_action", "Test message", 
                   extra_data="test_value")
    
    # Test performance tracking
    with tracker.track_request("test_component", "test_operation"):
        time.sleep(0.1)  # Simulate work
    
    # Test metrics
    metrics.increment_counter("test_counter", 1, test_tag="test_value")
    metrics.set_gauge("test_gauge", 42.0)
    
    # Print results
    print("Metrics:", json.dumps(metrics.get_all_metrics(), indent=2, default=str))
    print("Performance:", json.dumps(tracker.get_performance_summary("test_component"), indent=2, default=str))
