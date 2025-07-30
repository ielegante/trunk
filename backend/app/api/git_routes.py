from typing import List, Optional

from app.api.auth_routes import get_current_user_id
from app.git_ops.repository import GitOperations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/git", tags=["git operations"])
git_ops = GitOperations()


class CloneRequest(BaseModel):
    repo_url: str
    repo_name: str


class CommitRequest(BaseModel):
    message: str
    files: Optional[List[str]] = None


class BranchRequest(BaseModel):
    branch_name: str


@router.post("/clone")
async def clone_repository(
    request: CloneRequest, user_id: str = Depends(get_current_user_id)
):
    """Clone a repository for the authenticated user"""
    result = git_ops.clone_repository(request.repo_url, request.repo_name, user_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/status/{repo_name}")
async def get_repository_status(
    repo_name: str, user_id: str = Depends(get_current_user_id)
):
    """Get status of a repository"""
    result = git_ops.get_repository_status(repo_name, user_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/commit/{repo_name}")
async def commit_changes(
    repo_name: str, request: CommitRequest, user_id: str = Depends(get_current_user_id)
):
    """Commit changes to repository"""
    result = git_ops.commit_changes(repo_name, user_id, request.message, request.files)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/push/{repo_name}")
async def push_changes(
    repo_name: str, branch: str = "main", user_id: str = Depends(get_current_user_id)
):
    """Push changes to remote repository"""
    result = git_ops.push_changes(repo_name, user_id, branch)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/pull/{repo_name}")
async def pull_changes(
    repo_name: str, branch: str = "main", user_id: str = Depends(get_current_user_id)
):
    """Pull changes from remote repository"""
    result = git_ops.pull_changes(repo_name, user_id, branch)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/branch/{repo_name}")
async def create_branch(
    repo_name: str, request: BranchRequest, user_id: str = Depends(get_current_user_id)
):
    """Create and switch to new branch"""
    result = git_ops.create_branch(repo_name, user_id, request.branch_name)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/branches/{repo_name}")
async def list_branches(repo_name: str, user_id: str = Depends(get_current_user_id)):
    """List all branches in repository"""
    result = git_ops.list_branches(repo_name, user_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/history/{repo_name}")
async def get_commit_history(
    repo_name: str, limit: int = 10, user_id: str = Depends(get_current_user_id)
):
    """Get commit history for repository"""
    result = git_ops.get_commit_history(repo_name, user_id, limit)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
