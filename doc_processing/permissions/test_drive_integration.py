"""Tests for Google Drive API integration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from googleapiclient.errors import HttpError

from .drive_client import DriveFile, DrivePermission, GoogleDriveClient


class TestDrivePermission(unittest.TestCase):
    """Test cases for DrivePermission class."""

    def test_from_api_response(self):
        """Test creating DrivePermission from API response."""
        api_data = {
            "id": "permission_id",
            "type": "user",
            "role": "writer",
            "emailAddress": "user@example.com",
            "displayName": "Test User",
            "domain": None,
            "photoLink": "https://example.com/photo.jpg",
            "deleted": False,
            "pendingOwner": False,
        }

        permission = DrivePermission.from_api_response(api_data)

        self.assertEqual(permission.id, "permission_id")
        self.assertEqual(permission.type, "user")
        self.assertEqual(permission.role, "writer")
        self.assertEqual(permission.email_address, "user@example.com")
        self.assertEqual(permission.display_name, "Test User")
        self.assertEqual(permission.photo_link, "https://example.com/photo.jpg")
        self.assertFalse(permission.deleted)
        self.assertFalse(permission.pending_owner)

    def test_to_dict(self):
        """Test converting DrivePermission to dictionary."""
        permission = DrivePermission(
            id="test_id",
            type="user",
            role="reader",
            email_address="test@example.com",
            display_name="Test User",
        )

        dict_repr = permission.to_dict()

        self.assertEqual(dict_repr["id"], "test_id")
        self.assertEqual(dict_repr["type"], "user")
        self.assertEqual(dict_repr["role"], "reader")
        self.assertEqual(dict_repr["email_address"], "test@example.com")
        self.assertEqual(dict_repr["display_name"], "Test User")


class TestDriveFile(unittest.TestCase):
    """Test cases for DriveFile class."""

    def test_from_api_response(self):
        """Test creating DriveFile from API response."""
        permissions = [
            DrivePermission(
                id="1", type="user", role="owner", email_address="owner@example.com"
            )
        ]

        file_data = {
            "id": "file_id",
            "name": "Test Document",
            "mimeType": "application/vnd.google-apps.document",
            "parents": ["parent_folder"],
            "webViewLink": "https://docs.google.com/document/d/file_id/edit",
            "createdTime": "2023-01-01T00:00:00.000Z",
            "modifiedTime": "2023-01-02T00:00:00.000Z",
            "owners": [
                {"displayName": "Owner User", "emailAddress": "owner@example.com"}
            ],
        }

        drive_file = DriveFile.from_api_response(file_data, permissions)

        self.assertEqual(drive_file.id, "file_id")
        self.assertEqual(drive_file.name, "Test Document")
        self.assertEqual(drive_file.mime_type, "application/vnd.google-apps.document")
        self.assertEqual(drive_file.parents, ["parent_folder"])
        self.assertEqual(
            drive_file.web_view_link, "https://docs.google.com/document/d/file_id/edit"
        )
        self.assertEqual(len(drive_file.permissions), 1)
        self.assertEqual(len(drive_file.owners), 1)

    def test_to_dict(self):
        """Test converting DriveFile to dictionary."""
        permissions = [
            DrivePermission(
                id="1", type="user", role="owner", email_address="owner@example.com"
            )
        ]

        drive_file = DriveFile(
            id="test_id",
            name="Test Document",
            mime_type="application/vnd.google-apps.document",
            permissions=permissions,
            parents=["parent_folder"],
        )

        dict_repr = drive_file.to_dict()

        self.assertEqual(dict_repr["id"], "test_id")
        self.assertEqual(dict_repr["name"], "Test Document")
        self.assertEqual(len(dict_repr["permissions"]), 1)
        self.assertIsInstance(dict_repr["permissions"][0], dict)


class TestGoogleDriveClient(unittest.TestCase):
    """Test cases for GoogleDriveClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.credentials_file = Path(self.temp_dir) / "credentials.json"
        self.token_file = Path(self.temp_dir) / "token.json"

        # Create mock credentials file
        credentials_data = {
            "web": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/oauth2callback"],
            }
        }

        with open(self.credentials_file, "w") as f:
            json.dump(credentials_data, f)

        self.client = GoogleDriveClient(
            credentials_file=self.credentials_file, token_file=self.token_file
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_init_with_custom_oauth(self):
        """Test initialization with custom OAuth credentials."""
        client = GoogleDriveClient(
            client_id="custom_client_id", client_secret="custom_client_secret"
        )

        # Verify OAuth config was updated
        from .drive_client import OAUTH2_CONFIG

        self.assertEqual(OAUTH2_CONFIG["web"]["client_id"], "custom_client_id")
        self.assertEqual(OAUTH2_CONFIG["web"]["client_secret"], "custom_client_secret")

    @patch("doc_processing.permissions.drive_client.build")
    @patch("doc_processing.permissions.drive_client.Credentials")
    def test_authenticate_with_existing_token(self, mock_credentials, mock_build):
        """Test authentication with existing valid token."""
        # Mock existing valid credentials
        mock_creds = Mock()
        mock_creds.valid = True
        mock_credentials.from_authorized_user_file.return_value = mock_creds

        # Mock service build
        mock_service = Mock()
        mock_activity_service = Mock()
        mock_build.side_effect = [mock_service, mock_activity_service]

        # Create token file
        token_data = {
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        }

        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

        # Authenticate
        result = self.client.authenticate()

        # Verify authentication
        self.assertTrue(result)
        self.assertEqual(self.client.service, mock_service)
        self.assertEqual(self.client.activity_service, mock_activity_service)
        self.assertEqual(self.client.credentials, mock_creds)

    def test_authenticate_without_credentials_file(self):
        """Test authentication failure when credentials file doesn't exist."""
        client = GoogleDriveClient(
            credentials_file=Path("nonexistent.json"),
            token_file=Path("nonexistent_token.json"),
        )

        result = client.authenticate()

        self.assertFalse(result)

    def test_get_file_permissions(self):
        """Test getting file permissions."""
        # Mock service
        mock_service = Mock()
        mock_permissions = Mock()
        mock_list = Mock()

        mock_service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list
        mock_list.execute.return_value = {
            "permissions": [
                {
                    "id": "1",
                    "type": "user",
                    "role": "owner",
                    "emailAddress": "owner@example.com",
                    "displayName": "Owner User",
                },
                {
                    "id": "2",
                    "type": "user",
                    "role": "writer",
                    "emailAddress": "writer@example.com",
                    "displayName": "Writer User",
                },
            ]
        }

        self.client.service = mock_service

        # Get permissions
        permissions = self.client.get_file_permissions("test_file_id")

        # Verify results
        self.assertEqual(len(permissions), 2)
        self.assertEqual(permissions[0].email_address, "owner@example.com")
        self.assertEqual(permissions[0].role, "owner")
        self.assertEqual(permissions[1].email_address, "writer@example.com")
        self.assertEqual(permissions[1].role, "writer")

        # Verify API call
        mock_permissions.list.assert_called_once_with(
            fileId="test_file_id",
            fields="permissions(id,type,role,emailAddress,displayName,domain,photoLink,deleted,pendingOwner)",
        )

    def test_get_file_permissions_http_error(self):
        """Test handling of HTTP errors when getting permissions."""
        # Mock service to raise HttpError
        mock_service = Mock()
        mock_permissions = Mock()
        mock_list = Mock()

        mock_service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list
        mock_list.execute.side_effect = HttpError(
            resp=Mock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        self.client.service = mock_service

        # Get permissions (should return empty list on error)
        permissions = self.client.get_file_permissions("test_file_id")

        self.assertEqual(len(permissions), 0)

    def test_get_file_metadata(self):
        """Test getting file metadata."""
        # Mock service
        mock_service = Mock()
        mock_files = Mock()
        mock_get = Mock()

        mock_service.files.return_value = mock_files
        mock_files.get.return_value = mock_get
        mock_get.execute.return_value = {
            "id": "test_file_id",
            "name": "Test Document",
            "mimeType": "application/vnd.google-apps.document",
            "parents": ["parent_folder"],
            "webViewLink": "https://docs.google.com/document/d/test_file_id/edit",
            "createdTime": "2023-01-01T00:00:00.000Z",
            "modifiedTime": "2023-01-02T00:00:00.000Z",
            "owners": [{"displayName": "Owner", "emailAddress": "owner@example.com"}],
        }

        self.client.service = mock_service

        # Mock get_file_permissions to return empty list
        with patch.object(self.client, "get_file_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = []

            # Get metadata
            drive_file = self.client.get_file_metadata("test_file_id")

            # Verify results
            self.assertIsNotNone(drive_file)
            self.assertEqual(drive_file.id, "test_file_id")
            self.assertEqual(drive_file.name, "Test Document")
            self.assertEqual(
                drive_file.mime_type, "application/vnd.google-apps.document"
            )
            self.assertEqual(drive_file.parents, ["parent_folder"])

            # Verify API call
            mock_files.get.assert_called_once_with(
                fileId="test_file_id",
                fields="id,name,mimeType,parents,webViewLink,createdTime,modifiedTime,owners",
            )

    def test_get_file_metadata_without_permissions(self):
        """Test getting file metadata without permissions."""
        # Mock service
        mock_service = Mock()
        mock_files = Mock()
        mock_get = Mock()

        mock_service.files.return_value = mock_files
        mock_files.get.return_value = mock_get
        mock_get.execute.return_value = {
            "id": "test_file_id",
            "name": "Test Document",
            "mimeType": "application/vnd.google-apps.document",
            "parents": ["parent_folder"],
        }

        self.client.service = mock_service

        # Get metadata without permissions
        drive_file = self.client.get_file_metadata(
            "test_file_id", include_permissions=False
        )

        # Verify results
        self.assertIsNotNone(drive_file)
        self.assertEqual(len(drive_file.permissions), 0)

    def test_validate_permissions(self):
        """Test permission validation and analysis."""
        # Mock service and permissions
        mock_service = Mock()
        self.client.service = mock_service

        with patch.object(self.client, "get_file_permissions") as mock_get_permissions:
            mock_get_permissions.return_value = [
                DrivePermission(
                    id="1", type="user", role="owner", email_address="owner@example.com"
                ),
                DrivePermission(
                    id="2",
                    type="user",
                    role="writer",
                    email_address="writer@example.com",
                ),
                DrivePermission(id="3", type="anyone", role="reader"),
                DrivePermission(
                    id="4",
                    type="group",
                    role="commenter",
                    email_address="group@example.com",
                ),
            ]

            # Validate permissions
            analysis = self.client.validate_permissions("test_file_id")

            # Verify analysis
            self.assertEqual(analysis["total_permissions"], 4)
            self.assertEqual(analysis["permission_types"]["user"], 2)
            self.assertEqual(analysis["permission_types"]["anyone"], 1)
            self.assertEqual(analysis["permission_types"]["group"], 1)
            self.assertEqual(analysis["permission_roles"]["owner"], 1)
            self.assertEqual(analysis["permission_roles"]["writer"], 1)
            self.assertEqual(analysis["permission_roles"]["reader"], 1)
            self.assertEqual(analysis["permission_roles"]["commenter"], 1)
            self.assertTrue(analysis["has_public_access"])
            self.assertFalse(analysis["has_domain_access"])
            self.assertEqual(analysis["user_count"], 2)
            self.assertEqual(analysis["group_count"], 1)

    def test_get_file_changes(self):
        """Test getting file changes using Drive Activity API."""
        # Mock activity service
        mock_activity_service = Mock()
        mock_activity = Mock()
        mock_query = Mock()

        mock_activity_service.activity.return_value = mock_activity
        mock_activity.query.return_value = mock_query
        mock_query.execute.return_value = {
            "activities": [
                {
                    "timestamp": "2023-01-01T12:00:00Z",
                    "actors": [
                        {
                            "user": {
                                "knownUser": {
                                    "personName": "user@example.com",
                                    "isDeletedUser": False,
                                }
                            }
                        }
                    ],
                    "primaryActionDetail": {"edit": {"editType": "CONTENT_EDIT"}},
                    "targets": [
                        {
                            "driveItem": {
                                "name": "Test Document",
                                "title": "Test Document",
                                "mimeType": "application/vnd.google-apps.document",
                            }
                        }
                    ],
                }
            ]
        }

        self.client.activity_service = mock_activity_service

        # Get file changes
        changes = self.client.get_file_changes("test_file_id")

        # Verify results
        self.assertEqual(len(changes), 1)

        change = changes[0]
        self.assertEqual(change["timestamp"], "2023-01-01T12:00:00Z")
        self.assertEqual(len(change["actors"]), 1)
        self.assertEqual(change["actors"][0]["name"], "user@example.com")
        self.assertEqual(len(change["actions"]), 1)
        self.assertEqual(change["actions"][0]["type"], "edit")
        self.assertEqual(len(change["targets"]), 1)
        self.assertEqual(change["targets"][0]["name"], "Test Document")

        # Verify API call
        mock_activity.query.assert_called_once_with(
            body={"itemName": "items/test_file_id", "pageSize": 100}
        )

    def test_get_file_changes_with_start_time(self):
        """Test getting file changes with start time filter."""
        # Mock activity service
        mock_activity_service = Mock()
        mock_activity = Mock()
        mock_query = Mock()

        mock_activity_service.activity.return_value = mock_activity
        mock_activity.query.return_value = mock_query
        mock_query.execute.return_value = {"activities": []}

        self.client.activity_service = mock_activity_service

        # Get file changes with start time
        changes = self.client.get_file_changes(
            "test_file_id", start_time="2023-01-01T00:00:00Z"
        )

        # Verify API call included filter
        mock_activity.query.assert_called_once_with(
            body={
                "itemName": "items/test_file_id",
                "pageSize": 100,
                "filter": 'time >= "2023-01-01T00:00:00Z"',
            }
        )

    def test_setup_change_notifications(self):
        """Test setting up change notifications."""
        # Mock service
        mock_service = Mock()
        mock_files = Mock()
        mock_watch = Mock()

        mock_service.files.return_value = mock_files
        mock_files.watch.return_value = mock_watch
        mock_watch.execute.return_value = {
            "id": "channel_id",
            "resourceId": "resource_id",
            "resourceUri": "https://www.googleapis.com/drive/v3/files/test_file_id",
            "token": "notification_token",
            "expiration": "1672531200000",
        }

        self.client.service = mock_service

        # Setup notifications
        response = self.client.setup_change_notifications(
            "test_file_id", "https://example.com/webhook"
        )

        # Verify response
        self.assertIn("id", response)
        self.assertIn("resourceId", response)

        # Verify API call
        mock_files.watch.assert_called_once()
        call_args = mock_files.watch.call_args
        self.assertEqual(call_args[1]["fileId"], "test_file_id")

        body = call_args[1]["body"]
        self.assertEqual(body["type"], "web_hook")
        self.assertEqual(body["address"], "https://example.com/webhook")
        self.assertIn("id", body)
        self.assertIn("expiration", body)

    def test_get_user_info(self):
        """Test getting user information."""
        # Mock service
        mock_service = Mock()
        mock_about = Mock()
        mock_get = Mock()

        mock_service.about.return_value = mock_about
        mock_about.get.return_value = mock_get
        mock_get.execute.return_value = {
            "user": {
                "displayName": "Test User",
                "emailAddress": "test@example.com",
                "photoLink": "https://example.com/photo.jpg",
                "me": True,
            }
        }

        self.client.service = mock_service

        # Get user info
        user_info = self.client.get_user_info()

        # Verify results
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["displayName"], "Test User")
        self.assertEqual(user_info["emailAddress"], "test@example.com")
        self.assertTrue(user_info["me"])

        # Verify API call
        mock_about.get.assert_called_once_with(fields="user")


class TestDriveClientIntegration(unittest.TestCase):
    """Integration tests for GoogleDriveClient."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.client = GoogleDriveClient()

    def test_service_not_initialized_errors(self):
        """Test that methods raise appropriate errors when service not initialized."""
        with self.assertRaises(RuntimeError) as context:
            self.client.get_file_permissions("test_file_id")

        self.assertIn("Drive service not initialized", str(context.exception))

        with self.assertRaises(RuntimeError) as context:
            self.client.get_file_metadata("test_file_id")

        self.assertIn("Drive service not initialized", str(context.exception))

        with self.assertRaises(RuntimeError) as context:
            self.client.scan_folder_permissions("test_folder_id")

        self.assertIn("Drive service not initialized", str(context.exception))

    def test_activity_service_not_initialized_errors(self):
        """Test that activity methods raise appropriate errors when service not initialized."""
        with self.assertRaises(RuntimeError) as context:
            self.client.get_file_changes("test_file_id")

        self.assertIn("Drive Activity service not initialized", str(context.exception))


if __name__ == "__main__":
    unittest.main()
