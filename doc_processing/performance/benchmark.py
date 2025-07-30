"""Performance benchmarking system for document processing."""

import asyncio
import json
import logging
import resource
import statistics
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    name: str
    duration_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    operations_per_second: float
    throughput_mb_per_second: float
    error_rate_percent: float
    timestamp: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    name: str
    iterations: int = 10
    warmup_iterations: int = 3
    timeout_seconds: float = 300
    max_memory_mb: float = 1024
    max_cpu_percent: float = 90
    concurrent_workers: int = 1
    data_size_mb: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PerformanceMonitor:
    """Monitor system performance during benchmarks."""

    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self.monitoring = False
        self.measurements: List[Dict[str, Any]] = []
        self.monitor_task: Optional[asyncio.Task] = None
        self.start_time: Optional[float] = None
        self.process = psutil.Process()

    async def start_monitoring(self):
        """Start performance monitoring."""
        if self.monitoring:
            return

        self.monitoring = True
        self.measurements = []
        self.start_time = time.time()
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.monitoring:
            return

        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                measurement = {
                    "timestamp": time.time() - self.start_time,
                    "cpu_percent": self.process.cpu_percent(),
                    "memory_mb": self.process.memory_info().rss / (1024 * 1024),
                    "memory_percent": self.process.memory_percent(),
                    "threads": self.process.num_threads(),
                    "open_files": len(self.process.open_files()),
                    "connections": len(self.process.connections()),
                }

                self.measurements.append(measurement)
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(self.interval)

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.measurements:
            return {}

        cpu_values = [m["cpu_percent"] for m in self.measurements]
        memory_values = [m["memory_mb"] for m in self.measurements]

        return {
            "duration_seconds": (
                self.measurements[-1]["timestamp"] if self.measurements else 0
            ),
            "cpu_usage": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "mean": statistics.mean(cpu_values),
                "median": statistics.median(cpu_values),
            },
            "memory_usage": {
                "min": min(memory_values),
                "max": max(memory_values),
                "mean": statistics.mean(memory_values),
                "median": statistics.median(memory_values),
            },
            "peak_memory_mb": max(memory_values),
            "average_cpu_percent": statistics.mean(cpu_values),
            "measurement_count": len(self.measurements),
        }


