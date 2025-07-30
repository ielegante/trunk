"""Document change detection system for Google Drive files."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .drive_client import GoogleDriveClient

logger = logging.getLogger(__name__)


@dataclass
class DocumentChange:
    """Represents a detected change in a document."""

    file_id: str
    file_name: str
    change_type: str  # content, permissions, metadata, structure
    timestamp: datetime
    actor: Optional[str] = None
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class ChangeDetectionConfig:
    """Configuration for change detection."""

    check_interval_minutes: int = 15
    include_content_changes: bool = True
    include_permission_changes: bool = True
    include_metadata_changes: bool = True
    content_hash_algorithm: str = "sha256"
    max_file_size_mb: int = 100
    notification_webhooks: List[str] = None

    def __post_init__(self):
        if self.notification_webhooks is None:
            self.notification_webhooks = []


class DocumentChangeDetector:
    """Detects changes in Google Drive documents."""

    def __init__(
        self,
        drive_client: GoogleDriveClient,
        config: Optional[ChangeDetectionConfig] = None,
        state_dir: Optional[Path] = None,
    ):
        """Initialize change detector.

        Args:
            drive_client: GoogleDriveClient instance
            config: Optional ChangeDetectionConfig
            state_dir: Directory to store change detection state
        """
        self.drive_client = drive_client
        self.config = config or ChangeDetectionConfig()
        self.state_dir = state_dir or Path(".trunk/change_detection")

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # File paths for persistence
        self.snapshots_file = self.state_dir / "document_snapshots.json"
        self.changes_file = self.state_dir / "detected_changes.json"

        # Internal state
        self.document_snapshots: Dict[str, Dict[str, Any]] = {}
        self.detected_changes: List[DocumentChange] = []

        # Load persisted state
        self._load_state()

    def detect_changes(self, file_ids: List[str]) -> List[DocumentChange]:
        """Detect changes in specified Google Drive files.

        Args:
            file_ids: List of Google Drive file IDs to check

        Returns:
            List of detected DocumentChange objects
        """
        changes = []

        for file_id in file_ids:
            try:
                file_changes = self._detect_file_changes(file_id)
                changes.extend(file_changes)
            except Exception as e:
                logger.error(f"Failed to detect changes for file {file_id}: {e}")

        # Save detected changes
        if changes:
            self.detected_changes.extend(changes)
            self._save_changes()

        return changes

    def _detect_file_changes(self, file_id: str) -> List[DocumentChange]:
        """Detect changes in a single file.

        Args:
            file_id: Google Drive file ID

        Returns:
            List of detected changes for this file
        """
        changes = []

        # Get current file state
        current_file = self.drive_client.get_file_metadata(
            file_id, include_permissions=self.config.include_permission_changes
        )

        if not current_file:
            logger.warning(f"File {file_id} not found")
            return changes

        # Get previous snapshot
        previous_snapshot = self.document_snapshots.get(file_id)

        # Create current snapshot
        current_snapshot = self._create_file_snapshot(current_file)

        if previous_snapshot:
            # Compare snapshots to detect changes

            # Check content changes
            if self.config.include_content_changes:
                content_change = self._detect_content_change(
                    file_id, previous_snapshot, current_snapshot
                )
                if content_change:
                    changes.append(content_change)

            # Check permission changes
            if self.config.include_permission_changes:
                permission_changes = self._detect_permission_changes(
                    current_file, previous_snapshot, current_snapshot
                )
                changes.extend(permission_changes)

            # Check metadata changes
            if self.config.include_metadata_changes:
                metadata_change = self._detect_metadata_change(
                    current_file, previous_snapshot, current_snapshot
                )
                if metadata_change:
                    changes.append(metadata_change)

        # Update snapshot
        self.document_snapshots[file_id] = current_snapshot
        self._save_snapshots()

        return changes

    def _create_file_snapshot(self, drive_file) -> Dict[str, Any]:
        """Create a snapshot of file state for comparison.

        Args:
            drive_file: DriveFile object

        Returns:
            Dictionary containing file snapshot
        """
        snapshot = {
            "file_id": drive_file.id,
            "file_name": drive_file.name,
            "mime_type": drive_file.mime_type,
            "modified_time": drive_file.modified_time,
            "snapshot_time": datetime.now().isoformat(),
            "content_hash": None,
            "permissions_hash": None,
            "metadata_hash": None,
        }

        # Calculate content hash if enabled
        if self.config.include_content_changes:
            content_hash = self._calculate_content_hash(drive_file)
            if content_hash:
                snapshot["content_hash"] = content_hash

        # Calculate permissions hash
        if self.config.include_permission_changes and drive_file.permissions:
            permissions_data = json.dumps(
                [perm.to_dict() for perm in drive_file.permissions], sort_keys=True
            )
            snapshot["permissions_hash"] = hashlib.sha256(
                permissions_data.encode()
            ).hexdigest()

        # Calculate metadata hash
        if self.config.include_metadata_changes:
            metadata = {
                "name": drive_file.name,
                "mime_type": drive_file.mime_type,
                "parents": drive_file.parents,
            }
            metadata_data = json.dumps(metadata, sort_keys=True)
            snapshot["metadata_hash"] = hashlib.sha256(
                metadata_data.encode()
            ).hexdigest()

        return snapshot

    def _calculate_content_hash(self, drive_file) -> Optional[str]:
        """Calculate hash of file content.

        Args:
            drive_file: DriveFile object

        Returns:
            Content hash or None if unable to calculate
        """
        # For now, use modified time as a proxy for content changes
        # In a full implementation, would download and hash actual content
        if drive_file.modified_time:
            return hashlib.sha256(
                f"{drive_file.id}:{drive_file.modified_time}".encode()
            ).hexdigest()
        return None

    def _detect_content_change(
        self, file_id: str, previous: Dict[str, Any], current: Dict[str, Any]
    ) -> Optional[DocumentChange]:
        """Detect content changes between snapshots.

        Args:
            file_id: Google Drive file ID
            previous: Previous snapshot
            current: Current snapshot

        Returns:
            DocumentChange if content changed, None otherwise
        """
        if previous.get("content_hash") != current.get("content_hash"):
            return DocumentChange(
                file_id=file_id,
                file_name=current["file_name"],
                change_type="content",
                timestamp=datetime.now(),
                previous_hash=previous.get("content_hash"),
                current_hash=current.get("content_hash"),
                details={
                    "previous_modified": previous.get("modified_time"),
                    "current_modified": current.get("modified_time"),
                },
            )
        return None

    def _detect_permission_changes(
        self, drive_file, previous: Dict[str, Any], current: Dict[str, Any]
    ) -> List[DocumentChange]:
        """Detect permission changes between snapshots.

        Args:
            drive_file: Current DriveFile object
            previous: Previous snapshot
            current: Current snapshot

        Returns:
            List of permission changes
        """
        changes = []

        if previous.get("permissions_hash") != current.get("permissions_hash"):
            # Get detailed permission changes using Drive Activity API
            recent_changes = self.drive_client.get_file_changes(
                drive_file.id, start_time=previous.get("snapshot_time")
            )

            for activity in recent_changes:
                # Filter for permission-related actions
                for action in activity.get("actions", []):
                    if action["type"] in ["permissionChange", "create", "delete"]:
                        change = DocumentChange(
                            file_id=drive_file.id,
                            file_name=drive_file.name,
                            change_type="permissions",
                            timestamp=datetime.fromisoformat(
                                activity["timestamp"].replace("Z", "+00:00")
                            ),
                            actor=self._extract_actor_name(activity),
                            details={
                                "action": action["type"],
                                "action_detail": action.get("detail", {}),
                                "previous_hash": previous.get("permissions_hash"),
                                "current_hash": current.get("permissions_hash"),
                            },
                        )
                        changes.append(change)

        return changes

    def _detect_metadata_change(
        self, drive_file, previous: Dict[str, Any], current: Dict[str, Any]
    ) -> Optional[DocumentChange]:
        """Detect metadata changes between snapshots.

        Args:
            drive_file: Current DriveFile object
            previous: Previous snapshot
            current: Current snapshot

        Returns:
            DocumentChange if metadata changed, None otherwise
        """
        if previous.get("metadata_hash") != current.get("metadata_hash"):
            return DocumentChange(
                file_id=drive_file.id,
                file_name=drive_file.name,
                change_type="metadata",
                timestamp=datetime.now(),
                previous_hash=previous.get("metadata_hash"),
                current_hash=current.get("metadata_hash"),
                details={
                    "previous_name": previous.get("file_name"),
                    "current_name": current.get("file_name"),
                    "mime_type_changed": previous.get("mime_type")
                    != current.get("mime_type"),
                },
            )
        return None

    def _extract_actor_name(self, activity: Dict[str, Any]) -> Optional[str]:
        """Extract actor name from Drive Activity response.

        Args:
            activity: Activity dictionary from Drive API

        Returns:
            Actor name or None
        """
        for actor in activity.get("actors", []):
            if "user" in actor and "name" in actor["user"]:
                return actor["user"]["name"]
        return None

    def get_recent_changes(
        self,
        file_id: Optional[str] = None,
        change_type: Optional[str] = None,
        hours: int = 24,
    ) -> List[DocumentChange]:
        """Get recent changes with optional filtering.

        Args:
            file_id: Optional filter by file ID
            change_type: Optional filter by change type
            hours: Number of hours to look back

        Returns:
            List of recent DocumentChange objects
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        changes = self.detected_changes

        # Apply filters
        if file_id:
            changes = [c for c in changes if c.file_id == file_id]

        if change_type:
            changes = [c for c in changes if c.change_type == change_type]

        # Filter by time
        changes = [c for c in changes if c.timestamp > cutoff_time]

        # Sort by timestamp (newest first)
        changes.sort(key=lambda c: c.timestamp, reverse=True)

        return changes

    def clear_old_changes(self, days: int = 30) -> int:
        """Clear old detected changes.

        Args:
            days: Remove changes older than this many days

        Returns:
            Number of changes removed
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        original_count = len(self.detected_changes)
        self.detected_changes = [
            c for c in self.detected_changes if c.timestamp > cutoff_time
        ]

        removed_count = original_count - len(self.detected_changes)

        if removed_count > 0:
            self._save_changes()
            logger.info(f"Cleared {removed_count} old changes")

        return removed_count

    def _save_snapshots(self) -> None:
        """Save document snapshots to file."""
        with open(self.snapshots_file, "w") as f:
            json.dump(self.document_snapshots, f, indent=2)

    def _save_changes(self) -> None:
        """Save detected changes to file."""
        changes_data = [change.to_dict() for change in self.detected_changes]
        with open(self.changes_file, "w") as f:
            json.dump(changes_data, f, indent=2)

    def _load_state(self) -> None:
        """Load persisted state from files."""
        # Load snapshots
        if self.snapshots_file.exists():
            try:
                with open(self.snapshots_file, "r") as f:
                    self.document_snapshots = json.load(f)
                logger.debug(
                    f"Loaded {len(self.document_snapshots)} document snapshots"
                )
            except Exception as e:
                logger.error(f"Failed to load snapshots: {e}")

        # Load changes
        if self.changes_file.exists():
            try:
                with open(self.changes_file, "r") as f:
                    changes_data = json.load(f)

                for change_dict in changes_data:
                    # Convert timestamp string back to datetime
                    change_dict["timestamp"] = datetime.fromisoformat(
                        change_dict["timestamp"]
                    )
                    self.detected_changes.append(DocumentChange(**change_dict))

                logger.debug(f"Loaded {len(self.detected_changes)} detected changes")
            except Exception as e:
                logger.error(f"Failed to load changes: {e}")
