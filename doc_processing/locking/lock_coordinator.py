"""Lock coordination for distributed environments."""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from .document_lock import DocumentLock, DocumentLockingSystem, LockRequest

logger = logging.getLogger(__name__)


@dataclass
class LockConflict:
    """Represents a lock conflict."""

    conflict_id: str
    document_path: str
    existing_lock: DocumentLock
    requested_by: str
    requested_at: datetime
    resolution: Optional[str] = None  # 'wait', 'force', 'cancel'
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["requested_at"] = self.requested_at.isoformat()
        if self.resolved_at:
            data["resolved_at"] = self.resolved_at.isoformat()
        data["existing_lock"] = self.existing_lock.to_dict()
        return data


@dataclass
class LockNotification:
    """Notification about lock events."""

    notification_id: str
    event_type: str  # 'lock_acquired', 'lock_released', 'lock_expiring', 'conflict'
    document_path: str
    user: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class LockCoordinator:
    """Coordinates document locks across multiple users."""

    def __init__(self, locking_system: DocumentLockingSystem):
        """Initialize lock coordinator.

        Args:
            locking_system: Document locking system instance
        """
        self.locking_system = locking_system
        self.lock_queue: Dict[str, List[LockRequest]] = {}
        self.conflicts: List[LockConflict] = []
        self.notifications: List[LockNotification] = []
        self.notification_callbacks: List[Callable[[LockNotification], None]] = []

        # Start monitoring
        self._start_monitoring()

    async def request_lock_with_wait(
        self, request: LockRequest, max_wait_minutes: int = 30
    ) -> Tuple[bool, Optional[DocumentLock], str]:
        """Request a lock with option to wait for availability.

        Args:
            request: Lock request
            max_wait_minutes: Maximum time to wait for lock

        Returns:
            Tuple of (success, lock, message)
        """
        # Try immediate lock
        success, lock, message = await self.locking_system.acquire_lock(request)

        if success:
            await self._notify(
                LockNotification(
                    notification_id=str(uuid4()),
                    event_type="lock_acquired",
                    document_path=request.document_path,
                    user=request.requested_by,
                    timestamp=datetime.now(),
                    details={"immediate": True},
                )
            )
            return success, lock, message

        # Check if we should queue
        if not request.force and max_wait_minutes > 0:
            # Add to queue
            if request.document_path not in self.lock_queue:
                self.lock_queue[request.document_path] = []

            self.lock_queue[request.document_path].append(request)

            # Record conflict
            existing_lock = self.locking_system.get_lock(request.document_path)
            if existing_lock:
                conflict = LockConflict(
                    conflict_id=str(uuid4()),
                    document_path=request.document_path,
                    existing_lock=existing_lock,
                    requested_by=request.requested_by,
                    requested_at=datetime.now(),
                )
                self.conflicts.append(conflict)

                await self._notify(
                    LockNotification(
                        notification_id=str(uuid4()),
                        event_type="conflict",
                        document_path=request.document_path,
                        user=request.requested_by,
                        timestamp=datetime.now(),
                        details={
                            "current_owner": existing_lock.locked_by,
                            "expires_in": int(
                                existing_lock.time_remaining().total_seconds() / 60
                            ),
                        },
                    )
                )

            # Wait for lock
            start_time = datetime.now()
            max_wait = timedelta(minutes=max_wait_minutes)

            while datetime.now() - start_time < max_wait:
                await asyncio.sleep(10)  # Check every 10 seconds

                # Try to acquire lock
                success, lock, message = await self.locking_system.acquire_lock(request)

                if success:
                    # Remove from queue
                    self.lock_queue[request.document_path].remove(request)
                    if not self.lock_queue[request.document_path]:
                        del self.lock_queue[request.document_path]

                    await self._notify(
                        LockNotification(
                            notification_id=str(uuid4()),
                            event_type="lock_acquired",
                            document_path=request.document_path,
                            user=request.requested_by,
                            timestamp=datetime.now(),
                            details={
                                "waited_minutes": int(
                                    (datetime.now() - start_time).total_seconds() / 60
                                )
                            },
                        )
                    )

                    return success, lock, message

            # Timeout
            self.lock_queue[request.document_path].remove(request)
            if not self.lock_queue[request.document_path]:
                del self.lock_queue[request.document_path]

            return False, None, f"Lock wait timeout after {max_wait_minutes} minutes"

        return success, lock, message

    async def coordinate_bulk_operation(
        self,
        document_paths: List[str],
        user: str,
        operation: Callable[[List[str]], Any],
        lock_duration: int = 30,
    ) -> Tuple[bool, Any, str]:
        """Coordinate a bulk operation requiring multiple locks.

        Args:
            document_paths: Documents to lock
            user: User performing operation
            operation: Function to execute with locks held
            lock_duration: Lock duration in minutes

        Returns:
            Tuple of (success, operation_result, message)
        """
        acquired_locks = []

        try:
            # Try to acquire all locks
            for doc_path in document_paths:
                request = LockRequest(
                    document_path=doc_path,
                    requested_by=user,
                    duration_minutes=lock_duration,
                    reason="Bulk operation",
                )

                success, lock, message = await self.locking_system.acquire_lock(request)

                if not success:
                    # Release acquired locks
                    for acquired_path in acquired_locks:
                        await self.locking_system.release_lock(acquired_path, user)

                    return (
                        False,
                        None,
                        f"Failed to acquire lock on {doc_path}: {message}",
                    )

                acquired_locks.append(doc_path)

            # Execute operation
            await self._notify(
                LockNotification(
                    notification_id=str(uuid4()),
                    event_type="bulk_operation_start",
                    document_path="multiple",
                    user=user,
                    timestamp=datetime.now(),
                    details={"document_count": len(document_paths)},
                )
            )

            result = await operation(document_paths)

            # Release all locks
            for doc_path in acquired_locks:
                await self.locking_system.release_lock(doc_path, user)

            await self._notify(
                LockNotification(
                    notification_id=str(uuid4()),
                    event_type="bulk_operation_complete",
                    document_path="multiple",
                    user=user,
                    timestamp=datetime.now(),
                    details={"document_count": len(document_paths), "success": True},
                )
            )

            return True, result, "Bulk operation completed successfully"

        except Exception as e:
            # Release any acquired locks
            for doc_path in acquired_locks:
                try:
                    await self.locking_system.release_lock(doc_path, user)
                except Exception:
                    pass

            logger.error(f"Bulk operation failed: {e}")
            return False, None, f"Bulk operation failed: {str(e)}"

    async def get_lock_recommendations(self, user: str) -> List[Dict[str, Any]]:
        """Get recommendations for lock management.

        Args:
            user: User to get recommendations for

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check user's current locks
        user_locks = self.locking_system.get_user_locks(user)

        # Recommend releasing soon-to-expire locks
        for lock in user_locks:
            time_remaining = lock.time_remaining()
            if time_remaining < timedelta(minutes=10):
                recommendations.append(
                    {
                        "type": "expiring_soon",
                        "document": lock.document_path,
                        "expires_in_minutes": int(time_remaining.total_seconds() / 60),
                        "action": "extend_or_release",
                        "priority": "high",
                    }
                )

        # Check if user has many locks
        if len(user_locks) > 5:
            recommendations.append(
                {
                    "type": "many_locks",
                    "count": len(user_locks),
                    "action": "consider_releasing_unused",
                    "priority": "medium",
                }
            )

        # Check if user is waiting for locks
        waiting_for = []
        for doc_path, queue in self.lock_queue.items():
            for request in queue:
                if request.requested_by == user:
                    waiting_for.append(doc_path)

        if waiting_for:
            recommendations.append(
                {
                    "type": "waiting_for_locks",
                    "documents": waiting_for,
                    "action": "consider_alternative_documents",
                    "priority": "low",
                }
            )

        return recommendations

    async def monitor_lock_health(self) -> Dict[str, Any]:
        """Monitor overall lock system health.

        Returns:
            Health status report
        """
        all_locks = self.locking_system.get_all_locks()

        # Calculate metrics
        total_locks = len(all_locks)
        expiring_soon = sum(
            1
            for lock in all_locks.values()
            if lock.time_remaining() < timedelta(minutes=10)
        )

        # User distribution
        user_distribution = {}
        for lock in all_locks.values():
            user_distribution[lock.locked_by] = (
                user_distribution.get(lock.locked_by, 0) + 1
            )

        # Queue status
        total_waiting = sum(len(queue) for queue in self.lock_queue.values())

        # Conflict rate
        recent_conflicts = [
            c
            for c in self.conflicts
            if c.requested_at > datetime.now() - timedelta(hours=1)
        ]

        return {
            "total_active_locks": total_locks,
            "expiring_soon": expiring_soon,
            "user_distribution": user_distribution,
            "total_waiting_requests": total_waiting,
            "queued_documents": list(self.lock_queue.keys()),
            "recent_conflicts": len(recent_conflicts),
            "health_status": self._calculate_health_status(
                total_locks, total_waiting, len(recent_conflicts)
            ),
        }

    def register_notification_callback(
        self, callback: Callable[[LockNotification], None]
    ):
        """Register a callback for lock notifications.

        Args:
            callback: Function to call with notifications
        """
        self.notification_callbacks.append(callback)

    async def resolve_conflict(
        self, conflict_id: str, resolution: str, resolver: str
    ) -> Tuple[bool, str]:
        """Resolve a lock conflict.

        Args:
            conflict_id: Conflict ID
            resolution: Resolution type ('wait', 'force', 'cancel')
            resolver: User resolving conflict

        Returns:
            Tuple of (success, message)
        """
        conflict = next(
            (c for c in self.conflicts if c.conflict_id == conflict_id), None
        )

        if not conflict:
            return False, "Conflict not found"

        if conflict.resolved_at:
            return False, "Conflict already resolved"

        if resolution == "force":
            # Force unlock and acquire
            success, _ = await self.locking_system.release_lock(
                conflict.document_path, resolver, force=True
            )

            if success:
                # Try to give lock to waiting user
                request = LockRequest(
                    document_path=conflict.document_path,
                    requested_by=conflict.requested_by,
                    reason="Conflict resolution - forced",
                )

                await self.locking_system.acquire_lock(request)

        elif resolution == "cancel":
            # Remove from queue if still waiting
            if conflict.document_path in self.lock_queue:
                self.lock_queue[conflict.document_path] = [
                    r
                    for r in self.lock_queue[conflict.document_path]
                    if r.requested_by != conflict.requested_by
                ]

        # Mark resolved
        conflict.resolution = resolution
        conflict.resolved_at = datetime.now()

        return True, f"Conflict resolved with {resolution}"

    async def _notify(self, notification: LockNotification):
        """Send notification to registered callbacks."""
        self.notifications.append(notification)

        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")

    async def _monitor_expiring_locks(self):
        """Monitor for expiring locks and notify users."""
        while True:
            await asyncio.sleep(60)  # Check every minute

            all_locks = self.locking_system.get_all_locks()

            for lock in all_locks.values():
                time_remaining = lock.time_remaining()

                # Notify at 5 minutes remaining
                if timedelta(minutes=4) < time_remaining < timedelta(minutes=5):
                    await self._notify(
                        LockNotification(
                            notification_id=str(uuid4()),
                            event_type="lock_expiring",
                            document_path=lock.document_path,
                            user=lock.locked_by,
                            timestamp=datetime.now(),
                            details={"minutes_remaining": 5},
                        )
                    )

    async def _process_lock_queue(self):
        """Process waiting lock requests."""
        while True:
            await asyncio.sleep(15)  # Check every 15 seconds

            for doc_path, queue in list(self.lock_queue.items()):
                if not queue:
                    del self.lock_queue[doc_path]
                    continue

                # Check if document is now available
                current_lock = self.locking_system.get_lock(doc_path)
                if not current_lock:
                    # Try to give lock to first in queue
                    request = queue[0]
                    success, lock, message = await self.locking_system.acquire_lock(
                        request
                    )

                    if success:
                        queue.pop(0)
                        await self._notify(
                            LockNotification(
                                notification_id=str(uuid4()),
                                event_type="lock_acquired",
                                document_path=doc_path,
                                user=request.requested_by,
                                timestamp=datetime.now(),
                                details={"from_queue": True},
                            )
                        )

    def _calculate_health_status(
        self, total_locks: int, waiting_requests: int, recent_conflicts: int
    ) -> str:
        """Calculate overall health status."""
        if recent_conflicts > 10 or waiting_requests > 20:
            return "degraded"
        elif recent_conflicts > 5 or waiting_requests > 10:
            return "warning"
        else:
            return "healthy"

    def _start_monitoring(self):
        """Start monitoring tasks."""
        try:
            asyncio.create_task(self._monitor_expiring_locks())
            asyncio.create_task(self._process_lock_queue())
        except RuntimeError:
            # No event loop running, skip monitoring
            pass
