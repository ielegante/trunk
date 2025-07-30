"""SQLite-based locking manager to replace Redis dependencies."""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from app.database import database_manager
from app.models import LockEntry
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class LockStatus(Enum):
    AVAILABLE = "available"
    LOCKED = "locked"
    REQUESTED = "requested"
    EXPIRED = "expired"


@dataclass
class DocumentLock:
    """Document lock information"""

    document_id: str
    repository_id: str
    user_id: str
    user_name: str
    locked_at: datetime
    expires_at: datetime
    lock_type: str = "exclusive"


@dataclass
class LockInfo:
    """Information about a lock."""

    resource_id: str
    owner_id: str
    created_at: datetime
    expires_at: datetime
    lock_type: str
    metadata: Dict[str, Any]


class SQLiteLockManager:
    """SQLite-based distributed locking manager."""

    def __init__(self, default_timeout: int = 300):
        """Initialize lock manager.

        Args:
            default_timeout: Default lock timeout in seconds
        """
        self.db = database_manager
        self.default_timeout = default_timeout
        self.local_locks = {}  # Local thread locks for performance
        self.lock = threading.RLock()

        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired_locks, daemon=True
        )
        self.cleanup_thread.start()

    def acquire_lock(
        self,
        resource_id: str,
        owner_id: str,
        timeout: Optional[int] = None,
        lock_type: str = "document",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Acquire a lock on a resource.

        Args:
            resource_id: ID of the resource to lock
            owner_id: ID of the lock owner
            timeout: Lock timeout in seconds
            lock_type: Type of lock
            metadata: Additional metadata

        Returns:
            True if lock acquired, False otherwise
        """
        timeout = timeout or self.default_timeout
        metadata = metadata or {}

        try:
            with self.db.get_session() as session:
                # Check if lock already exists and is not expired
                existing_lock = (
                    session.query(LockEntry).filter_by(resource_id=resource_id).first()
                )

                if existing_lock:
                    # Check if expired
                    if datetime.utcnow() > existing_lock.expires_at:
                        # Remove expired lock
                        session.delete(existing_lock)
                        session.commit()
                    elif existing_lock.owner_id == owner_id:
                        # Same owner, refresh the lock
                        existing_lock.expires_at = datetime.utcnow() + timedelta(
                            seconds=timeout
                        )
                        existing_lock.metadata = metadata
                        session.commit()
                        return True
                    else:
                        # Lock held by different owner
                        return False

                # Create new lock
                lock_entry = LockEntry(
                    resource_id=resource_id,
                    owner_id=owner_id,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(seconds=timeout),
                    lock_type=lock_type,
                    metadata=metadata,
                )

                session.add(lock_entry)
                session.commit()

                # Add to local cache
                with self.lock:
                    self.local_locks[resource_id] = {
                        "owner_id": owner_id,
                        "expires_at": lock_entry.expires_at,
                        "lock_type": lock_type,
                    }

                logger.info(f"Lock acquired: {resource_id} by {owner_id}")
                return True

        except IntegrityError:
            # Lock already exists (race condition)
            logger.warning(
                f"Lock acquisition failed due to race condition: {resource_id}"
            )
            return False
        except Exception as e:
            logger.error(f"Lock acquisition error: {str(e)}")
            return False

    def release_lock(self, resource_id: str, owner_id: str) -> bool:
        """Release a lock.

        Args:
            resource_id: ID of the resource to unlock
            owner_id: ID of the lock owner

        Returns:
            True if lock released, False otherwise
        """
        try:
            with self.db.get_session() as session:
                lock_entry = (
                    session.query(LockEntry)
                    .filter_by(resource_id=resource_id, owner_id=owner_id)
                    .first()
                )

                if lock_entry:
                    session.delete(lock_entry)
                    session.commit()

                    # Remove from local cache
                    with self.lock:
                        self.local_locks.pop(resource_id, None)

                    logger.info(f"Lock released: {resource_id} by {owner_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Lock release error: {str(e)}")
            return False

    def refresh_lock(
        self, resource_id: str, owner_id: str, timeout: Optional[int] = None
    ) -> bool:
        """Refresh a lock to extend its timeout.

        Args:
            resource_id: ID of the resource
            owner_id: ID of the lock owner
            timeout: New timeout in seconds

        Returns:
            True if lock refreshed, False otherwise
        """
        timeout = timeout or self.default_timeout

        try:
            with self.db.get_session() as session:
                lock_entry = (
                    session.query(LockEntry)
                    .filter_by(resource_id=resource_id, owner_id=owner_id)
                    .first()
                )

                if lock_entry:
                    lock_entry.expires_at = datetime.utcnow() + timedelta(
                        seconds=timeout
                    )
                    session.commit()

                    # Update local cache
                    with self.lock:
                        if resource_id in self.local_locks:
                            self.local_locks[resource_id][
                                "expires_at"
                            ] = lock_entry.expires_at

                    logger.info(f"Lock refreshed: {resource_id} by {owner_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Lock refresh error: {str(e)}")
            return False

    def is_locked(self, resource_id: str) -> bool:
        """Check if a resource is locked.

        Args:
            resource_id: ID of the resource

        Returns:
            True if locked, False otherwise
        """
        # Check local cache first
        with self.lock:
            if resource_id in self.local_locks:
                local_lock = self.local_locks[resource_id]
                if datetime.utcnow() < local_lock["expires_at"]:
                    return True
                else:
                    # Remove expired local lock
                    self.local_locks.pop(resource_id, None)

        # Check database
        try:
            with self.db.get_session() as session:
                lock_entry = (
                    session.query(LockEntry).filter_by(resource_id=resource_id).first()
                )

                if lock_entry:
                    if datetime.utcnow() > lock_entry.expires_at:
                        # Remove expired lock
                        session.delete(lock_entry)
                        session.commit()
                        return False
                    else:
                        return True

                return False

        except Exception as e:
            logger.error(f"Lock check error: {str(e)}")
            return False

    def get_lock_info(self, resource_id: str) -> Optional[LockInfo]:
        """Get information about a lock.

        Args:
            resource_id: ID of the resource

        Returns:
            LockInfo if lock exists, None otherwise
        """
        try:
            with self.db.get_session() as session:
                lock_entry = (
                    session.query(LockEntry).filter_by(resource_id=resource_id).first()
                )

                if lock_entry:
                    if datetime.utcnow() > lock_entry.expires_at:
                        # Remove expired lock
                        session.delete(lock_entry)
                        session.commit()
                        return None

                    return LockInfo(
                        resource_id=lock_entry.resource_id,
                        owner_id=lock_entry.owner_id,
                        created_at=lock_entry.created_at,
                        expires_at=lock_entry.expires_at,
                        lock_type=lock_entry.lock_type,
                        metadata=lock_entry.metadata,
                    )

                return None

        except Exception as e:
            logger.error(f"Get lock info error: {str(e)}")
            return None

    def get_locks_by_owner(self, owner_id: str) -> List[LockInfo]:
        """Get all locks owned by a specific owner.

        Args:
            owner_id: ID of the owner

        Returns:
            List of LockInfo objects
        """
        try:
            with self.db.get_session() as session:
                lock_entries = (
                    session.query(LockEntry).filter_by(owner_id=owner_id).all()
                )

                locks = []
                current_time = datetime.utcnow()

                for lock_entry in lock_entries:
                    if current_time > lock_entry.expires_at:
                        # Remove expired lock
                        session.delete(lock_entry)
                    else:
                        locks.append(
                            LockInfo(
                                resource_id=lock_entry.resource_id,
                                owner_id=lock_entry.owner_id,
                                created_at=lock_entry.created_at,
                                expires_at=lock_entry.expires_at,
                                lock_type=lock_entry.lock_type,
                                metadata=lock_entry.metadata,
                            )
                        )

                session.commit()
                return locks

        except Exception as e:
            logger.error(f"Get locks by owner error: {str(e)}")
            return []

    def release_all_locks(self, owner_id: str) -> int:
        """Release all locks owned by a specific owner.

        Args:
            owner_id: ID of the owner

        Returns:
            Number of locks released
        """
        try:
            with self.db.get_session() as session:
                lock_entries = (
                    session.query(LockEntry).filter_by(owner_id=owner_id).all()
                )

                count = len(lock_entries)
                for lock_entry in lock_entries:
                    session.delete(lock_entry)

                    # Remove from local cache
                    with self.lock:
                        self.local_locks.pop(lock_entry.resource_id, None)

                session.commit()
                logger.info(f"Released {count} locks for owner {owner_id}")
                return count

        except Exception as e:
            logger.error(f"Release all locks error: {str(e)}")
            return 0

    @contextmanager
    def lock_context(
        self,
        resource_id: str,
        owner_id: str,
        timeout: Optional[int] = None,
        lock_type: str = "document",
    ):
        """Context manager for acquiring and releasing locks.

        Args:
            resource_id: ID of the resource to lock
            owner_id: ID of the lock owner
            timeout: Lock timeout in seconds
            lock_type: Type of lock

        Yields:
            True if lock acquired, False otherwise
        """
        acquired = self.acquire_lock(resource_id, owner_id, timeout, lock_type)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_lock(resource_id, owner_id)

    def force_release_lock(self, resource_id: str) -> bool:
        """Force release a lock regardless of owner.

        Args:
            resource_id: ID of the resource

        Returns:
            True if lock released, False otherwise
        """
        try:
            with self.db.get_session() as session:
                lock_entry = (
                    session.query(LockEntry).filter_by(resource_id=resource_id).first()
                )

                if lock_entry:
                    session.delete(lock_entry)
                    session.commit()

                    # Remove from local cache
                    with self.lock:
                        self.local_locks.pop(resource_id, None)

                    logger.warning(f"Lock force released: {resource_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Force release lock error: {str(e)}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get locking statistics."""
        try:
            with self.db.get_session() as session:
                # Total locks
                total_locks = session.query(LockEntry).count()

                # Locks by type
                lock_types = (
                    session.query(LockEntry.lock_type, func.count(LockEntry.id))
                    .group_by(LockEntry.lock_type)
                    .all()
                )

                # Expired locks
                expired_locks = (
                    session.query(LockEntry)
                    .filter(LockEntry.expires_at < datetime.utcnow())
                    .count()
                )

                return {
                    "total_locks": total_locks,
                    "expired_locks": expired_locks,
                    "active_locks": total_locks - expired_locks,
                    "lock_types": {lock_type: count for lock_type, count in lock_types},
                    "local_cache_size": len(self.local_locks),
                }

        except Exception as e:
            logger.error(f"Get statistics error: {str(e)}")
            return {"error": str(e)}

    def _cleanup_expired_locks(self):
        """Background thread to clean up expired locks."""
        while True:
            try:
                time.sleep(60)  # Check every minute

                with self.db.get_session() as session:
                    expired_locks = (
                        session.query(LockEntry)
                        .filter(LockEntry.expires_at < datetime.utcnow())
                        .all()
                    )

                    if expired_locks:
                        count = len(expired_locks)
                        for lock in expired_locks:
                            session.delete(lock)

                            # Remove from local cache
                            with self.lock:
                                self.local_locks.pop(lock.resource_id, None)

                        session.commit()
                        logger.info(f"Cleaned up {count} expired locks")

                # Also clean up local cache
                with self.lock:
                    current_time = datetime.utcnow()
                    expired_local = [
                        resource_id
                        for resource_id, info in self.local_locks.items()
                        if current_time > info["expires_at"]
                    ]

                    for resource_id in expired_local:
                        self.local_locks.pop(resource_id, None)

            except Exception as e:
                logger.error(f"Lock cleanup error: {str(e)}")
                time.sleep(60)  # Wait before retrying


# Global lock manager instance
sqlite_lock_manager = SQLiteLockManager()
