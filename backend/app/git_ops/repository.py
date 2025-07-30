import shutil
from pathlib import Path
from typing import Dict, List, Optional

from git import GitCommandError, Repo


class GitOperations:
    def __init__(self, base_path: str = "./repositories"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def clone_repository(
        self, repo_url: str, repo_name: str, user_id: str
    ) -> Dict[str, any]:
        """Clone a repository for a specific user"""
        user_repo_path = self.base_path / user_id / repo_name

        try:
            if user_repo_path.exists():
                shutil.rmtree(user_repo_path)

            user_repo_path.parent.mkdir(parents=True, exist_ok=True)
            repo = Repo.clone_from(repo_url, user_repo_path)

            return {
                "success": True,
                "message": f"Repository {repo_name} cloned successfully",
                "path": str(user_repo_path),
                "current_branch": repo.active_branch.name,
                "commit_count": len(list(repo.iter_commits())),
            }
        except GitCommandError as e:
            return {"success": False, "error": f"Git clone failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Clone operation failed: {str(e)}"}

    def get_repository_status(self, repo_name: str, user_id: str) -> Dict[str, any]:
        """Get current status of a repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)

            return {
                "success": True,
                "current_branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
                "latest_commit": {
                    "hash": repo.head.commit.hexsha[:8],
                    "message": repo.head.commit.message.strip(),
                    "author": str(repo.head.commit.author),
                    "date": repo.head.commit.committed_datetime.isoformat(),
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get repository status: {str(e)}",
            }

    def commit_changes(
        self,
        repo_name: str,
        user_id: str,
        message: str,
        files: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """Commit changes to repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)

            if files:
                for file_path in files:
                    repo.index.add([file_path])
            else:
                repo.git.add(A=True)

            if not repo.index.diff("HEAD"):
                return {"success": False, "error": "No changes to commit"}

            commit = repo.index.commit(message)

            return {
                "success": True,
                "message": "Changes committed successfully",
                "commit_hash": commit.hexsha[:8],
                "files_changed": len(commit.stats.files),
            }
        except Exception as e:
            return {"success": False, "error": f"Commit failed: {str(e)}"}

    def push_changes(
        self, repo_name: str, user_id: str, branch: str = "main"
    ) -> Dict[str, any]:
        """Push changes to remote repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)
            origin = repo.remote("origin")
            push_info = origin.push(branch)

            return {
                "success": True,
                "message": f"Changes pushed to {branch}",
                "push_info": str(push_info[0].summary),
            }
        except Exception as e:
            return {"success": False, "error": f"Push failed: {str(e)}"}

    def pull_changes(
        self, repo_name: str, user_id: str, branch: str = "main"
    ) -> Dict[str, any]:
        """Pull changes from remote repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)
            origin = repo.remote("origin")
            pull_info = origin.pull(branch)

            return {
                "success": True,
                "message": f"Changes pulled from {branch}",
                "pull_info": str(pull_info[0]),
            }
        except Exception as e:
            return {"success": False, "error": f"Pull failed: {str(e)}"}

    def create_branch(
        self, repo_name: str, user_id: str, branch_name: str
    ) -> Dict[str, any]:
        """Create and switch to new branch"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()

            return {
                "success": True,
                "message": f"Branch '{branch_name}' created and checked out",
                "current_branch": repo.active_branch.name,
            }
        except Exception as e:
            return {"success": False, "error": f"Branch creation failed: {str(e)}"}

    def list_branches(self, repo_name: str, user_id: str) -> Dict[str, any]:
        """List all branches in repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)
            branches = [branch.name for branch in repo.branches]

            return {
                "success": True,
                "current_branch": repo.active_branch.name,
                "branches": branches,
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list branches: {str(e)}"}

    def get_commit_history(
        self, repo_name: str, user_id: str, limit: int = 10
    ) -> Dict[str, any]:
        """Get commit history for repository"""
        repo_path = self.base_path / user_id / repo_name

        try:
            if not repo_path.exists():
                return {"success": False, "error": "Repository not found"}

            repo = Repo(repo_path)
            commits = []

            for commit in repo.iter_commits(max_count=limit):
                commits.append(
                    {
                        "hash": commit.hexsha[:8],
                        "message": commit.message.strip(),
                        "author": str(commit.author),
                        "date": commit.committed_datetime.isoformat(),
                        "files_changed": len(commit.stats.files),
                    }
                )

            return {"success": True, "commits": commits}
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get commit history: {str(e)}",
            }
