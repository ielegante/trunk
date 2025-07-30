"""Tests for document change detection system."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from .change_detector import (
    ChangeDetectionConfig,
    DocumentChange,
    DocumentChangeDetector,
)
from .drive_client import DriveFile, DrivePermission, GoogleDriveClient


class TestDocumentChange(unittest.TestCase):
    """Test cases for DocumentChange class."""

    def test_document_change_creation(self):
        """Test creating a DocumentChange object."""
        timestamp = datetime.now()

        change = DocumentChange(
            file_id="test_file_id",
            file_name="Test Document",
            change_type="content",
            timestamp=timestamp,
            actor="user@example.com",
            previous_hash="old_hash",
            current_hash="new_hash",
            details={"key": "value"},
        )

        self.assertEqual(change.file_id, "test_file_id")
        self.assertEqual(change.file_name, "Test Document")
        self.assertEqual(change.change_type, "content")
        self.assertEqual(change.timestamp, timestamp)
        self.assertEqual(change.actor, "user@example.com")
        self.assertEqual(change.previous_hash, "old_hash")
        self.assertEqual(change.current_hash, "new_hash")
        self.assertEqual(change.details["key"], "value")

    def test_to_dict(self):
        """Test converting DocumentChange to dictionary."""
        timestamp = datetime.now()

        change = DocumentChange(
            file_id="test_file_id",
            file_name="Test Document",
            change_type="permissions",
            timestamp=timestamp,
            actor="user@example.com",
        )

        dict_repr = change.to_dict()

        self.assertEqual(dict_repr["file_id"], "test_file_id")
        self.assertEqual(dict_repr["file_name"], "Test Document")
        self.assertEqual(dict_repr["change_type"], "permissions")
        self.assertEqual(dict_repr["timestamp"], timestamp.isoformat())
        self.assertEqual(dict_repr["actor"], "user@example.com")


class TestChangeDetectionConfig(unittest.TestCase):
    """Test cases for ChangeDetectionConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ChangeDetectionConfig()

        self.assertEqual(config.check_interval_minutes, 15)
        self.assertTrue(config.include_content_changes)
        self.assertTrue(config.include_permission_changes)
        self.assertTrue(config.include_metadata_changes)
        self.assertEqual(config.content_hash_algorithm, "sha256")
        self.assertEqual(config.max_file_size_mb, 100)
        self.assertEqual(config.notification_webhooks, [])

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ChangeDetectionConfig(
            check_interval_minutes=30,
            include_content_changes=False,
            content_hash_algorithm="md5",
            max_file_size_mb=50,
            notification_webhooks=["https://example.com/webhook"],
        )

        self.assertEqual(config.check_interval_minutes, 30)
        self.assertFalse(config.include_content_changes)
        self.assertEqual(config.content_hash_algorithm, "md5")
        self.assertEqual(config.max_file_size_mb, 50)
        self.assertEqual(config.notification_webhooks, ["https://example.com/webhook"])


