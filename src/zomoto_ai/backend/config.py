"""Backend Configuration - Centralized configuration management

Provides centralized configuration management for all backend
components with environment variable support and validation.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase6.production import ProductionConfig, DatabaseConfig, RedisConfig, LLMConfig


@dataclass
class BackendConfig:
    """Configuration for backend services."""
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_debug: bool = False
    api_reload: bool = False
    
    # Database Configuration
    database_type: str = "sqlite"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "zomoto_ai"
    database_user: str = "postgres"
    database_password: str = ""
    database_ssl_mode: str = "prefer"
    database_pool_size: int = 20
    sqlite_path: str = "data/restaurants.db"
    
    # Redis Configuration
    redis_enabled: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_max_connections: int = 20
    
    # LLM Configuration
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    llm_timeout: float = 30.0
    llm_max_retries: int = 3
    
    # Rate Limiting Configuration
    rate_limiting_enabled: bool = True
    rate_limit_anonymous_rpm: int = 60
    rate_limit_authenticated_rpm: int = 120
    rate_limit_premium_rpm: int = 300
    rate_limit_admin_rpm: int = 1000
    
    # Cache Configuration
    cache_ttl: int = 3600  # 1 hour
    cache_max_size: int = 10000
    
    # Job Queue Configuration
    job_queue_enabled: bool = True
    job_queue_workers: int = 3
    job_queue_timeout: float = 30.0
    
    # Monitoring Configuration
    monitoring_enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True
    health_check_interval: int = 30
    
    # Security Configuration
    cors_origins: list = None
    cors_allow_credentials: bool = True
    cors_allow_methods: list = None
    cors_allow_headers: list = None
    
    def __post_init__(self):
        # Set default values for list fields
        if self.cors_origins is None:
            self.cors_origins = ["*"]
        if self.cors_allow_methods is None:
            self.cors_allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        if self.cors_allow_headers is None:
            self.cors_allow_headers = ["*"]


class ConfigManager:
    """Manages backend configuration with environment variable support."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> BackendConfig:
        """Load configuration from environment variables."""
        return BackendConfig(
            # API Configuration
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            api_workers=int(os.getenv("API_WORKERS", "4")),
            api_debug=os.getenv("API_DEBUG", "false").lower() == "true",
            api_reload=os.getenv("API_RELOAD", "false").lower() == "true",
            
            # Database Configuration
            database_type=os.getenv("DB_TYPE", "sqlite"),
            database_host=os.getenv("DB_HOST", "localhost"),
            database_port=int(os.getenv("DB_PORT", "5432")),
            database_name=os.getenv("DB_NAME", "zomoto_ai"),
            database_user=os.getenv("DB_USER", "postgres"),
            database_password=os.getenv("DB_PASSWORD", ""),
            database_ssl_mode=os.getenv("DB_SSL_MODE", "prefer"),
            database_pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            sqlite_path=os.getenv("SQLITE_PATH", "data/restaurants.db"),
            
            # Redis Configuration
            redis_enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
            
            # LLM Configuration
            llm_provider=os.getenv("LLM_PROVIDER", "groq"),
            llm_api_key=os.getenv("GROQ_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            llm_timeout=float(os.getenv("LLM_TIMEOUT", "30.0")),
            llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            
            # Rate Limiting Configuration
            rate_limiting_enabled=os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true",
            rate_limit_anonymous_rpm=int(os.getenv("RATE_LIMIT_ANONYMOUS_RPM", "60")),
            rate_limit_authenticated_rpm=int(os.getenv("RATE_LIMIT_AUTHENTICATED_RPM", "120")),
            rate_limit_premium_rpm=int(os.getenv("RATE_LIMIT_PREMIUM_RPM", "300")),
            rate_limit_admin_rpm=int(os.getenv("RATE_LIMIT_ADMIN_RPM", "1000")),
            
            # Cache Configuration
            cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
            cache_max_size=int(os.getenv("CACHE_MAX_SIZE", "10000")),
            
            # Job Queue Configuration
            job_queue_enabled=os.getenv("JOB_QUEUE_ENABLED", "true").lower() == "true",
            job_queue_workers=int(os.getenv("JOB_QUEUE_WORKERS", "3")),
            job_queue_timeout=float(os.getenv("JOB_QUEUE_TIMEOUT", "30.0")),
            
            # Monitoring Configuration
            monitoring_enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
            
            # Security Configuration
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            cors_allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true",
            cors_allow_methods=os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS").split(","),
            cors_allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(",")
        )
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate required fields
        if not self.config.llm_api_key:
            issues.append("LLM API key is required")
        
        # Validate database configuration
        if self.config.database_type == "postgresql":
            if not self.config.database_host:
                issues.append("Database host is required for PostgreSQL")
            if not self.config.database_user:
                issues.append("Database username is required for PostgreSQL")
        
        # Validate numeric ranges
        if self.config.api_port < 1 or self.config.api_port > 65535:
            issues.append("API port must be between 1 and 65535")
        
        if self.config.database_port < 1 or self.config.database_port > 65535:
            issues.append("Database port must be between 1 and 65535")
        
        if self.config.redis_port < 1 or self.config.redis_port > 65535:
            issues.append("Redis port must be between 1 and 65535")
        
        # Validate timeouts
        if self.config.llm_timeout <= 0:
            issues.append("LLM timeout must be positive")
        
        if self.config.job_queue_timeout <= 0:
            issues.append("Job queue timeout must be positive")
        
        # Validate worker counts
        if self.config.api_workers < 1:
            issues.append("API workers must be at least 1")
        
        if self.config.job_queue_workers < 1:
            issues.append("Job queue workers must be at least 1")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.config.log_level not in valid_log_levels:
            issues.append(f"Log level must be one of: {', '.join(valid_log_levels)}")
        
        return issues
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return DatabaseConfig(
            type=self.config.database_type,
            host=self.config.database_host,
            port=self.config.database_port,
            database=self.config.database_name,
            username=self.config.database_user,
            password=self.config.database_password,
            ssl_mode=self.config.database_ssl_mode,
            pool_size=self.config.database_pool_size,
            sqlite_path=self.config.sqlite_path
        )
    
    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration."""
        return RedisConfig(
            enabled=self.config.redis_enabled,
            host=self.config.redis_host,
            port=self.config.redis_port,
            database=self.config.redis_db,
            password=self.config.redis_password,
            max_connections=self.config.redis_max_connections
        )
    
    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration."""
        return LLMConfig(
            provider=self.config.llm_provider,
            api_key=self.config.llm_api_key,
            model=self.config.llm_model,
            temperature=self.config.llm_temperature,
            timeout=self.config.llm_timeout,
            max_retries=self.config.llm_max_retries
        )
    
    def get_production_config(self) -> ProductionConfig:
        """Get production configuration."""
        return ProductionConfig(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=self.config.api_debug,
            host=self.config.api_host,
            port=self.config.api_port,
            database=self.get_database_config(),
            redis=self.get_redis_config(),
            llm=self.get_llm_config(),
            monitoring_enabled=self.config.monitoring_enabled,
            log_level=self.config.log_level,
            log_format=self.config.log_format,
            metrics_enabled=self.config.metrics_enabled,
            health_check_interval=self.config.health_check_interval,
            cors_origins=self.config.cors_origins,
            cors_allow_credentials=self.config.cors_allow_credentials,
            cors_allow_methods=self.config.cors_allow_methods,
            cors_allow_headers=self.config.cors_allow_headers,
            rate_limiting_enabled=self.config.rate_limiting_enabled,
            requests_per_minute=self.config.rate_limit_anonymous_rpm,
            requests_per_hour=self.config.rate_limit_anonymous_rpm * 60,
            uvicorn_workers=self.config.api_workers,
            request_timeout=60.0,
            max_memory_mb=1024,
            cache_ttl=self.config.cache_ttl,
            cache_max_size=self.config.cache_max_size,
            job_queue_workers=self.config.job_queue_workers,
            job_queue_timeout=self.config.job_queue_timeout
        )
    
    def save_config_to_file(self, file_path: str):
        """Save configuration to file."""
        import json
        
        config_dict = {
            "api": {
                "host": self.config.api_host,
                "port": self.config.api_port,
                "workers": self.config.api_workers,
                "debug": self.config.api_debug,
                "reload": self.config.api_reload
            },
            "database": {
                "type": self.config.database_type,
                "host": self.config.database_host,
                "port": self.config.database_port,
                "name": self.config.database_name,
                "user": self.config.database_user,
                "password": self.config.database_password,
                "ssl_mode": self.config.database_ssl_mode,
                "pool_size": self.config.database_pool_size,
                "sqlite_path": self.config.sqlite_path
            },
            "redis": {
                "enabled": self.config.redis_enabled,
                "host": self.config.redis_host,
                "port": self.config.redis_port,
                "db": self.config.redis_db,
                "password": self.config.redis_password,
                "max_connections": self.config.redis_max_connections
            },
            "llm": {
                "provider": self.config.llm_provider,
                "api_key": self.config.llm_api_key,
                "model": self.config.llm_model,
                "temperature": self.config.llm_temperature,
                "timeout": self.config.llm_timeout,
                "max_retries": self.config.llm_max_retries
            },
            "rate_limiting": {
                "enabled": self.config.rate_limiting_enabled,
                "anonymous_rpm": self.config.rate_limit_anonymous_rpm,
                "authenticated_rpm": self.config.rate_limit_authenticated_rpm,
                "premium_rpm": self.config.rate_limit_premium_rpm,
                "admin_rpm": self.config.rate_limit_admin_rpm
            },
            "cache": {
                "ttl": self.config.cache_ttl,
                "max_size": self.config.cache_max_size
            },
            "job_queue": {
                "enabled": self.config.job_queue_enabled,
                "workers": self.config.job_queue_workers,
                "timeout": self.config.job_queue_timeout
            },
            "monitoring": {
                "enabled": self.config.monitoring_enabled,
                "log_level": self.config.log_level,
                "log_format": self.config.log_format,
                "metrics_enabled": self.config.metrics_enabled,
                "health_check_interval": self.config.health_check_interval
            },
            "security": {
                "cors_origins": self.config.cors_origins,
                "cors_allow_credentials": self.config.cors_allow_credentials,
                "cors_allow_methods": self.config.cors_allow_methods,
                "cors_allow_headers": self.config.cors_allow_headers
            }
        }
        
        # Create directory if it doesn't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def print_config_summary(self):
        """Print configuration summary."""
        print("Backend Configuration Summary:")
        print("=" * 40)
        print(f"API: {self.config.api_host}:{self.config.api_port}")
        print(f"Database: {self.config.database_type} ({self.config.database_host}:{self.config.database_port})")
        print(f"Redis: {'enabled' if self.config.redis_enabled else 'disabled'} ({self.config.redis_host}:{self.config.redis_port})")
        print(f"LLM: {self.config.llm_provider} ({self.config.llm_model})")
        print(f"Rate Limiting: {'enabled' if self.config.rate_limiting_enabled else 'disabled'}")
        print(f"Monitoring: {'enabled' if self.config.monitoring_enabled else 'disabled'}")
        print(f"Job Queue: {'enabled' if self.config.job_queue_enabled else 'disabled'}")
        print("=" * 40)


# Global configuration manager
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_backend_config() -> BackendConfig:
    """Get backend configuration."""
    return get_config_manager().config
