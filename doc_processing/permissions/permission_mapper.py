"""Permission mapping between Google Drive and git repository access levels."""

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .drive_client import DriveFile, DrivePermission

logger = logging.getLogger(__name__)


class GitPermissionLevel(Enum):
    """Git repository permission levels."""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class DriveRole(Enum):
    """Google Drive role mappings."""

    READER = "reader"
    COMMENTER = "commenter"
    WRITER = "writer"
    FILE_ORGANIZER = "fileOrganizer"
    ORGANIZER = "organizer"
    OWNER = "owner"


@dataclass
class GitPermission:
    """Represents a git repository permission."""

    user_email: str
    permission_level: GitPermissionLevel
    source_drive_role: str
    source_drive_type: str
    display_name: Optional[str] = None
    is_inherited: bool = False
    inheritance_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["permission_level"] = self.permission_level.value
        return data


@dataclass
class PermissionMapping:
    """Represents a mapping between Drive and git permissions."""

    drive_file_id: str
    drive_file_name: str
    git_repo_path: str
    drive_permissions: List[DrivePermission]
    git_permissions: List[GitPermission]
    mapping_conflicts: List[str]
    last_synced: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["drive_permissions"] = [perm.to_dict() for perm in self.drive_permissions]
        data["git_permissions"] = [perm.to_dict() for perm in self.git_permissions]
        return data


