"""Production Deployment Configuration for Phase 6

Provides production-ready deployment configurations including Docker,
environment management, and operational settings.
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration for production."""
    type: str = "postgresql"  # sqlite, postgresql
    host: str = "localhost"
    port: int = 5432
    database: str = "zomoto_ai"
    username: str = "postgres"
    password: str = ""
    ssl_mode: str = "require"
    pool_size: int = 20
    max_overflow: int = 30
    
    # SQLite specific
    sqlite_path: str = "data/production_restaurants.db"


@dataclass
class RedisConfig:
    """Redis configuration for caching and job queues."""
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    ssl: bool = True
    max_connections: int = 20
    
    # Job queue settings
    job_queue_name: str = "zomoto_jobs"
    cache_prefix: str = "zomoto_cache"


@dataclass
class LLMConfig:
    """LLM service configuration."""
    provider: str = "groq"
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    timeout: float = 30.0
    max_retries: int = 3
    
    # Rate limiting
    requests_per_minute: int = 60
    requests_per_hour: int = 1000


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    
    # Health checks
    health_check_interval: int = 30
    
    # Alerting
    alerting_enabled: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: list = None
    
    # Webhook alerts
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_timeout: float = 10.0


@dataclass
class SecurityConfig:
    """Security configuration."""
    cors_origins: list = None
    cors_allow_credentials: bool = True
    cors_allow_methods: list = None
    cors_allow_headers: list = None
    
    # Rate limiting
    rate_limiting_enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    
    # API keys
    api_keys_enabled: bool = False
    api_keys: dict = None
    
    # JWT (if implemented)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24


@dataclass
class PerformanceConfig:
    """Performance tuning configuration."""
    # Workers
    uvicorn_workers: int = 4
    uvicorn_worker_class: str = "uvicorn.workers.UvicornWorker"
    
    # Timeouts
    request_timeout: float = 60.0
    keepalive_timeout: float = 65.0
    
    # Memory
    max_memory_mb: int = 1024
    
    # Caching
    cache_ttl: int = 3600  # 1 hour
    cache_max_size: int = 10000
    
    # Job queue
    job_queue_workers: int = 3
    job_queue_timeout: float = 30.0


@dataclass
class ProductionConfig:
    """Complete production configuration."""
    environment: str = "production"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    llm: LLMConfig = LLMConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    security: SecurityConfig = SecurityConfig()
    performance: PerformanceConfig = PerformanceConfig()


