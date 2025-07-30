"""Tests for permission synchronization functionality."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from .drive_client import DriveFile, DrivePermission, GoogleDriveClient
from .git_permissions import GitCollaborator, GitPermissionManager
from .permission_mapper import DriveRole, GitPermissionLevel, PermissionMapper
from .sync_manager import PermissionSyncManager, SyncConfiguration


class TestPermissionMapper(unittest.TestCase):
    """Test cases for PermissionMapper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mapper = PermissionMapper()

    def test_default_role_mapping(self):
        """Test default role mapping between Drive and git."""
        # Test basic mappings
        self.assertEqual(
            self.mapper.role_mapping[DriveRole.READER], GitPermissionLevel.READ
        )
        self.assertEqual(
            self.mapper.role_mapping[DriveRole.WRITER], GitPermissionLevel.WRITE
        )
        self.assertEqual(
            self.mapper.role_mapping[DriveRole.OWNER], GitPermissionLevel.OWNER
        )

    def test_custom_role_mapping(self):
        """Test custom role mapping configuration."""
        custom_mapping = {"writer": "admin", "reader": "read"}

        mapper = PermissionMapper(custom_mapping)

        # Check custom mappings were applied
        self.assertEqual(
            mapper.role_mapping[DriveRole.WRITER], GitPermissionLevel.ADMIN
        )
        self.assertEqual(mapper.role_mapping[DriveRole.READER], GitPermissionLevel.READ)

    def test_map_drive_to_git_permissions(self):
        """Test mapping Drive file permissions to git permissions."""
        # Create mock Drive file with permissions
        permissions = [
            DrivePermission(
                id="1",
                type="user",
                role="owner",
                email_address="owner@example.com",
                display_name="Owner User",
            ),
            DrivePermission(
                id="2",
                type="user",
                role="writer",
                email_address="writer@example.com",
                display_name="Writer User",
            ),
            DrivePermission(
                id="3",
                type="user",
                role="reader",
                email_address="reader@example.com",
                display_name="Reader User",
            ),
        ]

        drive_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=permissions,
            parents=["parent_folder"],
        )

        # Map permissions
        git_permissions = self.mapper.map_drive_to_git_permissions(drive_file)

        # Verify mappings
        self.assertEqual(len(git_permissions), 3)

        # Check specific permission mappings
        owner_perm = next(
            p for p in git_permissions if p.user_email == "owner@example.com"
        )
        self.assertEqual(owner_perm.permission_level, GitPermissionLevel.OWNER)

        writer_perm = next(
            p for p in git_permissions if p.user_email == "writer@example.com"
        )
        self.assertEqual(writer_perm.permission_level, GitPermissionLevel.WRITE)

        reader_perm = next(
            p for p in git_permissions if p.user_email == "reader@example.com"
        )
        self.assertEqual(reader_perm.permission_level, GitPermissionLevel.READ)

    def test_resolve_duplicate_permissions(self):
        """Test resolving duplicate permissions for same user."""
        # Create Drive file with duplicate permissions for same user
        permissions = [
            DrivePermission(
                id="1",
                type="user",
                role="reader",
                email_address="user@example.com",
                display_name="Test User",
            ),
            DrivePermission(
                id="2",
                type="user",
                role="writer",
                email_address="user@example.com",
                display_name="Test User",
            ),
        ]

        drive_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=permissions,
            parents=["parent_folder"],
        )

        # Map permissions
        git_permissions = self.mapper.map_drive_to_git_permissions(drive_file)

        # Should have only one permission (the highest level)
        self.assertEqual(len(git_permissions), 1)
        self.assertEqual(git_permissions[0].permission_level, GitPermissionLevel.WRITE)

    def test_validate_permission_mapping(self):
        """Test permission mapping validation."""
        # Create test mapping
        drive_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[
                DrivePermission(
                    id="1", type="user", role="owner", email_address="owner@example.com"
                )
            ],
            parents=["parent_folder"],
        )

        mapping = self.mapper.create_permission_mapping(drive_file, "/test/repo")
        validation = self.mapper.validate_permission_mapping(mapping)

        # Should be valid with one owner
        self.assertTrue(validation["is_valid"])
        self.assertEqual(validation["mapping_stats"]["git_permissions"], 1)

    def test_get_permission_diff(self):
        """Test detecting permission differences."""
        # Create original mapping
        original_permissions = [
            DrivePermission(
                id="1", type="user", role="owner", email_address="owner@example.com"
            )
        ]

        original_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=original_permissions,
            parents=["parent_folder"],
        )

        current_mapping = self.mapper.create_permission_mapping(
            original_file, "/test/repo"
        )

        # Create updated file with new permission
        updated_permissions = [
            DrivePermission(
                id="1", type="user", role="owner", email_address="owner@example.com"
            ),
            DrivePermission(
                id="2", type="user", role="writer", email_address="writer@example.com"
            ),
        ]

        updated_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=updated_permissions,
            parents=["parent_folder"],
        )

        diff = self.mapper.get_permission_diff(current_mapping, updated_file)

        # Should detect the added permission
        self.assertTrue(diff["has_changes"])
        self.assertEqual(diff["summary"]["users_added"], 1)
        self.assertEqual(len(diff["added_permissions"]), 1)


