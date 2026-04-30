"""Performance Benchmarks and Load Testing for Phase 6

Provides comprehensive performance testing and benchmarking capabilities
for the restaurant recommendation system.
"""

import asyncio
import time
import json
import statistics
import threading
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import random
from pathlib import Path

# Import system components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import UserPreference, Budget, Restaurant, CandidateSet
from zomoto_ai.phase3.retrieval import retrieve_with_relaxation, load_restaurants_from_parquet
from zomoto_ai.phase4.groq_ranker import GroqLLMClient
from zomoto_ai.phase5.api import app as api_app
from fastapi.testclient import TestClient
import requests
from .logging import get_logger, get_metrics, get_performance_tracker
from .reliability import get_reliable_llm_client


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    timestamp: datetime
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    concurrent_users: int = 10
    requests_per_user: int = 100
    ramp_up_time: int = 30  # seconds
    test_duration: int = 300  # seconds
    
    # Test scenarios
    include_llm_calls: bool = True
    include_database_queries: bool = True
    include_cache_operations: bool = True
    
    # Performance targets
    target_rps: float = 50.0
    target_avg_response_time: float = 2.0
    target_p95_response_time: float = 5.0
    target_error_rate: float = 0.01  # 1%


class PerformanceBenchmark:
    """Performance benchmarking suite."""
    
    def __init__(self):
        self.logger = get_logger()
        self.metrics = get_metrics()
        self.performance_tracker = get_performance_tracker()
        
        # Load test data
        self.restaurants = self._load_test_restaurants()
        self.test_preferences = self._generate_test_preferences()
        
        # API client for testing
        self.api_client = TestClient(api_app)
    
    def _load_test_restaurants(self) -> List[Restaurant]:
        """Load restaurant data for testing."""
        try:
            return load_restaurants_from_parquet("data/restaurants_processed.parquet")
        except:
            # Create mock data if parquet not available
            return self._create_mock_restaurants()
    
    def _create_mock_restaurants(self) -> List[Restaurant]:
        """Create mock restaurant data for testing."""
        restaurants = []
        cuisines = ["Italian", "Chinese", "Indian", "Thai", "Mexican", "American"]
        locations = ["Bangalore", "Delhi", "Mumbai", "Chennai", "Kolkata"]
        
        for i in range(1000):
            restaurants.append(Restaurant(
                id=f"rest_{i}",
                name=f"Restaurant {i}",
                location=random.choice(locations),
                city=random.choice(locations),
                area=f"Area {i % 50}",
                cuisines=[random.choice(cuisines)],
                cost_for_two=random.randint(200, 2000),
                rating=random.uniform(3.0, 5.0),
                votes=random.randint(10, 1000)
            ))
        
        return restaurants
    
    def _generate_test_preferences(self) -> List[UserPreference]:
        """Generate test user preferences."""
        preferences = []
        locations = ["Bangalore", "Delhi", "Mumbai"]
        cuisines = ["Italian", "Chinese", "Indian", "Thai"]
        
        for _ in range(100):
            preferences.append(UserPreference(
                location=random.choice(locations),
                budget=Budget(
                    kind="range",
                    max_cost_for_two=random.choice([500, 1000, 1500, 2000])
                ),
                cuisine=random.choice(cuisines + [None]),
                min_rating=random.uniform(3.5, 4.5),
                optional_constraints=[]
            ))
        
        return preferences
    
    def benchmark_phase3_retrieval(self, candidate_count: int = 50) -> BenchmarkResult:
        """Benchmark Phase 3 retrieval performance."""
        test_name = "phase3_retrieval"
        response_times = []
        
        self.logger.info("benchmark", "started", f"Starting {test_name} benchmark")
        
        for i, preference in enumerate(self.test_preferences[:100]):
            start_time = time.time()
            
            try:
                # Phase 3 retrieval
                result = retrieve_with_relaxation(
                    self.restaurants, 
                    preference, 
                    top_n=candidate_count
                )
                
                duration = time.time() - start_time
                response_times.append(duration)
                
                self.metrics.record_histogram(f"{test_name}_duration", duration)
                
            except Exception as e:
                self.logger.error("benchmark", "test_failed", 
                                f"Test {i} failed: {e}")
                response_times.append(None)
        
        # Calculate metrics
        valid_times = [t for t in response_times if t is not None]
        
        if not valid_times:
            return BenchmarkResult(
                test_name=test_name,
                total_requests=len(response_times),
                successful_requests=0,
                failed_requests=len(response_times),
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                requests_per_second=0,
                error_rate=1.0
            )
        
        return BenchmarkResult(
            test_name=test_name,
            total_requests=len(response_times),
            successful_requests=len(valid_times),
            failed_requests=len(response_times) - len(valid_times),
            avg_response_time=statistics.mean(valid_times),
            min_response_time=min(valid_times),
            max_response_time=max(valid_times),
            p50_response_time=statistics.median(valid_times),
            p95_response_time=valid_times[int(len(valid_times) * 0.95)],
            p99_response_time=valid_times[int(len(valid_times) * 0.99)],
            requests_per_second=len(valid_times) / sum(valid_times),
            error_rate=(len(response_times) - len(valid_times)) / len(response_times)
        )
    
    def benchmark_phase4_llm_ranking(self, candidate_count: int = 10) -> BenchmarkResult:
        """Benchmark Phase 4 LLM ranking performance."""
        test_name = "phase4_llm_ranking"
        response_times = []
        
        self.logger.info("benchmark", "started", f"Starting {test_name} benchmark")
        
        # Create test candidate sets
        for i, preference in enumerate(self.test_preferences[:20]):  # Fewer tests for LLM
            start_time = time.time()
            
            try:
                # Phase 3 retrieval first
                retrieval_result = retrieve_with_relaxation(
                    self.restaurants, 
                    preference, 
                    top_n=candidate_count
                )
                
                if not retrieval_result.candidate_set.candidates:
                    response_times.append(None)
                    continue
                
                # Phase 4 LLM ranking
                client = get_reliable_llm_client()
                result = client.rank_and_explain(retrieval_result.candidate_set)
                
                duration = time.time() - start_time
                response_times.append(duration)
                
                self.metrics.record_histogram(f"{test_name}_duration", duration)
                
            except Exception as e:
                self.logger.error("benchmark", "test_failed", 
                                f"LLM test {i} failed: {e}")
                response_times.append(None)
        
        # Calculate metrics
        valid_times = [t for t in response_times if t is not None]
        
        if not valid_times:
            return BenchmarkResult(
                test_name=test_name,
                total_requests=len(response_times),
                successful_requests=0,
                failed_requests=len(response_times),
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                requests_per_second=0,
                error_rate=1.0
            )
        
        return BenchmarkResult(
            test_name=test_name,
            total_requests=len(response_times),
            successful_requests=len(valid_times),
            failed_requests=len(response_times) - len(valid_times),
            avg_response_time=statistics.mean(valid_times),
            min_response_time=min(valid_times),
            max_response_time=max(valid_times),
            p50_response_time=statistics.median(valid_times),
            p95_response_time=valid_times[int(len(valid_times) * 0.95)],
            p99_response_time=valid_times[int(len(valid_times) * 0.99)],
            requests_per_second=len(valid_times) / sum(valid_times),
            error_rate=(len(response_times) - len(valid_times)) / len(response_times)
        )
    
    def benchmark_api_endpoints(self) -> BenchmarkResult:
        """Benchmark API endpoint performance."""
        test_name = "api_endpoints"
        response_times = []
        
        self.logger.info("benchmark", "started", f"Starting {test_name} benchmark")
        
        # Test recommendations endpoint
        for i, preference in enumerate(self.test_preferences[:50]):
            start_time = time.time()
            
            try:
                request_data = {
                    "preferences": {
                        "location": preference.location,
                        "min_rating": preference.min_rating,
                        "budget": asdict(preference.budget) if preference.budget else None
                    },
                    "top_n": 10
                }
                
                response = self.api_client.post("/recommendations", json=request_data)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    response_times.append(duration)
                    self.metrics.record_histogram(f"{test_name}_duration", duration)
                else:
                    response_times.append(None)
                    
            except Exception as e:
                self.logger.error("benchmark", "test_failed", 
                                f"API test {i} failed: {e}")
                response_times.append(None)
        
        # Calculate metrics
        valid_times = [t for t in response_times if t is not None]
        
        return BenchmarkResult(
            test_name=test_name,
            total_requests=len(response_times),
            successful_requests=len(valid_times),
            failed_requests=len(response_times) - len(valid_times),
            avg_response_time=statistics.mean(valid_times) if valid_times else 0,
            min_response_time=min(valid_times) if valid_times else 0,
            max_response_time=max(valid_times) if valid_times else 0,
            p50_response_time=statistics.median(valid_times) if valid_times else 0,
            p95_response_time=valid_times[int(len(valid_times) * 0.95)] if valid_times else 0,
            p99_response_time=valid_times[int(len(valid_times) * 0.99)] if valid_times else 0,
            requests_per_second=len(valid_times) / sum(valid_times) if valid_times else 0,
            error_rate=(len(response_times) - len(valid_times)) / len(response_times)
        )
    
    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all benchmark tests."""
        results = []
        
        # Phase 3 retrieval benchmark
        result3 = self.benchmark_phase3_retrieval()
        results.append(result3)
        
        # Phase 4 LLM ranking benchmark
        result4 = self.benchmark_phase4_llm_ranking()
        results.append(result4)
        
        # API endpoints benchmark
        result_api = self.benchmark_api_endpoints()
        results.append(result_api)
        
        return results


class LoadTester:
    """Load testing suite."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.logger = get_logger()
        self.metrics = get_metrics()
        self.performance_tracker = get_performance_tracker()
        
        # Test data
        self.benchmark = PerformanceBenchmark()
        self.test_preferences = self.benchmark.test_preferences
        
        # Results storage
        self.results = []
        self.active_threads = []
        self.stop_event = threading.Event()
    
    def run_load_test(self) -> BenchmarkResult:
        """Run load test with specified configuration."""
        self.logger.info("load_test", "started", 
                        f"Starting load test: {self.config.concurrent_users} users, "
                        f"{self.config.requests_per_user} requests per user")
        
        # Clear previous results
        self.results = []
        self.stop_event.clear()
        
        start_time = time.time()
        
        # Start user threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_users) as executor:
            futures = []
            
            for user_id in range(self.config.concurrent_users):
                future = executor.submit(self._simulate_user, user_id)
                futures.append(future)
            
            # Wait for all users to complete
            concurrent.futures.wait(futures)
        
        total_time = time.time() - start_time
        
        # Calculate aggregate metrics
        all_response_times = [r for result in self.results for r in result.response_times if r is not None]
        
        if not all_response_times:
            return BenchmarkResult(
                test_name="load_test",
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                requests_per_second=0,
                error_rate=0
            )
        
        return BenchmarkResult(
            test_name="load_test",
            total_requests=len(self.results) * self.config.requests_per_user,
            successful_requests=len(all_response_times),
            failed_requests=len(self.results) * self.config.requests_per_user - len(all_response_times),
            avg_response_time=statistics.mean(all_response_times),
            min_response_time=min(all_response_times),
            max_response_time=max(all_response_times),
            p50_response_time=statistics.median(all_response_times),
            p95_response_time=all_response_times[int(len(all_response_times) * 0.95)],
            p99_response_time=all_response_times[int(len(all_response_times) * 0.99)],
            requests_per_second=len(all_response_times) / total_time,
            error_rate=(len(self.results) * self.config.requests_per_user - len(all_response_times)) / (len(self.results) * self.config.requests_per_user)
        )
    
    def _simulate_user(self, user_id: int):
        """Simulate a single user's activity."""
        response_times = []
        
        # Ramp up delay
        ramp_delay = (self.config.ramp_up_time / self.config.concurrent_users) * user_id
        time.sleep(ramp_delay)
        
        for request_id in range(self.config.requests_per_user):
            if self.stop_event.is_set():
                break
            
            start_time = time.time()
            
            try:
                # Simulate API request
                preference = random.choice(self.test_preferences)
                request_data = {
                    "preferences": {
                        "location": preference.location,
                        "min_rating": preference.min_rating,
                        "budget": asdict(preference.budget) if preference.budget else None
                    },
                    "top_n": 10
                }
                
                response = self.benchmark.api_client.post("/recommendations", json=request_data)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    response_times.append(duration)
                    self.metrics.record_histogram("load_test_request_duration", duration)
                else:
                    response_times.append(None)
                
                # Think time between requests
                think_time = random.uniform(0.1, 1.0)
                time.sleep(think_time)
                
            except Exception as e:
                self.logger.error("load_test", "user_request_failed",
                                f"User {user_id} request {request_id} failed: {e}")
                response_times.append(None)
        
        # Store results for this user
        self.results.append(UserTestResult(user_id, response_times))


