"""Permission synchronization manager for coordinating Drive and git permissions."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .drive_client import GoogleDriveClient
from .git_permissions import GitPermissionManager
from .permission_mapper import PermissionMapper, PermissionMapping

logger = logging.getLogger(__name__)


@dataclass
class SyncJob:
    """Represents a permission synchronization job."""

    job_id: str
    drive_file_id: str
    git_repo_path: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    sync_results: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data["created_at"] = self.created_at.isoformat()
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        return data


@dataclass
class SyncConfiguration:
    """Configuration for permission synchronization."""

    auto_sync_enabled: bool = True
    sync_interval_minutes: int = 60
    max_concurrent_syncs: int = 5
    retry_failed_jobs: bool = True
    max_retries: int = 3
    notification_webhooks: List[str] = None

    def __post_init__(self):
        if self.notification_webhooks is None:
            self.notification_webhooks = []


class PermissionSyncManager:
    """Manages synchronization of permissions between Google Drive and git repositories."""

    def __init__(
        self,
        drive_client: GoogleDriveClient,
        permission_mapper: PermissionMapper,
        sync_config: Optional[SyncConfiguration] = None,
    ):
        """Initialize permission sync manager.

        Args:
            drive_client: GoogleDriveClient for Drive API access
            permission_mapper: PermissionMapper for permission conversion
            sync_config: Optional SyncConfiguration
        """
        self.drive_client = drive_client
        self.permission_mapper = permission_mapper
        self.sync_config = sync_config or SyncConfiguration()

        # Internal state
        self.sync_jobs: Dict[str, SyncJob] = {}
        self.active_syncs: Set[str] = set()
        self.permission_mappings: Dict[str, PermissionMapping] = {}

        # File paths for persistence
        self.jobs_file = Path(".trunk/sync_jobs.json")
        self.mappings_file = Path(".trunk/permission_mappings.json")
        self.config_file = Path(".trunk/sync_config.json")

        # Ensure .trunk directory exists
        Path(".trunk").mkdir(exist_ok=True)

        # Load persisted state
        self._load_state()

    def create_sync_job(
        self, drive_file_id: str, git_repo_path: str, force_sync: bool = False
    ) -> SyncJob:
        """Create a new permission synchronization job.

        Args:
            drive_file_id: Google Drive file ID
            git_repo_path: Path to git repository
            force_sync: Whether to force sync even if recently synced

        Returns:
            Created SyncJob
        """
        job_id = f"{drive_file_id}_{int(datetime.now().timestamp())}"

        # Check if recent sync exists and force_sync is False
        if not force_sync:
            recent_job = self._get_recent_sync_job(drive_file_id, git_repo_path)
            if recent_job and recent_job.status == "completed":
                logger.info(f"Recent sync exists for {drive_file_id}, skipping")
                return recent_job

        sync_job = SyncJob(
            job_id=job_id,
            drive_file_id=drive_file_id,
            git_repo_path=git_repo_path,
            status="pending",
            created_at=datetime.now(),
        )

        self.sync_jobs[job_id] = sync_job
        self._save_jobs()

        logger.info(f"Created sync job {job_id} for Drive file {drive_file_id}")
        return sync_job

    async def execute_sync_job(self, job_id: str) -> Dict[str, Any]:
        """Execute a permission synchronization job.

        Args:
            job_id: ID of sync job to execute

        Returns:
            Dictionary with sync results
        """
        if job_id not in self.sync_jobs:
            raise ValueError(f"Sync job {job_id} not found")

        if job_id in self.active_syncs:
            return {"status": "already_running", "job_id": job_id}

        job = self.sync_jobs[job_id]

        try:
            # Mark job as running
            job.status = "running"
            job.started_at = datetime.now()
            self.active_syncs.add(job_id)
            self._save_jobs()

            logger.info(f"Starting sync job {job_id}")

            # Execute the sync process
            sync_results = await self._perform_permission_sync(job)

            # Update job status
            job.status = "completed"
            job.completed_at = datetime.now()
            job.sync_results = sync_results

            logger.info(f"Completed sync job {job_id}")

        except Exception as e:
            # Mark job as failed
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error_message = str(e)

            logger.error(f"Sync job {job_id} failed: {e}")
            sync_results = {"status": "failed", "error": str(e)}

        finally:
            # Clean up
            self.active_syncs.discard(job_id)
            self._save_jobs()

        return sync_results

    async def _perform_permission_sync(self, job: SyncJob) -> Dict[str, Any]:
        """Perform the actual permission synchronization.

        Args:
            job: SyncJob to execute

        Returns:
            Dictionary with sync results
        """
        results = {
            "status": "success",
            "drive_file_id": job.drive_file_id,
            "git_repo_path": job.git_repo_path,
            "permissions_applied": 0,
            "permissions_failed": 0,
            "warnings": [],
            "errors": [],
        }

        try:
            # Get Drive file with permissions
            drive_file = self.drive_client.get_file_metadata(
                job.drive_file_id, include_permissions=True
            )

            if not drive_file:
                raise ValueError(f"Drive file {job.drive_file_id} not found")

            # Create permission mapping
            mapping = self.permission_mapper.create_permission_mapping(
                drive_file, job.git_repo_path
            )

            # Validate mapping
            validation = self.permission_mapper.validate_permission_mapping(mapping)
            if not validation["is_valid"]:
                results["errors"].extend(validation["errors"])
                raise ValueError("Invalid permission mapping")

            if validation["warnings"]:
                results["warnings"].extend(validation["warnings"])

            # Apply permissions to git repository
            git_manager = GitPermissionManager(Path(job.git_repo_path))
            git_results = git_manager.apply_permissions(mapping.git_permissions)

            # Update results
            results["permissions_applied"] = len(git_results["applied_permissions"])
            results["permissions_failed"] = len(git_results["failed_permissions"])
            results["warnings"].extend(git_results["warnings"])
            results["errors"].extend(git_results["errors"])

            # Store mapping for future reference
            self.permission_mappings[
                f"{job.drive_file_id}_{job.git_repo_path}"
            ] = mapping
            self._save_mappings()

            # Check for any failures
            if results["errors"]:
                results["status"] = "partial_success"

            logger.info(
                f"Sync completed: {results['permissions_applied']} permissions applied"
            )

        except Exception as e:
            results["status"] = "failed"
            results["errors"].append(str(e))
            logger.error(f"Sync failed: {e}")

        return results

    def schedule_auto_sync(self, drive_file_id: str, git_repo_path: str) -> None:
        """Schedule automatic permission synchronization.

        Args:
            drive_file_id: Google Drive file ID
            git_repo_path: Path to git repository
        """
        if not self.sync_config.auto_sync_enabled:
            logger.info("Auto-sync is disabled")
            return

        # Create recurring sync job (implementation would use task scheduler)
        logger.info(
            f"Scheduled auto-sync for {drive_file_id} every {self.sync_config.sync_interval_minutes} minutes"
        )

        # For now, just create a single sync job
        self.create_sync_job(drive_file_id, git_repo_path)

    def get_sync_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a sync job.

        Args:
            job_id: ID of sync job

        Returns:
            Dictionary with job status or None if not found
        """
        if job_id not in self.sync_jobs:
            return None

        job = self.sync_jobs[job_id]
        return job.to_dict()

    def list_sync_jobs(
        self,
        drive_file_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List sync jobs with optional filtering.

        Args:
            drive_file_id: Optional filter by Drive file ID
            status_filter: Optional filter by job status
            limit: Maximum number of jobs to return

        Returns:
            List of job dictionaries
        """
        jobs = list(self.sync_jobs.values())

        # Apply filters
        if drive_file_id:
            jobs = [job for job in jobs if job.drive_file_id == drive_file_id]

        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Apply limit
        jobs = jobs[:limit]

        return [job.to_dict() for job in jobs]

    def cancel_sync_job(self, job_id: str) -> bool:
        """Cancel a pending or running sync job.

        Args:
            job_id: ID of sync job to cancel

        Returns:
            True if job was cancelled, False if not found or not cancellable
        """
        if job_id not in self.sync_jobs:
            return False

        job = self.sync_jobs[job_id]

        if job.status in ["completed", "failed"]:
            return False

        job.status = "cancelled"
        job.completed_at = datetime.now()
        self.active_syncs.discard(job_id)
        self._save_jobs()

        logger.info(f"Cancelled sync job {job_id}")
        return True

    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """Clean up old sync jobs.

        Args:
            days_old: Remove jobs older than this many days

        Returns:
            Number of jobs removed
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)

        jobs_to_remove = [
            job_id
            for job_id, job in self.sync_jobs.items()
            if (
                job.created_at < cutoff_date
                and job.status in ["completed", "failed", "cancelled"]
            )
        ]

        for job_id in jobs_to_remove:
            del self.sync_jobs[job_id]

        if jobs_to_remove:
            self._save_jobs()
            logger.info(f"Cleaned up {len(jobs_to_remove)} old sync jobs")

        return len(jobs_to_remove)

    def get_permission_diff(
        self, drive_file_id: str, git_repo_path: str
    ) -> Optional[Dict[str, Any]]:
        """Get difference between current Drive permissions and last sync.

        Args:
            drive_file_id: Google Drive file ID
            git_repo_path: Path to git repository

        Returns:
            Dictionary with permission differences or None if no previous sync
        """
        mapping_key = f"{drive_file_id}_{git_repo_path}"

        if mapping_key not in self.permission_mappings:
            return None

        current_mapping = self.permission_mappings[mapping_key]

        # Get current Drive file permissions
        current_drive_file = self.drive_client.get_file_metadata(
            drive_file_id, include_permissions=True
        )

        if not current_drive_file:
            return None

        return self.permission_mapper.get_permission_diff(
            current_mapping, current_drive_file
        )

    def _get_recent_sync_job(
        self, drive_file_id: str, git_repo_path: str, hours: int = 1
    ) -> Optional[SyncJob]:
        """Get recent sync job for Drive file and repo.

        Args:
            drive_file_id: Google Drive file ID
            git_repo_path: Path to git repository
            hours: Consider jobs within this many hours as recent

        Returns:
            Recent SyncJob or None if not found
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_jobs = [
            job
            for job in self.sync_jobs.values()
            if (
                job.drive_file_id == drive_file_id
                and job.git_repo_path == git_repo_path
                and job.created_at > cutoff_time
            )
        ]

        if recent_jobs:
            # Return most recent job
            return max(recent_jobs, key=lambda j: j.created_at)

        return None

    def _save_jobs(self) -> None:
        """Save sync jobs to file."""
        jobs_data = {job_id: job.to_dict() for job_id, job in self.sync_jobs.items()}

        with open(self.jobs_file, "w") as f:
            json.dump(jobs_data, f, indent=2)

    def _save_mappings(self) -> None:
        """Save permission mappings to file."""
        mappings_data = {
            key: mapping.to_dict() for key, mapping in self.permission_mappings.items()
        }

        with open(self.mappings_file, "w") as f:
            json.dump(mappings_data, f, indent=2)

    def _load_state(self) -> None:
        """Load persisted state from files."""
        # Load sync jobs
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file, "r") as f:
                    jobs_data = json.load(f)

                for job_id, job_dict in jobs_data.items():
                    # Convert datetime strings back to datetime objects
                    job_dict["created_at"] = datetime.fromisoformat(
                        job_dict["created_at"]
                    )
                    if job_dict["started_at"]:
                        job_dict["started_at"] = datetime.fromisoformat(
                            job_dict["started_at"]
                        )
                    if job_dict["completed_at"]:
                        job_dict["completed_at"] = datetime.fromisoformat(
                            job_dict["completed_at"]
                        )

                    self.sync_jobs[job_id] = SyncJob(**job_dict)

                logger.debug(f"Loaded {len(self.sync_jobs)} sync jobs")

            except Exception as e:
                logger.error(f"Failed to load sync jobs: {e}")

        # Load permission mappings
        if self.mappings_file.exists():
            try:
                with open(self.mappings_file, "r") as f:
                    mappings_data = json.load(f)

                # Note: This is simplified - full implementation would reconstruct
                # PermissionMapping objects from the saved data
                logger.debug(f"Loaded {len(mappings_data)} permission mappings")

            except Exception as e:
                logger.error(f"Failed to load permission mappings: {e}")