class TestGitPermissionManager(unittest.TestCase):
    """Test cases for GitPermissionManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.manager = GitPermissionManager(self.repo_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_apply_permissions(self):
        """Test applying permissions to repository."""
        from .permission_mapper import GitPermission

        # Create test permissions
        permissions = [
            GitPermission(
                user_email="owner@example.com",
                permission_level=GitPermissionLevel.OWNER,
                source_drive_role="owner",
                source_drive_type="user",
                display_name="Owner User",
            ),
            GitPermission(
                user_email="writer@example.com",
                permission_level=GitPermissionLevel.WRITE,
                source_drive_role="writer",
                source_drive_type="user",
                display_name="Writer User",
            ),
        ]

        # Apply permissions
        results = self.manager.apply_permissions(permissions)

        # Check results
        self.assertEqual(len(results["applied_permissions"]), 2)
        self.assertIn("owner@example.com", results["applied_permissions"])
        self.assertIn("writer@example.com", results["applied_permissions"])

    def test_save_and_load_permissions(self):
        """Test saving and loading permissions."""
        from .permission_mapper import GitPermission

        # Create test permissions
        permissions = [
            GitPermission(
                user_email="test@example.com",
                permission_level=GitPermissionLevel.WRITE,
                source_drive_role="writer",
                source_drive_type="user",
            )
        ]

        # Apply permissions (this saves them)
        self.manager.apply_permissions(permissions)

        # Load permissions
        loaded_permissions = self.manager.get_current_permissions()

        # Verify loaded permissions
        self.assertEqual(len(loaded_permissions), 1)
        self.assertEqual(loaded_permissions[0].email, "test@example.com")
        self.assertEqual(
            loaded_permissions[0].permission_level, GitPermissionLevel.WRITE
        )

    def test_validate_permissions(self):
        """Test permission validation."""
        from .permission_mapper import GitPermission

        # Create permissions without owner
        permissions = [
            GitPermission(
                user_email="writer@example.com",
                permission_level=GitPermissionLevel.WRITE,
                source_drive_role="writer",
                source_drive_type="user",
            )
        ]

        self.manager.apply_permissions(permissions)
        validation = self.manager.validate_permissions()

        # Should be invalid without owner
        self.assertFalse(validation["is_valid"])
        self.assertIn("No active repository owner found", validation["errors"])

    def test_remove_user_permission(self):
        """Test removing user permission."""
        from .permission_mapper import GitPermission

        # Add user permission
        permissions = [
            GitPermission(
                user_email="user@example.com",
                permission_level=GitPermissionLevel.WRITE,
                source_drive_role="writer",
                source_drive_type="user",
            )
        ]

        self.manager.apply_permissions(permissions)

        # Remove user permission
        removed = self.manager.remove_user_permission("user@example.com")

        # Verify removal
        self.assertTrue(removed)
        current_permissions = self.manager.get_current_permissions()
        self.assertEqual(len(current_permissions), 0)


class TestSyncManager(unittest.TestCase):
    """Test cases for PermissionSyncManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_drive_client = Mock(spec=GoogleDriveClient)
        self.mock_mapper = Mock(spec=PermissionMapper)
        self.config = SyncConfiguration(auto_sync_enabled=True)

        self.sync_manager = PermissionSyncManager(
            drive_client=self.mock_drive_client,
            permission_mapper=self.mock_mapper,
            sync_config=self.config,
        )

    def test_create_sync_job(self):
        """Test creating a sync job."""
        # Create sync job
        job = self.sync_manager.create_sync_job(
            drive_file_id="test_file", git_repo_path="/test/repo"
        )

        # Verify job creation
        self.assertIsNotNone(job)
        self.assertEqual(job.drive_file_id, "test_file")
        self.assertEqual(job.git_repo_path, "/test/repo")
        self.assertEqual(job.status, "pending")

    def test_get_sync_status(self):
        """Test getting sync job status."""
        # Create job
        job = self.sync_manager.create_sync_job(
            drive_file_id="test_file", git_repo_path="/test/repo"
        )

        # Get status
        status = self.sync_manager.get_sync_status(job.job_id)

        # Verify status
        self.assertIsNotNone(status)
        self.assertEqual(status["drive_file_id"], "test_file")
        self.assertEqual(status["status"], "pending")

    def test_list_sync_jobs(self):
        """Test listing sync jobs with filters."""
        # Create multiple jobs
        job1 = self.sync_manager.create_sync_job(
            drive_file_id="file1", git_repo_path="/repo1"
        )
        job2 = self.sync_manager.create_sync_job(
            drive_file_id="file2", git_repo_path="/repo2"
        )

        # List all jobs
        all_jobs = self.sync_manager.list_sync_jobs()
        self.assertEqual(len(all_jobs), 2)

        # Filter by file ID
        filtered_jobs = self.sync_manager.list_sync_jobs(drive_file_id="file1")
        self.assertEqual(len(filtered_jobs), 1)
        self.assertEqual(filtered_jobs[0]["drive_file_id"], "file1")

    def test_cancel_sync_job(self):
        """Test cancelling a sync job."""
        # Create job
        job = self.sync_manager.create_sync_job(
            drive_file_id="test_file", git_repo_path="/test/repo"
        )

        # Cancel job
        cancelled = self.sync_manager.cancel_sync_job(job.job_id)

        # Verify cancellation
        self.assertTrue(cancelled)
        status = self.sync_manager.get_sync_status(job.job_id)
        self.assertEqual(status["status"], "cancelled")

    @patch("doc_processing.permissions.sync_manager.GitPermissionManager")
    async def test_execute_sync_job(self, mock_git_manager_class):
        """Test executing a sync job."""
        # Setup mocks
        mock_git_manager = Mock()
        mock_git_manager_class.return_value = mock_git_manager
        mock_git_manager.apply_permissions.return_value = {
            "applied_permissions": ["user@example.com"],
            "failed_permissions": [],
            "warnings": [],
            "errors": [],
        }

        # Mock drive client
        mock_drive_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=[],
            parents=["parent_folder"],
        )

        self.mock_drive_client.get_file_metadata.return_value = mock_drive_file

        # Mock mapper
        from .permission_mapper import PermissionMapping

        mock_mapping = Mock(spec=PermissionMapping)
        mock_mapping.git_permissions = []
        mock_mapping.mapping_conflicts = []

        self.mock_mapper.create_permission_mapping.return_value = mock_mapping
        self.mock_mapper.validate_permission_mapping.return_value = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
        }

        # Create and execute job
        job = self.sync_manager.create_sync_job(
            drive_file_id="test_file", git_repo_path="/test/repo"
        )

        results = await self.sync_manager.execute_sync_job(job.job_id)

        # Verify execution
        self.assertEqual(results["status"], "success")
        self.assertEqual(results["drive_file_id"], "test_file")

        # Verify job status updated
        status = self.sync_manager.get_sync_status(job.job_id)
        self.assertEqual(status["status"], "completed")