@dataclass
class UserTestResult:
    """Result for a single user in load test."""
    user_id: int
    response_times: List[Optional[float]]


class BenchmarkReporter:
    """Generate benchmark reports."""
    
    def __init__(self):
        self.logger = get_logger()
    
    def generate_report(self, results: List[BenchmarkResult]) -> str:
        """Generate comprehensive benchmark report."""
        report = []
        report.append("# Performance Benchmark Report")
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        # Summary table
        report.append("## Summary")
        report.append("| Test | Requests/s | Avg Response Time (s) | P95 Response Time (s) | Error Rate | Status |")
        report.append("|------|------------|----------------------|----------------------|------------|--------|")
        
        for result in results:
            status = "PASS"
            if result.error_rate > 0.05:
                status = "FAIL"
            elif result.avg_response_time > 2.0:
                status = "WARN"
            
            report.append(f"| {result.test_name} | {result.requests_per_second:.2f} | "
                         f"{result.avg_response_time:.3f} | {result.p95_response_time:.3f} | "
                         f"{result.error_rate:.2%} | {status} |")
        
        report.append("")
        
        # Detailed results
        for result in results:
            report.append(f"## {result.test_name}")
            report.append(f"- **Total Requests**: {result.total_requests}")
            report.append(f"- **Successful Requests**: {result.successful_requests}")
            report.append(f"- **Failed Requests**: {result.failed_requests}")
            report.append(f"- **Average Response Time**: {result.avg_response_time:.3f}s")
            report.append(f"- **Min Response Time**: {result.min_response_time:.3f}s")
            report.append(f"- **Max Response Time**: {result.max_response_time:.3f}s")
            report.append(f"- **P50 Response Time**: {result.p50_response_time:.3f}s")
            report.append(f"- **P95 Response Time**: {result.p95_response_time:.3f}s")
            report.append(f"- **P99 Response Time**: {result.p99_response_time:.3f}s")
            report.append(f"- **Requests per Second**: {result.requests_per_second:.2f}")
            report.append(f"- **Error Rate**: {result.error_rate:.2%}")
            report.append("")
        
        return "\n".join(report)
    
    def save_report(self, results: List[BenchmarkResult], filename: str = "benchmark_report.md"):
        """Save benchmark report to file."""
        report = self.generate_report(results)
        
        with open(filename, 'w') as f:
            f.write(report)
        
        self.logger.info("benchmark_reporter", "report_saved",
                        f"Benchmark report saved to {filename}")
    
    def compare_results(self, baseline: List[BenchmarkResult], current: List[BenchmarkResult]) -> str:
        """Compare benchmark results with baseline."""
        report = []
        report.append("# Benchmark Comparison Report")
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        # Create lookup dictionaries
        baseline_dict = {r.test_name: r for r in baseline}
        current_dict = {r.test_name: r for r in current}
        
        report.append("## Performance Comparison")
        report.append("| Test | Metric | Baseline | Current | Change | Status |")
        report.append("|------|--------|----------|---------|--------|--------|")
        
        for test_name in baseline_dict:
            if test_name not in current_dict:
                continue
            
            baseline_result = baseline_dict[test_name]
            current_result = current_dict[test_name]
            
            # Compare key metrics
            metrics = [
                ("RPS", baseline_result.requests_per_second, current_result.requests_per_second),
                ("Avg Time", baseline_result.avg_response_time, current_result.avg_response_time),
                ("P95 Time", baseline_result.p95_response_time, current_result.p95_response_time),
                ("Error Rate", baseline_result.error_rate, current_result.error_rate)
            ]
            
            for metric_name, baseline_val, current_val in metrics:
                if baseline_val == 0:
                    change_pct = "N/A"
                else:
                    change_pct = ((current_val - baseline_val) / baseline_val) * 100
                
                # Determine status
                status = "STABLE"
                if metric_name in ["Avg Time", "P95 Time", "Error Rate"]:
                    if change_pct != "N/A" and change_pct > 10:
                        status = "DEGRADED"
                    elif change_pct != "N/A" and change_pct < -10:
                        status = "IMPROVED"
                else:  # RPS
                    if change_pct != "N/A" and change_pct < -10:
                        status = "DEGRADED"
                    elif change_pct != "N/A" and change_pct > 10:
                        status = "IMPROVED"
                
                if isinstance(change_pct, float):
                    change_str = f"{change_pct:+.1f}%"
                else:
                    change_str = change_pct
                
                report.append(f"| {test_name} | {metric_name} | {baseline_val:.3f} | "
                             f"{current_val:.3f} | {change_str} | {status} |")
        
        report.append("")
        return "\n".join(report)


