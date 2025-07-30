"""Real-time change detection and tracking for Google Docs documents."""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .google_docs import ConversionResult, GoogleDocsConverter

logger = logging.getLogger(__name__)


@dataclass
class DocumentSnapshot:
    """Represents a snapshot of a document at a specific time."""

    document_id: str
    timestamp: datetime
    content_hash: str
    structure_hash: str
    metadata: Dict[str, Any]
    elements_count: int
    content_length: int
    last_modified: Optional[str] = None
    version_id: Optional[str] = None


@dataclass
class ChangeEvent:
    """Represents a detected change in a document."""

    document_id: str
    change_type: str  # content, structure, metadata, comments, suggestions
    timestamp: datetime
    change_details: Dict[str, Any]
    affected_range: Optional[Dict[str, int]] = None  # start_index, end_index
    author: Optional[str] = None
    change_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "document_id": self.document_id,
            "change_type": self.change_type,
            "timestamp": self.timestamp.isoformat(),
            "change_details": self.change_details,
            "affected_range": self.affected_range,
            "author": self.author,
            "change_id": self.change_id,
        }


@dataclass
class TrackingConfig:
    """Configuration for real-time change tracking."""

    polling_interval: int = 30  # seconds
    enable_content_tracking: bool = True
    enable_structure_tracking: bool = True
    enable_metadata_tracking: bool = True
    enable_comment_tracking: bool = True
    enable_suggestion_tracking: bool = True
    change_batch_size: int = 100
    max_history_days: int = 30
    webhook_endpoints: List[str] = None

    def __post_init__(self):
        if self.webhook_endpoints is None:
            self.webhook_endpoints = []


