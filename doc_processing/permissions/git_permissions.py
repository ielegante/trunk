"""Git repository permission management for mirroring Google Drive permissions."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .permission_mapper import GitPermission, GitPermissionLevel

logger = logging.getLogger(__name__)


@dataclass
class GitCollaborator:
    """Represents a git repository collaborator."""

    username: str
    email: str
    permission_level: GitPermissionLevel
    is_active: bool = True
    added_date: Optional[str] = None
    last_activity: Optional[str] = None


class GitPermissionManager:
    """Manages git repository permissions to mirror Google Drive access."""

    def __init__(self, repo_path: Path):
        """Initialize git permission manager.

        Args:
            repo_path: Path to git repository
        """
        self.repo_path = repo_path
        self.permissions_file = repo_path / ".trunk" / "permissions.json"
        self.hooks_dir = repo_path / ".git" / "hooks"

        # Ensure .trunk directory exists
        self.permissions_file.parent.mkdir(exist_ok=True)

    def apply_permissions(self, git_permissions: List[GitPermission]) -> Dict[str, Any]:
        """Apply git permissions to repository.

        Args:
            git_permissions: List of GitPermission objects to apply

        Returns:
            Dictionary with application results
        """
        results = {
            "success": False,
            "applied_permissions": [],
            "failed_permissions": [],
            "warnings": [],
            "errors": [],
        }

        try:
            # Load existing permissions
            self._load_permissions()

            # Convert permissions to internal format
            new_collaborators = []
            for git_perm in git_permissions:
                collaborator = GitCollaborator(
                    username=self._email_to_username(git_perm.user_email),
                    email=git_perm.user_email,
                    permission_level=git_perm.permission_level,
                    is_active=True,
                )
                new_collaborators.append(collaborator)

            # Update repository permissions
            self._update_repository_permissions(new_collaborators, results)

            # Save permissions to file
            self._save_permissions(new_collaborators)

            # Install git hooks for permission enforcement
            self._install_permission_hooks()

            results["success"] = len(results["errors"]) == 0
            results["applied_permissions"] = [c.email for c in new_collaborators]

            logger.info(f"Applied {len(new_collaborators)} permissions to repository")

        except Exception as e:
            logger.error(f"Failed to apply permissions: {e}")
            results["errors"].append(str(e))

        return results

    def _load_permissions(self) -> List[GitCollaborator]:
        """Load existing permissions from file.

        Returns:
            List of existing GitCollaborator objects
        """
        if not self.permissions_file.exists():
            return []

        try:
            with open(self.permissions_file, "r") as f:
                data = json.load(f)

            collaborators = []
            for collab_data in data.get("collaborators", []):
                collaborator = GitCollaborator(
                    username=collab_data["username"],
                    email=collab_data["email"],
                    permission_level=GitPermissionLevel(
                        collab_data["permission_level"]
                    ),
                    is_active=collab_data.get("is_active", True),
                    added_date=collab_data.get("added_date"),
                    last_activity=collab_data.get("last_activity"),
                )
                collaborators.append(collaborator)

            return collaborators

        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")
            return []

    def _save_permissions(self, collaborators: List[GitCollaborator]) -> None:
        """Save permissions to file.

        Args:
            collaborators: List of GitCollaborator objects to save
        """
        data = {"version": "1.0", "collaborators": []}

        for collab in collaborators:
            collab_data = {
                "username": collab.username,
                "email": collab.email,
                "permission_level": collab.permission_level.value,
                "is_active": collab.is_active,
                "added_date": collab.added_date,
                "last_activity": collab.last_activity,
            }
            data["collaborators"].append(collab_data)

        with open(self.permissions_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(
            f"Saved {len(collaborators)} permissions to {self.permissions_file}"
        )

    def _update_repository_permissions(
        self, collaborators: List[GitCollaborator], results: Dict[str, Any]
    ) -> None:
        """Update repository permissions based on collaborator list.

        Args:
            collaborators: List of GitCollaborator objects
            results: Results dictionary to update
        """
        # For local git repositories, we implement permission control through:
        # 1. File system permissions
        # 2. Git hooks for push/pull control
        # 3. Branch protection (if using hosting service)

        for collab in collaborators:
            try:
                # Set file system permissions based on git permission level
                self._set_filesystem_permissions(collab, results)

                # Configure git user access
                self._configure_git_access(collab, results)

            except Exception as e:
                error_msg = f"Failed to set permissions for {collab.email}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["failed_permissions"].append(collab.email)

    def _set_filesystem_permissions(
        self, collaborator: GitCollaborator, results: Dict[str, Any]
    ) -> None:
        """Set filesystem permissions for collaborator.

        Args:
            collaborator: GitCollaborator object
            results: Results dictionary to update
        """
        # Map git permission levels to filesystem permissions
        permission_mapping = {
            GitPermissionLevel.READ: 0o444,  # Read-only
            GitPermissionLevel.WRITE: 0o664,  # Read-write
            GitPermissionLevel.ADMIN: 0o775,  # Read-write-execute
            GitPermissionLevel.OWNER: 0o775,  # Read-write-execute
        }

        fs_permission = permission_mapping.get(collaborator.permission_level, 0o444)

        # Note: Actual filesystem permission implementation would depend on
        # the hosting environment and user management system
        logger.debug(
            f"Would set filesystem permission {oct(fs_permission)} for {collaborator.email}"
        )

        # For now, just log the intended permission
        results["warnings"].append(
            f"Filesystem permissions require system integration for {collaborator.email}"
        )

    def _configure_git_access(
        self, collaborator: GitCollaborator, results: Dict[str, Any]
    ) -> None:
        """Configure git access for collaborator.

        Args:
            collaborator: GitCollaborator object
            results: Results dictionary to update
        """
        # Add user to git configuration for commit access control
        try:
            # Create a configuration entry for this collaborator
            {
                "email": collaborator.email,
                "username": collaborator.username,
                "permission_level": collaborator.permission_level.value,
                "is_active": collaborator.is_active,
            }

            logger.debug(f"Configured git access for {collaborator.email}")

        except Exception as e:
            error_msg = f"Failed to configure git access for {collaborator.email}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

    def _install_permission_hooks(self) -> None:
        """Install git hooks for permission enforcement."""
        if not self.hooks_dir.exists():
            self.hooks_dir.mkdir(parents=True)

        # Install pre-receive hook for push validation
        pre_receive_hook = self.hooks_dir / "pre-receive"
        pre_receive_script = self._generate_pre_receive_hook()

        with open(pre_receive_hook, "w") as f:
            f.write(pre_receive_script)

        # Make hook executable
        os.chmod(pre_receive_hook, 0o755)

        logger.debug("Installed git permission hooks")

    def _generate_pre_receive_hook(self) -> str:
        """Generate pre-receive hook script for permission validation.

        Returns:
            Hook script content
        """
        return """#!/bin/bash
