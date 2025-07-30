"""Google Drive API client for permission management and document access."""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Drive API scopes for permission management
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.activity.readonly",  # For change detection
]

# OAuth2 configuration
OAUTH2_CONFIG = {
    "web": {
        "client_id": None,  # Will be loaded from environment or config
        "client_secret": None,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8080/oauth2callback"],
    }
}

logger = logging.getLogger(__name__)


@dataclass
class DrivePermission:
    """Represents a Google Drive permission entry."""

    id: str
    type: str  # user, group, domain, anyone
    role: str  # owner, organizer, fileOrganizer, writer, commenter, reader
    email_address: Optional[str] = None
    display_name: Optional[str] = None
    domain: Optional[str] = None
    photo_link: Optional[str] = None
    deleted: bool = False
    pending_owner: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_api_response(cls, permission_data: Dict[str, Any]) -> "DrivePermission":
        """Create DrivePermission from Google Drive API response."""
        return cls(
            id=permission_data.get("id", ""),
            type=permission_data.get("type", ""),
            role=permission_data.get("role", ""),
            email_address=permission_data.get("emailAddress"),
            display_name=permission_data.get("displayName"),
            domain=permission_data.get("domain"),
            photo_link=permission_data.get("photoLink"),
            deleted=permission_data.get("deleted", False),
            pending_owner=permission_data.get("pendingOwner", False),
        )


@dataclass
class DriveFile:
    """Represents a Google Drive file with permissions."""

    id: str
    name: str
    mime_type: str
    permissions: List[DrivePermission]
    parents: List[str]
    web_view_link: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    owners: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.owners is None:
            self.owners = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["permissions"] = [perm.to_dict() for perm in self.permissions]
        return data

    @classmethod
    def from_api_response(
        cls, file_data: Dict[str, Any], permissions: List[DrivePermission]
    ) -> "DriveFile":
        """Create DriveFile from Google Drive API response."""
        return cls(
            id=file_data.get("id", ""),
            name=file_data.get("name", ""),
            mime_type=file_data.get("mimeType", ""),
            permissions=permissions,
            parents=file_data.get("parents", []),
            web_view_link=file_data.get("webViewLink"),
            created_time=file_data.get("createdTime"),
            modified_time=file_data.get("modifiedTime"),
            owners=file_data.get("owners", []),
        )