class RealTimeChangeTracker:
    """Tracks changes in Google Docs documents in real-time."""

    def __init__(
        self,
        converter: GoogleDocsConverter,
        config: Optional[TrackingConfig] = None,
        storage_path: Optional[Path] = None,
    ):
        """Initialize change tracker.

        Args:
            converter: GoogleDocsConverter instance
            config: TrackingConfig for customizing behavior
            storage_path: Path for storing snapshots and change history
        """
        self.converter = converter
        self.config = config or TrackingConfig()
        self.storage_path = storage_path or Path(".trunk/change_tracking")

        # Internal state
        self.tracked_documents: Set[str] = set()
        self.document_snapshots: Dict[str, DocumentSnapshot] = {}
        self.change_history: List[ChangeEvent] = []
        self.change_callbacks: List[Callable[[ChangeEvent], None]] = []
        self.is_running = False
        self.tracking_task = None

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load persisted state
        self._load_state()

    def start_tracking(self, document_ids: List[str]):
        """Start real-time tracking for specified documents.

        Args:
            document_ids: List of Google Docs document IDs to track
        """
        self.tracked_documents.update(document_ids)

        # Create initial snapshots for new documents
        for doc_id in document_ids:
            if doc_id not in self.document_snapshots:
                try:
                    snapshot = self._create_snapshot(doc_id)
                    self.document_snapshots[doc_id] = snapshot
                    logger.info(f"Created initial snapshot for document {doc_id}")
                except Exception as e:
                    logger.error(f"Failed to create initial snapshot for {doc_id}: {e}")

        # Start tracking loop if not already running
        if not self.is_running:
            self.is_running = True
            self.tracking_task = asyncio.create_task(self._tracking_loop())
            logger.info(f"Started real-time tracking for {len(document_ids)} documents")

    def stop_tracking(self, document_ids: Optional[List[str]] = None):
        """Stop tracking for specified documents or all documents.

        Args:
            document_ids: Optional list of document IDs to stop tracking.
                         If None, stops tracking all documents.
        """
        if document_ids is None:
            # Stop tracking all documents
            self.tracked_documents.clear()
            self.is_running = False
            if self.tracking_task:
                self.tracking_task.cancel()
            logger.info("Stopped tracking all documents")
        else:
            # Stop tracking specific documents
            self.tracked_documents.difference_update(document_ids)
            logger.info(f"Stopped tracking {len(document_ids)} documents")

            # If no documents left, stop the tracking loop
            if not self.tracked_documents:
                self.is_running = False
                if self.tracking_task:
                    self.tracking_task.cancel()

    def add_change_callback(self, callback: Callable[[ChangeEvent], None]):
        """Add a callback function to be called when changes are detected.

        Args:
            callback: Function to call with ChangeEvent when changes occur
        """
        self.change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[ChangeEvent], None]):
        """Remove a change callback function.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self.change_callbacks:
            self.change_callbacks.remove(callback)

    async def _tracking_loop(self):
        """Main tracking loop that polls for changes."""
        while self.is_running:
            try:
                # Check each tracked document for changes
                for doc_id in list(self.tracked_documents):
                    try:
                        await self._check_document_changes(doc_id)
                    except Exception as e:
                        logger.error(
                            f"Error checking changes for document {doc_id}: {e}"
                        )

                # Clean up old history
                self._cleanup_old_history()

                # Save state periodically
                self._save_state()

                # Wait before next poll
                await asyncio.sleep(self.config.polling_interval)

            except asyncio.CancelledError:
                logger.info("Change tracking loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")
                await asyncio.sleep(self.config.polling_interval)

    async def _check_document_changes(self, document_id: str):
        """Check for changes in a specific document.

        Args:
            document_id: Google Docs document ID to check
        """
        try:
            # Create new snapshot
            new_snapshot = self._create_snapshot(document_id)

            # Get previous snapshot
            previous_snapshot = self.document_snapshots.get(document_id)

            if previous_snapshot:
                # Detect changes by comparing snapshots
                changes = self._detect_changes(previous_snapshot, new_snapshot)

                # Process detected changes
                for change in changes:
                    await self._process_change(change)

            # Update stored snapshot
            self.document_snapshots[document_id] = new_snapshot

        except Exception as e:
            logger.error(f"Failed to check changes for document {document_id}: {e}")

    def _create_snapshot(self, document_id: str) -> DocumentSnapshot:
        """Create a snapshot of the current document state.

        Args:
            document_id: Google Docs document ID

        Returns:
            DocumentSnapshot of current state
        """
        try:
            # Get current document content
            conversion_result = self.converter.to_markdown(document_id)

            # Calculate content hash
            content_hash = hashlib.sha256(
                conversion_result.content.encode("utf-8")
            ).hexdigest()

            # Calculate structure hash (based on elements)
            structure_data = json.dumps(
                [
                    (elem.element_type, elem.formatting)
                    for elem in conversion_result.elements
                ],
                sort_keys=True,
            )
            structure_hash = hashlib.sha256(structure_data.encode("utf-8")).hexdigest()

            # Create snapshot
            snapshot = DocumentSnapshot(
                document_id=document_id,
                timestamp=datetime.now(),
                content_hash=content_hash,
                structure_hash=structure_hash,
                metadata=conversion_result.metadata,
                elements_count=len(conversion_result.elements),
                content_length=len(conversion_result.content),
                last_modified=conversion_result.metadata.get("modified_time"),
                version_id=conversion_result.metadata.get("version_id"),
            )

            return snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot for document {document_id}: {e}")
            raise

    def _detect_changes(
        self, previous: DocumentSnapshot, current: DocumentSnapshot
    ) -> List[ChangeEvent]:
        """Detect changes between two snapshots.

        Args:
            previous: Previous document snapshot
            current: Current document snapshot

        Returns:
            List of detected changes
        """
        changes = []

        # Content changes
        if (
            self.config.enable_content_tracking
            and previous.content_hash != current.content_hash
        ):
            change = ChangeEvent(
                document_id=current.document_id,
                change_type="content",
                timestamp=current.timestamp,
                change_details={
                    "previous_hash": previous.content_hash,
                    "current_hash": current.content_hash,
                    "previous_length": previous.content_length,
                    "current_length": current.content_length,
                    "length_delta": current.content_length - previous.content_length,
                },
                author=current.metadata.get("last_modifying_user", {}).get(
                    "displayName"
                ),
            )
            changes.append(change)

        # Structure changes
        if (
            self.config.enable_structure_tracking
            and previous.structure_hash != current.structure_hash
        ):
            change = ChangeEvent(
                document_id=current.document_id,
                change_type="structure",
                timestamp=current.timestamp,
                change_details={
                    "previous_hash": previous.structure_hash,
                    "current_hash": current.structure_hash,
                    "previous_elements": previous.elements_count,
                    "current_elements": current.elements_count,
                    "elements_delta": current.elements_count - previous.elements_count,
                },
                author=current.metadata.get("last_modifying_user", {}).get(
                    "displayName"
                ),
            )
            changes.append(change)

        # Metadata changes
        if self.config.enable_metadata_tracking:
            metadata_changes = self._detect_metadata_changes(
                previous.metadata, current.metadata
            )
            if metadata_changes:
                change = ChangeEvent(
                    document_id=current.document_id,
                    change_type="metadata",
                    timestamp=current.timestamp,
                    change_details=metadata_changes,
                    author=current.metadata.get("last_modifying_user", {}).get(
                        "displayName"
                    ),
                )
                changes.append(change)

        return changes

    def _detect_metadata_changes(
        self, previous: Dict[str, Any], current: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Detect changes in document metadata.

        Args:
            previous: Previous metadata
            current: Current metadata

        Returns:
            Dictionary of detected changes or None
        """
        changes = {}

        # Check for title changes
        if previous.get("title") != current.get("title"):
            changes["title"] = {
                "previous": previous.get("title"),
                "current": current.get("title"),
            }

        # Check for modification time changes
        if previous.get("modified_time") != current.get("modified_time"):
            changes["modified_time"] = {
                "previous": previous.get("modified_time"),
                "current": current.get("modified_time"),
            }

        # Check for last modifying user changes
        prev_user = previous.get("last_modifying_user", {})
        curr_user = current.get("last_modifying_user", {})

        if prev_user.get("emailAddress") != curr_user.get("emailAddress"):
            changes["last_modifying_user"] = {
                "previous": prev_user.get("emailAddress"),
                "current": curr_user.get("emailAddress"),
            }

        return changes if changes else None

    async def _process_change(self, change: ChangeEvent):
        """Process a detected change.

        Args:
            change: Detected change event
        """
        # Add to change history
        self.change_history.append(change)

        # Log the change
        logger.info(
            f"Change detected in document {change.document_id}: "
            f"{change.change_type} by {change.author or 'unknown'}"
        )

        # Call registered callbacks
        for callback in self.change_callbacks:
            try:
                await asyncio.get_event_loop().run_in_executor(None, callback, change)
            except Exception as e:
                logger.error(f"Error in change callback: {e}")

        # Send webhook notifications if configured
        if self.config.webhook_endpoints:
            await self._send_webhook_notifications(change)

    async def _send_webhook_notifications(self, change: ChangeEvent):
        """Send webhook notifications for a change.

        Args:
            change: Change event to notify about
        """
        import aiohttp

        payload = {"event": "document_change", "change": change.to_dict()}

        async with aiohttp.ClientSession() as session:
            for webhook_url in self.config.webhook_endpoints:
                try:
                    async with session.post(
                        webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:
                        if response.status == 200:
                            logger.debug(f"Webhook notification sent to {webhook_url}")
                        else:
                            logger.warning(
                                f"Webhook notification failed: {response.status}"
                            )
                except Exception as e:
                    logger.error(
                        f"Failed to send webhook notification to {webhook_url}: {e}"
                    )

    def get_change_history(
        self,
        document_id: Optional[str] = None,
        change_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ChangeEvent]:
        """Get change history with optional filtering.

        Args:
            document_id: Optional filter by document ID
            change_type: Optional filter by change type
            since: Optional filter by timestamp
            limit: Maximum number of changes to return

        Returns:
            List of change events
        """
        changes = self.change_history

        # Apply filters
        if document_id:
            changes = [c for c in changes if c.document_id == document_id]

        if change_type:
            changes = [c for c in changes if c.change_type == change_type]

        if since:
            changes = [c for c in changes if c.timestamp >= since]

        # Sort by timestamp (newest first) and apply limit
        changes.sort(key=lambda c: c.timestamp, reverse=True)
        return changes[:limit]

    def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """Get current status of a tracked document.

        Args:
            document_id: Google Docs document ID

        Returns:
            Dictionary with document status information
        """
        if document_id not in self.tracked_documents:
            return {"error": "Document not being tracked"}

        snapshot = self.document_snapshots.get(document_id)
        if not snapshot:
            return {"error": "No snapshot available"}

        # Get recent changes for this document
        recent_changes = self.get_change_history(
            document_id=document_id, since=datetime.now() - timedelta(hours=24)
        )

        return {
            "document_id": document_id,
            "is_tracked": True,
            "last_snapshot": snapshot.timestamp.isoformat(),
            "content_hash": snapshot.content_hash,
            "structure_hash": snapshot.structure_hash,
            "elements_count": snapshot.elements_count,
            "content_length": snapshot.content_length,
            "last_modified": snapshot.last_modified,
            "recent_changes": len(recent_changes),
            "change_types": list(set(c.change_type for c in recent_changes)),
        }

    def _cleanup_old_history(self):
        """Remove old change history entries."""
        cutoff_date = datetime.now() - timedelta(days=self.config.max_history_days)

        original_count = len(self.change_history)
        self.change_history = [
            change for change in self.change_history if change.timestamp >= cutoff_date
        ]

        removed_count = original_count - len(self.change_history)
        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} old change history entries")

    def _save_state(self):
        """Save current state to storage."""
        try:
            # Save snapshots
            snapshots_file = self.storage_path / "snapshots.json"
            snapshots_data = {}

            for doc_id, snapshot in self.document_snapshots.items():
                snapshots_data[doc_id] = {
                    "document_id": snapshot.document_id,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "content_hash": snapshot.content_hash,
                    "structure_hash": snapshot.structure_hash,
                    "metadata": snapshot.metadata,
                    "elements_count": snapshot.elements_count,
                    "content_length": snapshot.content_length,
                    "last_modified": snapshot.last_modified,
                    "version_id": snapshot.version_id,
                }

            with open(snapshots_file, "w") as f:
                json.dump(snapshots_data, f, indent=2)

            # Save change history
            history_file = self.storage_path / "change_history.json"
            history_data = [change.to_dict() for change in self.change_history]

            with open(history_file, "w") as f:
                json.dump(history_data, f, indent=2)

            # Save tracked documents
            tracked_file = self.storage_path / "tracked_documents.json"
            with open(tracked_file, "w") as f:
                json.dump(list(self.tracked_documents), f, indent=2)

            logger.debug("State saved successfully")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """Load previously saved state."""
        try:
            # Load snapshots
            snapshots_file = self.storage_path / "snapshots.json"
            if snapshots_file.exists():
                with open(snapshots_file, "r") as f:
                    snapshots_data = json.load(f)

                for doc_id, snapshot_data in snapshots_data.items():
                    snapshot = DocumentSnapshot(
                        document_id=snapshot_data["document_id"],
                        timestamp=datetime.fromisoformat(snapshot_data["timestamp"]),
                        content_hash=snapshot_data["content_hash"],
                        structure_hash=snapshot_data["structure_hash"],
                        metadata=snapshot_data["metadata"],
                        elements_count=snapshot_data["elements_count"],
                        content_length=snapshot_data["content_length"],
                        last_modified=snapshot_data.get("last_modified"),
                        version_id=snapshot_data.get("version_id"),
                    )
                    self.document_snapshots[doc_id] = snapshot

                logger.debug(
                    f"Loaded {len(self.document_snapshots)} document snapshots"
                )

            # Load change history
            history_file = self.storage_path / "change_history.json"
            if history_file.exists():
                with open(history_file, "r") as f:
                    history_data = json.load(f)

                for change_data in history_data:
                    change = ChangeEvent(
                        document_id=change_data["document_id"],
                        change_type=change_data["change_type"],
                        timestamp=datetime.fromisoformat(change_data["timestamp"]),
                        change_details=change_data["change_details"],
                        affected_range=change_data.get("affected_range"),
                        author=change_data.get("author"),
                        change_id=change_data.get("change_id"),
                    )
                    self.change_history.append(change)

                logger.debug(
                    f"Loaded {len(self.change_history)} change history entries"
                )

            # Load tracked documents
            tracked_file = self.storage_path / "tracked_documents.json"
            if tracked_file.exists():
                with open(tracked_file, "r") as f:
                    tracked_docs = json.load(f)

                self.tracked_documents = set(tracked_docs)
                logger.debug(f"Loaded {len(self.tracked_documents)} tracked documents")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def force_refresh(self, document_id: str):
        """Force refresh of a specific document snapshot.

        Args:
            document_id: Google Docs document ID to refresh
        """
        if document_id not in self.tracked_documents:
            raise ValueError(f"Document {document_id} is not being tracked")

        try:
            new_snapshot = self._create_snapshot(document_id)
            self.document_snapshots[document_id] = new_snapshot
            logger.info(f"Force refreshed snapshot for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to force refresh document {document_id}: {e}")
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """Get tracking statistics.

        Returns:
            Dictionary with tracking statistics
        """
        if not self.change_history:
            return {
                "tracked_documents": len(self.tracked_documents),
                "total_changes": 0,
                "change_types": {},
                "most_active_document": None,
                "tracking_status": "running" if self.is_running else "stopped",
            }

        # Calculate statistics
        change_types = {}
        document_activity = {}

        for change in self.change_history:
            # Count change types
            change_types[change.change_type] = (
                change_types.get(change.change_type, 0) + 1
            )

            # Count document activity
            doc_id = change.document_id
            document_activity[doc_id] = document_activity.get(doc_id, 0) + 1

        # Find most active document
        most_active_document = (
            max(document_activity.items(), key=lambda x: x[1])[0]
            if document_activity
            else None
        )

        return {
            "tracked_documents": len(self.tracked_documents),
            "total_changes": len(self.change_history),
            "change_types": change_types,
            "most_active_document": most_active_document,
            "tracking_status": "running" if self.is_running else "stopped",
            "uptime": time.time()
            - (
                self.change_history[0].timestamp.timestamp()
                if self.change_history
                else time.time()
            ),
        }
