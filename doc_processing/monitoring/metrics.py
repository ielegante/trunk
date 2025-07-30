"""Metrics collection and monitoring for document processing."""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric measurement point."""

    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
        }


@dataclass
class SystemMetrics:
    """System resource metrics."""

    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_io_bytes_sent: int
    network_io_bytes_recv: int
    process_count: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_usage_percent": self.disk_usage_percent,
            "network_io_bytes_sent": self.network_io_bytes_sent,
            "network_io_bytes_recv": self.network_io_bytes_recv,
            "process_count": self.process_count,
            "timestamp": self.timestamp.isoformat(),
        }


class MetricsCollector:
    """Collects and stores metrics for document processing operations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize metrics collector.

        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.metrics: List[MetricPoint] = []
        self.lock = threading.RLock()
        self.is_collecting = False
        self.collection_task: Optional[asyncio.Task] = None

        # Configuration
        self.max_metrics = self.config.get("max_metrics", 10000)
        self.collection_interval = self.config.get("collection_interval", 60)
        self.retention_hours = self.config.get("retention_hours", 24)
        self.export_file = self.config.get("export_file", None)

        # Counters for application metrics
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}

        # Initialize counters
        self._initialize_counters()

    def _initialize_counters(self):
        """Initialize application counters."""
        self.counters.update(
            {
                "documents_processed": 0,
                "conversion_requests": 0,
                "conversion_errors": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "redaction_operations": 0,
                "template_instantiations": 0,
                "api_requests": 0,
                "api_errors": 0,
            }
        )

        self.gauges.update(
            {
                "active_connections": 0,
                "queue_size": 0,
                "cache_size_mb": 0,
                "memory_usage_mb": 0,
            }
        )

        self.histograms.update(
            {
                "document_processing_time": [],
                "conversion_time": [],
                "cache_response_time": [],
                "api_response_time": [],
            }
        )

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric point.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for the metric
        """
        with self.lock:
            metric = MetricPoint(
                name=name, value=value, timestamp=datetime.now(), tags=tags or {}
            )

            self.metrics.append(metric)

            # Trim old metrics if we exceed the limit
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics :]

            logger.debug(f"Recorded metric: {name} = {value}")

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric.

        Args:
            name: Counter name
            value: Value to increment by
            tags: Optional tags
        """
        with self.lock:
            self.counters[name] = self.counters.get(name, 0) + value
            self.record_metric(f"counter.{name}", self.counters[name], tags)

    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric.

        Args:
            name: Gauge name
            value: Gauge value
            tags: Optional tags
        """
        with self.lock:
            self.gauges[name] = value
            self.record_metric(f"gauge.{name}", value, tags)

    def record_histogram(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ):
        """Record a histogram value.

        Args:
            name: Histogram name
            value: Value to record
            tags: Optional tags
        """
        with self.lock:
            if name not in self.histograms:
                self.histograms[name] = []

            self.histograms[name].append(value)

            # Keep only recent values (last 1000)
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]

            self.record_metric(f"histogram.{name}", value, tags)

    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics.

        Returns:
            SystemMetrics object
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_usage_percent = (disk.used / disk.total) * 100

            # Network I/O
            network_io = psutil.net_io_counters()

            # Process count
            process_count = len(psutil.pids())

            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_usage_percent=disk_usage_percent,
                network_io_bytes_sent=network_io.bytes_sent,
                network_io_bytes_recv=network_io.bytes_recv,
                process_count=process_count,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0,
                memory_percent=0,
                disk_usage_percent=0,
                network_io_bytes_sent=0,
                network_io_bytes_recv=0,
                process_count=0,
                timestamp=datetime.now(),
            )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics.

        Returns:
            Dictionary with metrics summary
        """
        with self.lock:
            now = datetime.now()

            # Calculate histogram statistics
            histogram_stats = {}
            for name, values in self.histograms.items():
                if values:
                    histogram_stats[name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / len(values),
                        "p95": (
                            sorted(values)[int(len(values) * 0.95)]
                            if len(values) > 0
                            else 0
                        ),
                        "p99": (
                            sorted(values)[int(len(values) * 0.99)]
                            if len(values) > 0
                            else 0
                        ),
                    }

            # Get recent metrics (last hour)
            recent_metrics = [
                m for m in self.metrics if (now - m.timestamp).total_seconds() < 3600
            ]

            return {
                "collection_time": now.isoformat(),
                "total_metrics": len(self.metrics),
                "recent_metrics": len(recent_metrics),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": histogram_stats,
                "system_metrics": self.get_system_metrics().to_dict(),
            }

    def get_metrics_by_name(self, name: str, hours_back: int = 1) -> List[MetricPoint]:
        """Get metrics by name within a time window.

        Args:
            name: Metric name
            hours_back: Hours to look back

        Returns:
            List of metric points
        """
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            return [
                m for m in self.metrics if m.name == name and m.timestamp > cutoff_time
            ]

    def export_metrics(self, file_path: Optional[Path] = None) -> bool:
        """Export metrics to a file.

        Args:
            file_path: Optional file path to export to

        Returns:
            True if successful
        """
        try:
            export_path = file_path or self.export_file
            if not export_path:
                logger.warning("No export file specified")
                return False

            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)

            with self.lock:
                data = {
                    "export_time": datetime.now().isoformat(),
                    "metrics": [m.to_dict() for m in self.metrics],
                    "summary": self.get_metrics_summary(),
                }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Exported {len(self.metrics)} metrics to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return False

    def cleanup_old_metrics(self):
        """Remove old metrics based on retention policy."""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

            original_count = len(self.metrics)
            self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

            removed_count = original_count - len(self.metrics)
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old metrics")

    async def start_collection(self):
        """Start automatic metrics collection."""
        if self.is_collecting:
            logger.warning("Metrics collection is already running")
            return

        self.is_collecting = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Started metrics collection")

    async def stop_collection(self):
        """Stop automatic metrics collection."""
        if not self.is_collecting:
            return

        self.is_collecting = False

        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped metrics collection")

    async def _collection_loop(self):
        """Main collection loop."""
        while self.is_collecting:
            try:
                # Collect system metrics
                system_metrics = self.get_system_metrics()

                # Record system metrics
                self.record_metric("system.cpu_percent", system_metrics.cpu_percent)
                self.record_metric(
                    "system.memory_percent", system_metrics.memory_percent
                )
                self.record_metric(
                    "system.disk_usage_percent", system_metrics.disk_usage_percent
                )
                self.record_metric("system.process_count", system_metrics.process_count)

                # Update gauges
                self.set_gauge("memory_usage_mb", system_metrics.memory_percent)

                # Cleanup old metrics
                self.cleanup_old_metrics()

                # Export metrics if configured
                if self.export_file:
                    self.export_metrics()

                # Wait for next collection interval
                await asyncio.sleep(self.collection_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(self.collection_interval)

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report.

        Returns:
            Dictionary with performance metrics
        """
        summary = self.get_metrics_summary()

        # Calculate performance indicators
        performance_indicators = {}

        # Processing throughput
        if "documents_processed" in self.counters:
            performance_indicators["documents_per_hour"] = self.counters[
                "documents_processed"
            ]

        # Error rates
        if (
            "conversion_requests" in self.counters
            and "conversion_errors" in self.counters
        ):
            total_requests = self.counters["conversion_requests"]
            if total_requests > 0:
                error_rate = (self.counters["conversion_errors"] / total_requests) * 100
                performance_indicators["conversion_error_rate_percent"] = error_rate

        # Cache hit rate
        if "cache_hits" in self.counters and "cache_misses" in self.counters:
            total_cache_ops = (
                self.counters["cache_hits"] + self.counters["cache_misses"]
            )
            if total_cache_ops > 0:
                hit_rate = (self.counters["cache_hits"] / total_cache_ops) * 100
                performance_indicators["cache_hit_rate_percent"] = hit_rate

        # Response time analysis
        response_times = {}
        for hist_name, stats in summary["histograms"].items():
            if "time" in hist_name:
                response_times[hist_name] = {
                    "mean_ms": stats["mean"],
                    "p95_ms": stats["p95"],
                    "p99_ms": stats["p99"],
                }

        return {
            "report_time": datetime.now().isoformat(),
            "performance_indicators": performance_indicators,
            "response_times": response_times,
            "system_health": summary["system_metrics"],
            "counters": summary["counters"],
            "gauges": summary["gauges"],
        }
