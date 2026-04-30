"""FastAPI Application - Main application setup

Configures the FastAPI application with middleware, routes, and
lifecycle management for production deployment.
"""

import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .middleware import (
    CorrelationIDMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    ErrorHandlingMiddleware,
    SecurityHeadersMiddleware,
    MetricsMiddleware
)
from .endpoints import router
from zomoto_ai.phase6.logging import get_logger
from zomoto_ai.phase6.monitoring import start_monitoring, stop_monitoring
from zomoto_ai.phase6.production import get_production_manager


# Global variables
logger = get_logger()
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application", "starting", "FastAPI application starting up")
    
    # Skip monitoring system for now to prevent shutdown issues
    # try:
    #     start_monitoring()
    #     logger.info("application", "monitoring_started", "Monitoring system started")
    # except Exception as e:
    #     logger.error("application", "monitoring_failed", f"Failed to start monitoring: {e}")
    
    # Initialize services
    try:
        # Initialize database connections, cache, etc.
        from ..data import initialize_backends
        await initialize_backends()
        logger.info("application", "backends_initialized", "Data backends initialized")
    except Exception as e:
        logger.error("application", "backends_failed", f"Failed to initialize backends: {e}")
    
    yield
    
    # Shutdown
    logger.info("application", "shutting_down", "FastAPI application shutting down")
    
    # Skip monitoring system shutdown
    # try:
    #     stop_monitoring()
    #     logger.info("application", "monitoring_stopped", "Monitoring system stopped")
    # except Exception as e:
    #     logger.error("application", "monitoring_stop_failed", f"Failed to stop monitoring: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Get production configuration
    production_manager = get_production_manager()
    config = production_manager.config
    
    # Create FastAPI app
    app = FastAPI(
        title="Zomoto AI Recommendation API",
        description="Restaurant recommendation system with LLM-powered ranking",
        version="1.0.0",
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    if config.security.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.security.cors_origins,
            allow_credentials=config.security.cors_allow_credentials,
            allow_methods=config.security.cors_allow_methods,
            allow_headers=config.security.cors_allow_headers
        )
    
    # Add custom middleware (order matters)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    
    # Add rate limiting if enabled
    if config.security.rate_limiting_enabled:
        from zomoto_ai.phase6.rate_limiting import RateLimitConfig
        rate_limit_config = RateLimitConfig(
            requests_per_minute=config.security.requests_per_minute,
            requests_per_hour=config.security.requests_per_hour
        )
        app.add_middleware(RateLimitMiddleware, config=rate_limit_config)
    
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Add API routes
    app.include_router(router)
    
    # Add root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with basic information."""
        uptime = time.time() - start_time
        return {
            "name": "Zomoto AI Recommendation API",
            "version": "1.0.0",
            "status": "running",
            "uptime_seconds": uptime,
            "docs": "/docs" if config.debug else "Documentation disabled in production"
        }
    
    # Health check endpoint (simple version)
    @app.get("/health")
    async def simple_health():
        """Simple health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": time.time() - start_time
        }
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    # Get production configuration
    production_manager = get_production_manager()
    config = production_manager.config
    
    # Run server
    uvicorn.run(
        "src.zomoto_ai.backend.api.app:app",
        host=config.host,
        port=config.port,
        workers=1,  # Use 1 worker for development, multiple for production
        reload=config.debug,
        log_level="info",
        access_log=True
    )
