"""Document locking system for reserved editing."""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class DocumentLock:
    """Represents a lock on a document."""

    lock_id: str
    document_path: str
    locked_by: str  # User email or ID
    locked_at: datetime
    expires_at: datetime
    lock_type: str  # 'exclusive' or 'advisory'
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if lock has expired."""
        return datetime.now() > self.expires_at

    def time_remaining(self) -> timedelta:
        """Get time remaining on lock."""
        return self.expires_at - datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["locked_at"] = self.locked_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentLock":
        """Create from dictionary representation."""
        data["locked_at"] = datetime.fromisoformat(data["locked_at"])
        data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)


@dataclass
class LockRequest:
    """Request to lock a document."""

    document_path: str
    requested_by: str
    lock_type: str = "exclusive"
    duration_minutes: int = 60
    reason: Optional[str] = None
    force: bool = False  # Force lock even if document is already locked

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class LockEvent:
    """Event in lock history."""

    event_id: str
    event_type: str  # 'locked', 'unlocked', 'expired', 'force_unlocked'
    document_path: str
    user: str
    timestamp: datetime
    lock_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class DocumentLockingSystem:
    """System for managing document locks."""

    def __init__(self, repo_path: Path, lock_dir: Optional[Path] = None):
        """Initialize document locking system.

        Args:
            repo_path: Path to repository
            lock_dir: Optional directory for lock files (defaults to .trunk/locks)
        """
        self.repo_path = Path(repo_path)
        self.lock_dir = lock_dir or self.repo_path / ".trunk" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self.active_locks: Dict[str, DocumentLock] = {}
        self.lock_history: List[LockEvent] = []

        # Lock file paths
        self.locks_file = self.lock_dir / "active_locks.json"
        self.history_file = self.lock_dir / "lock_history.json"

        # Load existing locks
        self._load_locks()

        # Start cleanup task
        self._start_cleanup_task()

    async def acquire_lock(
        self, request: LockRequest
    ) -> Tuple[bool, Optional[DocumentLock], str]:
        """Acquire a lock on a document.

        Args:
            request: Lock request details

        Returns:
            Tuple of (success, lock_if_successful, message)
        """
        logger.info(
            f"Lock request for {request.document_path} by {request.requested_by}"
        )

        # Validate document exists
        doc_path = self.repo_path / request.document_path
        if not doc_path.exists():
            return False, None, "Document does not exist"

        # Check for existing lock
        existing_lock = self.get_lock(request.document_path)

        if existing_lock and not existing_lock.is_expired():
            if not request.force:
                time_remaining = existing_lock.time_remaining()
                minutes = int(time_remaining.total_seconds() / 60)
                return (
                    False,
                    None,
                    (
                        f"Document is locked by {existing_lock.locked_by} "
                        f"for {minutes} more minutes"
                    ),
                )
            else:
                # Force unlock
                await self.release_lock(
                    request.document_path, request.requested_by, force=True
                )

        # Create new lock
        lock = DocumentLock(
            lock_id=str(uuid4()),
            document_path=request.document_path,
            locked_by=request.requested_by,
            locked_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=request.duration_minutes),
            lock_type=request.lock_type,
            reason=request.reason,
        )

        # Store lock
        self.active_locks[request.document_path] = lock
        self._save_locks()

        # Record event
        self._record_event(
            LockEvent(
                event_id=str(uuid4()),
                event_type="locked",
                document_path=request.document_path,
                user=request.requested_by,
                timestamp=datetime.now(),
                lock_id=lock.lock_id,
                details={
                    "reason": request.reason,
                    "duration": request.duration_minutes,
                },
            )
        )

        logger.info(f"Lock acquired: {lock.lock_id}")
        return True, lock, "Lock acquired successfully"

    async def release_lock(
        self, document_path: str, user: str, force: bool = False
    ) -> Tuple[bool, str]:
        """Release a lock on a document.

        Args:
            document_path: Path to document
            user: User releasing the lock
            force: Force release even if user doesn't own lock

        Returns:
            Tuple of (success, message)
        """
        lock = self.get_lock(document_path)

        if not lock:
            return False, "No active lock on document"

        # Check ownership
        if not force and lock.locked_by != user:
            return False, "You do not own this lock"

        # Remove lock
        del self.active_locks[document_path]
        self._save_locks()

        # Record event
        event_type = "force_unlocked" if force else "unlocked"
        self._record_event(
            LockEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                document_path=document_path,
                user=user,
                timestamp=datetime.now(),
                lock_id=lock.lock_id,
                details={"forced": force, "original_owner": lock.locked_by},
            )
        )

        logger.info(f"Lock released: {lock.lock_id}")
        return True, "Lock released successfully"

    async def extend_lock(
        self, document_path: str, user: str, additional_minutes: int
    ) -> Tuple[bool, Optional[DocumentLock], str]:
        """Extend an existing lock.

        Args:
            document_path: Path to document
            user: User extending the lock
            additional_minutes: Minutes to add to lock

        Returns:
            Tuple of (success, updated_lock, message)
        """
        lock = self.get_lock(document_path)

        if not lock:
            return False, None, "No active lock on document"

        if lock.locked_by != user:
            return False, None, "You do not own this lock"

        # Extend expiration
        lock.expires_at += timedelta(minutes=additional_minutes)
        self._save_locks()

        # Record event
        self._record_event(
            LockEvent(
                event_id=str(uuid4()),
                event_type="extended",
                document_path=document_path,
                user=user,
                timestamp=datetime.now(),
                lock_id=lock.lock_id,
                details={"additional_minutes": additional_minutes},
            )
        )

        return True, lock, f"Lock extended by {additional_minutes} minutes"

    def get_lock(self, document_path: str) -> Optional[DocumentLock]:
        """Get active lock for a document.

        Args:
            document_path: Path to document

        Returns:
            Lock if exists and not expired, None otherwise
        """
        lock = self.active_locks.get(document_path)

        if lock and not lock.is_expired():
            return lock

        # Clean up expired lock
        if lock:
            del self.active_locks[document_path]
            self._save_locks()

            # Record expiration
            self._record_event(
                LockEvent(
                    event_id=str(uuid4()),
                    event_type="expired",
                    document_path=document_path,
                    user=lock.locked_by,
                    timestamp=datetime.now(),
                    lock_id=lock.lock_id,
                )
            )

        return None

    def get_user_locks(self, user: str) -> List[DocumentLock]:
        """Get all active locks held by a user.

        Args:
            user: User email or ID

        Returns:
            List of active locks
        """
        user_locks = []

        for doc_path, lock in list(self.active_locks.items()):
            if lock.locked_by == user and not lock.is_expired():
                user_locks.append(lock)
            elif lock.is_expired():
                # Clean up expired lock
                del self.active_locks[doc_path]

        if len(user_locks) != len(
            [l for l in self.active_locks.values() if l.locked_by == user]
        ):
            self._save_locks()

        return user_locks

    def get_all_locks(self) -> Dict[str, DocumentLock]:
        """Get all active locks.

        Returns:
            Dictionary mapping document paths to locks
        """
        # Clean up expired locks
        expired_docs = []
        for doc_path, lock in self.active_locks.items():
            if lock.is_expired():
                expired_docs.append(doc_path)

        for doc_path in expired_docs:
            del self.active_locks[doc_path]

        if expired_docs:
            self._save_locks()

        return self.active_locks.copy()

    def check_lock_status(self, document_path: str) -> Dict[str, Any]:
        """Check detailed lock status for a document.

        Args:
            document_path: Path to document

        Returns:
            Lock status information
        """
        lock = self.get_lock(document_path)

        if not lock:
            return {
                "locked": False,
                "can_edit": True,
                "message": "Document is available for editing",
            }

        time_remaining = lock.time_remaining()
        minutes = int(time_remaining.total_seconds() / 60)

        return {
            "locked": True,
            "can_edit": False,
            "locked_by": lock.locked_by,
            "lock_type": lock.lock_type,
            "expires_in_minutes": minutes,
            "expires_at": lock.expires_at.isoformat(),
            "reason": lock.reason,
            "message": f"Locked by {lock.locked_by} for {minutes} more minutes",
        }

    def get_lock_history(
        self,
        document_path: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 100,
    ) -> List[LockEvent]:
        """Get lock history.

        Args:
            document_path: Filter by document (optional)
            user: Filter by user (optional)
            limit: Maximum events to return

        Returns:
            List of lock events
        """
        events = self.lock_history

        # Apply filters
        if document_path:
            events = [e for e in events if e.document_path == document_path]

        if user:
            events = [e for e in events if e.user == user]

        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def bulk_lock(
        self,
        document_paths: List[str],
        user: str,
        duration_minutes: int = 60,
        reason: Optional[str] = None,
    ) -> Dict[str, Tuple[bool, str]]:
        """Lock multiple documents at once.

        Args:
            document_paths: List of document paths
            user: User requesting locks
            duration_minutes: Lock duration
            reason: Reason for locking

        Returns:
            Dictionary mapping paths to (success, message) tuples
        """
        results = {}

        for doc_path in document_paths:
            request = LockRequest(
                document_path=doc_path,
                requested_by=user,
                duration_minutes=duration_minutes,
                reason=reason,
            )

            success, lock, message = await self.acquire_lock(request)
            results[doc_path] = (success, message)

        return results

    async def cleanup_expired_locks(self):
        """Clean up expired locks."""
        expired_count = 0

        for doc_path in list(self.active_locks.keys()):
            lock = self.active_locks[doc_path]
            if lock.is_expired():
                del self.active_locks[doc_path]
                expired_count += 1

                # Record expiration
                self._record_event(
                    LockEvent(
                        event_id=str(uuid4()),
                        event_type="expired",
                        document_path=doc_path,
                        user=lock.locked_by,
                        timestamp=datetime.now(),
                        lock_id=lock.lock_id,
                    )
                )

        if expired_count > 0:
            self._save_locks()
            logger.info(f"Cleaned up {expired_count} expired locks")

    def _load_locks(self):
        """Load locks from disk."""
        # Load active locks
        if self.locks_file.exists():
            try:
                with open(self.locks_file, "r") as f:
                    data = json.load(f)
                    for doc_path, lock_data in data.items():
                        lock = DocumentLock.from_dict(lock_data)
                        if not lock.is_expired():
                            self.active_locks[doc_path] = lock
            except Exception as e:
                logger.error(f"Failed to load locks: {e}")

        # Load history
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    for event_data in data:
                        event_data["timestamp"] = datetime.fromisoformat(
                            event_data["timestamp"]
                        )
                        self.lock_history.append(LockEvent(**event_data))
            except Exception as e:
                logger.error(f"Failed to load lock history: {e}")

    def _save_locks(self):
        """Save locks to disk."""
        # Save active locks
        try:
            lock_data = {
                path: lock.to_dict() for path, lock in self.active_locks.items()
            }

            with open(self.locks_file, "w") as f:
                json.dump(lock_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save locks: {e}")

        # Trim and save history
        try:
            # Keep only last 1000 events
            if len(self.lock_history) > 1000:
                self.lock_history = self.lock_history[-1000:]

            history_data = [event.to_dict() for event in self.lock_history]

            with open(self.history_file, "w") as f:
                json.dump(history_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save lock history: {e}")

    def _record_event(self, event: LockEvent):
        """Record a lock event."""
        self.lock_history.append(event)
        self._save_locks()

    def _start_cleanup_task(self):
        """Start background cleanup task."""

        async def cleanup_loop():
            while True:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self.cleanup_expired_locks()

        # Start task in background
        try:
            asyncio.create_task(cleanup_loop())
        except RuntimeError:
            # No event loop running, skip background task
            pass