class PermissionMapper:
    """Maps Google Drive permissions to git repository permissions."""

    # Default mapping from Drive roles to git permission levels
    DEFAULT_ROLE_MAPPING = {
        DriveRole.READER: GitPermissionLevel.READ,
        DriveRole.COMMENTER: GitPermissionLevel.READ,
        DriveRole.WRITER: GitPermissionLevel.WRITE,
        DriveRole.FILE_ORGANIZER: GitPermissionLevel.WRITE,
        DriveRole.ORGANIZER: GitPermissionLevel.ADMIN,
        DriveRole.OWNER: GitPermissionLevel.OWNER,
    }

    def __init__(self, custom_role_mapping: Optional[Dict[str, str]] = None):
        """Initialize permission mapper.

        Args:
            custom_role_mapping: Custom mapping from Drive roles to git permissions
        """
        self.role_mapping = self.DEFAULT_ROLE_MAPPING.copy()

        # Apply custom mappings if provided
        if custom_role_mapping:
            for drive_role, git_level in custom_role_mapping.items():
                try:
                    drive_enum = DriveRole(drive_role)
                    git_enum = GitPermissionLevel(git_level)
                    self.role_mapping[drive_enum] = git_enum
                except ValueError as e:
                    logger.warning(
                        f"Invalid role mapping {drive_role}->{git_level}: {e}"
                    )

    def map_drive_to_git_permissions(
        self, drive_file: DriveFile
    ) -> List[GitPermission]:
        """Map Google Drive permissions to git repository permissions.

        Args:
            drive_file: DriveFile with permissions to map

        Returns:
            List of GitPermission objects
        """
        git_permissions = []
        conflicts = []

        for drive_perm in drive_file.permissions:
            git_perm = self._map_single_permission(drive_perm)
            if git_perm:
                git_permissions.append(git_perm)
            else:
                conflicts.append(
                    f"Unable to map permission: {drive_perm.type}:{drive_perm.role}"
                )

        if conflicts:
            logger.warning(
                f"Permission mapping conflicts for {drive_file.name}: {conflicts}"
            )

        # Remove duplicate permissions (same user with multiple Drive permissions)
        git_permissions = self._resolve_duplicate_permissions(git_permissions)

        return git_permissions

    def _map_single_permission(
        self, drive_perm: DrivePermission
    ) -> Optional[GitPermission]:
        """Map a single Google Drive permission to git permission.

        Args:
            drive_perm: DrivePermission to map

        Returns:
            GitPermission object or None if unmappable
        """
        # Skip deleted or pending permissions
        if drive_perm.deleted or drive_perm.pending_owner:
            return None

        # Handle different permission types
        if drive_perm.type == "user":
            if not drive_perm.email_address:
                logger.warning(
                    f"User permission without email address: {drive_perm.id}"
                )
                return None

            git_level = self._map_drive_role_to_git_level(drive_perm.role)
            if git_level is None:
                return None

            return GitPermission(
                user_email=drive_perm.email_address,
                permission_level=git_level,
                source_drive_role=drive_perm.role,
                source_drive_type=drive_perm.type,
                display_name=drive_perm.display_name,
            )

        elif drive_perm.type == "group":
            # Groups need special handling - expand to individual users
            # For now, log and skip (implementation depends on group expansion API)
            logger.info(
                f"Group permission detected (needs expansion): {drive_perm.email_address}"
            )
            return None

        elif drive_perm.type == "domain":
            # Domain permissions are complex for git repos
            logger.info(f"Domain permission detected: {drive_perm.domain}")
            return None

        elif drive_perm.type == "anyone":
            # Public permissions don't map well to git repos
            logger.info("Public 'anyone' permission detected")
            return None

        else:
            logger.warning(f"Unknown permission type: {drive_perm.type}")
            return None

    def _map_drive_role_to_git_level(
        self, drive_role: str
    ) -> Optional[GitPermissionLevel]:
        """Map Google Drive role to git permission level.

        Args:
            drive_role: Google Drive role string

        Returns:
            GitPermissionLevel or None if unmappable
        """
        try:
            drive_enum = DriveRole(drive_role)
            return self.role_mapping.get(drive_enum)
        except ValueError:
            logger.warning(f"Unknown Drive role: {drive_role}")
            return None

    def _resolve_duplicate_permissions(
        self, git_permissions: List[GitPermission]
    ) -> List[GitPermission]:
        """Resolve duplicate permissions for the same user.

        Args:
            git_permissions: List of GitPermission objects

        Returns:
            Deduplicated list with highest permission level per user
        """
        user_permissions = {}

        # Permission level hierarchy (higher number = more permissions)
        level_hierarchy = {
            GitPermissionLevel.NONE: 0,
            GitPermissionLevel.READ: 1,
            GitPermissionLevel.WRITE: 2,
            GitPermissionLevel.ADMIN: 3,
            GitPermissionLevel.OWNER: 4,
        }

        for git_perm in git_permissions:
            email = git_perm.user_email
            current_level = level_hierarchy.get(git_perm.permission_level, 0)

            if email not in user_permissions:
                user_permissions[email] = git_perm
            else:
                existing_level = level_hierarchy.get(
                    user_permissions[email].permission_level, 0
                )
                if current_level > existing_level:
                    user_permissions[email] = git_perm

        return list(user_permissions.values())

    def create_permission_mapping(
        self, drive_file: DriveFile, git_repo_path: str
    ) -> PermissionMapping:
        """Create a complete permission mapping between Drive file and git repo.

        Args:
            drive_file: DriveFile with permissions
            git_repo_path: Path to git repository

        Returns:
            PermissionMapping object
        """
        git_permissions = self.map_drive_to_git_permissions(drive_file)

        # Identify any mapping conflicts
        conflicts = []

        # Check for unmappable Drive permissions
        mappable_count = len(git_permissions)
        total_count = len([p for p in drive_file.permissions if not p.deleted])
        if mappable_count < total_count:
            conflicts.append(
                f"Only {mappable_count}/{total_count} permissions could be mapped"
            )

        # Check for permission escalation risks
        admin_count = len(
            [
                p
                for p in git_permissions
                if p.permission_level
                in [GitPermissionLevel.ADMIN, GitPermissionLevel.OWNER]
            ]
        )
        if admin_count > 3:  # Arbitrary threshold
            conflicts.append(f"High number of admin users: {admin_count}")

        return PermissionMapping(
            drive_file_id=drive_file.id,
            drive_file_name=drive_file.name,
            git_repo_path=git_repo_path,
            drive_permissions=drive_file.permissions,
            git_permissions=git_permissions,
            mapping_conflicts=conflicts,
        )

    def validate_permission_mapping(self, mapping: PermissionMapping) -> Dict[str, Any]:
        """Validate a permission mapping for security and correctness.

        Args:
            mapping: PermissionMapping to validate

        Returns:
            Dictionary with validation results
        """
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "security_issues": [],
            "mapping_stats": {
                "drive_permissions": len(mapping.drive_permissions),
                "git_permissions": len(mapping.git_permissions),
                "mapping_success_rate": 0.0,
            },
        }

        # Calculate mapping success rate
        active_drive_perms = len(
            [p for p in mapping.drive_permissions if not p.deleted]
        )
        if active_drive_perms > 0:
            success_rate = len(mapping.git_permissions) / active_drive_perms
            validation["mapping_stats"]["mapping_success_rate"] = success_rate

            if success_rate < 0.5:
                validation["warnings"].append("Low permission mapping success rate")

        # Check for security issues
        owner_count = len(
            [
                p
                for p in mapping.git_permissions
                if p.permission_level == GitPermissionLevel.OWNER
            ]
        )
        if owner_count == 0:
            validation["errors"].append("No repository owner mapped")
            validation["is_valid"] = False
        elif owner_count > 1:
            validation["security_issues"].append("Multiple repository owners detected")

        # Check for excessive admin permissions
        admin_count = len(
            [
                p
                for p in mapping.git_permissions
                if p.permission_level == GitPermissionLevel.ADMIN
            ]
        )
        if admin_count > 5:  # Arbitrary threshold
            validation["security_issues"].append(
                f"High number of admin users: {admin_count}"
            )

        # Check for permission inheritance issues
        if any(p.is_inherited for p in mapping.git_permissions):
            validation["warnings"].append("Some permissions are inherited")

        # Include mapping conflicts
        if mapping.mapping_conflicts:
            validation["warnings"].extend(mapping.mapping_conflicts)

        return validation

    def get_permission_diff(
        self, current_mapping: PermissionMapping, new_drive_file: DriveFile
    ) -> Dict[str, Any]:
        """Compare current mapping with new Drive permissions to identify changes.

        Args:
            current_mapping: Current PermissionMapping
            new_drive_file: Updated DriveFile with new permissions

        Returns:
            Dictionary with permission differences
        """
        new_git_permissions = self.map_drive_to_git_permissions(new_drive_file)

        # Convert to sets for comparison
        current_perms = {
            (p.user_email, p.permission_level) for p in current_mapping.git_permissions
        }
        new_perms = {(p.user_email, p.permission_level) for p in new_git_permissions}

        added = new_perms - current_perms
        removed = current_perms - new_perms

        # Identify permission level changes
        current_users = {
            p.user_email: p.permission_level for p in current_mapping.git_permissions
        }
        new_users = {p.user_email: p.permission_level for p in new_git_permissions}

        changed = []
        for email in current_users:
            if email in new_users and current_users[email] != new_users[email]:
                changed.append((email, current_users[email], new_users[email]))

        return {
            "has_changes": bool(added or removed or changed),
            "added_permissions": list(added),
            "removed_permissions": list(removed),
            "changed_permissions": changed,
            "summary": {
                "users_added": len(set(email for email, _ in added)),
                "users_removed": len(set(email for email, _ in removed)),
                "users_changed": len(changed),
            },
        }
