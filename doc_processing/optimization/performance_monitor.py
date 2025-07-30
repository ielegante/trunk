"""Performance monitoring and metrics collection for document processing."""

import asyncio
import functools
import logging
import threading
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    memory_start_mb: Optional[float] = None
    memory_end_mb: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self):
        """Mark operation as complete and calculate duration."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "memory_start_mb": self.memory_start_mb,
            "memory_end_mb": self.memory_end_mb,
            "memory_peak_mb": self.memory_peak_mb,
            "cpu_percent": self.cpu_percent,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class PerformanceMonitor:
    """Monitor and track performance metrics for document processing operations."""

    def __init__(
        self, enable_memory_tracking: bool = True, enable_cpu_tracking: bool = True
    ):
        """Initialize performance monitor.

        Args:
            enable_memory_tracking: Whether to track memory usage
            enable_cpu_tracking: Whether to track CPU usage
        """
        self.enable_memory_tracking = enable_memory_tracking
        self.enable_cpu_tracking = enable_cpu_tracking
        self.metrics: List[PerformanceMetrics] = []
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0.0,
                "min_duration": float("in"),
                "max_duration": 0.0,
                "avg_duration": 0.0,
                "success_count": 0,
                "error_count": 0,
                "total_memory_mb": 0.0,
                "max_memory_mb": 0.0,
            }
        )
        self.lock = threading.RLock()
        self.process = psutil.Process()

        # Start memory tracking if enabled
        if self.enable_memory_tracking:
            tracemalloc.start()

    def track_operation(
        self, operation: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager to track an operation's performance.

        Args:
            operation: Name of the operation being tracked
            metadata: Additional metadata for the operation

        Yields:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics(
            operation=operation, start_time=time.time(), metadata=metadata or {}
        )

        # Track initial memory
        if self.enable_memory_tracking:
            metrics.memory_start_mb = self._get_memory_usage_mb()

        # Track initial CPU
        if self.enable_cpu_tracking:
            cpu_start = self.process.cpu_percent(interval=None)

        try:
            yield metrics
            metrics.success = True
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Operation {operation} failed: {e}")
            raise
        finally:
            # Complete metrics
            metrics.complete()

            # Track final memory
            if self.enable_memory_tracking:
                metrics.memory_end_mb = self._get_memory_usage_mb()
                if tracemalloc.is_tracing():
                    current, peak = tracemalloc.get_traced_memory()
                    metrics.memory_peak_mb = peak / (1024 * 1024)

            # Track CPU usage
            if self.enable_cpu_tracking:
                metrics.cpu_percent = (
                    self.process.cpu_percent(interval=None) - cpu_start
                )

            # Store metrics
            self._record_metrics(metrics)

    async def track_async_operation(
        self, operation: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Async context manager to track an operation's performance.

        Args:
            operation: Name of the operation being tracked
            metadata: Additional metadata for the operation

        Yields:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics(
            operation=operation, start_time=time.time(), metadata=metadata or {}
        )

        # Track initial memory
        if self.enable_memory_tracking:
            metrics.memory_start_mb = self._get_memory_usage_mb()

        try:
            yield metrics
            metrics.success = True
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Async operation {operation} failed: {e}")
            raise
        finally:
            # Complete metrics
            metrics.complete()

            # Track final memory
            if self.enable_memory_tracking:
                metrics.memory_end_mb = self._get_memory_usage_mb()
                if tracemalloc.is_tracing():
                    current, peak = tracemalloc.get_traced_memory()
                    metrics.memory_peak_mb = peak / (1024 * 1024)

            # Store metrics
            self._record_metrics(metrics)

    def _record_metrics(self, metrics: PerformanceMetrics):
        """Record metrics and update statistics."""
        with self.lock:
            # Store individual metrics
            self.metrics.append(metrics)

            # Update operation statistics
            stats = self.operation_stats[metrics.operation]
            stats["count"] += 1
            stats["total_duration"] += metrics.duration_seconds
            stats["min_duration"] = min(stats["min_duration"], metrics.duration_seconds)
            stats["max_duration"] = max(stats["max_duration"], metrics.duration_seconds)
            stats["avg_duration"] = stats["total_duration"] / stats["count"]

            if metrics.success:
                stats["success_count"] += 1
            else:
                stats["error_count"] += 1

            if metrics.memory_end_mb:
                memory_used = metrics.memory_end_mb - (metrics.memory_start_mb or 0)
                stats["total_memory_mb"] += memory_used
                stats["max_memory_mb"] = max(stats["max_memory_mb"], memory_used)

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in megabytes."""
        return self.process.memory_info().rss / (1024 * 1024)

    def get_operation_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for operations.

        Args:
            operation: Specific operation to get stats for, or None for all

        Returns:
            Dictionary of operation statistics
        """
        with self.lock:
            if operation:
                return dict(self.operation_stats.get(operation, {}))
            else:
                return dict(self.operation_stats)

    def get_recent_metrics(
        self, limit: int = 100, operation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent performance metrics.

        Args:
            limit: Maximum number of metrics to return
            operation: Filter by specific operation

        Returns:
            List of recent metrics as dictionaries
        """
        with self.lock:
            metrics = self.metrics

            if operation:
                metrics = [m for m in metrics if m.operation == operation]

            # Return most recent metrics
            return [m.to_dict() for m in metrics[-limit:]]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary.

        Returns:
            Dictionary with performance summary
        """
        with self.lock:
            total_operations = len(self.metrics)
            if total_operations == 0:
                return {"total_operations": 0, "message": "No operations tracked yet"}

            successful_ops = sum(1 for m in self.metrics if m.success)
            failed_ops = total_operations - successful_ops

            # Calculate aggregates
            all_durations = [
                m.duration_seconds for m in self.metrics if m.duration_seconds
            ]
            avg_duration = (
                sum(all_durations) / len(all_durations) if all_durations else 0
            )

            memory_deltas = []
            for m in self.metrics:
                if m.memory_start_mb and m.memory_end_mb:
                    memory_deltas.append(m.memory_end_mb - m.memory_start_mb)

            avg_memory_delta = (
                sum(memory_deltas) / len(memory_deltas) if memory_deltas else 0
            )

            return {
                "total_operations": total_operations,
                "successful_operations": successful_ops,
                "failed_operations": failed_ops,
                "success_rate": successful_ops / total_operations,
                "average_duration_seconds": avg_duration,
                "average_memory_delta_mb": avg_memory_delta,
                "operation_breakdown": dict(self.operation_stats),
                "current_memory_mb": self._get_memory_usage_mb(),
                "tracking_start_time": (
                    self.metrics[0].start_time if self.metrics else None
                ),
            }

    def get_bottlenecks(self, threshold_percentile: float = 0.95) -> Dict[str, Any]:
        """Identify performance bottlenecks.

        Args:
            threshold_percentile: Percentile to identify slow operations

        Returns:
            Dictionary with bottleneck analysis
        """
        with self.lock:
            bottlenecks = {
                "slow_operations": [],
                "memory_intensive_operations": [],
                "high_failure_operations": [],
            }

            # Analyze each operation type
            for operation, stats in self.operation_stats.items():
                # Check for slow operations
                if stats["max_duration"] > stats["avg_duration"] * 2:
                    bottlenecks["slow_operations"].append(
                        {
                            "operation": operation,
                            "avg_duration": stats["avg_duration"],
                            "max_duration": stats["max_duration"],
                            "count": stats["count"],
                        }
                    )

                # Check for memory intensive operations
                if stats["max_memory_mb"] > 100:  # More than 100MB
                    bottlenecks["memory_intensive_operations"].append(
                        {
                            "operation": operation,
                            "max_memory_mb": stats["max_memory_mb"],
                            "avg_memory_mb": (
                                stats["total_memory_mb"] / stats["count"]
                                if stats["count"] > 0
                                else 0
                            ),
                        }
                    )

                # Check for high failure rate
                if stats["error_count"] > 0:
                    failure_rate = stats["error_count"] / stats["count"]
                    if failure_rate > 0.1:  # More than 10% failure
                        bottlenecks["high_failure_operations"].append(
                            {
                                "operation": operation,
                                "failure_rate": failure_rate,
                                "error_count": stats["error_count"],
                                "total_count": stats["count"],
                            }
                        )

            return bottlenecks

    def reset_metrics(self):
        """Reset all collected metrics."""
        with self.lock:
            self.metrics.clear()
            self.operation_stats.clear()
            logger.info("Performance metrics reset")

    def export_metrics(self, filepath: str):
        """Export metrics to a JSON file.

        Args:
            filepath: Path to export metrics to
        """
        import json

        with self.lock:
            export_data = {
                "summary": self.get_performance_summary(),
                "operation_stats": dict(self.operation_stats),
                "recent_metrics": self.get_recent_metrics(limit=1000),
                "bottlenecks": self.get_bottlenecks(),
                "export_timestamp": datetime.now().isoformat(),
            }

            with open(filepath, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported performance metrics to {filepath}")


def performance_tracked(monitor: PerformanceMonitor, operation: Optional[str] = None):
    """Decorator to automatically track function performance.

    Args:
        monitor: PerformanceMonitor instance
        operation: Operation name (defaults to function name)

    Returns:
        Decorator function
    """

    def decorator(func):
        op_name = operation or func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with monitor.track_async_operation(op_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with monitor.track_operation(op_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


class PerformanceOptimizer:
    """Analyzes performance metrics and suggests optimizations."""

    def __init__(self, monitor: PerformanceMonitor):
        """Initialize optimizer with a performance monitor.

        Args:
            monitor: PerformanceMonitor instance
        """
        self.monitor = monitor

    def analyze_and_optimize(self) -> Dict[str, Any]:
        """Analyze performance and suggest optimizations.

        Returns:
            Dictionary with optimization suggestions
        """
        summary = self.monitor.get_performance_summary()
        bottlenecks = self.monitor.get_bottlenecks()

        suggestions = {
            "caching": [],
            "parallelization": [],
            "algorithm": [],
            "memory": [],
            "error_handling": [],
        }

        # Analyze slow operations
        for op in bottlenecks["slow_operations"]:
            if op["avg_duration"] > 1.0:  # Operations taking more than 1 second
                suggestions["caching"].append(
                    {
                        "operation": op["operation"],
                        "reason": f"Average duration {op['avg_duration']:.2f}s is high",
                        "suggestion": "Consider caching results for frequently accessed data",
                    }
                )

            if op["count"] > 100 and op["avg_duration"] > 0.1:
                suggestions["parallelization"].append(
                    {
                        "operation": op["operation"],
                        "reason": f"High frequency ({op['count']} calls) with significant duration",
                        "suggestion": "Consider batch processing or parallelization",
                    }
                )

        # Analyze memory intensive operations
        for op in bottlenecks["memory_intensive_operations"]:
            suggestions["memory"].append(
                {
                    "operation": op["operation"],
                    "reason": f"Peak memory usage {op['max_memory_mb']:.1f}MB",
                    "suggestion": "Consider streaming processing or chunking large data",
                }
            )

        # Analyze high failure operations
        for op in bottlenecks["high_failure_operations"]:
            suggestions["error_handling"].append(
                {
                    "operation": op["operation"],
                    "reason": f"High failure rate {op['failure_rate']:.1%}",
                    "suggestion": "Implement retry logic and better error handling",
                }
            )

        # General suggestions based on summary
        if summary.get("average_memory_delta_mb", 0) > 50:
            suggestions["memory"].append(
                {
                    "operation": "general",
                    "reason": "High average memory consumption",
                    "suggestion": "Implement object pooling and aggressive garbage collection",
                }
            )

        return {
            "summary": summary,
            "bottlenecks": bottlenecks,
            "optimization_suggestions": suggestions,
            "analysis_timestamp": datetime.now().isoformat(),
        }