class ProductionManager:
    """Manages production deployment and configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/production.json"
        self.config = self._load_config()
    
    def _load_config(self) -> ProductionConfig:
        """Load configuration from file or environment."""
        # Try to load from file first
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            return ProductionConfig(**config_data)
        
        # Fallback to environment variables
        return self._load_from_env()
    
    def _load_from_env(self) -> ProductionConfig:
        """Load configuration from environment variables."""
        return ProductionConfig(
            environment=os.getenv("ENVIRONMENT", "production"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            
            database=DatabaseConfig(
                type=os.getenv("DB_TYPE", "postgresql"),
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "zomoto_ai"),
                username=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
                ssl_mode=os.getenv("DB_SSL_MODE", "require"),
                pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
                sqlite_path=os.getenv("SQLITE_PATH", "data/production_restaurants.db")
            ),
            
            redis=RedisConfig(
                enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                database=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD"),
                ssl=os.getenv("REDIS_SSL", "true").lower() == "true",
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
            ),
            
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "groq"),
                api_key=os.getenv("GROQ_API_KEY", ""),
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
                timeout=float(os.getenv("LLM_TIMEOUT", "30.0")),
                max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
                requests_per_minute=int(os.getenv("LLM_RPM", "60")),
                requests_per_hour=int(os.getenv("LLM_RPH", "1000"))
            ),
            
            monitoring=MonitoringConfig(
                enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                log_format=os.getenv("LOG_FORMAT", "json"),
                metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
                metrics_port=int(os.getenv("METRICS_PORT", "9090")),
                health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
                alerting_enabled=os.getenv("ALERTING_ENABLED", "false").lower() == "true",
                smtp_server=os.getenv("SMTP_SERVER", ""),
                smtp_port=int(os.getenv("SMTP_PORT", "587")),
                smtp_username=os.getenv("SMTP_USERNAME", ""),
                smtp_password=os.getenv("SMTP_PASSWORD", ""),
                smtp_from=os.getenv("SMTP_FROM", ""),
                smtp_to=os.getenv("SMTP_TO", "").split(",") if os.getenv("SMTP_TO") else [],
                webhook_enabled=os.getenv("WEBHOOK_ENABLED", "false").lower() == "true",
                webhook_url=os.getenv("WEBHOOK_URL", ""),
                webhook_timeout=float(os.getenv("WEBHOOK_TIMEOUT", "10.0"))
            ),
            
            security=SecurityConfig(
                cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                cors_allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true",
                cors_allow_methods=os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE").split(","),
                cors_allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
                rate_limiting_enabled=os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true",
                requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "60")),
                requests_per_hour=int(os.getenv("RATE_LIMIT_RPH", "1000")),
                api_keys_enabled=os.getenv("API_KEYS_ENABLED", "false").lower() == "true",
                jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
                jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
                jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
            ),
            
            performance=PerformanceConfig(
                uvicorn_workers=int(os.getenv("UVICORN_WORKERS", "4")),
                uvicorn_worker_class=os.getenv("UVICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker"),
                request_timeout=float(os.getenv("REQUEST_TIMEOUT", "60.0")),
                keepalive_timeout=float(os.getenv("KEEPALIVE_TIMEOUT", "65.0")),
                max_memory_mb=int(os.getenv("MAX_MEMORY_MB", "1024")),
                cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
                cache_max_size=int(os.getenv("CACHE_MAX_SIZE", "10000")),
                job_queue_workers=int(os.getenv("JOB_QUEUE_WORKERS", "3")),
                job_queue_timeout=float(os.getenv("JOB_QUEUE_TIMEOUT", "30.0"))
            )
        )
    
    def save_config(self, path: Optional[str] = None):
        """Save configuration to file."""
        save_path = path or self.config_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2, default=str)
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate required fields
        if not self.config.llm.api_key:
            issues.append("LLM API key is required")
        
        if self.config.database.type == "postgresql":
            if not self.config.database.host:
                issues.append("Database host is required for PostgreSQL")
            if not self.config.database.username:
                issues.append("Database username is required for PostgreSQL")
        
        # Validate security settings
        if self.config.security.api_keys_enabled and not self.config.security.api_keys:
            issues.append("API keys are enabled but no keys are configured")
        
        # Validate monitoring settings
        if self.config.monitoring.alerting_enabled:
            if not self.config.monitoring.smtp_server:
                issues.append("SMTP server is required for email alerting")
            if not self.config.monitoring.smtp_to:
                issues.append("SMTP recipients are required for email alerting")
        
        # Validate performance settings
        if self.config.performance.uvicorn_workers < 1:
            issues.append("Number of workers must be at least 1")
        
        return issues
    
    def generate_docker_compose(self) -> str:
        """Generate Docker Compose configuration."""
        compose = {
            "version": "3.8",
            "services": {
                "api": {
                    "build": ".",
                    "ports": [f"{self.config.port}:{self.config.port}"],
                    "environment": self._get_env_vars(),
                    "depends_on": ["postgres", "redis"],
                    "restart": "unless-stopped",
                    "deploy": {
                        "replicas": self.config.performance.uvicorn_workers,
                        "resources": {
                            "limits": {
                                "memory": f"{self.config.performance.max_memory_mb}M"
                            }
                        }
                    }
                }
            }
        }
        
        # Add PostgreSQL service
        if self.config.database.type == "postgresql":
            compose["services"]["postgres"] = {
                "image": "postgres:15",
                "environment": {
                    "POSTGRES_DB": self.config.database.database,
                    "POSTGRES_USER": self.config.database.username,
                    "POSTGRES_PASSWORD": self.config.database.password
                },
                "ports": [f"{self.config.database.port}:5432"],
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "restart": "unless-stopped"
            }
            compose["volumes"] = {"postgres_data": None}
        
        # Add Redis service
        if self.config.redis.enabled:
            compose["services"]["redis"] = {
                "image": "redis:7-alpine",
                "ports": [f"{self.config.redis.port}:6379"],
                "command": f"redis-server --requirepass {self.config.redis.password}" if self.config.redis.password else "redis-server",
                "volumes": ["redis_data:/data"],
                "restart": "unless-stopped"
            }
            if "volumes" not in compose:
                compose["volumes"] = {}
            compose["volumes"]["redis_data"] = None
        
        # Add monitoring service
        if self.config.monitoring.metrics_enabled:
            compose["services"]["prometheus"] = {
                "image": "prom/prometheus:latest",
                "ports": [f"{self.config.monitoring.metrics_port}:9090"],
                "volumes": ["./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml"],
                "command": "--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus",
                "restart": "unless-stopped"
            }
        
        return json.dumps(compose, indent=2)
    
    def _get_env_vars(self) -> Dict[str, str]:
        """Get environment variables for Docker."""
        return {
            "ENVIRONMENT": self.config.environment,
            "DEBUG": str(self.config.debug).lower(),
            "HOST": self.config.host,
            "PORT": str(self.config.port),
            
            "DB_TYPE": self.config.database.type,
            "DB_HOST": self.config.database.host,
            "DB_PORT": str(self.config.database.port),
            "DB_NAME": self.config.database.database,
            "DB_USER": self.config.database.username,
            "DB_PASSWORD": self.config.database.password,
            "DB_SSL_MODE": self.config.database.ssl_mode,
            "DB_POOL_SIZE": str(self.config.database.pool_size),
            
            "REDIS_ENABLED": str(self.config.redis.enabled).lower(),
            "REDIS_HOST": self.config.redis.host,
            "REDIS_PORT": str(self.config.redis.port),
            "REDIS_DB": str(self.config.redis.database),
            "REDIS_PASSWORD": self.config.redis.password or "",
            "REDIS_SSL": str(self.config.redis.ssl).lower(),
            "REDIS_MAX_CONNECTIONS": str(self.config.redis.max_connections),
            
            "GROQ_API_KEY": self.config.llm.api_key,
            "LLM_PROVIDER": self.config.llm.provider,
            "LLM_MODEL": self.config.llm.model,
            "LLM_TEMPERATURE": str(self.config.llm.temperature),
            "LLM_TIMEOUT": str(self.config.llm.timeout),
            "LLM_MAX_RETRIES": str(self.config.llm.max_retries),
            "LLM_RPM": str(self.config.llm.requests_per_minute),
            "LLM_RPH": str(self.config.llm.requests_per_hour),
            
            "MONITORING_ENABLED": str(self.config.monitoring.enabled).lower(),
            "LOG_LEVEL": self.config.monitoring.log_level,
            "LOG_FORMAT": self.config.monitoring.log_format,
            "METRICS_ENABLED": str(self.config.monitoring.metrics_enabled).lower(),
            "METRICS_PORT": str(self.config.monitoring.metrics_port),
            "HEALTH_CHECK_INTERVAL": str(self.config.monitoring.health_check_interval),
            
            "RATE_LIMITING_ENABLED": str(self.config.security.rate_limiting_enabled).lower(),
            "RATE_LIMIT_RPM": str(self.config.security.requests_per_minute),
            "RATE_LIMIT_RPH": str(self.config.security.requests_per_hour),
            
            "UVICORN_WORKERS": str(self.config.performance.uvicorn_workers),
            "REQUEST_TIMEOUT": str(self.config.performance.request_timeout),
            "MAX_MEMORY_MB": str(self.config.performance.max_memory_mb),
            "CACHE_TTL": str(self.config.performance.cache_ttl),
            "CACHE_MAX_SIZE": str(self.config.performance.cache_max_size)
        }
    
    def generate_dockerfile(self) -> str:
        """Generate Dockerfile for production."""
        dockerfile = f"""# Multi-stage build for production
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \\
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application user
RUN useradd --create-home --shell /bin/bash zomoto

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=zomoto:zomoto . .