class BenchmarkRunner:
    """Runs performance benchmarks."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.lock = threading.RLock()
        self.active_benchmarks: Dict[str, Any] = {}

    async def run_benchmark(
        self,
        name: str,
        benchmark_func: Callable,
        config: BenchmarkConfig,
        *args,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a benchmark.

        Args:
            name: Benchmark name
            benchmark_func: Function to benchmark
            config: Benchmark configuration
            *args: Arguments for benchmark function
            **kwargs: Keyword arguments for benchmark function

        Returns:
            Benchmark result
        """
        logger.info(f"Starting benchmark: {name}")

        # Record start state
        start_time = time.time()
        monitor = PerformanceMonitor()

        with self.lock:
            self.active_benchmarks[name] = {
                "start_time": start_time,
                "config": config,
                "monitor": monitor,
            }

        try:
            # Start monitoring
            await monitor.start_monitoring()

            # Warmup runs
            if config.warmup_iterations > 0:
                logger.info(f"Running {config.warmup_iterations} warmup iterations")
                for i in range(config.warmup_iterations):
                    try:
                        if asyncio.iscoroutinefunction(benchmark_func):
                            await benchmark_func(*args, **kwargs)
                        else:
                            benchmark_func(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"Warmup iteration {i+1} failed: {e}")

            # Main benchmark runs
            logger.info(f"Running {config.iterations} benchmark iterations")
            durations = []
            errors = 0

            for i in range(config.iterations):
                iteration_start = time.time()

                try:
                    if asyncio.iscoroutinefunction(benchmark_func):
                        await benchmark_func(*args, **kwargs)
                    else:
                        benchmark_func(*args, **kwargs)

                    iteration_duration = time.time() - iteration_start
                    durations.append(iteration_duration)

                except Exception as e:
                    errors += 1
                    logger.error(f"Benchmark iteration {i+1} failed: {e}")

                # Check timeout
                if time.time() - start_time > config.timeout_seconds:
                    logger.warning(
                        f"Benchmark {name} timed out after {config.timeout_seconds}s"
                    )
                    break

            # Stop monitoring
            await monitor.stop_monitoring()

            # Calculate results
            total_duration = time.time() - start_time
            performance_summary = monitor.get_summary()

            # Calculate metrics
            avg_duration = statistics.mean(durations) if durations else 0
            operations_per_second = (
                len(durations) / total_duration if total_duration > 0 else 0
            )
            throughput_mb_per_second = (
                (config.data_size_mb * len(durations)) / total_duration
                if total_duration > 0
                else 0
            )
            error_rate = (
                (errors / config.iterations) * 100 if config.iterations > 0 else 0
            )

            result = BenchmarkResult(
                name=name,
                duration_seconds=total_duration,
                memory_usage_mb=performance_summary.get("peak_memory_mb", 0),
                cpu_usage_percent=performance_summary.get("average_cpu_percent", 0),
                operations_per_second=operations_per_second,
                throughput_mb_per_second=throughput_mb_per_second,
                error_rate_percent=error_rate,
                timestamp=datetime.now(),
                metadata={
                    "config": asdict(config),
                    "performance_summary": performance_summary,
                    "iteration_durations": durations,
                    "successful_iterations": len(durations),
                    "failed_iterations": errors,
                    "average_iteration_duration": avg_duration,
                    "min_iteration_duration": min(durations) if durations else 0,
                    "max_iteration_duration": max(durations) if durations else 0,
                },
            )

            with self.lock:
                self.results.append(result)
                if name in self.active_benchmarks:
                    del self.active_benchmarks[name]

            logger.info(
                f"Benchmark {name} completed: {operations_per_second:.2f} ops/sec, {throughput_mb_per_second:.2f} MB/sec"
            )
            return result

        except Exception as e:
            logger.error(f"Benchmark {name} failed: {e}")
            await monitor.stop_monitoring()

            with self.lock:
                if name in self.active_benchmarks:
                    del self.active_benchmarks[name]

            raise

    async def run_concurrent_benchmark(
        self,
        name: str,
        benchmark_func: Callable,
        config: BenchmarkConfig,
        *args,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a concurrent benchmark.

        Args:
            name: Benchmark name
            benchmark_func: Function to benchmark
            config: Benchmark configuration
            *args: Arguments for benchmark function
            **kwargs: Keyword arguments for benchmark function

        Returns:
            Benchmark result
        """
        logger.info(
            f"Starting concurrent benchmark: {name} with {config.concurrent_workers} workers"
        )

        # Create tasks for concurrent execution
        tasks = []
        for i in range(config.concurrent_workers):
            worker_config = BenchmarkConfig(
                name=f"{name}_worker_{i}",
                iterations=config.iterations // config.concurrent_workers,
                warmup_iterations=config.warmup_iterations // config.concurrent_workers,
                timeout_seconds=config.timeout_seconds,
                max_memory_mb=config.max_memory_mb,
                max_cpu_percent=config.max_cpu_percent,
                concurrent_workers=1,
                data_size_mb=config.data_size_mb,
                metadata=config.metadata,
            )

            task = asyncio.create_task(
                self.run_benchmark(
                    f"{name}_worker_{i}", benchmark_func, worker_config, *args, **kwargs
                )
            )
            tasks.append(task)

        # Wait for all tasks to complete
        worker_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        successful_results = [
            r for r in worker_results if isinstance(r, BenchmarkResult)
        ]
        failed_results = [r for r in worker_results if isinstance(r, Exception)]

        if not successful_results:
            raise RuntimeError(f"All concurrent workers failed for benchmark {name}")

        # Calculate aggregate metrics
        total_duration = max(r.duration_seconds for r in successful_results)
        total_operations = sum(
            r.operations_per_second * r.duration_seconds for r in successful_results
        )
        total_throughput = sum(r.throughput_mb_per_second for r in successful_results)
        avg_memory = statistics.mean(r.memory_usage_mb for r in successful_results)
        avg_cpu = statistics.mean(r.cpu_usage_percent for r in successful_results)
        avg_error_rate = statistics.mean(
            r.error_rate_percent for r in successful_results
        )

        aggregate_result = BenchmarkResult(
            name=name,
            duration_seconds=total_duration,
            memory_usage_mb=avg_memory,
            cpu_usage_percent=avg_cpu,
            operations_per_second=(
                total_operations / total_duration if total_duration > 0 else 0
            ),
            throughput_mb_per_second=total_throughput,
            error_rate_percent=avg_error_rate,
            timestamp=datetime.now(),
            metadata={
                "config": asdict(config),
                "concurrent_workers": config.concurrent_workers,
                "successful_workers": len(successful_results),
                "failed_workers": len(failed_results),
                "worker_results": [r.to_dict() for r in successful_results],
                "aggregate_metrics": {
                    "total_operations": total_operations,
                    "total_throughput": total_throughput,
                    "peak_memory": max(r.memory_usage_mb for r in successful_results),
                    "peak_cpu": max(r.cpu_usage_percent for r in successful_results),
                },
            },
        )

        with self.lock:
            self.results.append(aggregate_result)

        logger.info(
            f"Concurrent benchmark {name} completed: {aggregate_result.operations_per_second:.2f} ops/sec"
        )
        return aggregate_result

    def get_results(self, name: Optional[str] = None) -> List[BenchmarkResult]:
        """Get benchmark results.

        Args:
            name: Optional benchmark name filter

        Returns:
            List of benchmark results
        """
        with self.lock:
            if name:
                return [r for r in self.results if r.name == name]
            return list(self.results)

    def get_active_benchmarks(self) -> Dict[str, Any]:
        """Get currently active benchmarks.

        Returns:
            Dictionary of active benchmarks
        """
        with self.lock:
            return dict(self.active_benchmarks)

    def export_results(self, file_path: Path, format: str = "json"):
        """Export benchmark results to file.

        Args:
            file_path: Path to export file
            format: Export format (json, csv)
        """
        with self.lock:
            results_data = [r.to_dict() for r in self.results]

        file_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(results_data, f, indent=2, default=str)
        elif format == "csv":
            import csv

            if results_data:
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=results_data[0].keys())
                    writer.writeheader()
                    writer.writerows(results_data)

        logger.info(f"Exported {len(results_data)} benchmark results to {file_path}")

    def clear_results(self):
        """Clear all benchmark results."""
        with self.lock:
            self.results.clear()
            logger.info("Cleared all benchmark results")


class DocumentProcessingBenchmarks:
    """Predefined benchmarks for document processing operations."""

    def __init__(self, benchmark_runner: BenchmarkRunner):
        self.runner = benchmark_runner
        self.test_data_dir = Path("data/test_documents")
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

    def _create_test_document(self, size_mb: float = 1.0) -> str:
        """Create a test document of specified size."""
        content_size = int(size_mb * 1024 * 1024)  # Convert to bytes
        content = "This is test content for benchmarking. " * (content_size // 40)
        return content[:content_size]

    async def benchmark_text_extraction(self, iterations: int = 10) -> BenchmarkResult:
        """Benchmark text extraction from documents."""
        from ..converters.base import BaseConverter

        class TestConverter(BaseConverter):
            def to_markdown(self, source: str) -> str:
                # Simulate text extraction processing
                lines = source.split("\n")
                processed_lines = []
                for line in lines:
                    if line.strip():
                        processed_lines.append(f"* {line.strip()}")
                return "\n".join(processed_lines)

        converter = TestConverter()
        test_content = self._create_test_document(1.0)

        def benchmark_func():
            return converter.to_markdown(test_content)

        config = BenchmarkConfig(
            name="text_extraction", iterations=iterations, data_size_mb=1.0
        )

        return await self.runner.run_benchmark(
            "text_extraction", benchmark_func, config
        )

    async def benchmark_document_conversion(
        self, iterations: int = 10
    ) -> BenchmarkResult:
        """Benchmark document conversion operations."""
        test_content = self._create_test_document(2.0)

        def benchmark_func():
            # Simulate document conversion
            lines = test_content.split("\n")
            result = []
            for line in lines:
                if line.strip():
                    result.append(f"# {line.strip()}")
                else:
                    result.append("")
            return "\n".join(result)

        config = BenchmarkConfig(
            name="document_conversion", iterations=iterations, data_size_mb=2.0
        )

        return await self.runner.run_benchmark(
            "document_conversion", benchmark_func, config
        )

    async def benchmark_bulk_processing(self, iterations: int = 5) -> BenchmarkResult:
        """Benchmark bulk document processing."""
        documents = [self._create_test_document(0.5) for _ in range(10)]

        def benchmark_func():
            results = []
            for doc in documents:
                # Simulate processing
                lines = doc.split("\n")
                processed = [
                    f"Processed: {line}" for line in lines[:100]
                ]  # Limit for performance
                results.append("\n".join(processed))
            return results

        config = BenchmarkConfig(
            name="bulk_processing", iterations=iterations, data_size_mb=5.0
        )

        return await self.runner.run_benchmark(
            "bulk_processing", benchmark_func, config
        )

    async def benchmark_concurrent_processing(
        self, iterations: int = 10, workers: int = 4
    ) -> BenchmarkResult:
        """Benchmark concurrent document processing."""
        test_content = self._create_test_document(1.0)

        async def benchmark_func():
            # Simulate async processing
            await asyncio.sleep(0.01)  # Simulate I/O
            lines = test_content.split("\n")
            return f"Processed {len(lines)} lines"

        config = BenchmarkConfig(
            name="concurrent_processing",
            iterations=iterations,
            concurrent_workers=workers,
            data_size_mb=1.0,
        )

        return await self.runner.run_concurrent_benchmark(
            "concurrent_processing", benchmark_func, config
        )

    async def benchmark_memory_usage(self, iterations: int = 5) -> BenchmarkResult:
        """Benchmark memory usage patterns."""

        def benchmark_func():
            # Create large data structures to test memory usage
            large_data = []
            for i in range(10000):
                large_data.append(f"Data item {i} with some content to use memory")

            # Process the data
            processed = [item.upper() for item in large_data]
            return len(processed)

        config = BenchmarkConfig(
            name="memory_usage",
            iterations=iterations,
            max_memory_mb=500,
            data_size_mb=10.0,
        )

        return await self.runner.run_benchmark("memory_usage", benchmark_func, config)

    async def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all predefined benchmarks."""
        logger.info("Running all document processing benchmarks")

        results = []

        # Text extraction benchmark
        results.append(await self.benchmark_text_extraction())

        # Document conversion benchmark
        results.append(await self.benchmark_document_conversion())

        # Bulk processing benchmark
        results.append(await self.benchmark_bulk_processing())

        # Concurrent processing benchmark
        results.append(await self.benchmark_concurrent_processing())

        # Memory usage benchmark
        results.append(await self.benchmark_memory_usage())

        logger.info(f"Completed all benchmarks: {len(results)} results")
        return results


# Global benchmark runner instance
benchmark_runner = BenchmarkRunner()


async def run_benchmark(
    name: str, benchmark_func: Callable, config: BenchmarkConfig, *args, **kwargs
) -> BenchmarkResult:
    """Run a benchmark using the global runner.

    Args:
        name: Benchmark name
        benchmark_func: Function to benchmark
        config: Benchmark configuration
        *args: Arguments for benchmark function
        **kwargs: Keyword arguments for benchmark function

    Returns:
        Benchmark result
    """
    return await benchmark_runner.run_benchmark(
        name, benchmark_func, config, *args, **kwargs
    )


def get_benchmark_results(name: Optional[str] = None) -> List[BenchmarkResult]:
    """Get benchmark results from the global runner.

    Args:
        name: Optional benchmark name filter

    Returns:
        List of benchmark results
    """
    return benchmark_runner.get_results(name)


def export_benchmark_results(file_path: Path, format: str = "json"):
    """Export benchmark results from the global runner.

    Args:
        file_path: Path to export file
        format: Export format (json, csv)
    """
    benchmark_runner.export_results(file_path, format)


@contextmanager
def benchmark_context(name: str, data_size_mb: float = 1.0):
    """Context manager for quick benchmarking.

    Args:
        name: Benchmark name
        data_size_mb: Data size for throughput calculation
    """
    start_time = time.time()
    process = psutil.Process()
    start_memory = process.memory_info().rss / (1024 * 1024)

    try:
        yield
    finally:
        end_time = time.time()
        end_memory = process.memory_info().rss / (1024 * 1024)

        duration = end_time - start_time
        memory_used = end_memory - start_memory
        throughput = data_size_mb / duration if duration > 0 else 0

        logger.info(
            f"Benchmark {name}: {duration:.3f}s, {memory_used:.2f}MB, {throughput:.2f}MB/s"
        )
