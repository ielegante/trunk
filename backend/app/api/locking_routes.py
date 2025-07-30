import logging
from datetime import timedelta
from typing import List, Optional

from app.api.auth_routes import get_current_user
from app.locking.sqlite_lock_manager import (
    DocumentLock,
    LockStatus,
    SQLiteLockManager,
    sqlite_lock_manager,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# Request/Response Models
class LockAcquisitionRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to lock")
    repository_id: str = Field(..., description="Repository ID containing the document")
    reason: Optional[str] = Field(None, description="Reason for locking the document")
    timeout_hours: Optional[float] = Field(
        1.0, ge=0.1, le=8.0, description="Lock timeout in hours"
    )


class LockExtensionRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to extend lock for")
    additional_hours: float = Field(
        ..., ge=0.1, le=4.0, description="Additional hours to extend lock"
    )


class LockAccessRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to request access for")
    message: Optional[str] = Field(None, description="Message to lock holder")


class LockReleaseRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to release lock for")
    force: bool = Field(False, description="Force release (admin only)")


class LockResponse(BaseModel):
    document_id: str
    repository_id: str
    user_id: str
    user_name: str
    locked_at: str
    expires_at: str
    reason: Optional[str]
    lock_id: str
    status: str
    time_remaining_minutes: Optional[int]


class LockRequestResponse(BaseModel):
    request_id: str
    document_id: str
    requester_id: str
    requester_name: str
    requested_at: str
    message: Optional[str]


class UserLocksResponse(BaseModel):
    user_id: str
    locks: List[LockResponse]
    total_locks: int


# Dependency to get lock manager
def get_lock_manager():
    return sqlite_lock_manager


def _lock_to_response(lock: DocumentLock) -> LockResponse:
    """Convert DocumentLock to response model"""
    from datetime import datetime

    if lock.status != LockStatus.EXPIRED:
        time_remaining = (lock.expires_at - datetime.utcnow()).total_seconds() / 60
        time_remaining_minutes = max(0, int(time_remaining))
    else:
        time_remaining_minutes = 0

    return LockResponse(
        document_id=lock.document_id,
        repository_id=lock.repository_id,
        user_id=lock.user_id,
        user_name=lock.user_name,
        locked_at=lock.locked_at.isoformat(),
        expires_at=lock.expires_at.isoformat(),
        reason=lock.reason,
        lock_id=lock.lock_id or "",
        status=lock.status.value,
        time_remaining_minutes=time_remaining_minutes,
    )


# Lock Management Endpoints


@router.post("/acquire", response_model=LockResponse)
async def acquire_document_lock(
    request: LockAcquisitionRequest,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Acquire a lock on a document for editing
    """
    try:
        timeout = timedelta(hours=request.timeout_hours)

        lock = await lock_manager.acquire_lock(
            document_id=request.document_id,
            repository_id=request.repository_id,
            user_id=current_user["id"],
            user_name=current_user["name"],
            reason=request.reason,
            timeout=timeout,
        )

        if not lock:
            # Check if document is already locked
            existing_lock = await lock_manager.get_lock(request.document_id)
            if existing_lock and existing_lock.status != LockStatus.EXPIRED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Document is already locked",
                        "locked_by": existing_lock.user_name,
                        "locked_until": existing_lock.expires_at.isoformat(),
                        "reason": existing_lock.reason,
                        "lock_id": existing_lock.lock_id,
                    },
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to acquire lock for unknown reason",
                )

        logger.info(
            f"Lock acquired for document {request.document_id} by {current_user['name']}"
        )
        return _lock_to_response(lock)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acquire lock for document {request.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while acquiring lock",
        )


@router.post("/release")
async def release_document_lock(
    request: LockReleaseRequest,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Release a document lock
    """
    try:
        # Check if user is admin for force release
        is_admin = current_user.get("role") == "admin"
        force = request.force and is_admin

        if request.force and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can force release locks",
            )

        success = await lock_manager.release_lock(
            document_id=request.document_id, user_id=current_user["id"], force=force
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lock not found or you don't have permission to release it",
            )

        logger.info(
            f"Lock released for document {request.document_id} by {current_user['name']}"
        )
        return {
            "message": "Lock released successfully",
            "document_id": request.document_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to release lock for document {request.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while releasing lock",
        )


@router.get("/document/{document_id}", response_model=Optional[LockResponse])
async def get_document_lock(
    document_id: str,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Get current lock information for a document
    """
    try:
        lock = await lock_manager.get_lock(document_id)

        if not lock:
            return None

        if lock.status == LockStatus.EXPIRED:
            return None

        return _lock_to_response(lock)

    except Exception as e:
        logger.error(f"Failed to get lock for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving lock information",
        )


@router.post("/extend")
async def extend_document_lock(
    request: LockExtensionRequest,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Extend an existing document lock
    """
    try:
        additional_time = timedelta(hours=request.additional_hours)

        success = await lock_manager.extend_lock(
            document_id=request.document_id,
            user_id=current_user["id"],
            additional_time=additional_time,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lock not found or you don't have permission to extend it",
            )

        # Get updated lock information
        updated_lock = await lock_manager.get_lock(request.document_id)

        logger.info(
            f"Lock extended for document {request.document_id} by {current_user['name']}"
        )
        return _lock_to_response(updated_lock) if updated_lock else None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extend lock for document {request.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while extending lock",
        )


@router.post("/request-access")
async def request_lock_access(
    request: LockAccessRequest,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Request access to a locked document
    """
    try:
        # Check if document is actually locked
        current_lock = await lock_manager.get_lock(request.document_id)

        if not current_lock or current_lock.status == LockStatus.EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document is not currently locked",
            )

        if current_lock.user_id == current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already own this lock",
            )

        request_id = await lock_manager.request_lock_access(
            document_id=request.document_id,
            requester_id=current_user["id"],
            requester_name=current_user["name"],
            message=request.message,
        )

        logger.info(
            f"Lock access requested for document {request.document_id} by {current_user['name']}"
        )
        return {
            "message": "Access request submitted successfully",
            "request_id": request_id,
            "document_id": request.document_id,
            "locked_by": current_lock.user_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to request access for document {request.document_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while requesting access",
        )


@router.get("/requests/{document_id}", response_model=List[LockRequestResponse])
async def get_lock_requests(
    document_id: str,
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Get pending lock requests for a document (only for lock owner)
    """
    try:
        # Verify user owns the lock
        current_lock = await lock_manager.get_lock(document_id)

        if not current_lock or current_lock.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view requests for documents you have locked",
            )

        requests = await lock_manager.get_lock_requests(document_id)

        return [
            LockRequestResponse(
                request_id=req.request_id,
                document_id=req.document_id,
                requester_id=req.requester_id,
                requester_name=req.requester_name,
                requested_at=req.requested_at.isoformat(),
                message=req.message,
            )
            for req in requests
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get requests for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving lock requests",
        )


@router.get("/user/locks", response_model=UserLocksResponse)
async def get_user_locks(
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
):
    """
    Get all locks held by the current user
    """
    try:
        locks = await lock_manager.get_user_locks(current_user["id"])

        lock_responses = [_lock_to_response(lock) for lock in locks]

        return UserLocksResponse(
            user_id=current_user["id"],
            locks=lock_responses,
            total_locks=len(lock_responses),
        )

    except Exception as e:
        logger.error(f"Failed to get locks for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving user locks",
        )


# Admin endpoints
@router.post("/admin/cleanup")
async def cleanup_expired_locks(
    current_user=Depends(get_current_user),
    lock_manager: SQLiteLockManager = Depends(get_lock_manager),
    background_tasks: BackgroundTasks = None,
):
    """
    Clean up expired locks (admin only)
    """
    try:
        if current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can perform cleanup operations",
            )

        if background_tasks:
            background_tasks.add_task(lock_manager.cleanup_expired_locks)
            return {"message": "Cleanup task scheduled"}
        else:
            cleaned = await lock_manager.cleanup_expired_locks()
            return {"message": f"Cleaned up {cleaned} expired locks"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup expired locks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during cleanup",
        )