class TestIntegrationFlow(unittest.TestCase):
    """Integration tests for the complete permission sync flow."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)

        # Create mock Drive client
        self.mock_drive_client = Mock(spec=GoogleDriveClient)

        # Create real components
        self.mapper = PermissionMapper()
        self.git_manager = GitPermissionManager(self.repo_path)
        self.sync_manager = PermissionSyncManager(
            drive_client=self.mock_drive_client, permission_mapper=self.mapper
        )

    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_complete_sync_flow(self):
        """Test the complete permission synchronization flow."""
        # Create mock Drive file with permissions
        drive_permissions = [
            DrivePermission(
                id="1",
                type="user",
                role="owner",
                email_address="owner@example.com",
                display_name="Owner User",
            ),
            DrivePermission(
                id="2",
                type="user",
                role="writer",
                email_address="writer@example.com",
                display_name="Writer User",
            ),
        ]

        drive_file = DriveFile(
            id="test_file",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=drive_permissions,
            parents=["parent_folder"],
        )

        # Mock Drive client response
        self.mock_drive_client.get_file_metadata.return_value = drive_file

        # Create and execute sync job
        job = self.sync_manager.create_sync_job(
            drive_file_id="test_file", git_repo_path=str(self.repo_path)
        )

        # The sync process should:
        # 1. Get Drive file metadata
        # 2. Map Drive permissions to git permissions
        # 3. Apply permissions to git repository
        # 4. Save sync results

        # Verify the mapping process
        mapping = self.mapper.create_permission_mapping(drive_file, str(self.repo_path))

        self.assertEqual(len(mapping.git_permissions), 2)
        self.assertEqual(mapping.drive_file_id, "test_file")
        self.assertEqual(mapping.git_repo_path, str(self.repo_path))

        # Verify permission validation
        validation = self.mapper.validate_permission_mapping(mapping)
        self.assertTrue(validation["is_valid"])

        # Verify git permissions application
        results = self.git_manager.apply_permissions(mapping.git_permissions)
        self.assertEqual(len(results["applied_permissions"]), 2)

        # Verify permissions were saved
        saved_permissions = self.git_manager.get_current_permissions()
        self.assertEqual(len(saved_permissions), 2)

        # Check specific permissions
        owner_perm = next(
            p for p in saved_permissions if p.email == "owner@example.com"
        )
        self.assertEqual(owner_perm.permission_level, GitPermissionLevel.OWNER)

        writer_perm = next(
            p for p in saved_permissions if p.email == "writer@example.com"
        )
        self.assertEqual(writer_perm.permission_level, GitPermissionLevel.WRITE)


if __name__ == "__main__":
    unittest.main()