def run_performance_benchmarks() -> List[BenchmarkResult]:
    """Run all performance benchmarks."""
    benchmark = PerformanceBenchmark()
    return benchmark.run_all_benchmarks()


def run_load_test(config: LoadTestConfig = None) -> BenchmarkResult:
    """Run load test with specified configuration."""
    if config is None:
        config = LoadTestConfig()
    
    load_tester = LoadTester(config)
    return load_tester.run_load_test()


if __name__ == "__main__":
    # Run benchmarks
    print("Running performance benchmarks...")
    benchmark_results = run_performance_benchmarks()
    
    # Generate report
    reporter = BenchmarkReporter()
    report = reporter.generate_report(benchmark_results)
    print(report)
    
    # Save report
    reporter.save_report(benchmark_results)
    
    # Run load test
    print("\nRunning load test...")
    load_test_config = LoadTestConfig(
        concurrent_users=5,
        requests_per_user=20,
        ramp_up_time=10
    )
    load_test_result = run_load_test(load_test_config)
    
    print(f"\nLoad Test Results:")
    print(f"RPS: {load_test_result.requests_per_second:.2f}")
    print(f"Avg Response Time: {load_test_result.avg_response_time:.3f}s")
    print(f"Error Rate: {load_test_result.error_rate:.2%}")
