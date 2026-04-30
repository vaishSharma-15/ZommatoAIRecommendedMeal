"""Main entry point for Phase 6 - Reliability, Evaluation, and Production Hardening

Provides access to testing, monitoring, benchmarks, and production setup.
"""

import sys
import argparse
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .testing import run_comprehensive_tests
from .benchmarks import run_performance_benchmarks, run_load_test, LoadTestConfig
from .monitoring import get_monitoring_system, start_monitoring, stop_monitoring
from .production import get_production_manager


def main():
    """Main entry point with mode selection."""
    parser = argparse.ArgumentParser(
        description="Zomoto AI Phase 6 - Reliability, Evaluation, and Production Hardening",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run comprehensive tests
  python -m zomoto_ai.phase6 test
  
  # Run performance benchmarks
  python -m zomoto_ai.phase6 benchmark
  
  # Run load testing
  python -m zomoto_ai.phase6 load-test --users 10 --requests 100
  
  # Start monitoring system
  python -m zomoto_ai.phase6 monitor
  
  # Setup production environment
  python -m zomoto_ai.phase6 production setup
        """
    )
    
    parser.add_argument(
        "mode",
        choices=["test", "benchmark", "load-test", "monitor", "production"],
        help="Operation mode"
    )
    
    # Test options
    test_group = parser.add_argument_group("Test Options")
    test_group.add_argument("--test-type", choices=["unit", "golden", "all"], default="all",
                          help="Type of tests to run")
    
    # Benchmark options
    benchmark_group = parser.add_argument_group("Benchmark Options")
    benchmark_group.add_argument("--benchmark-type", choices=["phase3", "phase4", "api", "all"], 
                                default="all", help="Type of benchmarks to run")
    benchmark_group.add_argument("--save-report", action="store_true", 
                               help="Save benchmark report to file")
    
    # Load test options
    load_test_group = parser.add_argument_group("Load Test Options")
    load_test_group.add_argument("--users", type=int, default=10,
                                help="Number of concurrent users")
    load_test_group.add_argument("--requests", type=int, default=100,
                                help="Requests per user")
    load_test_group.add_argument("--ramp-up", type=int, default=30,
                                help="Ramp up time in seconds")
    load_test_group.add_argument("--duration", type=int, default=300,
                                help="Test duration in seconds")
    
    # Monitor options
    monitor_group = parser.add_argument_group("Monitor Options")
    monitor_group.add_argument("--action", choices=["start", "stop", "status"], default="start",
                               help="Monitor action")
    
    # Production options
    production_group = parser.add_argument_group("Production Options")
    production_group.add_argument("--action", choices=["setup", "validate", "config"], 
                                   default="setup", help="Production action")
    production_group.add_argument("--config-path", help="Path to config file")
    
    args = parser.parse_args()
    
    if args.mode == "test":
        # Run tests
        if args.test_type == "all":
            results = run_comprehensive_tests()
            print(f"Test Results: {results['summary']['success_rate']:.1f}% success rate")
        elif args.test_type == "unit":
            from .testing import TestSuite
            suite = TestSuite()
            results = suite.run_all_tests()
            print("Unit tests completed")
        elif args.test_type == "golden":
            from .testing import GoldenTestSuite
            suite = GoldenTestSuite()
            results = suite.run_golden_tests()
            print(f"Golden tests: {results['passed']}/{results['total']} passed")
    
    elif args.mode == "benchmark":
        # Run benchmarks
        if args.benchmark_type == "all":
            results = run_performance_benchmarks()
            
            from .benchmarks import BenchmarkReporter
            reporter = BenchmarkReporter()
            
            if args.save_report:
                reporter.save_report(results)
            
            print("Benchmark Results:")
            for result in results:
                print(f"  {result.test_name}: {result.requests_per_second:.2f} RPS, "
                      f"{result.avg_response_time:.3f}s avg, {result.error_rate:.2%} error rate")
        else:
            from .benchmarks import PerformanceBenchmark
            benchmark = PerformanceBenchmark()
            
            if args.benchmark_type == "phase3":
                result = benchmark.benchmark_phase3_retrieval()
            elif args.benchmark_type == "phase4":
                result = benchmark.benchmark_phase4_llm_ranking()
            elif args.benchmark_type == "api":
                result = benchmark.benchmark_api_endpoints()
            
            print(f"Benchmark Result: {result.test_name}")
            print(f"  RPS: {result.requests_per_second:.2f}")
            print(f"  Avg Time: {result.avg_response_time:.3f}s")
            print(f"  Error Rate: {result.error_rate:.2%}")
    
    elif args.mode == "load-test":
        # Run load test
        config = LoadTestConfig(
            concurrent_users=args.users,
            requests_per_user=args.requests,
            ramp_up_time=args.ramp_up,
            test_duration=args.duration
        )
        
        result = run_load_test(config)
        
        print("Load Test Results:")
        print(f"  Total Requests: {result.total_requests}")
        print(f"  Successful: {result.successful_requests}")
        print(f"  Failed: {result.failed_requests}")
        print(f"  RPS: {result.requests_per_second:.2f}")
        print(f"  Avg Response Time: {result.avg_response_time:.3f}s")
        print(f"  P95 Response Time: {result.p95_response_time:.3f}s")
        print(f"  Error Rate: {result.error_rate:.2%}")
    
    elif args.mode == "monitor":
        # Monitoring operations
        monitoring = get_monitoring_system()
        
        if args.action == "start":
            print("Starting monitoring system...")
            start_monitoring()
            print("Monitoring system started. Press Ctrl+C to stop.")
            
            try:
                import time
                while True:
                    time.sleep(10)
                    status = monitoring.get_system_status()
                    print(f"System status: {status['status']} "
                          f"({status['health_summary']['healthy_checks']}/{status['health_summary']['total_checks']} healthy)")
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                stop_monitoring()
                print("Monitoring stopped.")
        
        elif args.action == "stop":
            print("Stopping monitoring system...")
            stop_monitoring()
            print("Monitoring stopped.")
        
        elif args.action == "status":
            status = monitoring.get_system_status()
            print("System Status:")
            print(f"  Overall: {status['status']}")
            print(f"  Health: {status['health_summary']['health_percentage']:.1f}%")
            print(f"  Active Alerts: {status['alerts']['active_alerts']}")
    
    elif args.mode == "production":
        # Production operations
        manager = get_production_manager()
        
        if args.action == "setup":
            print("Setting up production environment...")
            manager.setup_production_environment()
            print("Production environment setup complete.")
            print("Files created:")
            print("  - config/production.json")
            print("  - config/docker-compose.yml")
            print("  - Dockerfile")
            print("  - k8s/ (Kubernetes manifests)")
        
        elif args.action == "validate":
            print("Validating production configuration...")
            issues = manager.validate_config()
            
            if issues:
                print("Configuration issues found:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("Configuration is valid!")
        
        elif args.action == "config":
            config_path = args.config_path or "config/production.json"
            print(f"Production configuration ({config_path}):")
            
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
