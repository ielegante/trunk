"""Graceful shutdown system for document processing service."""

import asyncio
import logging
import signal
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ShutdownState(Enum):
    """Shutdown states."""

    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN_COMPLETE = "shutdown_complete"


@dataclass
class ShutdownHandler:
    """Handler for graceful shutdown operations."""

    name: str
    handler: Callable[[], Any]
    priority: int = 10
    timeout: float = 30.0
    is_async: bool = True

    def __post_init__(self):
        if not asyncio.iscoroutinefunction(self.handler) and self.is_async:
            self.is_async = False


class GracefulShutdown:
    """Manages graceful shutdown of the document processing service."""

    def __init__(self, timeout: float = 30.0):
        """Initialize graceful shutdown manager.

        Args:
            timeout: Maximum time to wait for shutdown completion
        """
        self.timeout = timeout
        self.handlers: List[ShutdownHandler] = []
        self.state = ShutdownState.RUNNING
        self.shutdown_event = asyncio.Event()
        self.shutdown_complete_event = asyncio.Event()
        self.lock = threading.RLock()
        self.shutdown_start_time: Optional[float] = None
        self.shutdown_reason: Optional[str] = None

        # Active operations tracking
        self.active_operations: Dict[str, Any] = {}
        self.operation_lock = threading.RLock()

        # Signal handlers
        self.original_handlers: Dict[int, Any] = {}
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received signal {signal_name}, initiating graceful shutdown")

            # Start shutdown in a separate task
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop:
                loop.create_task(self.shutdown(reason=f"Signal {signal_name}"))

        # Handle SIGTERM and SIGINT
        for sig in [signal.SIGTERM, signal.SIGINT]:
            self.original_handlers[sig] = signal.signal(sig, signal_handler)

    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self.original_handlers.items():
            signal.signal(sig, handler)

    def register_shutdown_handler(
        self,
        name: str,
        handler: Callable[[], Any],
        priority: int = 10,
        timeout: float = 30.0,
        is_async: bool = True,
    ):
        """Register a shutdown handler.

        Args:
            name: Handler name
            handler: Handler function
            priority: Priority (lower numbers execute first)
            timeout: Timeout for handler execution
            is_async: Whether handler is async
        """
        with self.lock:
            shutdown_handler = ShutdownHandler(
                name=name,
                handler=handler,
                priority=priority,
                timeout=timeout,
                is_async=is_async,
            )

            self.handlers.append(shutdown_handler)
            self.handlers.sort(key=lambda h: h.priority)

            logger.info(f"Registered shutdown handler: {name} (priority: {priority})")

    def unregister_shutdown_handler(self, name: str):
        """Unregister a shutdown handler.

        Args:
            name: Handler name to remove
        """
        with self.lock:
            self.handlers = [h for h in self.handlers if h.name != name]
            logger.info(f"Unregistered shutdown handler: {name}")

    def register_operation(self, operation_id: str, operation_info: Any):
        """Register an active operation.

        Args:
            operation_id: Unique operation identifier
            operation_info: Operation information
        """
        with self.operation_lock:
            self.active_operations[operation_id] = {
                "info": operation_info,
                "start_time": time.time(),
                "last_heartbeat": time.time(),
            }
            logger.debug(f"Registered operation: {operation_id}")

    def update_operation_heartbeat(self, operation_id: str):
        """Update operation heartbeat.

        Args:
            operation_id: Operation identifier
        """
        with self.operation_lock:
            if operation_id in self.active_operations:
                self.active_operations[operation_id]["last_heartbeat"] = time.time()

    def unregister_operation(self, operation_id: str):
        """Unregister an operation.

        Args:
            operation_id: Operation identifier
        """
        with self.operation_lock:
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
                logger.debug(f"Unregistered operation: {operation_id}")

    def get_active_operations(self) -> Dict[str, Any]:
        """Get currently active operations.

        Returns:
            Dictionary of active operations
        """
        with self.operation_lock:
            return dict(self.active_operations)

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress.

        Returns:
            True if shutting down
        """
        return self.state != ShutdownState.RUNNING

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """Wait for shutdown to complete.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if shutdown completed within timeout
        """
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.shutdown_complete_event.wait())

            if timeout:
                done, pending = loop.run_until_complete(
                    asyncio.wait_for(task, timeout=timeout)
                )
                return True
            else:
                loop.run_until_complete(task)
                return True

        except asyncio.TimeoutError:
            return False
        except RuntimeError:
            # No running loop
            return self.state == ShutdownState.SHUTDOWN_COMPLETE

    async def shutdown(self, reason: str = "Manual shutdown"):
        """Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown
        """
        with self.lock:
            if self.state != ShutdownState.RUNNING:
                logger.warning(f"Shutdown already in progress (state: {self.state})")
                return

            self.state = ShutdownState.SHUTTING_DOWN
            self.shutdown_start_time = time.time()
            self.shutdown_reason = reason

            logger.info(f"Starting graceful shutdown: {reason}")
            self.shutdown_event.set()

        try:
            await self._execute_shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            with self.lock:
                self.state = ShutdownState.SHUTDOWN_COMPLETE
                self.shutdown_complete_event.set()
                logger.info("Graceful shutdown completed")

    async def _execute_shutdown(self):
        """Execute the shutdown process."""
        # Step 1: Stop accepting new requests
        logger.info("Step 1: Stopping acceptance of new requests")

        # Step 2: Wait for active operations to complete
        logger.info("Step 2: Waiting for active operations to complete")
        await self._wait_for_active_operations()

        # Step 3: Execute shutdown handlers
        logger.info("Step 3: Executing shutdown handlers")
        await self._execute_shutdown_handlers()

        # Step 4: Final cleanup
        logger.info("Step 4: Performing final cleanup")
        await self._final_cleanup()

    async def _wait_for_active_operations(self):
        """Wait for active operations to complete."""
        start_time = time.time()
        operation_timeout = self.timeout * 0.5  # Use half the total timeout

        while time.time() - start_time < operation_timeout:
            with self.operation_lock:
                if not self.active_operations:
                    logger.info("All operations completed")
                    return

                # Log active operations
                operation_count = len(self.active_operations)
                logger.info(
                    f"Waiting for {operation_count} active operations to complete"
                )

                # Check for stuck operations
                current_time = time.time()
                stuck_operations = []
                for op_id, op_data in self.active_operations.items():
                    if current_time - op_data["last_heartbeat"] > 60:  # 1 minute
                        stuck_operations.append(op_id)

                if stuck_operations:
                    logger.warning(f"Potentially stuck operations: {stuck_operations}")

            await asyncio.sleep(1)

        # Force terminate remaining operations
        with self.operation_lock:
            if self.active_operations:
                logger.warning(
                    f"Force terminating {len(self.active_operations)} operations"
                )
                self.active_operations.clear()

    async def _execute_shutdown_handlers(self):
        """Execute all shutdown handlers."""
        for handler in self.handlers:
            logger.info(f"Executing shutdown handler: {handler.name}")
            start_time = time.time()

            try:
                if handler.is_async:
                    await asyncio.wait_for(handler.handler(), timeout=handler.timeout)
                else:
                    # Run sync handler in thread pool
                    loop = asyncio.get_running_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, handler.handler),
                        timeout=handler.timeout,
                    )

                execution_time = time.time() - start_time
                logger.info(
                    f"Shutdown handler {handler.name} completed in {execution_time:.2f}s"
                )

            except asyncio.TimeoutError:
                logger.error(
                    f"Shutdown handler {handler.name} timed out after {handler.timeout}s"
                )
            except Exception as e:
                logger.error(f"Shutdown handler {handler.name} failed: {e}")

    async def _final_cleanup(self):
        """Perform final cleanup operations."""
        try:
            # Restore signal handlers
            self.restore_signal_handlers()

            # Cancel any remaining tasks
            current_task = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if task != current_task]

            if tasks:
                logger.info(f"Cancelling {len(tasks)} remaining tasks")
                for task in tasks:
                    task.cancel()

                # Wait for tasks to complete cancellation
                await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("Final cleanup completed")

        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")

    def get_shutdown_status(self) -> Dict[str, Any]:
        """Get current shutdown status.

        Returns:
            Dictionary with shutdown status information
        """
        with self.lock:
            status = {
                "state": self.state.value,
                "shutdown_reason": self.shutdown_reason,
                "shutdown_start_time": self.shutdown_start_time,
                "registered_handlers": len(self.handlers),
                "active_operations": len(self.active_operations),
            }

            if self.shutdown_start_time:
                status["shutdown_duration"] = time.time() - self.shutdown_start_time

            return status

    @asynccontextmanager
    async def operation_context(self, operation_id: str, operation_info: Any):
        """Context manager for tracking operations.

        Args:
            operation_id: Unique operation identifier
            operation_info: Operation information
        """
        if self.is_shutting_down():
            raise RuntimeError("Cannot start operation during shutdown")

        self.register_operation(operation_id, operation_info)
        try:
            yield
        finally:
            self.unregister_operation(operation_id)

    def operation_heartbeat(self, operation_id: str):
        """Send heartbeat for an operation.

        Args:
            operation_id: Operation identifier
        """
        self.update_operation_heartbeat(operation_id)


# Global shutdown manager instance
shutdown_manager = GracefulShutdown()


def register_shutdown_handler(
    name: str,
    handler: Callable[[], Any],
    priority: int = 10,
    timeout: float = 30.0,
    is_async: bool = True,
):
    """Register a shutdown handler with the global manager.

    Args:
        name: Handler name
        handler: Handler function
        priority: Priority (lower numbers execute first)
        timeout: Timeout for handler execution
        is_async: Whether handler is async
    """
    shutdown_manager.register_shutdown_handler(
        name=name,
        handler=handler,
        priority=priority,
        timeout=timeout,
        is_async=is_async,
    )


def unregister_shutdown_handler(name: str):
    """Unregister a shutdown handler from the global manager.

    Args:
        name: Handler name to remove
    """
    shutdown_manager.unregister_shutdown_handler(name)


@asynccontextmanager
async def operation_context(operation_id: str, operation_info: Any):
    """Context manager for tracking operations with the global manager.

    Args:
        operation_id: Unique operation identifier
        operation_info: Operation information
    """
    async with shutdown_manager.operation_context(operation_id, operation_info):
        yield


def operation_heartbeat(operation_id: str):
    """Send heartbeat for an operation with the global manager.

    Args:
        operation_id: Operation identifier
    """
    shutdown_manager.operation_heartbeat(operation_id)


def is_shutting_down() -> bool:
    """Check if the global shutdown manager is shutting down.

    Returns:
        True if shutting down
    """
    return shutdown_manager.is_shutting_down()


async def shutdown(reason: str = "Manual shutdown"):
    """Initiate graceful shutdown with the global manager.

    Args:
        reason: Reason for shutdown
    """
    await shutdown_manager.shutdown(reason)
