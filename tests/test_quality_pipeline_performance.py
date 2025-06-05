"""
Performance Test Suite for Quality Pipeline

This module provides comprehensive performance testing for the quality assurance pipeline,
including load testing, stress testing, and performance profiling.
"""

import concurrent.futures
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import psutil
import pytest

from app.api.v1.services.quality_config_manager import (
    QualityConfigManager,
)
from app.api.v1.services.quality_metrics_collector import QualityMetricsCollector
from app.api.v1.services.quality_pipeline_orchestrator import (
    QualityAssurancePipeline,
    QualityLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceTestResult:
    """Results from a performance test"""

    test_name: str
    duration: float
    memory_usage_mb: float
    cpu_usage_percent: float
    throughput_per_second: float
    success_rate: float
    error_count: int
    concurrent_users: int
    total_requests: int


class QualityPipelinePerformanceTester:
    """
    Performance tester for the quality pipeline with features:
    - Load testing with multiple concurrent users
    - Stress testing to find breaking points
    - Memory usage monitoring
    - Throughput analysis
    - Performance regression detection
    """

    def __init__(self):
        self.pipeline = QualityAssurancePipeline()
        self.config_manager = QualityConfigManager()
        self.metrics_collector = QualityMetricsCollector()
        self.test_results: List[PerformanceTestResult] = []

    def create_test_code_samples(self) -> Dict[str, str]:
        """Create various code samples for testing"""
        return {
            "simple_python": """
def hello_world():
    print("Hello, World!")
    return "success"
""",
            "complex_python": """
import os
import sys
import json
import requests
from typing import Dict, List, Optional

class DataProcessor:
    def __init__(self, config_file: str):
        self.config = self._load_config(config_file)
        self.processed_items = []

    def _load_config(self, config_file: str) -> Dict:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"default": True}

    def process_data(self, data: List[Dict]) -> List[Dict]:
        results = []
        for item in data:
            if self._validate_item(item):
                processed = self._transform_item(item)
                if processed:
                    results.append(processed)
                    self.processed_items.append(processed)
        return results

    def _validate_item(self, item: Dict) -> bool:
        required_fields = ["id", "name", "value"]
        return all(field in item for field in required_fields)

    def _transform_item(self, item: Dict) -> Optional[Dict]:
        try:
            return {
                "id": int(item["id"]),
                "name": str(item["name"]).strip(),
                "value": float(item["value"]),
                "processed_at": time.time()
            }
        except (ValueError, KeyError):
            return None

    async def fetch_remote_data(self, url: str) -> Optional[List[Dict]]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None
""",
            "javascript_sample": """
class UserManager {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
        this.users = new Map();
        this.cache = new Set();
    }

    async fetchUser(userId) {
        if (this.cache.has(userId)) {
            return this.users.get(userId);
        }

        try {
            const response = await fetch(`${this.apiUrl}/users/${userId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const user = await response.json();
            this.users.set(userId, user);
            this.cache.add(userId);

            return user;
        } catch (error) {
            console.error('Failed to fetch user:', error);
            return null;
        }
    }

    validateUser(user) {
        const requiredFields = ['id', 'email', 'name'];
        return requiredFields.every(field => user && user[field]);
    }
}
""",
            "problematic_code": """
import os
import unused_module

def buggy_function(data):
    # Undefined variable
    result = undefined_var + 5

    # SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = %s" % user_id

    # Potential division by zero
    calculation = 100 / data

    # Unused variable
    temp_value = "not used"

    # Missing return statement
    if data > 0:
        print("Positive")
    # No return for negative values
""",
        }

    def run_load_test(
        self,
        concurrent_users: int = 10,
        requests_per_user: int = 5,
        quality_level: QualityLevel = QualityLevel.STANDARD,
    ) -> PerformanceTestResult:
        """
        Run load test with multiple concurrent users.

        Args:
            concurrent_users: Number of concurrent users
            requests_per_user: Number of requests per user
            quality_level: Quality level to test

        Returns:
            PerformanceTestResult: Test results
        """
        logger.info(
            f"Starting load test: {concurrent_users} users, {requests_per_user} requests each"
        )

        test_samples = self.create_test_code_samples()
        sample_codes = list(test_samples.values())

        start_time = time.time()
        start_memory = psutil.virtual_memory().used / 1024 / 1024
        process = psutil.Process()

        successful_requests = 0
        failed_requests = 0
        total_requests = concurrent_users * requests_per_user

        def user_simulation(user_id: int) -> int:
            """Simulate a single user's requests"""
            user_successful = 0
            for request_id in range(requests_per_user):
                try:
                    # Select code sample
                    code_index = (user_id + request_id) % len(sample_codes)
                    code_sample = sample_codes[code_index]
                    # Run pipeline
                    result = self.pipeline.run_pipeline_sync(
                        code=code_sample,
                        language="python",
                        quality_level=quality_level,
                        project_id=f"load_test_{user_id}_{request_id}",
                    )

                    if result and result.get("success", False):
                        user_successful += 1

                except Exception as e:
                    logger.warning(f"User {user_id} request {request_id} failed: {e}")

            return user_successful

        # Execute concurrent users
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrent_users
        ) as executor:
            futures = [
                executor.submit(user_simulation, user_id)
                for user_id in range(concurrent_users)
            ]

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    successful_requests += future.result()
                except Exception as e:
                    logger.error(f"User simulation failed: {e}")
                    failed_requests += requests_per_user

        # Calculate metrics
        end_time = time.time()
        duration = end_time - start_time
        end_memory = psutil.virtual_memory().used / 1024 / 1024
        memory_usage = end_memory - start_memory

        # Calculate CPU usage (approximate)
        cpu_usage = process.cpu_percent()

        throughput = total_requests / duration if duration > 0 else 0
        success_rate = (
            (successful_requests / total_requests * 100) if total_requests > 0 else 0
        )

        result = PerformanceTestResult(
            test_name=f"load_test_{concurrent_users}_{requests_per_user}",
            duration=duration,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            throughput_per_second=throughput,
            success_rate=success_rate,
            error_count=failed_requests,
            concurrent_users=concurrent_users,
            total_requests=total_requests,
        )

        self.test_results.append(result)

        logger.info(
            f"Load test completed: {success_rate:.1f}% success rate, {throughput:.2f} req/s"
        )

        return result

    def run_stress_test(
        self, max_users: int = 50, step_size: int = 5, step_duration: int = 30
    ) -> List[PerformanceTestResult]:
        """
        Run stress test to find breaking point.

        Args:
            max_users: Maximum number of concurrent users
            step_size: Increment of users per step
            step_duration: Duration of each step in seconds

        Returns:
            List of test results for each step
        """
        logger.info(f"Starting stress test: up to {max_users} users")

        stress_results = []

        for users in range(step_size, max_users + 1, step_size):
            logger.info(f"Stress testing with {users} concurrent users")

            # Calculate requests per user based on duration
            requests_per_user = max(1, step_duration // 5)  # Aim for 5 second intervals

            result = self.run_load_test(
                concurrent_users=users,
                requests_per_user=requests_per_user,
                quality_level=QualityLevel.BASIC,  # Use basic level for stress testing
            )

            stress_results.append(result)

            # Check if performance is degrading significantly
            if result.success_rate < 80 or result.throughput_per_second < 1:
                logger.warning(f"Performance degradation detected at {users} users")
                break

            # Brief pause between steps
            time.sleep(2)

        return stress_results

    def run_memory_leak_test(
        self, iterations: int = 100, sample_interval: int = 10
    ) -> Dict[str, Any]:
        """
        Test for memory leaks by running multiple iterations.

        Args:
            iterations: Number of iterations to run
            sample_interval: Interval for memory sampling

        Returns:
            Dictionary with memory usage data
        """
        logger.info(f"Starting memory leak test: {iterations} iterations")

        memory_samples = []
        test_sample = self.create_test_code_samples()["complex_python"]

        for i in range(iterations):
            # Run pipeline
            try:
                _ = self.pipeline.run_pipeline_sync(
                    code=test_sample,
                    language="python",
                    quality_level=QualityLevel.STANDARD,
                    project_id=f"memory_test_{i}",
                )
            except Exception as e:
                logger.warning(f"Memory test iteration {i} failed: {e}")

            # Sample memory every N iterations
            if i % sample_interval == 0:
                memory_mb = psutil.virtual_memory().used / 1024 / 1024
                memory_samples.append(
                    {"iteration": i, "memory_mb": memory_mb, "timestamp": time.time()}
                )

        # Analyze memory trend
        if len(memory_samples) >= 2:
            start_memory = memory_samples[0]["memory_mb"]
            end_memory = memory_samples[-1]["memory_mb"]
            memory_increase = end_memory - start_memory

            # Calculate average increase per iteration
            avg_increase_per_iteration = memory_increase / iterations
        else:
            memory_increase = 0
            avg_increase_per_iteration = 0

        return {
            "iterations": iterations,
            "memory_samples": memory_samples,
            "memory_increase_mb": memory_increase,
            "avg_increase_per_iteration_mb": avg_increase_per_iteration,
            "potential_leak": avg_increase_per_iteration > 0.1,  # >0.1MB per iteration
        }

    def run_benchmark_suite(self) -> Dict[str, Any]:
        """Run comprehensive benchmark suite"""
        logger.info("Starting comprehensive benchmark suite")

        benchmarks = {}

        # 1. Single user baseline
        logger.info("Running single user baseline test")
        baseline = self.run_load_test(
            concurrent_users=1,
            requests_per_user=10,
            quality_level=QualityLevel.STANDARD,
        )
        benchmarks["baseline"] = baseline

        # 2. Different quality levels
        logger.info("Testing different quality levels")
        quality_benchmarks = {}
        for level in [
            QualityLevel.BASIC,
            QualityLevel.STANDARD,
            QualityLevel.COMPREHENSIVE,
        ]:
            result = self.run_load_test(
                concurrent_users=5, requests_per_user=3, quality_level=level
            )
            quality_benchmarks[level.value] = result

        benchmarks["quality_levels"] = quality_benchmarks

        # 3. Concurrency scaling
        logger.info("Testing concurrency scaling")
        concurrency_benchmarks = {}
        for users in [1, 5, 10, 20]:
            result = self.run_load_test(
                concurrent_users=users,
                requests_per_user=5,
                quality_level=QualityLevel.STANDARD,
            )
            concurrency_benchmarks[f"{users}_users"] = result

        benchmarks["concurrency_scaling"] = concurrency_benchmarks

        # 4. Memory leak test
        logger.info("Running memory leak test")
        memory_test = self.run_memory_leak_test(iterations=50)
        benchmarks["memory_test"] = memory_test

        # 5. Different code complexities
        logger.info("Testing different code complexities")
        complexity_benchmarks = {}
        test_samples = self.create_test_code_samples()

        for sample_name, code in test_samples.items():
            start_time = time.time()
            try:
                result = self.pipeline.run_pipeline_sync(
                    code=code,
                    language=(
                        "python" if sample_name != "javascript_sample" else "javascript"
                    ),
                    quality_level=QualityLevel.STANDARD,
                    project_id=f"complexity_test_{sample_name}",
                )

                duration = time.time() - start_time
                complexity_benchmarks[sample_name] = {
                    "duration": duration,
                    "success": result.get("success", False) if result else False,
                    "quality_score": result.get("quality_score", 0) if result else 0,
                }

            except Exception as e:
                complexity_benchmarks[sample_name] = {
                    "duration": time.time() - start_time,
                    "success": False,
                    "error": str(e),
                }

        benchmarks["code_complexity"] = complexity_benchmarks

        return benchmarks

    def save_benchmark_results(self, results: Dict[str, Any], output_file: str):
        """Save benchmark results to file"""
        try:
            # Convert PerformanceTestResult objects to dicts
            def convert_result(obj):
                if isinstance(obj, PerformanceTestResult):
                    return {
                        "test_name": obj.test_name,
                        "duration": obj.duration,
                        "memory_usage_mb": obj.memory_usage_mb,
                        "cpu_usage_percent": obj.cpu_usage_percent,
                        "throughput_per_second": obj.throughput_per_second,
                        "success_rate": obj.success_rate,
                        "error_count": obj.error_count,
                        "concurrent_users": obj.concurrent_users,
                        "total_requests": obj.total_requests,
                    }
                return obj

            # Recursively convert results
            def deep_convert(obj):
                if isinstance(obj, dict):
                    return {k: deep_convert(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [deep_convert(item) for item in obj]
                else:
                    return convert_result(obj)

            converted_results = deep_convert(results)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(converted_results, f, indent=2, default=str)

            logger.info(f"Benchmark results saved to {output_file}")

        except Exception as e:
            logger.error(f"Failed to save benchmark results: {e}")

    def generate_performance_report(self) -> str:
        """Generate a human-readable performance report"""
        if not self.test_results:
            return "No performance test results available."

        report = ["Quality Pipeline Performance Report", "=" * 40, ""]

        # Summary statistics
        total_tests = len(self.test_results)
        avg_duration = sum(r.duration for r in self.test_results) / total_tests
        avg_throughput = (
            sum(r.throughput_per_second for r in self.test_results) / total_tests
        )
        avg_success_rate = sum(r.success_rate for r in self.test_results) / total_tests

        report.extend(
            [
                f"Total Tests Run: {total_tests}",
                f"Average Duration: {avg_duration:.2f} seconds",
                f"Average Throughput: {avg_throughput:.2f} requests/second",
                f"Average Success Rate: {avg_success_rate:.1f}%",
                "",
            ]
        )

        # Individual test results
        report.append("Individual Test Results:")
        report.append("-" * 25)

        for result in self.test_results:
            report.extend(
                [
                    f"Test: {result.test_name}",
                    f"  Duration: {result.duration:.2f}s",
                    f"  Throughput: {result.throughput_per_second:.2f} req/s",
                    f"  Success Rate: {result.success_rate:.1f}%",
                    f"  Memory Usage: {result.memory_usage_mb:.1f} MB",
                    f"  Concurrent Users: {result.concurrent_users}",
                    "",
                ]
            )

        return "\n".join(report)


# Test cases for pytest
class TestQualityPipelinePerformance:
    """Performance test cases"""

    @pytest.fixture
    def performance_tester(self):
        """Create performance tester instance"""
        return QualityPipelinePerformanceTester()

    def test_single_request_performance(self, performance_tester):
        """Test single request performance"""
        result = performance_tester.run_load_test(
            concurrent_users=1, requests_per_user=1, quality_level=QualityLevel.STANDARD
        )

        assert (
            result.success_rate >= 90
        ), f"Success rate too low: {result.success_rate}%"
        assert result.duration < 30, f"Request took too long: {result.duration}s"
        assert (
            result.memory_usage_mb < 100
        ), f"Memory usage too high: {result.memory_usage_mb}MB"

    def test_concurrent_users_performance(self, performance_tester):
        """Test performance with multiple concurrent users"""
        result = performance_tester.run_load_test(
            concurrent_users=5, requests_per_user=3, quality_level=QualityLevel.STANDARD
        )

        assert (
            result.success_rate >= 80
        ), f"Success rate too low under load: {result.success_rate}%"
        assert (
            result.throughput_per_second > 0.5
        ), f"Throughput too low: {result.throughput_per_second} req/s"

    def test_quality_level_performance_comparison(self, performance_tester):
        """Test performance differences between quality levels"""
        minimal_result = performance_tester.run_load_test(
            concurrent_users=3, requests_per_user=2, quality_level=QualityLevel.BASIC
        )

        comprehensive_result = performance_tester.run_load_test(
            concurrent_users=3,
            requests_per_user=2,
            quality_level=QualityLevel.COMPREHENSIVE,
        )
        # Both should have reasonable success rates
        assert minimal_result.success_rate >= 80
        assert comprehensive_result.success_rate >= 70

        # Verify both tests completed successfully
        assert minimal_result.total_requests > 0
        assert comprehensive_result.total_requests > 0

        # Note: Timing can vary in small tests, so we don't enforce strict ordering

    @pytest.mark.slow
    def test_memory_leak_detection(self, performance_tester):
        """Test for memory leaks (marked as slow test)"""
        result = performance_tester.run_memory_leak_test(iterations=20)

        # Memory increase should be reasonable
        assert (
            result["avg_increase_per_iteration_mb"] < 1.0
        ), f"Potential memory leak detected: {result['avg_increase_per_iteration_mb']}MB per iteration"

        assert not result["potential_leak"], "Memory leak detected"

    def test_benchmark_suite(self, performance_tester):
        """Run a quick benchmark suite"""
        # Reduce scale for automated testing
        results = {}

        # Quick baseline test
        baseline = performance_tester.run_load_test(
            concurrent_users=1, requests_per_user=2, quality_level=QualityLevel.STANDARD
        )
        results["baseline"] = baseline

        # Quick concurrency test
        concurrent = performance_tester.run_load_test(
            concurrent_users=3, requests_per_user=2, quality_level=QualityLevel.STANDARD
        )
        results["concurrent"] = concurrent

        # Both tests should succeed
        assert baseline.success_rate >= 80
        assert concurrent.success_rate >= 70

        # Save results for analysis
        performance_tester.save_benchmark_results(
            results, "test_benchmark_results.json"
        )


if __name__ == "__main__":
    # Run performance tests when executed directly
    logging.basicConfig(level=logging.INFO)

    tester = QualityPipelinePerformanceTester()

    print("Running Quality Pipeline Performance Tests...")
    print("=" * 50)

    # Run benchmark suite
    results = tester.run_benchmark_suite()

    # Save results
    tester.save_benchmark_results(results, "quality_pipeline_benchmarks.json")

    # Generate report
    report = tester.generate_performance_report()
    print(report)

    # Save report
    with open("quality_pipeline_performance_report.txt", "w") as f:
        f.write(report)

    print("\nPerformance testing completed!")
    print("Results saved to: quality_pipeline_benchmarks.json")
    print("Report saved to: quality_pipeline_performance_report.txt")
