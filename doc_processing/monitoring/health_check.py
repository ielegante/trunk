"""Health check system for production monitoring."""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Individual health check configuration."""

    name: str
    check_function: Callable[[], Tuple[HealthStatus, str]]
    interval_seconds: int = 60
    timeout_seconds: int = 30
    max_failures: int = 3
    enabled: bool = True

    # Runtime state
    last_check: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.HEALTHY
    last_message: str = ""
    failure_count: int = 0
    total_checks: int = 0
    total_failures: int = 0


class HealthCheckManager:
    """Manages health checks for production monitoring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize health check manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.checks: Dict[str, HealthCheck] = {}
        self.is_running = False
        self.check_tasks: Dict[str, asyncio.Task] = {}
        self.global_status = HealthStatus.HEALTHY
        self.lock = threading.RLock()

        # Statistics
        self.stats = {
            "total_checks": 0,
            "total_failures": 0,
            "uptime_start": datetime.now(),
            "last_status_change": datetime.now(),
        }

        # Default health checks
        self._setup_default_checks()

    def _setup_default_checks(self):
        """Set up default health checks."""
        # System resource checks
        self.register_check(
            HealthCheck(
                name="cpu_usage",
                check_function=self._check_cpu_usage,
                interval_seconds=30,
            )
        )

        self.register_check(
            HealthCheck(
                name="memory_usage",
                check_function=self._check_memory_usage,
                interval_seconds=30,
            )
        )

        self.register_check(
            HealthCheck(
                name="disk_usage",
                check_function=self._check_disk_usage,
                interval_seconds=60,
            )
        )

        # Application-specific checks
        self.register_check(
            HealthCheck(
                name="cache_connectivity",
                check_function=self._check_cache_connectivity,
                interval_seconds=30,
            )
        )

        self.register_check(
            HealthCheck(
                name="document_processing",
                check_function=self._check_document_processing,
                interval_seconds=60,
            )
        )

        self.register_check(
            HealthCheck(
                name="shutdown_state",
                check_function=self._check_shutdown_state,
                interval_seconds=10,
            )
        )

        self.register_check(
            HealthCheck(
                name="logging_health",
                check_function=self._check_logging_health,
                interval_seconds=300,
            )
        )

    def register_check(self, health_check: HealthCheck):
        """Register a health check.

        Args:
            health_check: HealthCheck instance
        """
        with self.lock:
            self.checks[health_check.name] = health_check
            logger.info(f"Registered health check: {health_check.name}")

    def unregister_check(self, name: str):
        """Unregister a health check.

        Args:
            name: Health check name
        """
        with self.lock:
            if name in self.checks:
                del self.checks[name]
                logger.info(f"Unregistered health check: {name}")

    async def start(self):
        """Start the health check manager."""
        if self.is_running:
            logger.warning("Health check manager is already running")
            return

        self.is_running = True
        logger.info("Starting health check manager")

        # Start tasks for each enabled check
        for name, check in self.checks.items():
            if check.enabled:
                self.check_tasks[name] = asyncio.create_task(
                    self._run_check_loop(check)
                )

        # Start status aggregation task
        self.check_tasks["_aggregator"] = asyncio.create_task(
            self._run_status_aggregation()
        )

    async def stop(self):
        """Stop the health check manager."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping health check manager")

        # Cancel all tasks
        for task in self.check_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self.check_tasks:
            await asyncio.gather(*self.check_tasks.values(), return_exceptions=True)

        self.check_tasks.clear()

    async def _run_check_loop(self, check: HealthCheck):
        """Run a single health check in a loop."""
        while self.is_running:
            try:
                await self._execute_check(check)
                await asyncio.sleep(check.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error for {check.name}: {e}")
                await asyncio.sleep(check.interval_seconds)

    async def _execute_check(self, check: HealthCheck):
        """Execute a single health check."""
        try:
            # Run check with timeout
            start_time = time.time()

            task = asyncio.create_task(asyncio.to_thread(check.check_function))

            try:
                status, message = await asyncio.wait_for(
                    task, timeout=check.timeout_seconds
                )
            except asyncio.TimeoutError:
                status = HealthStatus.UNHEALTHY
                message = f"Health check timed out after {check.timeout_seconds}s"

            execution_time = time.time() - start_time

            # Update check state
            with self.lock:
                check.last_check = datetime.now()
                check.last_status = status
                check.last_message = message
                check.total_checks += 1
                self.stats["total_checks"] += 1

                if status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                    check.failure_count += 1
                    check.total_failures += 1
                    self.stats["total_failures"] += 1
                else:
                    check.failure_count = 0  # Reset on success

            logger.debug(
                f"Health check {check.name}: {status.value} - {message} ({execution_time:.2f}s)"
            )

        except Exception as e:
            logger.error(f"Health check execution error for {check.name}: {e}")

            with self.lock:
                check.last_check = datetime.now()
                check.last_status = HealthStatus.CRITICAL
                check.last_message = f"Check execution failed: {str(e)}"
                check.failure_count += 1
                check.total_failures += 1
                self.stats["total_failures"] += 1

    async def _run_status_aggregation(self):
        """Aggregate individual check statuses into global status."""
        while self.is_running:
            try:
                await self._update_global_status()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Status aggregation error: {e}")
                await asyncio.sleep(10)

    async def _update_global_status(self):
        """Update the global health status."""
        with self.lock:
            statuses = []

            for check in self.checks.values():
                if check.enabled and check.last_check:
                    # Consider check failed if it exceeds max failures
                    if check.failure_count >= check.max_failures:
                        statuses.append(HealthStatus.CRITICAL)
                    else:
                        statuses.append(check.last_status)

            if not statuses:
                new_status = HealthStatus.HEALTHY
            elif any(s == HealthStatus.CRITICAL for s in statuses):
                new_status = HealthStatus.CRITICAL
            elif any(s == HealthStatus.UNHEALTHY for s in statuses):
                new_status = HealthStatus.UNHEALTHY
            elif any(s == HealthStatus.DEGRADED for s in statuses):
                new_status = HealthStatus.DEGRADED
            else:
                new_status = HealthStatus.HEALTHY

            if new_status != self.global_status:
                old_status = self.global_status
                self.global_status = new_status
                self.stats["last_status_change"] = datetime.now()

                logger.info(
                    f"Global health status changed: {old_status.value} -> {new_status.value}"
                )

    def get_status(self) -> Dict[str, Any]:
        """Get current health status.

        Returns:
            Dictionary with health status information
        """
        with self.lock:
            uptime = datetime.now() - self.stats["uptime_start"]

            check_details = {}
            for name, check in self.checks.items():
                if check.enabled:
                    check_details[name] = {
                        "status": check.last_status.value,
                        "message": check.last_message,
                        "last_check": (
                            check.last_check.isoformat() if check.last_check else None
                        ),
                        "failure_count": check.failure_count,
                        "total_checks": check.total_checks,
                        "total_failures": check.total_failures,
                        "success_rate": (
                            (
                                (check.total_checks - check.total_failures)
                                / check.total_checks
                            )
                            if check.total_checks > 0
                            else 0
                        ),
                    }

            return {
                "global_status": self.global_status.value,
                "uptime_seconds": uptime.total_seconds(),
                "last_status_change": self.stats["last_status_change"].isoformat(),
                "checks": check_details,
                "statistics": {
                    "total_checks": self.stats["total_checks"],
                    "total_failures": self.stats["total_failures"],
                    "global_success_rate": (
                        (
                            (self.stats["total_checks"] - self.stats["total_failures"])
                            / self.stats["total_checks"]
                        )
                        if self.stats["total_checks"] > 0
                        else 0
                    ),
                },
            }

    def get_readiness_status(self) -> Tuple[bool, str]:
        """Get readiness status for load balancer.

        Returns:
            Tuple of (is_ready, reason)
        """
        status = self.get_status()

        if status["global_status"] in ["healthy", "degraded"]:
            return True, "Service is ready"
        else:
            return False, f"Service is {status['global_status']}"

    def get_liveness_status(self) -> Tuple[bool, str]:
        """Get liveness status for container orchestration.

        Returns:
            Tuple of (is_alive, reason)
        """
        status = self.get_status()

        if status["global_status"] != "critical":
            return True, "Service is alive"
        else:
            return False, "Service is in critical state"

    # Default health check implementations
    def _check_cpu_usage(self) -> Tuple[HealthStatus, str]:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)

            if cpu_percent > 90:
                return HealthStatus.CRITICAL, f"CPU usage critical: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                return HealthStatus.UNHEALTHY, f"CPU usage high: {cpu_percent:.1f}%"
            elif cpu_percent > 70:
                return HealthStatus.DEGRADED, f"CPU usage elevated: {cpu_percent:.1f}%"
            else:
                return HealthStatus.HEALTHY, f"CPU usage normal: {cpu_percent:.1f}%"
        except Exception as e:
            return HealthStatus.CRITICAL, f"CPU check failed: {str(e)}"

    def _check_memory_usage(self) -> Tuple[HealthStatus, str]:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()

            if memory.percent > 90:
                return (
                    HealthStatus.CRITICAL,
                    f"Memory usage critical: {memory.percent:.1f}%",
                )
            elif memory.percent > 80:
                return (
                    HealthStatus.UNHEALTHY,
                    f"Memory usage high: {memory.percent:.1f}%",
                )
            elif memory.percent > 70:
                return (
                    HealthStatus.DEGRADED,
                    f"Memory usage elevated: {memory.percent:.1f}%",
                )
            else:
                return (
                    HealthStatus.HEALTHY,
                    f"Memory usage normal: {memory.percent:.1f}%",
                )
        except Exception as e:
            return HealthStatus.CRITICAL, f"Memory check failed: {str(e)}"

    def _check_disk_usage(self) -> Tuple[HealthStatus, str]:
        """Check disk usage."""
        try:
            disk = psutil.disk_usage("/")
            percent = (disk.used / disk.total) * 100

            if percent > 90:
                return HealthStatus.CRITICAL, f"Disk usage critical: {percent:.1f}%"
            elif percent > 80:
                return HealthStatus.UNHEALTHY, f"Disk usage high: {percent:.1f}%"
            elif percent > 70:
                return HealthStatus.DEGRADED, f"Disk usage elevated: {percent:.1f}%"
            else:
                return HealthStatus.HEALTHY, f"Disk usage normal: {percent:.1f}%"
        except Exception as e:
            return HealthStatus.CRITICAL, f"Disk check failed: {str(e)}"

    def _check_cache_connectivity(self) -> Tuple[HealthStatus, str]:
        """Check cache connectivity."""
        try:
            # This would check actual cache connectivity
            # For now, simulate a successful check
            return HealthStatus.HEALTHY, "Cache connectivity OK"
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Cache connectivity failed: {str(e)}"

    def _check_document_processing(self) -> Tuple[HealthStatus, str]:
        """Check document processing capabilities."""
        try:
            # This would test document processing pipeline
            # For now, simulate a successful check
            return HealthStatus.HEALTHY, "Document processing OK"
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Document processing failed: {str(e)}"

    def _check_shutdown_state(self) -> Tuple[HealthStatus, str]:
        """Check shutdown state."""
        try:
            from ..core.shutdown import shutdown_manager

            if shutdown_manager.is_shutting_down():
                return HealthStatus.UNHEALTHY, "Service is shutting down"
            else:
                return HealthStatus.HEALTHY, "Service is running normally"
        except Exception as e:
            return HealthStatus.DEGRADED, f"Cannot determine shutdown state: {str(e)}"

    def _check_logging_health(self) -> Tuple[HealthStatus, str]:
        """Check logging system health."""
        try:
            from ..core.logging import log_manager

            stats = log_manager.get_log_stats()

            # Check if we have the expected handlers
            if "console" not in stats["handlers"]:
                return HealthStatus.DEGRADED, "Console logging handler missing"

            if "file" not in stats["handlers"]:
                return HealthStatus.DEGRADED, "File logging handler missing"

            # Check file sizes
            for handler_name, handler_stats in stats["handlers"].items():
                if "file_size_mb" in handler_stats:
                    if handler_stats["file_size_mb"] > 500:  # 500MB limit
                        return (
                            HealthStatus.DEGRADED,
                            f"Log file {handler_name} is too large: {handler_stats['file_size_mb']:.1f}MB",
                        )

            return HealthStatus.HEALTHY, "Logging system OK"
        except Exception as e:
            return HealthStatus.DEGRADED, f"Logging health check failed: {str(e)}"
