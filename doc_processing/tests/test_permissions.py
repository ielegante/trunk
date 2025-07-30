"""Tests for permission management system."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from doc_processing.permissions import (
    GitPermissionManager,
    GoogleDriveClient,
    PermissionMapper,
    PermissionSyncManager,
)
from doc_processing.permissions.drive_client import DriveFile, DrivePermission
from doc_processing.permissions.git_permissions import GitCollaborator
from doc_processing.permissions.permission_mapper import (
    GitPermission,
    GitPermissionLevel,
    PermissionMapping,
)
from doc_processing.permissions.sync_manager import SyncConfiguration


class TestDrivePermission:
    """Test DrivePermission dataclass."""

    def test_permission_creation(self):
        """Test creating a DrivePermission."""
        perm = DrivePermission(
            id="12345",
            type="user",
            role="writer",
            email_address="user@example.com",
            display_name="Test User",
        )
        assert perm.id == "12345"
        assert perm.type == "user"
        assert perm.role == "writer"
        assert perm.email_address == "user@example.com"

    def test_from_api_response(self):
        """Test creating DrivePermission from API response."""
        api_data = {
            "id": "67890",
            "type": "user",
            "role": "reader",
            "emailAddress": "reader@example.com",
            "displayName": "Reader User",
            "deleted": False,
        }

        perm = DrivePermission.from_api_response(api_data)
        assert perm.id == "67890"
        assert perm.email_address == "reader@example.com"
        assert perm.deleted is False

    def test_to_dict(self):
        """Test converting DrivePermission to dictionary."""
        perm = DrivePermission(
            id="12345", type="user", role="writer", email_address="user@example.com"
        )

        data = perm.to_dict()
        assert data["id"] == "12345"
        assert data["email_address"] == "user@example.com"


class TestGoogleDriveClient:
    """Test GoogleDriveClient functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = GoogleDriveClient()

    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.credentials_file.name == "credentials.json"
        assert self.client.token_file.name == "token.json"
        assert self.client.service is None

    @patch("doc_processing.permissions.drive_client.build")
    @patch(
        "doc_processing.permissions.drive_client.Credentials.from_authorized_user_file"
    )
    def test_authentication_with_existing_token(self, mock_creds, mock_build):
        """Test authentication with existing valid token."""
        # Mock valid credentials
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_creds.return_value = mock_credentials

        # Mock token file exists
        with patch.object(self.client.token_file, "exists", return_value=True):
            result = self.client.authenticate()

        assert result is True
        assert self.client.credentials == mock_credentials
        mock_build.assert_called_once()

    def test_authentication_without_credentials_file(self):
        """Test authentication failure when credentials file missing."""
        with patch.object(self.client.credentials_file, "exists", return_value=False):
            result = self.client.authenticate()

        assert result is False

    def test_get_file_permissions_without_service(self):
        """Test getting permissions without initialized service."""
        with pytest.raises(RuntimeError, match="Drive service not initialized"):
            self.client.get_file_permissions("test_file_id")

    @patch("doc_processing.permissions.drive_client.build")
    def test_get_file_permissions_success(self, mock_build):
        """Test successful permission retrieval."""
        # Mock service
        mock_service = Mock()
        mock_permissions = Mock()
        mock_service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value.execute.return_value = {
            "permissions": [
                {
                    "id": "123",
                    "type": "user",
                    "role": "writer",
                    "emailAddress": "user@example.com",
                }
            ]
        }

        self.client.service = mock_service

        permissions = self.client.get_file_permissions("test_file_id")

        assert len(permissions) == 1
        assert permissions[0].id == "123"
        assert permissions[0].email_address == "user@example.com"

    def test_validate_permissions(self):
        """Test permission validation and analysis."""
        with patch.object(self.client, "get_file_permissions") as mock_get:
            mock_get.return_value = [
                DrivePermission("1", "user", "owner", "owner@example.com"),
                DrivePermission("2", "user", "writer", "writer@example.com"),
                DrivePermission("3", "anyone", "reader", None),
                DrivePermission("4", "domain", "reader", None, domain="example.com"),
            ]

            analysis = self.client.validate_permissions("test_file_id")

            assert analysis["total_permissions"] == 4
            assert analysis["has_public_access"] is True
            assert analysis["has_domain_access"] is True
            assert analysis["user_count"] == 2
            assert analysis["permission_roles"]["owner"] == 1
            assert analysis["permission_roles"]["writer"] == 1
            assert analysis["permission_roles"]["reader"] == 2