# Create necessary directories
RUN mkdir -p data logs config && \\
    chown -R zomoto:zomoto /app

# Switch to non-root user
USER zomoto

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{self.config.port}/health || exit 1

# Expose port
EXPOSE {self.config.port}

# Start application
CMD ["uvicorn", "zomoto_ai.phase5.api:app", \\
    "--host", "0.0.0.0", \\
    "--port", "{self.config.port}", \\
    "--workers", "{self.config.performance.uvicorn_workers}", \\
    "--worker-class", "{self.config.performance.uvicorn_worker_class}", \\
    "--timeout", "{self.config.performance.request_timeout}", \\
    "--keepalive-timeout", "{self.config.performance.keepalive_timeout}"]
"""
        return dockerfile
    
    def generate_kubernetes_manifests(self) -> Dict[str, Any]:
        """Generate Kubernetes manifests."""
        manifests = {}
        
        # ConfigMap
        manifests["configmap"] = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "zomoto-ai-config",
                "namespace": "default"
            },
            "data": self._get_env_vars()
        }
        
        # Deployment
        manifests["deployment"] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "zomoto-ai",
                "namespace": "default",
                "labels": {"app": "zomoto-ai"}
            },
            "spec": {
                "replicas": self.config.performance.uvicorn_workers,
                "selector": {"matchLabels": {"app": "zomoto-ai"}},
                "template": {
                    "metadata": {"labels": {"app": "zomoto-ai"}},
                    "spec": {
                        "containers": [{
                            "name": "zomoto-ai",
                            "image": "zomoto-ai:latest",
                            "ports": [{"containerPort": self.config.port}],
                            "envFrom": [{"configMapRef": {"name": "zomoto-ai-config"}}],
                            "resources": {
                                "requests": {
                                    "memory": f"{self.config.performance.max_memory_mb // 2}Mi",
                                    "cpu": "250m"
                                },
                                "limits": {
                                    "memory": f"{self.config.performance.max_memory_mb}Mi",
                                    "cpu": "500m"
                                }
                            },
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": self.config.port
                                },
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": self.config.port
                                },
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5
                            }
                        }]
                    }
                }
            }
        }
        
        # Service
        manifests["service"] = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "zomoto-ai-service",
                "namespace": "default"
            },
            "spec": {
                "selector": {"app": "zomoto-ai"},
                "ports": [{
                    "protocol": "TCP",
                    "port": 80,
                    "targetPort": self.config.port
                }],
                "type": "LoadBalancer"
            }
        }
        
        return manifests
    
    def setup_production_environment(self):
        """Setup production environment files."""
        # Create config directory
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Save configuration
        self.save_config()
        
        # Generate Docker Compose
        with open(config_dir / "docker-compose.yml", 'w') as f:
            f.write(self.generate_docker_compose())
        
        # Generate Dockerfile
        with open("Dockerfile", 'w') as f:
            f.write(self.generate_dockerfile())
        
        # Generate Kubernetes manifests
        k8s_dir = Path("k8s")
        k8s_dir.mkdir(exist_ok=True)
        
        manifests = self.generate_kubernetes_manifests()
        for name, manifest in manifests.items():
            with open(k8s_dir / f"{name}.yaml", 'w') as f:
                import yaml
                yaml.dump(manifest, f, default_flow_style=False)
        
        # Generate environment file
        with open(config_dir / ".env", 'w') as f:
            for key, value in self._get_env_vars().items():
                f.write(f"{key}={value}\n")


# Global production manager
default_production_manager = ProductionManager()


def get_production_manager() -> ProductionManager:
    """Get default production manager instance."""
    return default_production_manager


if __name__ == "__main__":
    # Setup production environment
    manager = get_production_manager()
    
    # Validate configuration
    issues = manager.validate_config()
    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration is valid")
    
    # Setup production files
    manager.setup_production_environment()
    print("Production environment setup complete")
