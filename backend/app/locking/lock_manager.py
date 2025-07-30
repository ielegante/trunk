import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

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
    reason: Optional[str] = None
    lock_id: Optional[str] = None
    status: LockStatus = LockStatus.LOCKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "repository_id": self.repository_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "locked_at": self.locked_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "reason": self.reason,
            "lock_id": self.lock_id,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentLock":
        return cls(
            document_id=data["document_id"],
            repository_id=data["repository_id"],
            user_id=data["user_id"],
            user_name=data["user_name"],
            locked_at=datetime.fromisoformat(data["locked_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            reason=data.get("reason"),
            lock_id=data.get("lock_id"),
            status=LockStatus(data.get("status", "locked")),
        )


@dataclass
class LockRequest:
    """Lock request from another user"""

    request_id: str
    document_id: str
    requester_id: str
    requester_name: str
    requested_at: datetime
    message: Optional[str] = None


class LockManager:
    """Manages document locks using Redis as backend"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.lock_prefix = "trunk:lock:"
        self.request_prefix = "trunk:lock_request:"
        self.default_timeout = timedelta(hours=1)
        self.max_timeout = timedelta(hours=8)

    def _lock_key(self, document_id: str) -> str:
        return f"{self.lock_prefix}{document_id}"

    def _request_key(self, document_id: str) -> str:
        return f"{self.request_prefix}{document_id}"

    async def acquire_lock(
        self,
        document_id: str,
        repository_id: str,
        user_id: str,
        user_name: str,
        reason: Optional[str] = None,
        timeout: Optional[timedelta] = None,
    ) -> Optional[DocumentLock]:
        """
        Acquire a lock on a document

        Returns:
            DocumentLock if successful, None if document is already locked
        """
        if timeout is None:
            timeout = self.default_timeout
        elif timeout > self.max_timeout:
            timeout = self.max_timeout

        lock_key = self._lock_key(document_id)
        lock_id = str(uuid.uuid4())

        now = datetime.utcnow()
        expires_at = now + timeout

        lock = DocumentLock(
            document_id=document_id,
            repository_id=repository_id,
            user_id=user_id,
            user_name=user_name,
            locked_at=now,
            expires_at=expires_at,
            reason=reason,
            lock_id=lock_id,
        )

        # Use Redis SET with NX (only if not exists) and EX (expiry)
        lock_data = json.dumps(lock.to_dict())

        # Set lock with expiry, only if key doesn't exist
        result = await self.redis.set(
            lock_key,
            lock_data,
            nx=True,  # Only set if key doesn't exist
            ex=int(timeout.total_seconds()),
        )

        if result:
            logger.info(f"Lock acquired for document {document_id} by {user_name}")
            return lock
        else:
            logger.info(
                f"Lock acquisition failed for document {document_id} - already locked"
            )
            return None

    async def release_lock(
        self, document_id: str, user_id: str, force: bool = False
    ) -> bool:
        """
        Release a document lock

        Args:
            document_id: Document to unlock
            user_id: User requesting unlock
            force: Admin override to force unlock

        Returns:
            True if lock was released, False if not authorized or no lock exists
        """
        lock_key = self._lock_key(document_id)

        # Get current lock
        current_lock = await self.get_lock(document_id)
        if not current_lock:
            return True  # No lock exists

        # Check authorization
        if not force and current_lock.user_id != user_id:
            logger.warning(
                f"Unauthorized lock release attempt by {user_id} for document {document_id}"
            )
            return False

        # Remove lock
        deleted = await self.redis.delete(lock_key)

        if deleted:
            logger.info(f"Lock released for document {document_id} by {user_id}")
            # Clear any pending requests
            await self.redis.delete(self._request_key(document_id))
            return True

        return False

    async def get_lock(self, document_id: str) -> Optional[DocumentLock]:
        """Get current lock information for a document"""
        lock_key = self._lock_key(document_id)

        lock_data = await self.redis.get(lock_key)
        if not lock_data:
            return None

        try:
            lock_dict = json.loads(lock_data)
            lock = DocumentLock.from_dict(lock_dict)

            # Check if lock has expired
            if datetime.utcnow() > lock.expires_at:
                # Clean up expired lock
                await self.redis.delete(lock_key)
                lock.status = LockStatus.EXPIRED
                return lock

            return lock
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse lock data for {document_id}: {e}")
            # Clean up corrupted lock data
            await self.redis.delete(lock_key)
            return None

    async def extend_lock(
        self, document_id: str, user_id: str, additional_time: timedelta
    ) -> bool:
        """Extend an existing lock"""
        current_lock = await self.get_lock(document_id)

        if not current_lock or current_lock.user_id != user_id:
            return False

        new_expires_at = current_lock.expires_at + additional_time
        max_expires_at = datetime.utcnow() + self.max_timeout

        if new_expires_at > max_expires_at:
            new_expires_at = max_expires_at

        current_lock.expires_at = new_expires_at

        lock_key = self._lock_key(document_id)
        lock_data = json.dumps(current_lock.to_dict())

        # Update lock with new expiry
        new_ttl = int((new_expires_at - datetime.utcnow()).total_seconds())
        await self.redis.setex(lock_key, new_ttl, lock_data)

        logger.info(f"Lock extended for document {document_id} until {new_expires_at}")
        return True

    async def request_lock_access(
        self,
        document_id: str,
        requester_id: str,
        requester_name: str,
        message: Optional[str] = None,
    ) -> str:
        """Request access to a locked document"""
        request_id = str(uuid.uuid4())

        request = LockRequest(
            request_id=request_id,
            document_id=document_id,
            requester_id=requester_id,
            requester_name=requester_name,
            requested_at=datetime.utcnow(),
            message=message,
        )

        request_key = self._request_key(document_id)

        # Store request (expire in 24 hours)
        request_data = json.dumps(
            {
                "request_id": request.request_id,
                "document_id": request.document_id,
                "requester_id": request.requester_id,
                "requester_name": request.requester_name,
                "requested_at": request.requested_at.isoformat(),
                "message": request.message,
            }
        )

        await self.redis.setex(request_key, 86400, request_data)  # 24 hours

        logger.info(
            f"Lock request created for document {document_id} by {requester_name}"
        )
        return request_id

    async def get_lock_requests(self, document_id: str) -> List[LockRequest]:
        """Get pending lock requests for a document"""
        request_key = self._request_key(document_id)

        request_data = await self.redis.get(request_key)
        if not request_data:
            return []

        try:
            request_dict = json.loads(request_data)
            return [
                LockRequest(
                    request_id=request_dict["request_id"],
                    document_id=request_dict["document_id"],
                    requester_id=request_dict["requester_id"],
                    requester_name=request_dict["requester_name"],
                    requested_at=datetime.fromisoformat(request_dict["requested_at"]),
                    message=request_dict.get("message"),
                )
            ]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse request data for {document_id}: {e}")
            return []

    async def get_user_locks(self, user_id: str) -> List[DocumentLock]:
        """Get all locks held by a user"""
        # This requires scanning all lock keys - in production, consider
        # maintaining a user->locks index for better performance
        pattern = f"{self.lock_prefix}*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        user_locks = []
        for key in keys:
            lock_data = await self.redis.get(key)
            if lock_data:
                try:
                    lock_dict = json.loads(lock_data)
                    if lock_dict.get("user_id") == user_id:
                        lock = DocumentLock.from_dict(lock_dict)

                        # Check if lock has expired
                        if datetime.utcnow() <= lock.expires_at:
                            user_locks.append(lock)
                        else:
                            # Clean up expired lock
                            await self.redis.delete(key)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        return user_locks

    async def cleanup_expired_locks(self) -> int:
        """Clean up expired locks (maintenance operation)"""
        pattern = f"{self.lock_prefix}*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        cleaned = 0
        for key in keys:
            lock_data = await self.redis.get(key)
            if lock_data:
                try:
                    lock_dict = json.loads(lock_data)
                    expires_at = datetime.fromisoformat(lock_dict["expires_at"])

                    if datetime.utcnow() > expires_at:
                        await self.redis.delete(key)
                        cleaned += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Clean up corrupted data
                    await self.redis.delete(key)
                    cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired locks")

        return cleaned
