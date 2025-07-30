"""Sanitization pipeline for cleaning template history."""

import hashlib
import json
import logging
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .redaction_system import RedactionResult, RedactionSystem

logger = logging.getLogger(__name__)


@dataclass
class SanitizationReport:
    """Report of sanitization operations performed."""

    original_commits: int
    sanitized_commits: int
    removed_commits: int
    files_processed: int
    redactions_made: int
    warnings: List[str]
    summary: Dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class FileChange:
    """Represents a change to a file in git history."""

    file_path: str
    change_type: str  # added, modified, deleted
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    commit_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class SanitizationPipeline:
    """Pipeline for sanitizing git history and document content."""

    def __init__(self, redaction_system: Optional[RedactionSystem] = None):
        """Initialize sanitization pipeline.

        Args:
            redaction_system: Optional RedactionSystem instance
        """
        self.redaction_system = redaction_system or RedactionSystem()
        self.processed_commits = set()
        self.sanitization_rules = self._default_sanitization_rules()

    def sanitize_git_history(
        self, repo_path: Path, branch: str = "main", output_branch: Optional[str] = None
    ) -> SanitizationReport:
        """Sanitize entire git history of a repository.

        Args:
            repo_path: Path to git repository
            branch: Branch to sanitize
            output_branch: Optional output branch name

        Returns:
            SanitizationReport
        """
        logger.info(f"Starting git history sanitization for {repo_path}")

        if not output_branch:
            output_branch = f"{branch}_sanitized"

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Clone repository
            clone_path = temp_path / "repo_clone"
            self._clone_repository(repo_path, clone_path)

            # Get commit history
            commits = self._get_commit_history(clone_path, branch)
            original_commits = len(commits)

            # Process each commit
            sanitized_commits = 0
            removed_commits = 0
            files_processed = set()
            total_redactions = 0
            warnings = []

            for commit in commits:
                try:
                    # Check out commit
                    self._checkout_commit(clone_path, commit["hash"])

                    # Get changed files
                    changed_files = self._get_changed_files(clone_path, commit["hash"])

                    # Sanitize files
                    commit_redactions = 0
                    for file_path in changed_files:
                        if self._should_process_file(file_path):
                            files_processed.add(file_path)
                            redactions = self._sanitize_file(clone_path / file_path)
                            commit_redactions += redactions

                    if commit_redactions > 0:
                        # Commit sanitized changes
                        self._commit_changes(
                            clone_path,
                            f"Sanitized: {commit['message']}",
                            commit["author"],
                            commit["date"],
                        )
                        sanitized_commits += 1
                        total_redactions += commit_redactions

                except Exception as e:
                    logger.error(f"Failed to process commit {commit['hash']}: {e}")
                    warnings.append(f"Failed to process commit {commit['hash'][:8]}")

            # Create sanitized branch
            self._create_branch(clone_path, output_branch)

            # Push sanitized branch back to original repo
            self._push_branch(clone_path, repo_path, output_branch)

        # Generate report
        report = SanitizationReport(
            original_commits=original_commits,
            sanitized_commits=sanitized_commits,
            removed_commits=removed_commits,
            files_processed=len(files_processed),
            redactions_made=total_redactions,
            warnings=warnings,
            summary={
                "branch": branch,
                "output_branch": output_branch,
                "success_rate": (
                    (sanitized_commits / original_commits * 100)
                    if original_commits > 0
                    else 0
                ),
            },
            timestamp=datetime.now(),
        )

        logger.info(
            f"Sanitization complete. Processed {original_commits} commits, made {total_redactions} redactions"
        )
        return report

    def sanitize_document(
        self, document_path: Path, output_path: Optional[Path] = None
    ) -> Tuple[Path, RedactionResult]:
        """Sanitize a single document.

        Args:
            document_path: Path to document
            output_path: Optional output path

        Returns:
            Tuple of (output_path, redaction_result)
        """
        logger.info(f"Sanitizing document: {document_path}")

        # Read document content
        with open(document_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Apply redaction
        sanitized_content, result = self.redaction_system.redact_content(
            content, aggressive=True
        )

        # Determine output path
        if not output_path:
            output_path = (
                document_path.parent
                / f"{document_path.stem}_sanitized{document_path.suffix}"
            )

        # Write sanitized content
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sanitized_content)

        logger.info(f"Document sanitized. Made {result.redactions_count} redactions")
        return output_path, result

    def create_sanitization_filter(self, patterns: List[str]) -> str:
        """Create a git filter script for sanitization.

        Args:
            patterns: List of patterns to filter

        Returns:
            Filter script content
        """
        script_lines = [
            "#!/usr/bin/env python3",
            "import sys",
            "import re",
            "",
            "# Patterns to redact",
            f"patterns = {patterns}",
            "",
            "# Read content from stdin",
            "content = sys.stdin.read()",
            "",
            "# Apply redactions",
            "for pattern in patterns:",
            "    content = re.sub(pattern, '[REDACTED]', content, flags=re.IGNORECASE)",
            "",
            "# Write to stdout",
            "sys.stdout.write(content)",
        ]

        return "\n".join(script_lines)

    def verify_sanitization(self, repo_path: Path, branch: str) -> Dict[str, Any]:
        """Verify that sanitization was successful.

        Args:
            repo_path: Path to repository
            branch: Branch to verify

        Returns:
            Verification results
        """
        logger.info(f"Verifying sanitization of {branch} in {repo_path}")

        results = {
            "branch": branch,
            "verified": True,
            "issues": [],
            "sensitive_content_found": [],
        }

        # Get all files in branch
        files = self._get_all_files(repo_path, branch)

        for file_path in files:
            if self._should_process_file(file_path):
                # Read file content
                content = self._read_file_from_branch(repo_path, branch, file_path)

                # Scan for sensitive content
                sensitive_items = self.redaction_system.scan_content(content)

                if sensitive_items:
                    results["verified"] = False
                    results["issues"].append(
                        f"Found {len(sensitive_items)} sensitive items in {file_path}"
                    )

                    for item in sensitive_items[:5]:  # Limit to first 5
                        results["sensitive_content_found"].append(
                            {
                                "file": file_path,
                                "type": item.content_type,
                                "preview": (
                                    item.original_text[:20] + "..."
                                    if len(item.original_text) > 20
                                    else item.original_text
                                ),
                            }
                        )

        return results

    def _default_sanitization_rules(self) -> Dict[str, Any]:
        """Get default sanitization rules.

        Returns:
            Dictionary of sanitization rules
        """
        return {
            "remove_comments": True,
            "remove_metadata": True,
            "remove_author_info": False,  # Keep for attribution
            "aggressive_redaction": True,
            "file_extensions": [".md", ".txt", ".docx", ".doc", ".rt"],
            "exclude_paths": ["node_modules", ".git", "dist", "build"],
        }

    def _clone_repository(self, source: Path, destination: Path):
        """Clone a git repository.

        Args:
            source: Source repository path
            destination: Destination path
        """
        cmd = ["git", "clone", str(source), str(destination)]
        subprocess.run(cmd, check=True, capture_output=True)

    def _get_commit_history(self, repo_path: Path, branch: str) -> List[Dict[str, Any]]:
        """Get commit history for a branch.

        Args:
            repo_path: Repository path
            branch: Branch name

        Returns:
            List of commit information
        """
        cmd = [
            "git",
            "-C",
            str(repo_path),
            "log",
            branch,
            "--pretty=format:%H|%an|%ae|%at|%s",
            "--reverse",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                commits.append(
                    {
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    }
                )

        return commits

    def _checkout_commit(self, repo_path: Path, commit_hash: str):
        """Check out a specific commit.

        Args:
            repo_path: Repository path
            commit_hash: Commit hash
        """
        cmd = ["git", "-C", str(repo_path), "checkout", commit_hash]
        subprocess.run(cmd, check=True, capture_output=True)

    def _get_changed_files(self, repo_path: Path, commit_hash: str) -> List[str]:
        """Get files changed in a commit.

        Args:
            repo_path: Repository path
            commit_hash: Commit hash

        Returns:
            List of file paths
        """
        cmd = [
            "git",
            "-C",
            str(repo_path),
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_hash,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                files.append(line)

        return files

    def _should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed.

        Args:
            file_path: File path to check

        Returns:
            True if file should be processed
        """
        path = Path(file_path)

        # Check extension
        if path.suffix.lower() not in self.sanitization_rules["file_extensions"]:
            return False

        # Check excluded paths
        for exclude in self.sanitization_rules["exclude_paths"]:
            if exclude in str(path):
                return False

        return True

    def _sanitize_file(self, file_path: Path) -> int:
        """Sanitize a single file.

        Args:
            file_path: Path to file

        Returns:
            Number of redactions made
        """
        if not file_path.exists():
            return 0

        try:
            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Apply redaction
            sanitized_content, result = self.redaction_system.redact_content(content)

            # Write back if changes were made
            if result.redactions_count > 0:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(sanitized_content)

            return result.redactions_count

        except Exception as e:
            logger.error(f"Failed to sanitize {file_path}: {e}")
            return 0

    def _commit_changes(self, repo_path: Path, message: str, author: str, date: str):
        """Commit changes to repository.

        Args:
            repo_path: Repository path
            message: Commit message
            author: Author name
            date: Commit date
        """
        # Stage all changes
        cmd = ["git", "-C", str(repo_path), "add", "-A"]
        subprocess.run(cmd, check=True, capture_output=True)

        # Commit with original author and date
        cmd = [
            "git",
            "-C",
            str(repo_path),
            "commit",
            "-m",
            message,
            f"--author={author}",
            f"--date={date}",
        ]
        subprocess.run(cmd, capture_output=True)  # May fail if no changes

    def _create_branch(self, repo_path: Path, branch_name: str):
        """Create a new branch.

        Args:
            repo_path: Repository path
            branch_name: Branch name
        """
        cmd = ["git", "-C", str(repo_path), "checkout", "-b", branch_name]
        subprocess.run(cmd, check=True, capture_output=True)

    def _push_branch(self, source_repo: Path, dest_repo: Path, branch: str):
        """Push branch from source to destination.

        Args:
            source_repo: Source repository
            dest_repo: Destination repository
            branch: Branch to push
        """
        # Add destination as remote
        cmd = ["git", "-C", str(source_repo), "remote", "add", "dest", str(dest_repo)]
        subprocess.run(cmd, capture_output=True)

        # Push branch
        cmd = ["git", "-C", str(source_repo), "push", "dest", branch]
        subprocess.run(cmd, check=True, capture_output=True)

    def _get_all_files(self, repo_path: Path, branch: str) -> List[str]:
        """Get all files in a branch.

        Args:
            repo_path: Repository path
            branch: Branch name

        Returns:
            List of file paths
        """
        cmd = ["git", "-C", str(repo_path), "ls-tree", "-r", branch, "--name-only"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                files.append(line)

        return files

    def _read_file_from_branch(
        self, repo_path: Path, branch: str, file_path: str
    ) -> str:
        """Read file content from a specific branch.

        Args:
            repo_path: Repository path
            branch: Branch name
            file_path: File path within repository

        Returns:
            File content
        """
        cmd = ["git", "-C", str(repo_path), "show", f"{branch}:{file_path}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
