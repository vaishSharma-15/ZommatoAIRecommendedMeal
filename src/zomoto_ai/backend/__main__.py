"""Backend Main Entry Point

Provides unified entry point for running the backend application
with various modes and configuration options.
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import get_config_manager
from .api.app import create_app
from .data import initialize_backends
from zomoto_ai.phase6.logging import get_logger
from zomoto_ai.phase6.monitoring import start_monitoring, stop_monitoring


def run_server():
    """Run the backend server."""
    config_manager = get_config_manager()
    config = config_manager.config
    
    # Validate configuration
    issues = config_manager.validate_config()
    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease fix these issues before starting the server.")
        return False
    
    # Print configuration summary
    config_manager.print_config_summary()
    
    # Create and run app
    app = create_app()
    
    import uvicorn
    
    print(f"\nStarting backend server on {config.api_host}:{config.api_port}")
    print(f"Workers: {config.api_workers}")
    print(f"Debug: {config.api_debug}")
    print(f"Documentation: http://{config.api_host}:{config.api_port}/docs")
    
    try:
        # Disable workers and reload for development mode
        uvicorn.run(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level=config.log_level.lower(),
            access_log=True
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        return False
    
    return True


async def initialize_system():
    """Initialize all system components."""
    logger = get_logger()
    
    try:
        print("Initializing backend system...")
        
        # Initialize data backends
        await initialize_backends()
        print("✓ Data backends initialized")
        
        # Start monitoring system
        start_monitoring()
        print("✓ Monitoring system started")
        
        logger.info("backend_main", "system_initialized", "Backend system initialized successfully")
        return True
        
    except Exception as e:
        logger.error("backend_main", "initialization_failed", f"System initialization failed: {e}")
        print(f"✗ Initialization failed: {e}")
        return False


async def cleanup_system():
    """Cleanup system components."""
    logger = get_logger()
    
    try:
        print("Cleaning up backend system...")
        
        # Stop monitoring system
        stop_monitoring()
        print("✓ Monitoring system stopped")
        
        logger.info("backend_main", "system_cleanup", "Backend system cleanup completed")
        
    except Exception as e:
        logger.error("backend_main", "cleanup_failed", f"System cleanup failed: {e}")
        print(f"✗ Cleanup failed: {e}")


def validate_config_command():
    """Validate configuration command."""
    config_manager = get_config_manager()
    issues = config_manager.validate_config()
    
    if issues:
        print("Configuration validation failed:")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    else:
        print("✅ Configuration is valid!")
        config_manager.print_config_summary()
        return True


def save_config_command(file_path: str = "config/backend.json"):
    """Save configuration to file command."""
    config_manager = get_config_manager()
    
    try:
        config_manager.save_config_to_file(file_path)
        print(f"✅ Configuration saved to {file_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")
        return False


async def health_check_command():
    """Run health check command."""
    try:
        from .services.monitoring import MonitoringService
        
        monitoring_service = MonitoringService()
        component_health = await monitoring_service.check_all_components()
        
        print("System Health Check:")
        print("=" * 30)
        
        overall_healthy = True
        for component, status in component_health.items():
            status_icon = "✅" if status.status == "healthy" else "❌"
            print(f"{status_icon} {component}: {status.status}")
            if status.error:
                print(f"   Error: {status.error}")
            if status.response_time_ms:
                print(f"   Response time: {status.response_time_ms:.2f}ms")
            
            if status.status != "healthy":
                overall_healthy = False
        
        print("=" * 30)
        if overall_healthy:
            print("✅ Overall system health: HEALTHY")
        else:
            print("❌ Overall system health: UNHEALTHY")
        
        return overall_healthy
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def test_backends_command():
    """Test all backends command."""
    try:
        print("Testing Backend Connections:")
        print("=" * 30)
        
        # Test database
        from .data import get_database_backend
        db_backend = get_database_backend()
        
        print("Testing database connection...")
        if await db_backend.connect():
            print("✅ Database: Connected")
            stats = db_backend.get_statistics()
            if "error" not in stats:
                print(f"   Restaurants: {stats.get('total_restaurants', 0)}")
            else:
                print(f"   Error: {stats['error']}")
            await db_backend.disconnect()
        else:
            print("❌ Database: Connection failed")
        
        # Test cache
        from .data import get_cache_backend
        cache_backend = get_cache_backend()
        
        print("Testing cache connection...")
        if hasattr(cache_backend, 'connect'):
            if await cache_backend.connect():
                print("✅ Cache: Connected")
                await cache_backend.disconnect()
            else:
                print("❌ Cache: Connection failed")
        else:
            print("✅ Cache: Memory backend (no connection needed)")
        
        # Test LLM service
        from zomoto_ai.phase6.reliability import get_reliable_llm_client
        llm_client = get_reliable_llm_client()
        
        print("Testing LLM service...")
        if llm_client._llm_client:
            print("✅ LLM: Available")
        else:
            print("⚠️  LLM: Not available (fallback will be used)")
        
        print("=" * 30)
        print("Backend test completed")
        return True
        
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Zomoto AI Backend Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the server
  python -m zomoto_ai.backend start
  
  # Validate configuration
  python -m zomoto_ai.backend validate-config
  
  # Test backends
  python -m zomoto_ai.backend test-backends
  
  # Run health check
  python -m zomoto_ai.backend health-check
        """
    )
    
    parser.add_argument(
        "command",
        choices=["start", "validate-config", "save-config", "health-check", "test-backends"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--config-file",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        help="Override API port"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    # Override configuration if provided
    if args.port:
        import os
        os.environ["API_PORT"] = str(args.port)
    
    if args.debug:
        import os
        os.environ["API_DEBUG"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Execute command
    if args.command == "start":
        success = asyncio.run(initialize_system())
        if success:
            run_server()
        else:
            sys.exit(1)
    
    elif args.command == "validate-config":
        success = validate_config_command()
        sys.exit(0 if success else 1)
    
    elif args.command == "save-config":
        file_path = args.config_file or "config/backend.json"
        success = save_config_command(file_path)
        sys.exit(0 if success else 1)
    
    elif args.command == "health-check":
        success = asyncio.run(health_check_command())
        sys.exit(0 if success else 1)
    
    elif args.command == "test-backends":
        success = asyncio.run(test_backends_command())
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