# Git pre-receive hook for Trunk permission validation
# Auto-generated by GitPermissionManager

PERMISSIONS_FILE="{self.permissions_file}"
REPO_PATH="{self.repo_path}"

# Get the user email from git config
USER_EMAIL=$(git config user.email)

# Check if user has permission to push
python3 -c "
import json
import sys
import os

permissions_file = '${{PERMISSIONS_FILE}}'
user_email = '${{USER_EMAIL}}'

if not os.path.exists(permissions_file):
    print('No permissions file found')
    sys.exit(1)

try:
    with open(permissions_file, 'r') as f:
        data = json.load(f)

    # Check if user has write permissions
    has_permission = False
    for collab in data.get('collaborators', []):
        if collab['email'] == user_email and collab['is_active']:
            perm_level = collab['permission_level']
            if perm_level in ['write', 'admin', 'owner']:
                has_permission = True
                break

    if not has_permission:
        print(f'User {{user_email}} does not have write permission')
        sys.exit(1)

    print(f'Permission validated for {{user_email}}')

except Exception as e:
    print(f'Permission validation failed: {{e}}')
    sys.exit(1)
"

exit $?
"""

    def _email_to_username(self, email: str) -> str:
        """Convert email address to username.

        Args:
            email: Email address

        Returns:
            Username derived from email
        """
        # Simple implementation - use part before @
        return email.split("@")[0]

    def get_current_permissions(self) -> List[GitCollaborator]:
        """Get current repository permissions.

        Returns:
            List of current GitCollaborator objects
        """
        return self._load_permissions()

    def remove_user_permission(self, user_email: str) -> bool:
        """Remove permission for a specific user.

        Args:
            user_email: Email of user to remove

        Returns:
            True if user was removed, False if not found
        """
        collaborators = self._load_permissions()

        # Find and remove user
        original_count = len(collaborators)
        collaborators = [c for c in collaborators if c.email != user_email]

        if len(collaborators) < original_count:
            self._save_permissions(collaborators)
            logger.info(f"Removed permission for {user_email}")
            return True

        return False

    def validate_permissions(self) -> Dict[str, Any]:
        """Validate current repository permissions.

        Returns:
            Dictionary with validation results
        """
        collaborators = self._load_permissions()

        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "permission_stats": {
                "total_users": len(collaborators),
                "active_users": len([c for c in collaborators if c.is_active]),
                "owners": len(
                    [
                        c
                        for c in collaborators
                        if c.permission_level == GitPermissionLevel.OWNER
                    ]
                ),
                "admins": len(
                    [
                        c
                        for c in collaborators
                        if c.permission_level == GitPermissionLevel.ADMIN
                    ]
                ),
                "writers": len(
                    [
                        c
                        for c in collaborators
                        if c.permission_level == GitPermissionLevel.WRITE
                    ]
                ),
                "readers": len(
                    [
                        c
                        for c in collaborators
                        if c.permission_level == GitPermissionLevel.READ
                    ]
                ),
            },
        }

        # Check for repository owner
        owners = [
            c
            for c in collaborators
            if c.permission_level == GitPermissionLevel.OWNER and c.is_active
        ]
        if not owners:
            validation["errors"].append("No active repository owner found")
            validation["is_valid"] = False
        elif len(owners) > 1:
            validation["warnings"].append(f"Multiple repository owners: {len(owners)}")

        # Check for excessive permissions
        admin_count = validation["permission_stats"]["admins"]
        if admin_count > 5:
            validation["warnings"].append(f"High number of admin users: {admin_count}")

        # Check for inactive users
        inactive_users = [c for c in collaborators if not c.is_active]
        if inactive_users:
            validation["warnings"].append(f"Found {len(inactive_users)} inactive users")

        return validation

    def sync_with_remote(self, remote_url: Optional[str] = None) -> Dict[str, Any]:
        """Sync permissions with remote repository hosting service.

        Args:
            remote_url: Optional remote repository URL

        Returns:
            Dictionary with sync results
        """
        # This would integrate with GitHub, GitLab, etc. APIs
        # For now, return placeholder implementation

        results = {
            "success": False,
            "synced_users": [],
            "failed_syncs": [],
            "message": "Remote sync not implemented - requires integration with hosting service API",
        }

        logger.info("Remote permission sync requested but not implemented")
        return results