class TestPermissionMapper:
    """Test PermissionMapper functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = PermissionMapper()

    def test_mapper_initialization(self):
        """Test mapper initialization with default settings."""
        assert len(self.mapper.role_mapping) == 6
        assert (
            self.mapper.role_mapping.get(
                self.mapper.DEFAULT_ROLE_MAPPING.__class__.READER
            )
            is not None
        )

    def test_custom_role_mapping(self):
        """Test mapper initialization with custom role mapping."""
        custom_mapping = {"writer": "admin"}
        mapper = PermissionMapper(custom_mapping)

        # Custom mapping should be applied
        from doc_processing.permissions.permission_mapper import DriveRole

        assert mapper.role_mapping[DriveRole.WRITER] == GitPermissionLevel.ADMIN

    def test_map_user_permission(self):
        """Test mapping a user permission."""
        drive_perm = DrivePermission(
            id="123",
            type="user",
            role="writer",
            email_address="user@example.com",
            display_name="Test User",
        )

        git_perm = self.mapper._map_single_permission(drive_perm)

        assert git_perm is not None
        assert git_perm.user_email == "user@example.com"
        assert git_perm.permission_level == GitPermissionLevel.WRITE
        assert git_perm.source_drive_role == "writer"

    def test_map_deleted_permission(self):
        """Test mapping a deleted permission."""
        drive_perm = DrivePermission(
            id="123",
            type="user",
            role="writer",
            email_address="user@example.com",
            deleted=True,
        )

        git_perm = self.mapper._map_single_permission(drive_perm)
        assert git_perm is None

    def test_map_group_permission(self):
        """Test mapping a group permission (should be skipped)."""
        drive_perm = DrivePermission(
            id="123", type="group", role="writer", email_address="group@example.com"
        )

        git_perm = self.mapper._map_single_permission(drive_perm)
        assert git_perm is None

    def test_resolve_duplicate_permissions(self):
        """Test resolving duplicate permissions for same user."""
        git_perms = [
            GitPermission(
                "user@example.com", GitPermissionLevel.READ, "reader", "user"
            ),
            GitPermission(
                "user@example.com", GitPermissionLevel.WRITE, "writer", "user"
            ),
            GitPermission(
                "other@example.com", GitPermissionLevel.READ, "reader", "user"
            ),
        ]

        resolved = self.mapper._resolve_duplicate_permissions(git_perms)

        assert len(resolved) == 2
        # Should keep higher permission level
        user_perm = next(p for p in resolved if p.user_email == "user@example.com")
        assert user_perm.permission_level == GitPermissionLevel.WRITE

    def test_create_permission_mapping(self):
        """Test creating a complete permission mapping."""
        drive_file = DriveFile(
            id="file123",
            name="test.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            permissions=[
                DrivePermission("1", "user", "owner", "owner@example.com"),
                DrivePermission("2", "user", "writer", "writer@example.com"),
            ],
            parents=[],
        )

        mapping = self.mapper.create_permission_mapping(drive_file, "/path/to/repo")

        assert mapping.drive_file_id == "file123"
        assert mapping.git_repo_path == "/path/to/repo"
        assert len(mapping.git_permissions) == 2
        assert len(mapping.drive_permissions) == 2

    def test_validate_permission_mapping(self):
        """Test validating a permission mapping."""
        mapping = PermissionMapping(
            drive_file_id="file123",
            drive_file_name="test.docx",
            git_repo_path="/path/to/repo",
            drive_permissions=[
                DrivePermission("1", "user", "owner", "owner@example.com")
            ],
            git_permissions=[
                GitPermission(
                    "owner@example.com", GitPermissionLevel.OWNER, "owner", "user"
                )
            ],
            mapping_conflicts=[],
        )

        validation = self.mapper.validate_permission_mapping(mapping)

        assert validation["is_valid"] is True
        assert validation["mapping_stats"]["git_permissions"] == 1
        assert validation["mapping_stats"]["mapping_success_rate"] == 1.0


class TestGitPermissionManager:
    """Test GitPermissionManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_repo = Path("/tmp/test_repo")
        self.manager = GitPermissionManager(self.temp_repo)

    def test_manager_initialization(self):
        """Test manager initialization."""
        assert self.manager.repo_path == self.temp_repo
        assert self.manager.permissions_file.name == "permissions.json"

    @patch("builtins.open", new_callable=mock_open, read_data='{"collaborators": []}')
    @patch.object(Path, "exists", return_value=True)
    def test_load_empty_permissions(self, mock_exists, mock_file):
        """Test loading empty permissions file."""
        collaborators = self.manager._load_permissions()
        assert collaborators == []

    @patch("builtins.open", new_callable=mock_open)
    @patch.object(Path, "exists", return_value=True)
    def test_save_permissions(self, mock_exists, mock_file):
        """Test saving permissions to file."""
        collaborators = [
            GitCollaborator(
                username="testuser",
                email="test@example.com",
                permission_level=GitPermissionLevel.WRITE,
            )
        ]

        self.manager._save_permissions(collaborators)

        # Verify file was written
        mock_file.assert_called_once()
        handle = mock_file()
        handle.write.assert_called()

    def test_email_to_username(self):
        """Test converting email to username."""
        username = self.manager._email_to_username("test.user@example.com")
        assert username == "test.user"

    def test_apply_permissions(self):
        """Test applying git permissions."""
        git_permissions = [
            GitPermission(
                user_email="user@example.com",
                permission_level=GitPermissionLevel.WRITE,
                source_drive_role="writer",
                source_drive_type="user",
            )
        ]

        with patch.object(self.manager, "_load_permissions", return_value=[]):
            with patch.object(self.manager, "_save_permissions"):
                with patch.object(self.manager, "_update_repository_permissions"):
                    with patch.object(self.manager, "_install_permission_hooks"):
                        results = self.manager.apply_permissions(git_permissions)

        assert results["success"] is True
        assert len(results["applied_permissions"]) == 1

    def test_validate_permissions(self):
        """Test validating repository permissions."""
        with patch.object(self.manager, "_load_permissions") as mock_load:
            mock_load.return_value = [
                GitCollaborator("owner", "owner@example.com", GitPermissionLevel.OWNER),
                GitCollaborator("user", "user@example.com", GitPermissionLevel.WRITE),
            ]

            validation = self.manager.validate_permissions()

            assert validation["is_valid"] is True
            assert validation["permission_stats"]["owners"] == 1
            assert validation["permission_stats"]["writers"] == 1


