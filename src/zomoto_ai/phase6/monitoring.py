"""Monitoring and Alerting System for Phase 6

Provides comprehensive monitoring, alerting, and health checks
for the restaurant recommendation system.
"""

import asyncio
import json
import time
import smtplib
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import requests
from pathlib import Path

from .logging import get_logger, get_metrics, get_performance_tracker


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class Alert:
    """Alert definition."""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_func: Callable[[], bool]
    timeout: float = 30.0
    critical: bool = True
    last_check: Optional[datetime] = None
    last_status: Optional[bool] = None
    failure_count: int = 0


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    check_interval: int = 60  # seconds
    alert_retention_hours: int = 24
    health_check_timeout: float = 30.0
    
    # Email alert settings
    smtp_enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: List[str] = None
    
    # Webhook alert settings
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_timeout: float = 10.0
    
    # Thresholds
    error_rate_threshold: float = 0.05  # 5%
    response_time_threshold: float = 5.0  # seconds
    llm_error_rate_threshold: float = 0.1  # 10%
    cache_hit_rate_threshold: float = 0.8  # 80%


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = get_logger()
        self.alerts: List[Alert] = []
        self.alert_rules: List[Callable[[], Optional[Alert]]] = []
        self._lock = threading.Lock()
    
    def add_alert_rule(self, rule_func: Callable[[], Optional[Alert]]):
        """Add an alert rule function."""
        self.alert_rules.append(rule_func)
    
    def check_alerts(self) -> List[Alert]:
        """Check all alert rules and return new alerts."""
        new_alerts = []
        
        for rule_func in self.alert_rules:
            try:
                alert = rule_func()
                if alert:
                    new_alerts.append(alert)
                    self._send_alert(alert)
            except Exception as e:
                self.logger.error("alert_manager", "rule_check_failed",
                                f"Alert rule check failed: {e}")
        
        # Store alerts
        with self._lock:
            self.alerts.extend(new_alerts)
            self._cleanup_old_alerts()
        
        return new_alerts
    
    def _send_alert(self, alert: Alert):
        """Send alert through configured channels."""
        self.logger.warning("alert_manager", "alert_triggered",
                          f"Alert triggered: {alert.name} - {alert.message}")
        
        # Send email if enabled
        if self.config.smtp_enabled:
            self._send_email_alert(alert)
        
        # Send webhook if enabled
        if self.config.webhook_enabled:
            self._send_webhook_alert(alert)
    
    def _send_email_alert(self, alert: Alert):
        """Send alert via email."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.smtp_from
            msg['To'] = ', '.join(self.config.smtp_to)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"
            
            body = f"""
Alert: {alert.name}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
Timestamp: {alert.timestamp.isoformat()}
Source: {alert.source}