class TestDocumentChangeDetector(unittest.TestCase):
    """Test cases for DocumentChangeDetector class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "change_detection"

        # Create mock drive client
        self.mock_drive_client = Mock(spec=GoogleDriveClient)

        # Create detector
        self.detector = DocumentChangeDetector(
            drive_client=self.mock_drive_client, state_dir=self.state_dir
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_detector_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector.drive_client)
        self.assertIsNotNone(self.detector.config)
        self.assertTrue(self.detector.state_dir.exists())
        self.assertEqual(self.detector.document_snapshots, {})
        self.assertEqual(self.detector.detected_changes, [])

    def test_create_file_snapshot(self):
        """Test creating a file snapshot."""
        # Create test drive file
        permissions = [
            DrivePermission(
                id="1", type="user", role="owner", email_address="owner@example.com"
            )
        ]

        drive_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=permissions,
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        # Create snapshot
        snapshot = self.detector._create_file_snapshot(drive_file)

        # Verify snapshot contents
        self.assertEqual(snapshot["file_id"], "test_file_id")
        self.assertEqual(snapshot["file_name"], "Test Document")
        self.assertEqual(snapshot["mime_type"], "application/vnd.google-apps.document")
        self.assertEqual(snapshot["modified_time"], "2023-01-01T12:00:00Z")
        self.assertIsNotNone(snapshot["snapshot_time"])
        self.assertIsNotNone(snapshot["content_hash"])
        self.assertIsNotNone(snapshot["permissions_hash"])
        self.assertIsNotNone(snapshot["metadata_hash"])

    def test_detect_content_change(self):
        """Test detecting content changes."""
        # Create snapshots with different content hashes
        previous_snapshot = {
            "file_name": "Test Document",
            "content_hash": "old_hash",
            "modified_time": "2023-01-01T12:00:00Z",
        }

        current_snapshot = {
            "file_name": "Test Document",
            "content_hash": "new_hash",
            "modified_time": "2023-01-01T13:00:00Z",
        }

        # Detect change
        change = self.detector._detect_content_change(
            "test_file_id", previous_snapshot, current_snapshot
        )

        # Verify change detection
        self.assertIsNotNone(change)
        self.assertEqual(change.file_id, "test_file_id")
        self.assertEqual(change.change_type, "content")
        self.assertEqual(change.previous_hash, "old_hash")
        self.assertEqual(change.current_hash, "new_hash")
        self.assertEqual(change.details["previous_modified"], "2023-01-01T12:00:00Z")
        self.assertEqual(change.details["current_modified"], "2023-01-01T13:00:00Z")

    def test_detect_no_content_change(self):
        """Test no content change detection when hashes are same."""
        # Create snapshots with same content hash
        previous_snapshot = {
            "file_name": "Test Document",
            "content_hash": "same_hash",
            "modified_time": "2023-01-01T12:00:00Z",
        }

        current_snapshot = {
            "file_name": "Test Document",
            "content_hash": "same_hash",
            "modified_time": "2023-01-01T12:00:00Z",
        }

        # Detect change
        change = self.detector._detect_content_change(
            "test_file_id", previous_snapshot, current_snapshot
        )

        # Should be no change
        self.assertIsNone(change)

    def test_detect_metadata_change(self):
        """Test detecting metadata changes."""
        # Create test drive file
        drive_file = DriveFile(
            id="test_file_id",
            name="Updated Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
        )

        # Create snapshots with different metadata
        previous_snapshot = {
            "file_name": "Original Document",
            "metadata_hash": "old_metadata_hash",
            "mime_type": "application/vnd.google-apps.document",
        }

        current_snapshot = {
            "file_name": "Updated Document",
            "metadata_hash": "new_metadata_hash",
            "mime_type": "application/vnd.google-apps.document",
        }

        # Detect change
        change = self.detector._detect_metadata_change(
            drive_file, previous_snapshot, current_snapshot
        )

        # Verify change detection
        self.assertIsNotNone(change)
        self.assertEqual(change.file_id, "test_file_id")
        self.assertEqual(change.change_type, "metadata")
        self.assertEqual(change.previous_hash, "old_metadata_hash")
        self.assertEqual(change.current_hash, "new_metadata_hash")
        self.assertEqual(change.details["previous_name"], "Original Document")
        self.assertEqual(change.details["current_name"], "Updated Document")
        self.assertFalse(change.details["mime_type_changed"])

    def test_detect_permission_changes(self):
        """Test detecting permission changes."""
        # Create test drive file
        drive_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
        )

        # Create snapshots with different permission hashes
        previous_snapshot = {
            "permissions_hash": "old_permissions_hash",
            "snapshot_time": "2023-01-01T12:00:00Z",
        }

        current_snapshot = {"permissions_hash": "new_permissions_hash"}

        # Mock drive client to return activity
        self.mock_drive_client.get_file_changes.return_value = [
            {
                "timestamp": "2023-01-01T12:30:00Z",
                "actors": [{"user": {"name": "user@example.com"}}],
                "actions": [{"type": "permissionChange", "detail": {}}],
            }
        ]

        # Detect changes
        changes = self.detector._detect_permission_changes(
            drive_file, previous_snapshot, current_snapshot
        )

        # Verify change detection
        self.assertEqual(len(changes), 1)

        change = changes[0]
        self.assertEqual(change.file_id, "test_file_id")
        self.assertEqual(change.change_type, "permissions")
        self.assertEqual(change.actor, "user@example.com")
        self.assertEqual(change.details["action"], "permissionChange")
        self.assertEqual(change.details["previous_hash"], "old_permissions_hash")
        self.assertEqual(change.details["current_hash"], "new_permissions_hash")

    def test_detect_file_changes_first_time(self):
        """Test detecting changes for a file seen for the first time."""
        # Create test drive file
        drive_file = DriveFile(
            id="new_file_id",
            name="New Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        # Mock drive client
        self.mock_drive_client.get_file_metadata.return_value = drive_file

        # Detect changes (first time seeing this file)
        changes = self.detector._detect_file_changes("new_file_id")

        # Should have no changes for first time
        self.assertEqual(len(changes), 0)

        # But should have saved a snapshot
        self.assertIn("new_file_id", self.detector.document_snapshots)

        snapshot = self.detector.document_snapshots["new_file_id"]
        self.assertEqual(snapshot["file_name"], "New Document")
        self.assertEqual(snapshot["file_id"], "new_file_id")

    def test_detect_file_changes_with_existing_snapshot(self):
        """Test detecting changes when file already has a snapshot."""
        # Create initial snapshot
        initial_snapshot = {
            "file_id": "existing_file_id",
            "file_name": "Original Document",
            "mime_type": "application/vnd.google-apps.document",
            "modified_time": "2023-01-01T12:00:00Z",
            "snapshot_time": "2023-01-01T12:00:00Z",
            "content_hash": "old_content_hash",
            "permissions_hash": "old_permissions_hash",
            "metadata_hash": "old_metadata_hash",
        }

        self.detector.document_snapshots["existing_file_id"] = initial_snapshot

        # Create updated drive file
        drive_file = DriveFile(
            id="existing_file_id",
            name="Updated Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T13:00:00Z",
        )

        # Mock drive client
        self.mock_drive_client.get_file_metadata.return_value = drive_file
        self.mock_drive_client.get_file_changes.return_value = []

        # Detect changes
        changes = self.detector._detect_file_changes("existing_file_id")

        # Should detect content and metadata changes
        self.assertGreater(len(changes), 0)

        # Check for content change
        content_changes = [c for c in changes if c.change_type == "content"]
        self.assertEqual(len(content_changes), 1)

        # Check for metadata change
        metadata_changes = [c for c in changes if c.change_type == "metadata"]
        self.assertEqual(len(metadata_changes), 1)

    def test_detect_changes_multiple_files(self):
        """Test detecting changes across multiple files."""
        # Create test drive files
        file1 = DriveFile(
            id="file1",
            name="Document 1",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        file2 = DriveFile(
            id="file2",
            name="Document 2",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        # Mock drive client to return different files
        def mock_get_file_metadata(file_id, **kwargs):
            if file_id == "file1":
                return file1
            elif file_id == "file2":
                return file2
            return None

        self.mock_drive_client.get_file_metadata.side_effect = mock_get_file_metadata

        # Detect changes for multiple files
        changes = self.detector.detect_changes(["file1", "file2"])

        # Should have no changes for first time
        self.assertEqual(len(changes), 0)

        # But should have snapshots for both files
        self.assertIn("file1", self.detector.document_snapshots)
        self.assertIn("file2", self.detector.document_snapshots)

    def test_get_recent_changes(self):
        """Test getting recent changes with filters."""
        # Create test changes
        old_change = DocumentChange(
            file_id="file1",
            file_name="Document 1",
            change_type="content",
            timestamp=datetime.now() - timedelta(days=2),
        )

        recent_change = DocumentChange(
            file_id="file2",
            file_name="Document 2",
            change_type="permissions",
            timestamp=datetime.now() - timedelta(hours=1),
        )

        self.detector.detected_changes = [old_change, recent_change]

        # Get recent changes (default 24 hours)
        recent = self.detector.get_recent_changes()

        # Should only include recent change
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].file_id, "file2")

        # Filter by file ID
        file_filtered = self.detector.get_recent_changes(file_id="file1", hours=48)
        self.assertEqual(len(file_filtered), 1)
        self.assertEqual(file_filtered[0].file_id, "file1")

        # Filter by change type
        type_filtered = self.detector.get_recent_changes(change_type="permissions")
        self.assertEqual(len(type_filtered), 1)
        self.assertEqual(type_filtered[0].change_type, "permissions")

    def test_clear_old_changes(self):
        """Test clearing old changes."""
        # Create test changes
        old_change = DocumentChange(
            file_id="file1",
            file_name="Document 1",
            change_type="content",
            timestamp=datetime.now() - timedelta(days=35),
        )

        recent_change = DocumentChange(
            file_id="file2",
            file_name="Document 2",
            change_type="permissions",
            timestamp=datetime.now() - timedelta(days=1),
        )

        self.detector.detected_changes = [old_change, recent_change]

        # Clear changes older than 30 days
        removed_count = self.detector.clear_old_changes(days=30)

        # Should have removed 1 old change
        self.assertEqual(removed_count, 1)
        self.assertEqual(len(self.detector.detected_changes), 1)
        self.assertEqual(self.detector.detected_changes[0].file_id, "file2")

    def test_extract_actor_name(self):
        """Test extracting actor name from activity."""
        # Activity with user actor
        activity_with_user = {"actors": [{"user": {"name": "user@example.com"}}]}

        actor = self.detector._extract_actor_name(activity_with_user)
        self.assertEqual(actor, "user@example.com")

        # Activity without user actor
        activity_without_user = {"actors": [{"system": {}}]}

        actor = self.detector._extract_actor_name(activity_without_user)
        self.assertIsNone(actor)

        # Activity with no actors
        activity_no_actors = {"actors": []}

        actor = self.detector._extract_actor_name(activity_no_actors)
        self.assertIsNone(actor)

    def test_save_and_load_state(self):
        """Test saving and loading detector state."""
        # Create test data
        test_snapshot = {
            "file_id": "test_file",
            "file_name": "Test Document",
            "content_hash": "test_hash",
        }

        test_change = DocumentChange(
            file_id="test_file",
            file_name="Test Document",
            change_type="content",
            timestamp=datetime.now(),
        )

        # Set detector state
        self.detector.document_snapshots["test_file"] = test_snapshot
        self.detector.detected_changes = [test_change]

        # Save state
        self.detector._save_snapshots()
        self.detector._save_changes()

        # Create new detector and load state
        new_detector = DocumentChangeDetector(
            drive_client=self.mock_drive_client, state_dir=self.state_dir
        )

        # Verify state was loaded
        self.assertEqual(len(new_detector.document_snapshots), 1)
        self.assertIn("test_file", new_detector.document_snapshots)
        self.assertEqual(
            new_detector.document_snapshots["test_file"]["file_name"], "Test Document"
        )

        self.assertEqual(len(new_detector.detected_changes), 1)
        self.assertEqual(new_detector.detected_changes[0].file_id, "test_file")
        self.assertEqual(new_detector.detected_changes[0].change_type, "content")

    def test_calculate_content_hash(self):
        """Test calculating content hash."""
        # Create test drive file
        drive_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        # Calculate content hash
        content_hash = self.detector._calculate_content_hash(drive_file)

        # Should generate a hash based on file ID and modified time
        self.assertIsNotNone(content_hash)
        self.assertIsInstance(content_hash, str)
        self.assertEqual(len(content_hash), 64)  # SHA256 hex string length

        # Same file should produce same hash
        same_hash = self.detector._calculate_content_hash(drive_file)
        self.assertEqual(content_hash, same_hash)

        # Different modified time should produce different hash
        drive_file.modified_time = "2023-01-01T13:00:00Z"
        different_hash = self.detector._calculate_content_hash(drive_file)
        self.assertNotEqual(content_hash, different_hash)

    def test_config_with_disabled_features(self):
        """Test change detection with disabled features."""
        # Create config with content changes disabled
        config = ChangeDetectionConfig(
            include_content_changes=False,
            include_permission_changes=True,
            include_metadata_changes=True,
        )

        detector = DocumentChangeDetector(
            drive_client=self.mock_drive_client, config=config, state_dir=self.state_dir
        )

        # Create test drive file
        drive_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        # Create snapshot
        snapshot = detector._create_file_snapshot(drive_file)

        # Should not have content hash
        self.assertIsNone(snapshot["content_hash"])

        # Should have other hashes
        self.assertIsNotNone(snapshot["permissions_hash"])
        self.assertIsNotNone(snapshot["metadata_hash"])


class TestChangeDetectionIntegration(unittest.TestCase):
    """Integration tests for change detection system."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "change_detection"

        # Create mock drive client
        self.mock_drive_client = Mock(spec=GoogleDriveClient)

        # Create detector with full configuration
        self.config = ChangeDetectionConfig(
            check_interval_minutes=5,
            include_content_changes=True,
            include_permission_changes=True,
            include_metadata_changes=True,
        )

        self.detector = DocumentChangeDetector(
            drive_client=self.mock_drive_client,
            config=self.config,
            state_dir=self.state_dir,
        )

    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_full_change_detection_cycle(self):
        """Test complete change detection cycle."""
        # Step 1: Initial file detection (no changes)
        initial_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[
                DrivePermission(
                    id="1", type="user", role="owner", email_address="owner@example.com"
                )
            ],
            parents=["parent_folder"],
            modified_time="2023-01-01T12:00:00Z",
        )

        self.mock_drive_client.get_file_metadata.return_value = initial_file

        # First detection should create snapshot but no changes
        changes = self.detector.detect_changes(["test_file_id"])
        self.assertEqual(len(changes), 0)
        self.assertIn("test_file_id", self.detector.document_snapshots)

        # Step 2: File content changes
        modified_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[
                DrivePermission(
                    id="1", type="user", role="owner", email_address="owner@example.com"
                )
            ],
            parents=["parent_folder"],
            modified_time="2023-01-01T13:00:00Z",  # Updated time
        )

        self.mock_drive_client.get_file_metadata.return_value = modified_file
        self.mock_drive_client.get_file_changes.return_value = []

        # Second detection should find content change
        changes = self.detector.detect_changes(["test_file_id"])
        self.assertGreater(len(changes), 0)

        content_changes = [c for c in changes if c.change_type == "content"]
        self.assertEqual(len(content_changes), 1)

        # Step 3: Permission changes
        permission_changed_file = DriveFile(
            id="test_file_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[
                DrivePermission(
                    id="1", type="user", role="owner", email_address="owner@example.com"
                ),
                DrivePermission(
                    id="2",
                    type="user",
                    role="writer",
                    email_address="writer@example.com",
                ),
            ],
            parents=["parent_folder"],
            modified_time="2023-01-01T13:00:00Z",
        )

        self.mock_drive_client.get_file_metadata.return_value = permission_changed_file
        self.mock_drive_client.get_file_changes.return_value = [
            {
                "timestamp": "2023-01-01T13:30:00Z",
                "actors": [{"user": {"name": "admin@example.com"}}],
                "actions": [{"type": "permissionChange", "detail": {}}],
            }
        ]

        # Third detection should find permission change
        changes = self.detector.detect_changes(["test_file_id"])

        permission_changes = [c for c in changes if c.change_type == "permissions"]
        self.assertEqual(len(permission_changes), 1)
        self.assertEqual(permission_changes[0].actor, "admin@example.com")

        # Step 4: Verify change history
        all_changes = self.detector.get_recent_changes(hours=24)
        self.assertGreater(len(all_changes), 0)

        # Should have changes from all detection cycles
        change_types = {c.change_type for c in all_changes}
        self.assertIn("content", change_types)
        self.assertIn("permissions", change_types)

        # Step 5: Test state persistence
        self.detector._save_snapshots()
        self.detector._save_changes()

        # Verify files were created
        self.assertTrue(self.detector.snapshots_file.exists())
        self.assertTrue(self.detector.changes_file.exists())

        # Verify content
        with open(self.detector.snapshots_file, "r") as f:
            snapshots_data = json.load(f)

        self.assertIn("test_file_id", snapshots_data)

        with open(self.detector.changes_file, "r") as f:
            changes_data = json.load(f)

        self.assertGreater(len(changes_data), 0)


if __name__ == "__main__":
    unittest.main()