class TestPermissionSyncManager:
    """Test PermissionSyncManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.drive_client = Mock(spec=GoogleDriveClient)
        self.mapper = Mock(spec=PermissionMapper)
        self.sync_config = SyncConfiguration(auto_sync_enabled=True)

        with patch("pathlib.Path.mkdir"):
            with patch.object(PermissionSyncManager, "_load_state"):
                self.manager = PermissionSyncManager(
                    self.drive_client, self.mapper, self.sync_config
                )

    def test_manager_initialization(self):
        """Test sync manager initialization."""
        assert self.manager.drive_client == self.drive_client
        assert self.manager.permission_mapper == self.mapper
        assert self.manager.sync_config.auto_sync_enabled is True

    def test_create_sync_job(self):
        """Test creating a sync job."""
        job = self.manager.create_sync_job("file123", "/path/to/repo")

        assert job.drive_file_id == "file123"
        assert job.git_repo_path == "/path/to/repo"
        assert job.status == "pending"
        assert job.job_id in self.manager.sync_jobs

    def test_create_sync_job_with_recent_sync(self):
        """Test creating sync job when recent sync exists."""
        # Create initial job
        job1 = self.manager.create_sync_job("file123", "/path/to/repo")
        job1.status = "completed"

        # Try to create another job (should return existing)
        job2 = self.manager.create_sync_job(
            "file123", "/path/to/repo", force_sync=False
        )

        assert job1.job_id == job2.job_id

    def test_get_sync_status(self):
        """Test getting sync job status."""
        job = self.manager.create_sync_job("file123", "/path/to/repo")

        status = self.manager.get_sync_status(job.job_id)

        assert status is not None
        assert status["drive_file_id"] == "file123"
        assert status["status"] == "pending"

    def test_get_sync_status_not_found(self):
        """Test getting status for non-existent job."""
        status = self.manager.get_sync_status("nonexistent")
        assert status is None

    def test_cancel_sync_job(self):
        """Test cancelling a sync job."""
        job = self.manager.create_sync_job("file123", "/path/to/repo")

        result = self.manager.cancel_sync_job(job.job_id)

        assert result is True
        assert self.manager.sync_jobs[job.job_id].status == "cancelled"

    def test_cancel_completed_job(self):
        """Test cancelling a completed job (should fail)."""
        job = self.manager.create_sync_job("file123", "/path/to/repo")
        job.status = "completed"

        result = self.manager.cancel_sync_job(job.job_id)

        assert result is False

    def test_list_sync_jobs_with_filter(self):
        """Test listing sync jobs with filters."""
        # Create jobs with different statuses
        job1 = self.manager.create_sync_job("file123", "/path/to/repo1")
        job2 = self.manager.create_sync_job("file456", "/path/to/repo2")
        job1.status = "completed"
        job2.status = "pending"

        # Filter by status
        completed_jobs = self.manager.list_sync_jobs(status_filter="completed")
        pending_jobs = self.manager.list_sync_jobs(status_filter="pending")

        assert len(completed_jobs) == 1
        assert len(pending_jobs) == 1
        assert completed_jobs[0]["job_id"] == job1.job_id

    def test_cleanup_old_jobs(self):
        """Test cleaning up old sync jobs."""
        # Create old completed job
        job = self.manager.create_sync_job("file123", "/path/to/repo")
        job.status = "completed"
        job.created_at = datetime(2020, 1, 1)  # Very old

        removed_count = self.manager.cleanup_old_jobs(days_old=1)

        assert removed_count == 1
        assert job.job_id not in self.manager.sync_jobs