Metadata:
{json.dumps(alert.metadata, indent=2)}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.starttls()
            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info("alert_manager", "email_sent",
                           f"Email alert sent for {alert.name}")
            
        except Exception as e:
            self.logger.error("alert_manager", "email_failed",
                            f"Failed to send email alert: {e}")
    
    def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook."""
        try:
            payload = {
                "alert_id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source,
                "metadata": alert.metadata
            }
            
            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=self.config.webhook_timeout
            )
            response.raise_for_status()
            
            self.logger.info("alert_manager", "webhook_sent",
                           f"Webhook alert sent for {alert.name}")
            
        except Exception as e:
            self.logger.error("alert_manager", "webhook_failed",
                            f"Failed to send webhook alert: {e}")
    
    def _cleanup_old_alerts(self):
        """Clean up old alerts."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.config.alert_retention_hours)
        
        self.alerts = [
            alert for alert in self.alerts
            if alert.timestamp >= cutoff_time
        ]
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active (unresolved) alerts."""
        with self._lock:
            return [alert for alert in self.alerts if not alert.resolved]
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.now(timezone.utc)
                    self.logger.info("alert_manager", "alert_resolved",
                                   f"Alert resolved: {alert.name}")
                    return True
        return False
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            total_alerts = len(self.alerts)
            active_alerts = len([a for a in self.alerts if not a.resolved])
            
            severity_counts = {}
            for severity in AlertSeverity:
                count = len([a for a in self.alerts if a.severity == severity])
                severity_counts[severity.value] = count
            
            return {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "severity_breakdown": severity_counts,
                "alert_rules_count": len(self.alert_rules)
            }


class HealthChecker:
    """Manages health checks for system components."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = get_logger()
        self.health_checks: List[HealthCheck] = []
        self._lock = threading.Lock()
    
    def add_health_check(self, name: str, check_func: Callable[[], bool], 
                        timeout: float = None, critical: bool = True):
        """Add a health check."""
        health_check = HealthCheck(
            name=name,
            check_func=check_func,
            timeout=timeout or self.config.health_check_timeout,
            critical=critical
        )
        
        with self._lock:
            self.health_checks.append(health_check)
    
    def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for check in self.health_checks:
            try:
                start_time = time.time()
                
                # Run check with timeout
                if asyncio.iscoroutinefunction(check.check_func):
                    # Async check
                    result = asyncio.run(
                        asyncio.wait_for(check.check_func(), timeout=check.timeout)
                    )
                else:
                    # Sync check with timeout using threading
                    result = self._run_with_timeout(check.check_func, check.timeout)
                
                duration = time.time() - start_time
                
                # Update check status
                with self._lock:
                    check.last_check = datetime.now(timezone.utc)
                    check.last_status = result
                    
                    if result:
                        check.failure_count = 0
                    else:
                        check.failure_count += 1
                
                results[check.name] = {
                    "status": "healthy" if result else "unhealthy",
                    "duration_ms": duration * 1000,
                    "critical": check.critical,
                    "failure_count": check.failure_count
                }
                
                # Update overall status
                if not result and check.critical:
                    overall_status = HealthStatus.UNHEALTHY
                elif not result and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                
            except Exception as e:
                self.logger.error("health_checker", "check_failed",
                                f"Health check {check.name} failed: {e}")
                
                with self._lock:
                    check.last_check = datetime.now(timezone.utc)
                    check.last_status = False
                    check.failure_count += 1
                
                results[check.name] = {
                    "status": "error",
                    "error": str(e),
                    "critical": check.critical,
                    "failure_count": check.failure_count
                }
                
                if check.critical:
                    overall_status = HealthStatus.UNHEALTHY
        
        return {
            "overall_status": overall_status.value,
            "checks": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _run_with_timeout(self, func: Callable[[], bool], timeout: float) -> bool:
        """Run function with timeout using threading."""
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = func()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            # Thread is still running, timeout occurred
            return False
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health check summary."""
        with self._lock:
            total_checks = len(self.health_checks)
            healthy_checks = sum(1 for check in self.health_checks 
                               if check.last_status is True)
            unhealthy_checks = sum(1 for check in self.health_checks 
                                 if check.last_status is False)
            
            return {
                "total_checks": total_checks,
                "healthy_checks": healthy_checks,
                "unhealthy_checks": unhealthy_checks,
                "health_percentage": (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            }


class MonitoringSystem:
    """Main monitoring system combining health checks and alerts."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = get_logger()
        self.alert_manager = AlertManager(config)
        self.health_checker = HealthChecker(config)
        self.metrics = get_metrics()
        self.performance_tracker = get_performance_tracker()
        
        self._running = False
        self._monitor_thread = None
        
        # Setup default health checks and alert rules
        self._setup_default_monitoring()
    
    def _setup_default_monitoring(self):
        """Setup default health checks and alert rules."""
        
        # Health checks
        self.health_checker.add_health_check(
            "llm_client",
            self._check_llm_client,
            critical=True
        )
        
        self.health_checker.add_health_check(
            "database_connection",
            self._check_database,
            critical=True
        )
        
        self.health_checker.add_health_check(
            "cache_system",
            self._check_cache,
            critical=False
        )
        
        self.health_checker.add_health_check(
            "memory_usage",
            self._check_memory_usage,
            critical=False
        )
        
        # Alert rules
        self.alert_manager.add_alert_rule(self._check_error_rate)
        self.alert_manager.add_alert_rule(self._check_response_time)
        self.alert_manager.add_alert_rule(self._check_llm_error_rate)
        self.alert_manager.add_alert_rule(self._check_cache_hit_rate)
    
    def _check_llm_client(self) -> bool:
        """Check if LLM client is healthy."""
        try:
            # Try to initialize LLM client
            from .reliability import get_reliable_llm_client
            client = get_reliable_llm_client()
            return client._llm_client is not None
        except:
            return False
    
    def _check_database(self) -> bool:
        """Check database connection."""
        try:
            from .database import create_sqlite_backend
            db = create_sqlite_backend(":memory:")
            stats = db.get_statistics()
            return "error" not in stats
        except:
            return False
    
    def _check_cache(self) -> bool:
        """Check cache system."""
        try:
            # Simple cache check - try to get metrics
            metrics = self.metrics.get_all_metrics()
            return True
        except:
            return False
    
    def _check_memory_usage(self) -> bool:
        """Check memory usage."""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            return memory_percent < 90  # Alert if > 90% memory usage
        except:
            return True  # If we can't check, assume healthy
    
    def _check_error_rate(self) -> Optional[Alert]:
        """Check error rate threshold."""
        try:
            perf_summary = self.performance_tracker.get_performance_summary("phase5")
            error_rate = perf_summary.get("error_rate", 0)
            
            if error_rate > self.config.error_rate_threshold:
                return Alert(
                    id=f"error_rate_{int(time.time())}",
                    name="High Error Rate",
                    severity=AlertSeverity.WARNING,
                    message=f"Error rate is {error_rate:.2%}, threshold is {self.config.error_rate_threshold:.2%}",
                    source="monitoring",
                    metadata={"error_rate": error_rate, "threshold": self.config.error_rate_threshold}
                )
        except:
            pass
        return None
    
    def _check_response_time(self) -> Optional[Alert]:
        """Check response time threshold."""
        try:
            metrics_summary = self.metrics.get_metric_summary("phase5_request_duration", 5)
            avg_response_time = metrics_summary.get("avg", 0) / 1000  # Convert ms to seconds
            
            if avg_response_time > self.config.response_time_threshold:
                return Alert(
                    id=f"response_time_{int(time.time())}",
                    name="High Response Time",
                    severity=AlertSeverity.WARNING,
                    message=f"Average response time is {avg_response_time:.2f}s, threshold is {self.config.response_time_threshold}s",
                    source="monitoring",
                    metadata={"avg_response_time": avg_response_time, "threshold": self.config.response_time_threshold}
                )
        except:
            pass
        return None
    
    def _check_llm_error_rate(self) -> Optional[Alert]:
        """Check LLM error rate threshold."""
        try:
            perf_summary = self.performance_tracker.get_performance_summary("phase6")
            llm_calls = perf_summary.get("llm_calls", 0)
            llm_errors = perf_summary.get("llm_errors", 0)
            
            if llm_calls > 0:
                llm_error_rate = llm_errors / llm_calls
                if llm_error_rate > self.config.llm_error_rate_threshold:
                    return Alert(
                        id=f"llm_error_rate_{int(time.time())}",
                        name="High LLM Error Rate",
                        severity=AlertSeverity.ERROR,
                        message=f"LLM error rate is {llm_error_rate:.2%}, threshold is {self.config.llm_error_rate_threshold:.2%}",
                        source="monitoring",
                        metadata={"llm_error_rate": llm_error_rate, "threshold": self.config.llm_error_rate_threshold}
                    )
        except:
            pass
        return None
    
    def _check_cache_hit_rate(self) -> Optional[Alert]:
        """Check cache hit rate threshold."""
        try:
            perf_summary = self.performance_tracker.get_performance_summary("phase6")
            cache_hits = perf_summary.get("cache_hits", 0)
            cache_misses = perf_summary.get("cache_misses", 0)
            
            total_cache_requests = cache_hits + cache_misses
            if total_cache_requests > 0:
                cache_hit_rate = cache_hits / total_cache_requests
                if cache_hit_rate < self.config.cache_hit_rate_threshold:
                    return Alert(
                        id=f"cache_hit_rate_{int(time.time())}",
                        name="Low Cache Hit Rate",
                        severity=AlertSeverity.WARNING,
                        message=f"Cache hit rate is {cache_hit_rate:.2%}, threshold is {self.config.cache_hit_rate_threshold:.2%}",
                        source="monitoring",
                        metadata={"cache_hit_rate": cache_hit_rate, "threshold": self.config.cache_hit_rate_threshold}
                    )
        except:
            pass
        return None
    
    def start(self):
        """Start monitoring system."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        self.logger.info("monitoring_system", "started",
                        "Monitoring system started")
    
    def stop(self):
        """Stop monitoring system."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        self.logger.info("monitoring_system", "stopped",
                        "Monitoring system stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Run health checks
                health_results = self.health_checker.run_health_checks()
                
                # Check for alerts
                new_alerts = self.alert_manager.check_alerts()
                
                # Log health status
                if health_results["overall_status"] != "healthy":
                    self.logger.warning("monitoring_system", "health_check",
                                      f"System health: {health_results['overall_status']}")
                
                # Sleep until next check
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                self.logger.error("monitoring_system", "monitor_loop_error",
                                f"Monitoring loop error: {e}")
                time.sleep(self.config.check_interval)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        health_results = self.health_checker.run_health_checks()
        alert_stats = self.alert_manager.get_alert_stats()
        health_summary = self.health_checker.get_health_summary()
        
        return {
            "status": health_results["overall_status"],
            "health_checks": health_results["checks"],
            "health_summary": health_summary,
            "alerts": alert_stats,
            "metrics": self.metrics.get_all_metrics(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active alerts."""
        return self.alert_manager.get_active_alerts()


# Global monitoring system
default_monitoring_config = MonitoringConfig()
default_monitoring_system = MonitoringSystem(default_monitoring_config)


def get_monitoring_system() -> MonitoringSystem:
    """Get default monitoring system instance."""
    return default_monitoring_system


def start_monitoring():
    """Start the default monitoring system."""
    default_monitoring_system.start()


def stop_monitoring():
    """Stop the default monitoring system."""
    default_monitoring_system.stop()


if __name__ == "__main__":
    # Example usage
    monitoring = MonitoringSystem(MonitoringConfig(
        check_interval=30,
        smtp_enabled=False,
        webhook_enabled=False
    ))
    
    monitoring.start()
    
    try:
        # Get system status
        status = monitoring.get_system_status()
        print("System Status:")
        print(json.dumps(status, indent=2, default=str))
        
        # Keep running for a bit
        time.sleep(60)
        
    finally:
        monitoring.stop()
