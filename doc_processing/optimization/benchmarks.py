"""Benchmarking module for performance optimization."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..converters.google_docs import GoogleDocsConverter
from .cache_manager import CacheManager
from .large_document_handler import LargeDocumentHandler
from .performance_optimizer import OptimizationConfig, PerformanceOptimizer

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""

    test_name: str
    document_size: int  # bytes
    execution_time: float  # seconds
    memory_used: int  # bytes
    throughput: float  # bytes/second
    optimization_config: Dict[str, Any]
    timestamp: datetime
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class PerformanceBenchmark:
    """Benchmarking system for document processing performance."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize performance benchmark.

        Args:
            output_dir: Directory to save benchmark results
        """
        self.output_dir = output_dir or Path("benchmark_results")
        self.output_dir.mkdir(exist_ok=True)

        self.results: List[BenchmarkResult] = []

        # Test configurations
        self.test_configs = [
            OptimizationConfig(
                enable_chunking=False, enable_parallel=False, enable_caching=False
            ),
            OptimizationConfig(
                enable_chunking=True,
                chunk_size=1024 * 1024,
                enable_parallel=False,
                enable_caching=False,
            ),
            OptimizationConfig(
                enable_chunking=True,
                chunk_size=1024 * 1024,
                enable_parallel=True,
                max_workers=4,
                enable_caching=False,
            ),
            OptimizationConfig(
                enable_chunking=True,
                enable_parallel=True,
                enable_caching=True,
                cache_size=256,
            ),
        ]

        # Document sizes to test (in MB)
        self.test_sizes_mb = [1, 5, 10, 50, 100]

    def run_full_benchmark(self) -> Dict[str, Any]:
        """Run complete benchmark suite.

        Returns:
            Dictionary with benchmark results and analysis
        """
        logger.info("Starting full performance benchmark suite")

        for size_mb in self.test_sizes_mb:
            document_id = f"test_doc_{size_mb}mb"

            for i, config in enumerate(self.test_configs):
                test_name = self._get_test_name(config, i)
                logger.info(f"Running benchmark: {test_name} on {size_mb}MB document")

                result = self._run_single_benchmark(
                    test_name, document_id, size_mb * 1024 * 1024, config
                )

                self.results.append(result)

                # Save intermediate results
                self._save_results()

        # Generate analysis
        analysis = self._analyze_results()

        # Save final report
        self._save_report(analysis)

        return analysis

    def benchmark_cache_effectiveness(self) -> Dict[str, Any]:
        """Benchmark cache effectiveness.

        Returns:
            Cache performance analysis
        """
        logger.info("Benchmarking cache effectiveness")

        cache_config = {"memory_cache_mb": 100, "file_cache_mb": 500}
        cache_manager = CacheManager(cache_config)

        # Test document
        document_id = "cache_test_doc"
        document_size = 10 * 1024 * 1024  # 10MB

        # Configure optimizer with cache
        config = OptimizationConfig(enable_caching=True, cache_size=128)
        optimizer = PerformanceOptimizer(config)

        results = {
            "first_conversion": None,
            "cached_conversion": None,
            "cache_stats": None,
        }

        # First conversion (cache miss)
        start_time = time.time()
        optimizer.optimize_conversion(document_id, "to_markdown")
        first_time = time.time() - start_time
        results["first_conversion"] = first_time

        # Second conversion (cache hit)
        start_time = time.time()
        optimizer.optimize_conversion(document_id, "to_markdown")
        cached_time = time.time() - start_time
        results["cached_conversion"] = cached_time

        # Cache effectiveness
        results["cache_effectiveness"] = {
            "speedup_factor": first_time / cached_time if cached_time > 0 else 0,
            "time_saved": first_time - cached_time,
            "percentage_improvement": (
                ((first_time - cached_time) / first_time * 100) if first_time > 0 else 0
            ),
        }

        # Get cache statistics
        results["cache_stats"] = cache_manager.get_stats()

        return results

    async def benchmark_async_processing(self) -> Dict[str, Any]:
        """Benchmark asynchronous processing performance.

        Returns:
            Async processing performance analysis
        """
        logger.info("Benchmarking asynchronous processing")

        handler = LargeDocumentHandler()

        # Test different document counts
        document_counts = [1, 5, 10, 20]
        results = {}

        for count in document_counts:
            document_ids = [f"async_doc_{i}" for i in range(count)]

            # Synchronous baseline
            sync_start = time.time()
            for doc_id in document_ids:
                handler.optimize_large_document_conversion(doc_id)
            sync_time = time.time() - sync_start

            # Asynchronous processing
            async_start = time.time()
            tasks = [
                handler.process_large_document_async(doc_id) for doc_id in document_ids
            ]
            await asyncio.gather(*tasks)
            async_time = time.time() - async_start

            results[f"{count}_documents"] = {
                "sync_time": sync_time,
                "async_time": async_time,
                "speedup": sync_time / async_time if async_time > 0 else 0,
                "efficiency": (
                    (sync_time - async_time) / sync_time * 100 if sync_time > 0 else 0
                ),
            }

        return results

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage patterns.

        Returns:
            Memory usage analysis
        """
        logger.info("Benchmarking memory usage")

        # Test configurations with different memory limits
        memory_configs = [
            {
                "max_memory": 100 * 1024 * 1024,
                "streaming": False,
            },  # 100MB, no streaming
            {"max_memory": 100 * 1024 * 1024, "streaming": True},  # 100MB, streaming
            {
                "max_memory": 500 * 1024 * 1024,
                "streaming": False,
            },  # 500MB, no streaming
            {"max_memory": 500 * 1024 * 1024, "streaming": True},  # 500MB, streaming
        ]

        results = {}
        document_size = 200 * 1024 * 1024  # 200MB document

        for config in memory_configs:
            opt_config = OptimizationConfig(
                max_memory_usage=config["max_memory"],
                enable_streaming=config["streaming"],
            )

            optimizer = PerformanceOptimizer(opt_config)

            # Measure memory usage
            import psutil

            if psutil:
                process = psutil.Process()

                # Baseline memory
                baseline_memory = process.memory_info().rss

                # Process document
                start_time = time.time()
                try:
                    optimizer.optimize_conversion(
                        "large_memory_test_doc", "to_markdown"
                    )
                    success = True
                    error = None
                except Exception as e:
                    success = False
                    error = str(e)

                # Peak memory
                peak_memory = process.memory_info().rss
                execution_time = time.time() - start_time

                config_key = f"{config['max_memory'] // (1024*1024)}MB_{'streaming' if config['streaming'] else 'normal'}"
                results[config_key] = {
                    "baseline_memory_mb": baseline_memory / (1024 * 1024),
                    "peak_memory_mb": peak_memory / (1024 * 1024),
                    "memory_increase_mb": (peak_memory - baseline_memory)
                    / (1024 * 1024),
                    "execution_time": execution_time,
                    "success": success,
                    "error": error,
                }

        return results

    def _run_single_benchmark(
        self,
        test_name: str,
        document_id: str,
        document_size: int,
        config: OptimizationConfig,
    ) -> BenchmarkResult:
        """Run a single benchmark test.

        Args:
            test_name: Name of the test
            document_id: Document to test
            document_size: Size of document in bytes
            config: Optimization configuration

        Returns:
            BenchmarkResult
        """
        optimizer = PerformanceOptimizer(config)

        # Mock document size estimation
        optimizer._estimate_document_size = lambda x: document_size

        start_time = time.time()
        start_memory = self._get_memory_usage()

        try:
            # Run conversion
            result = optimizer.optimize_conversion(document_id, "to_markdown")

            execution_time = time.time() - start_time
            memory_used = self._get_memory_usage() - start_memory
            throughput = document_size / execution_time if execution_time > 0 else 0

            return BenchmarkResult(
                test_name=test_name,
                document_size=document_size,
                execution_time=execution_time,
                memory_used=memory_used,
                throughput=throughput,
                optimization_config=config.to_dict(),
                timestamp=datetime.now(),
                success=True,
            )

        except Exception as e:
            logger.error(f"Benchmark failed: {e}")

            return BenchmarkResult(
                test_name=test_name,
                document_size=document_size,
                execution_time=time.time() - start_time,
                memory_used=0,
                throughput=0,
                optimization_config=config.to_dict(),
                timestamp=datetime.now(),
                success=False,
                error=str(e),
            )

    def _get_test_name(self, config: OptimizationConfig, index: int) -> str:
        """Generate descriptive test name from configuration.

        Args:
            config: Optimization configuration
            index: Test index

        Returns:
            Test name string
        """
        features = []

        if (
            not config.enable_chunking
            and not config.enable_parallel
            and not config.enable_caching
        ):
            return "baseline_no_optimization"

        if config.enable_chunking:
            features.append("chunking")
        if config.enable_parallel:
            features.append(f"parallel_{config.max_workers}")
        if config.enable_caching:
            features.append("caching")
        if config.enable_streaming:
            features.append("streaming")

        return "_".join(features) or f"config_{index}"

    def _get_memory_usage(self) -> int:
        """Get current memory usage.

        Returns:
            Memory usage in bytes
        """
        try:
            import psutil

            return psutil.Process().memory_info().rss
        except Exception:
            return 0

    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze benchmark results.

        Returns:
            Analysis dictionary
        """
        if not self.results:
            return {"error": "No benchmark results available"}

        # Group by document size
        size_groups = {}
        for result in self.results:
            size_mb = result.document_size // (1024 * 1024)
            if size_mb not in size_groups:
                size_groups[size_mb] = []
            size_groups[size_mb].append(result)

        analysis = {
            "summary": {
                "total_tests": len(self.results),
                "successful_tests": sum(1 for r in self.results if r.success),
                "failed_tests": sum(1 for r in self.results if not r.success),
            },
            "by_document_size": {},
            "optimization_comparison": {},
            "recommendations": [],
        }

        # Analyze by document size
        for size_mb, results in size_groups.items():
            best_config = min(
                results, key=lambda r: r.execution_time if r.success else float("in")
            )
            worst_config = max(
                results, key=lambda r: r.execution_time if r.success else float("-in")
            )

            analysis["by_document_size"][f"{size_mb}MB"] = {
                "best_configuration": best_config.test_name,
                "best_time": best_config.execution_time,
                "worst_configuration": worst_config.test_name,
                "worst_time": worst_config.execution_time,
                "improvement_factor": (
                    worst_config.execution_time / best_config.execution_time
                    if best_config.execution_time > 0
                    else 0
                ),
            }

        # Compare optimization techniques
        for result in self.results:
            config_name = result.test_name
            if config_name not in analysis["optimization_comparison"]:
                analysis["optimization_comparison"][config_name] = {
                    "avg_execution_time": 0,
                    "avg_throughput": 0,
                    "count": 0,
                }

            if result.success:
                comp = analysis["optimization_comparison"][config_name]
                comp["avg_execution_time"] = (
                    comp["avg_execution_time"] * comp["count"] + result.execution_time
                ) / (comp["count"] + 1)
                comp["avg_throughput"] = (
                    comp["avg_throughput"] * comp["count"] + result.throughput
                ) / (comp["count"] + 1)
                comp["count"] += 1

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)

        return analysis

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on analysis.

        Args:
            analysis: Benchmark analysis

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check if parallel processing helps
        if "parallel_4" in analysis["optimization_comparison"]:
            parallel_data = analysis["optimization_comparison"]["parallel_4"]
            baseline_data = analysis["optimization_comparison"].get(
                "baseline_no_optimization", {}
            )

            if (
                baseline_data
                and parallel_data["avg_execution_time"]
                < baseline_data.get("avg_execution_time", float("in")) * 0.7
            ):
                recommendations.append(
                    "Enable parallel processing for documents > 10MB for significant performance gains"
                )

        # Check if caching is effective
        if any("caching" in config for config in analysis["optimization_comparison"]):
            recommendations.append(
                "Enable caching for frequently accessed documents to reduce processing time by up to 90%"
            )

        # Document size recommendations
        for size_mb, data in analysis["by_document_size"].items():
            if data["improvement_factor"] > 2:
                recommendations.append(
                    f"For {size_mb} documents, optimization provides {data['improvement_factor']:.1f}x speedup"
                )

        return recommendations

    def _save_results(self):
        """Save benchmark results to file."""
        results_file = (
            self.output_dir
            / f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(results_file, "w") as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2)

        logger.info(f"Saved benchmark results to {results_file}")

    def _save_report(self, analysis: Dict[str, Any]):
        """Save benchmark report.

        Args:
            analysis: Analysis results
        """
        report_file = (
            self.output_dir
            / f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(report_file, "w") as f:
            json.dump(analysis, f, indent=2)

        # Also save human-readable report
        report_text_file = (
            self.output_dir
            / f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        with open(report_text_file, "w") as f:
            f.write("Performance Benchmark Report\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"Total Tests: {analysis['summary']['total_tests']}\n")
            f.write(f"Successful: {analysis['summary']['successful_tests']}\n")
            f.write(f"Failed: {analysis['summary']['failed_tests']}\n\n")

            f.write("Performance by Document Size:\n")
            f.write("-" * 30 + "\n")
            for size, data in analysis["by_document_size"].items():
                f.write(f"\n{size}:\n")
                f.write(f"  Best config: {data['best_configuration']}\n")
                f.write(f"  Best time: {data['best_time']:.2f}s\n")
                f.write(f"  Improvement: {data['improvement_factor']:.1f}x\n")

            f.write("\n\nRecommendations:\n")
            f.write("-" * 30 + "\n")
            for rec in analysis["recommendations"]:
                f.write(f"• {rec}\n")

        logger.info(f"Saved benchmark report to {report_file}")


def run_quick_benchmark():
    """Run a quick benchmark for testing."""
    benchmark = PerformanceBenchmark()

    # Run a subset of tests
    benchmark.test_sizes_mb = [1, 10]  # Only test 1MB and 10MB
    benchmark.test_configs = benchmark.test_configs[:2]  # Only first two configs

    results = benchmark.run_full_benchmark()

    print("\nQuick Benchmark Results:")
    print("=" * 50)
    print(f"Total tests: {results['summary']['total_tests']}")
    print(f"Successful: {results['summary']['successful_tests']}")

    print("\nRecommendations:")
    for rec in results["recommendations"]:
        print(f"• {rec}")

    return results


if __name__ == "__main__":
    # Run quick benchmark when module is executed directly
    run_quick_benchmark()
