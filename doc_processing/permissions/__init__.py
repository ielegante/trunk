"""Permission management system for Google Drive and git repository integration."""

from .change_detector import (
    ChangeDetectionConfig,
    DocumentChange,
    DocumentChangeDetector,
)
from .drive_client import DriveFile, DrivePermission, GoogleDriveClient
from .git_permissions import GitCollaborator, GitPermissionManager
from .permission_mapper import (
    DriveRole,
    GitPermission,
    GitPermissionLevel,
    PermissionMapper,
    PermissionMapping,
)
from .sync_manager import PermissionSyncManager, SyncConfiguration, SyncJob

__all__ = [
    # Drive client
    "GoogleDriveClient",
    "DriveFile",
    "DrivePermission",
    # Git permissions
    "GitPermissionManager",
    "GitCollaborator",
    # Permission mapping
    "PermissionMapper",
    "PermissionMapping",
    "GitPermission",
    "GitPermissionLevel",
    "DriveRole",
    # Sync management
    "PermissionSyncManager",
    "SyncConfiguration",
    "SyncJob",
    # Change detection
    "DocumentChangeDetector",
    "DocumentChange",
    "ChangeDetectionConfig",
]