class GoogleDriveClient:
    """Google Drive API client for permission management and document access."""

    def __init__(
        self,
        credentials_file: Optional[Path] = None,
        token_file: Optional[Path] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize Google Drive client.

        Args:
            credentials_file: Path to OAuth2 credentials JSON file
            token_file: Path to store/load access tokens
            client_id: OAuth2 client ID (overrides credentials file)
            client_secret: OAuth2 client secret (overrides credentials file)
        """
        self.credentials_file = credentials_file or Path("credentials.json")
        self.token_file = token_file or Path("token.json")
        self.service = None
        self.credentials = None
        self.activity_service = None

        # Override OAuth2 config if provided
        if client_id and client_secret:
            OAUTH2_CONFIG["web"]["client_id"] = client_id
            OAUTH2_CONFIG["web"]["client_secret"] = client_secret

    def authenticate(self) -> bool:
        """Authenticate with Google Drive API.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Load existing token if available
            if self.token_file.exists():
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.token_file), SCOPES
                )

            # If no valid credentials, initiate OAuth flow
            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    self.credentials.refresh(Request())
                else:
                    if not self.credentials_file.exists():
                        logger.error(
                            f"Credentials file not found: {self.credentials_file}"
                        )
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES
                    )
                    self.credentials = flow.run_local_server(port=0)

                # Save credentials for next run
                with open(self.token_file, "w") as token:
                    token.write(self.credentials.to_json())

            # Build Drive service
            self.service = build("drive", "v3", credentials=self.credentials)
            # Build Drive Activity service for change detection
            self.activity_service = build(
                "driveactivity", "v2", credentials=self.credentials
            )
            logger.info("Successfully authenticated with Google Drive API")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def get_file_permissions(self, file_id: str) -> List[DrivePermission]:
        """Get all permissions for a Google Drive file.

        Args:
            file_id: Google Drive file ID

        Returns:
            List of DrivePermission objects
        """
        if not self.service:
            raise RuntimeError(
                "Drive service not initialized. Call authenticate() first."
            )

        try:
            # Get permissions for the file
            permissions_result = (
                self.service.permissions()
                .list(
                    fileId=file_id,
                    fields="permissions(id,type,role,emailAddress,displayName,domain,photoLink,deleted,pendingOwner)",
                )
                .execute()
            )

            permissions = []
            for perm_data in permissions_result.get("permissions", []):
                permissions.append(DrivePermission.from_api_response(perm_data))

            logger.debug(f"Retrieved {len(permissions)} permissions for file {file_id}")
            return permissions

        except HttpError as e:
            logger.error(f"Failed to get permissions for file {file_id}: {e}")
            return []

    def get_file_metadata(
        self, file_id: str, include_permissions: bool = True
    ) -> Optional[DriveFile]:
        """Get metadata for a Google Drive file.

        Args:
            file_id: Google Drive file ID
            include_permissions: Whether to include permission data

        Returns:
            DriveFile object or None if not found
        """
        if not self.service:
            raise RuntimeError(
                "Drive service not initialized. Call authenticate() first."
            )

        try:
            # Get file metadata
            file_result = (
                self.service.files()
                .get(
                    fileId=file_id,
                    fields="id,name,mimeType,parents,webViewLink,createdTime,modifiedTime,owners",
                )
                .execute()
            )

            permissions = []
            if include_permissions:
                permissions = self.get_file_permissions(file_id)

            drive_file = DriveFile.from_api_response(file_result, permissions)
            logger.debug(f"Retrieved metadata for file: {drive_file.name}")
            return drive_file

        except HttpError as e:
            logger.error(f"Failed to get metadata for file {file_id}: {e}")
            return None

    def scan_folder_permissions(
        self, folder_id: str, recursive: bool = True
    ) -> List[DriveFile]:
        """Scan all files in a folder and retrieve their permissions.

        Args:
            folder_id: Google Drive folder ID
            recursive: Whether to scan subfolders recursively

        Returns:
            List of DriveFile objects with permissions
        """
        if not self.service:
            raise RuntimeError(
                "Drive service not initialized. Call authenticate() first."
            )

        files_with_permissions = []
        files_to_process = [folder_id]
        processed_folders = set()

        while files_to_process:
            current_folder = files_to_process.pop(0)

            if current_folder in processed_folders:
                continue
            processed_folders.add(current_folder)

            try:
                # Get all files in current folder
                results = (
                    self.service.files()
                    .list(
                        q=f"'{current_folder}' in parents and trashed=false",
                        fields="files(id,name,mimeType,parents,webViewLink,createdTime,modifiedTime,owners)",
                    )
                    .execute()
                )

                files = results.get("files", [])
                logger.debug(f"Found {len(files)} files in folder {current_folder}")

                for file_data in files:
                    file_id = file_data.get("id")
                    mime_type = file_data.get("mimeType", "")

                    # If it's a folder and we're scanning recursively, add to queue
                    if recursive and mime_type == "application/vnd.google-apps.folder":
                        files_to_process.append(file_id)

                    # Get permissions for this file
                    permissions = self.get_file_permissions(file_id)
                    drive_file = DriveFile.from_api_response(file_data, permissions)
                    files_with_permissions.append(drive_file)

            except HttpError as e:
                logger.error(f"Failed to scan folder {current_folder}: {e}")
                continue

        logger.info(f"Scanned {len(files_with_permissions)} files with permissions")
        return files_with_permissions

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the authenticated user.

        Returns:
            User information dictionary or None if failed
        """
        if not self.service:
            raise RuntimeError(
                "Drive service not initialized. Call authenticate() first."
            )

        try:
            about = self.service.about().get(fields="user").execute()
            user_info = about.get("user", {})
            logger.debug(f"Retrieved user info for: {user_info.get('emailAddress')}")
            return user_info

        except HttpError as e:
            logger.error(f"Failed to get user info: {e}")
            return None

    def validate_permissions(self, file_id: str) -> Dict[str, Any]:
        """Validate and analyze permissions for a file.

        Args:
            file_id: Google Drive file ID

        Returns:
            Dictionary with permission analysis
        """
        permissions = self.get_file_permissions(file_id)

        analysis = {
            "total_permissions": len(permissions),
            "permission_types": {},
            "permission_roles": {},
            "has_public_access": False,
            "has_domain_access": False,
            "user_count": 0,
            "group_count": 0,
        }

        for perm in permissions:
            # Count permission types
            perm_type = perm.type
            analysis["permission_types"][perm_type] = (
                analysis["permission_types"].get(perm_type, 0) + 1
            )

            # Count permission roles
            role = perm.role
            analysis["permission_roles"][role] = (
                analysis["permission_roles"].get(role, 0) + 1
            )

            # Check for public/domain access
            if perm_type == "anyone":
                analysis["has_public_access"] = True
            elif perm_type == "domain":
                analysis["has_domain_access"] = True
            elif perm_type == "user":
                analysis["user_count"] += 1
            elif perm_type == "group":
                analysis["group_count"] += 1

        return analysis

    def get_file_changes(
        self, file_id: str, start_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent changes to a file using Drive Activity API.

        Args:
            file_id: Google Drive file ID
            start_time: Optional RFC3339 timestamp to start from

        Returns:
            List of change activity dictionaries
        """
        if not self.activity_service:
            raise RuntimeError(
                "Drive Activity service not initialized. Call authenticate() first."
            )

        try:
            # Build the request for file-specific activities
            request_body = {
                "itemName": f"items/{file_id}",
                "pageSize": 100,
            }

            if start_time:
                request_body["filter"] = f'time >= "{start_time}"'

            # Query Drive Activity API
            results = (
                self.activity_service.activity().query(body=request_body).execute()
            )

            activities = results.get("activities", [])
            changes = []

            for activity in activities:
                change = self._parse_activity(activity)
                if change:
                    changes.append(change)

            logger.debug(f"Found {len(changes)} changes for file {file_id}")
            return changes

        except HttpError as e:
            logger.error(f"Failed to get changes for file {file_id}: {e}")
            return []

    def _parse_activity(self, activity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Drive Activity API response into simplified change object.

        Args:
            activity: Activity object from Drive Activity API

        Returns:
            Simplified change dictionary or None
        """
        try:
            change = {
                "timestamp": activity.get("timestamp"),
                "actors": [],
                "actions": [],
                "targets": [],
            }

            # Extract actors (users who made changes)
            for actor in activity.get("actors", []):
                if "user" in actor:
                    user = actor["user"]
                    if "knownUser" in user:
                        person = user["knownUser"]["personName"]
                        change["actors"].append(
                            {
                                "type": "user",
                                "name": person,
                                "is_deleted": user["knownUser"].get(
                                    "isDeletedUser", False
                                ),
                            }
                        )

            # Extract primary action
            primary_action = activity.get("primaryActionDetail", {})
            for action_type, action_detail in primary_action.items():
                change["actions"].append({"type": action_type, "detail": action_detail})

            # Extract targets
            for target in activity.get("targets", []):
                if "driveItem" in target:
                    item = target["driveItem"]
                    change["targets"].append(
                        {
                            "type": "drive_item",
                            "name": item.get("name"),
                            "title": item.get("title"),
                            "mime_type": item.get("mimeType"),
                        }
                    )

            return change if change["actions"] else None

        except Exception as e:
            logger.warning(f"Failed to parse activity: {e}")
            return None

    def setup_change_notifications(
        self, file_id: str, webhook_url: str
    ) -> Dict[str, Any]:
        """Set up push notifications for file changes.

        Args:
            file_id: Google Drive file ID to watch
            webhook_url: URL to receive change notifications

        Returns:
            Dictionary with watch channel information
        """
        if not self.service:
            raise RuntimeError(
                "Drive service not initialized. Call authenticate() first."
            )

        try:
            # Create a unique channel ID
            import uuid

            channel_id = str(uuid.uuid4())

            # Set up the watch request
            body = {
                "id": channel_id,
                "type": "web_hook",
                "address": webhook_url,
                "expiration": int(
                    (datetime.now() + timedelta(days=7)).timestamp() * 1000
                ),
            }

            # Start watching the file
            response = self.service.files().watch(fileId=file_id, body=body).execute()

            logger.info(f"Set up change notifications for file {file_id}")
            return response

        except HttpError as e:
            logger.error(f"Failed to set up notifications for file {file_id}: {e}")
            return {"error": str(e)}
