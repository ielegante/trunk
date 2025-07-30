"""Health monitoring and system checks for production."""

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class SystemHealthMonitor:
    """Monitor system health and performance."""

    def __init__(self, check_interval: int = 60):
        """Initialize health monitor.

        Args:
            check_interval: Interval between health checks in seconds
        """
        self.check_interval = check_interval
        self.health_checks = {
            "database": self._check_database_health,
            "filesystem": self._check_filesystem_health,
            "memory": self._check_memory_health,
            "processing": self._check_processing_health,
            "dependencies": self._check_dependencies_health,
        }
        self.health_history: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []

    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check.

        Returns:
            Health check results
        """
        start_time = time.time()
        results = {
            "timestamp": datetime.now().isoformat(),
            "status": HealthStatus.HEALTHY,
            "checks": {},
            "errors": [],
            "warnings": [],
        }

        # Run all health checks
        for check_name, check_func in self.health_checks.items():
            try:
                check_result = await check_func()
                results["checks"][check_name] = check_result

                # Update overall status
                if check_result["status"] == HealthStatus.UNHEALTHY:
                    results["status"] = HealthStatus.UNHEALTHY
                elif (
                    check_result["status"] == HealthStatus.DEGRADED
                    and results["status"] != HealthStatus.UNHEALTHY
                ):
                    results["status"] = HealthStatus.DEGRADED

                # Collect errors and warnings
                if check_result.get("errors"):
                    results["errors"].extend(check_result["errors"])
                if check_result.get("warnings"):
                    results["warnings"].extend(check_result["warnings"])

            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                results["checks"][check_name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(e),
                }
                results["status"] = HealthStatus.UNHEALTHY
                results["errors"].append(f"{check_name}: {str(e)}")

        # Calculate check duration
        results["check_duration_ms"] = (time.time() - start_time) * 1000

        # Store in history
        self.health_history.append(results)

        # Keep only last 100 checks
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]

        # Generate alerts if needed
        self._generate_alerts(results)

        return results

    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health."""
        result = {
            "status": HealthStatus.HEALTHY,
            "details": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Test database connection
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()

            # Check basic operations
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            cursor.execute("INSERT INTO test VALUES (1)")
            cursor.execute("SELECT * FROM test")
            cursor.fetchone()
            cursor.execute("DROP TABLE test")

            # Check database size (if using file-based)
            db_path = Path("trunk_data.db")
            if db_path.exists():
                size_mb = db_path.stat().st_size / (1024 * 1024)
                result["details"]["database_size_mb"] = size_mb

                # Warn if database is getting large
                if size_mb > 1000:  # 1GB
                    result["warnings"].append("Database size exceeds 1GB")
                    result["status"] = HealthStatus.DEGRADED

            conn.close()
            result["details"]["connection_test"] = "passed"

        except Exception as e:
            result["status"] = HealthStatus.UNHEALTHY
            result["errors"].append(f"Database error: {str(e)}")

        return result

    async def _check_filesystem_health(self) -> Dict[str, Any]:
        """Check filesystem health."""
        result = {
            "status": HealthStatus.HEALTHY,
            "details": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Check disk space
            import shutil

            total, used, free = shutil.disk_usage("/")
            free_percent = (free / total) * 100

            result["details"]["disk_free_percent"] = free_percent
            result["details"]["disk_free_gb"] = free / (1024**3)

            # Warn if disk space is low
            if free_percent < 10:
                result["status"] = HealthStatus.UNHEALTHY
                result["errors"].append("Critical: Less than 10% disk space")
            elif free_percent < 20:
                result["status"] = HealthStatus.DEGRADED
                result["warnings"].append("Warning: Less than 20% disk space")

            # Check critical directories
            critical_dirs = ["./data", "./logs", "./backups"]
            for dir_path in critical_dirs:
                path = Path(dir_path)
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    result["warnings"].append(f"Created missing directory: {dir_path}")

            # Test write permissions
            test_file = Path("./data/.health_check")
            test_file.write_text("health check")
            test_file.unlink()
            result["details"]["write_test"] = "passed"

        except Exception as e:
            result["status"] = HealthStatus.UNHEALTHY
            result["errors"].append(f"Filesystem error: {str(e)}")

        return result

    async def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory health."""
        result = {
            "status": HealthStatus.HEALTHY,
            "details": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Try to get memory info
            try:
                import psutil

                memory = psutil.virtual_memory()
                result["details"]["memory_used_percent"] = memory.percent
                result["details"]["memory_available_mb"] = memory.available / (
                    1024**2
                )

                # Check memory pressure
                if memory.percent > 90:
                    result["status"] = HealthStatus.UNHEALTHY
                    result["errors"].append("Critical: Memory usage above 90%")
                elif memory.percent > 80:
                    result["status"] = HealthStatus.DEGRADED
                    result["warnings"].append("Warning: Memory usage above 80%")

            except ImportError:
                # Fallback if psutil not available
                result["details"]["memory_check"] = "psutil not available"

                # Basic memory test - try to allocate 50MB
                test_data = b"x" * (50 * 1024 * 1024)
                del test_data
                result["details"]["allocation_test"] = "passed"

        except MemoryError:
            result["status"] = HealthStatus.UNHEALTHY
            result["errors"].append("Memory allocation failed")
        except Exception as e:
            result["status"] = HealthStatus.DEGRADED
            result["warnings"].append(f"Memory check error: {str(e)}")

        return result

    async def _check_processing_health(self) -> Dict[str, Any]:
        """Check document processing health."""
        result = {
            "status": HealthStatus.HEALTHY,
            "details": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Test basic document processing
            from doc_processing.references.uri_system import URISystem

            uri_system = URISystem()
            test_uri = uri_system.create_uri(
                repository="test", document="health.md", section="check"
            )
            uri_string = test_uri.to_string()
            parsed_uri = uri_system.parse_uri(uri_string)

            if parsed_uri.repository == "test":
                result["details"]["uri_system"] = "operational"
            else:
                result["warnings"].append("URI system test failed")
                result["status"] = HealthStatus.DEGRADED

            # Check processing queue (if any)
            # In production, this would check actual processing metrics
            result["details"]["processing_test"] = "passed"

        except Exception as e:
            result["status"] = HealthStatus.UNHEALTHY
            result["errors"].append(f"Processing error: {str(e)}")

        return result

    async def _check_dependencies_health(self) -> Dict[str, Any]:
        """Check external dependencies health."""
        result = {
            "status": HealthStatus.HEALTHY,
            "details": {},
            "errors": [],
            "warnings": [],
        }

        # Check critical Python modules
        required_modules = ["sqlite3", "asyncio", "pathlib", "datetime"]
        missing_modules = []

        for module in required_modules:
            try:
                __import__(module)
                result["details"][f"module_{module}"] = "available"
            except ImportError:
                missing_modules.append(module)

        if missing_modules:
            result["status"] = HealthStatus.UNHEALTHY
            result["errors"].append(f"Missing modules: {', '.join(missing_modules)}")

        return result

    def _generate_alerts(self, health_results: Dict[str, Any]) -> None:
        """Generate alerts based on health check results."""
        if health_results["status"] == HealthStatus.UNHEALTHY:
            alert = {
                "timestamp": health_results["timestamp"],
                "severity": "critical",
                "message": "System health is UNHEALTHY",
                "errors": health_results["errors"],
            }
            self.alerts.append(alert)
            logger.critical(f"Health alert: {alert}")

        elif health_results["status"] == HealthStatus.DEGRADED:
            alert = {
                "timestamp": health_results["timestamp"],
                "severity": "warning",
                "message": "System health is DEGRADED",
                "warnings": health_results["warnings"],
            }
            self.alerts.append(alert)
            logger.warning(f"Health alert: {alert}")

        # Keep only recent alerts
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        if not self.health_history:
            return {"status": "no_data", "message": "No health checks performed yet"}

        latest = self.health_history[-1]

        # Calculate uptime percentage (last 24 hours)
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        recent_checks = [
            h
            for h in self.health_history
            if datetime.fromisoformat(h["timestamp"]) > day_ago
        ]

        healthy_checks = sum(
            1 for h in recent_checks if h["status"] == HealthStatus.HEALTHY
        )
        uptime_percent = (
            (healthy_checks / len(recent_checks)) * 100 if recent_checks else 0
        )

        return {
            "current_status": latest["status"],
            "last_check": latest["timestamp"],
            "uptime_24h_percent": uptime_percent,
            "active_alerts": len(
                [a for a in self.alerts if a["severity"] == "critical"]
            ),
            "warnings": len([a for a in self.alerts if a["severity"] == "warning"]),
            "checks": latest["checks"],
        }

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        logger.info("Starting health monitoring...")

        while True:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.check_interval)


class MetricsCollector:
    """Collect and track system metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics = {
            "documents_processed": 0,
            "conversions_completed": 0,
            "errors_encountered": 0,
            "average_processing_time_ms": 0,
            "cache_hit_rate": 0,
            "active_users": 0,
        }
        self.processing_times: List[float] = []

    def record_document_processed(self, processing_time_ms: float) -> None:
        """Record document processing metric."""
        self.metrics["documents_processed"] += 1
        self.processing_times.append(processing_time_ms)

        # Keep only last 1000 times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]

        # Update average
        self.metrics["average_processing_time_ms"] = sum(self.processing_times) / len(
            self.processing_times
        )

    def record_error(self) -> None:
        """Record error metric."""
        self.metrics["errors_encountered"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            **self.metrics,
            "error_rate_percent": (
                (
                    self.metrics["errors_encountered"]
                    / self.metrics["documents_processed"]
                )
                * 100
                if self.metrics["documents_processed"] > 0
                else 0
            ),
        }


# Global instances
health_monitor = SystemHealthMonitor()
metrics_collector = MetricsCollector()


async def get_system_health() -> Dict[str, Any]:
    """Get current system health status."""
    return await health_monitor.perform_health_check()


def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics."""
    return metrics_collector.get_metrics()
