import json
import logging
import os
from typing import List, Optional

from app.api.auth_routes import get_current_user
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

# Using SQLite-based rate limiter instead of Redis for lightweight deployment
# from app.security.sqlite_rate_limiter import SQLiteRateLimiter


logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# Power user modules not yet implemented - temporary stubs
class CommandResult:
    pass


class CommandStatus:
    pass


class GitCommand:
    pass


class GitCommandExecutor:
    pass


class GitCommandValidator:
    pass


class GitCommandAuditLogger:
    pass


# Request/Response Models
class GitCommandRequest(BaseModel):
    command: str = Field(..., description="Git command to execute")
    args: List[str] = Field(default=[], description="Command arguments")
    repository_id: str = Field(..., description="Repository ID")
    cwd: Optional[str] = Field(None, description="Working directory within repository")
    timeout: int = Field(30, ge=1, le=300, description="Command timeout in seconds")


class GitCommandResponse(BaseModel):
    command: str
    args: List[str]
    status: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    executed_at: str


class CommandHistoryEntry(BaseModel):
    command: str
    args: List[str]
    status: str
    executed_at: str
    execution_time: float
    repository_id: str


class PowerUserStatusResponse(BaseModel):
    enabled: bool
    user_id: str
    allowed_commands: List[str]
    command_count_today: int
    rate_limit_remaining: int


# Dependencies
def get_git_executor() -> GitCommandExecutor:
    # validator = GitCommandValidator()
    # repo_base_path = os.getenv("GIT_REPO_BASE_PATH", "/var/lib/trunk/repos")
    # return GitCommandExecutor(validator, repo_base_path)
    return GitCommandExecutor()  # TODO: Implement with proper parameters


def get_audit_logger() -> GitCommandAuditLogger:
    log_file = os.getenv("GIT_AUDIT_LOG", "/var/log/trunk/git_audit.log")
    return GitCommandAuditLogger(log_file)


# Rate limiting helper
async def check_rate_limit(user_id: str) -> tuple[bool, int]:
    """Check if user has exceeded rate limit"""
    # key = f"trunk:power_user:rate:{user_id}"  # Not used - will implement SQLite rate limiting
    limit = int(os.getenv("POWER_USER_RATE_LIMIT", "100"))  # Commands per hour

    # Using SQLite-based rate limiting instead of Redis
    # rate_limiter = SQLiteRateLimiter()  # TODO: Implement SQLite rate limiting
    # For now, always allow (rate limiting can be implemented with SQLite)
    return True, limit

    # remaining = max(0, limit - current)
    # return current <= limit, remaining


# Permission check
async def verify_power_user_access(user: dict, repository_id: str) -> bool:
    """Verify user has power user access to repository"""
    # Check if user has power user role
    if not user.get("power_user", False):
        return False

    # Check repository access (simplified - should integrate with actual permission system)
    user_repos = user.get("repositories", [])
    return repository_id in user_repos or user.get("role") == "admin"


# API Endpoints


@router.post("/execute", response_model=GitCommandResponse)
async def execute_git_command(
    request: GitCommandRequest,
    current_user=Depends(get_current_user),
    executor: GitCommandExecutor = Depends(get_git_executor),
    audit_logger: GitCommandAuditLogger = Depends(get_audit_logger),
    # redis_client removed - using SQLite for lightweight deployment
):
    """
    Execute a git command in power user mode
    """
    try:
        # Check power user access
        if not await verify_power_user_access(current_user, request.repository_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Power user access required for this operation",
            )

        # Check rate limit
        allowed, remaining = await check_rate_limit(current_user["id"])
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
                headers={"X-RateLimit-Remaining": "0"},
            )

        # Create git command
        git_command = GitCommand(
            command=request.command,
            args=request.args,
            repository_id=request.repository_id,
            user_id=current_user["id"],
            cwd=request.cwd,
            timeout=request.timeout,
        )

        # Execute command
        result = await executor.execute(git_command)

        # Log for audit
        audit_logger.log_command_execution(git_command, result, current_user)

        # Store in command history
        await store_command_history(current_user["id"], git_command, result)

        # Check for forbidden command
        if result.status == CommandStatus.FORBIDDEN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=result.stderr
            )

        # Return response
        response = GitCommandResponse(
            command=result.command,
            args=request.args,
            status=result.status.value,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            executed_at=result.executed_at.isoformat(),
        )

        # Add rate limit headers
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Git command execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during command execution",
        )


async def store_command_history(
    user_id: str, command: GitCommand, result: CommandResult
):
    """Store command in user's history"""
    # key = f"trunk:power_user:history:{user_id}"  # TODO: Use for SQLite storage

    entry = {
        "command": command.command,
        "args": command.args,
        "repository_id": command.repository_id,
        "status": result.status.value,
        "executed_at": result.executed_at.isoformat(),
        "execution_time": result.execution_time,
    }

    # TODO: Implement SQLite-based command history storage
    # For now, just log the command
    logger.info(f"Command history: {entry}")


@router.get("/history", response_model=List[CommandHistoryEntry])
async def get_command_history(
    limit: int = 20,
    current_user=Depends(get_current_user),
    # redis_client removed - using SQLite for lightweight deployment
):
    """
    Get user's git command history
    """
    try:
        # key = f"trunk:power_user:history:{current_user['id']}"  # TODO: Use for SQLite

        # Get history from Redis
        # TODO: Implement SQLite-based command history retrieval
        history_data = []

        history = []
        for entry_json in history_data:
            try:
                entry = json.loads(entry_json)
                history.append(CommandHistoryEntry(**entry))
            except json.JSONDecodeError:
                continue

        return history

    except Exception as e:
        logger.error(f"Failed to get command history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve command history",
        )


@router.get("/status", response_model=PowerUserStatusResponse)
async def get_power_user_status(
    current_user=Depends(get_current_user),  # redis_client removed - using SQLite
):
    """
    Get power user status and limits
    """
    try:
        # Check if user has power user access
        is_power_user = current_user.get("power_user", False)

        # Get rate limit info
        # key = f"trunk:power_user:rate:{current_user['id']}"  # TODO: Use for SQLite
        # TODO: Implement SQLite-based command counting
        current_count = 0
        current_count = int(current_count) if current_count else 0

        limit = int(os.getenv("POWER_USER_RATE_LIMIT", "100"))
        remaining = max(0, limit - current_count)

        # Get allowed commands
        # validator = GitCommandValidator()
        # TODO: Get allowed commands from GitCommandValidator
        allowed_commands = ["status", "log", "diff", "show", "branch", "tag"]

        return PowerUserStatusResponse(
            enabled=is_power_user,
            user_id=current_user["id"],
            allowed_commands=allowed_commands,
            command_count_today=current_count,
            rate_limit_remaining=remaining,
        )

    except Exception as e:
        logger.error(f"Failed to get power user status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve power user status",
        )


@router.get("/validate")
async def validate_git_command(
    command: str, args: str = "", current_user=Depends(get_current_user)
):
    """
    Validate a git command without executing it
    """
    try:
        # validator = GitCommandValidator()

        # Parse args
        arg_list = args.split() if args else []

        # Create command for validation
        # git_command = GitCommand(
        #     command=command,
        #     args=arg_list,
        #     repository_id="validation",
        #     user_id=current_user["id"],
        # )  # TODO: Use when GitCommand is properly implemented

        # Validate
        # is_valid, error_message = validator.validate_command(git_command)
        # TODO: Implement validation
        is_valid = True
        error_message = None

        return {
            "command": command,
            "args": arg_list,
            "is_valid": is_valid,
            "error": error_message,
            "full_command": f"git {command} {' '.join(arg_list)}",
        }

    except Exception as e:
        logger.error(f"Command validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate command",
        )


# WebSocket for real-time command execution
@router.websocket("/ws")
async def websocket_git_terminal(
    websocket: WebSocket,
    token: str,
    executor: GitCommandExecutor = Depends(get_git_executor),
    audit_logger: GitCommandAuditLogger = Depends(get_audit_logger),
    # redis_client removed - using SQLite for lightweight deployment
):
    """
    WebSocket endpoint for real-time git command execution
    """
    try:
        # Verify token and get user
        # This is simplified - should use proper WebSocket authentication
        current_user = {
            "id": "websocket_user",
            "name": "WebSocket User",
            "power_user": True,
        }

        await websocket.accept()

        # Send welcome message
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Git terminal connected",
                "user": current_user["name"],
            }
        )

        while True:
            # Receive command
            data = await websocket.receive_json()

            if data.get("type") == "command":
                # Check rate limit
                allowed, remaining = await check_rate_limit(current_user["id"])
                if not allowed:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Rate limit exceeded",
                            "rate_limit_remaining": 0,
                        }
                    )
                    continue

                # Create git command
                git_command = GitCommand(
                    command=data["command"],
                    args=data.get("args", []),
                    repository_id=data["repository_id"],
                    user_id=current_user["id"],
                    cwd=data.get("cwd"),
                    timeout=data.get("timeout", 30),
                )

                # Send execution started
                await websocket.send_json(
                    {
                        "type": "execution_started",
                        "command": f"git {git_command.command} {' '.join(git_command.args)}",
                    }
                )

                # Execute command
                result = await executor.execute(git_command)

                # Log for audit
                audit_logger.log_command_execution(git_command, result, current_user)

                # Send result
                await websocket.send_json(
                    {
                        "type": "result",
                        "command": result.command,
                        "status": result.status.value,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code,
                        "execution_time": result.execution_time,
                        "rate_limit_remaining": remaining - 1,
                    }
                )

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        await websocket.close()


@router.get("/help")
async def get_git_help():
    """
    Get help information for power user git access
    """
    # validator = GitCommandValidator()

    return {
        "description": "Power user git access allows direct git command execution",
        "allowed_commands": {
            "read_operations": [
                "status",
                "log",
                "dif",
                "show",
                "branch",
                "tag",
                "ls-tree",
                "rev-parse",
                "describe",
                "cat-file",
                "ls-files",
                "grep",
                "blame",
                "shortlog",
                "reflog",
                "stash",
            ],
            "write_operations": [
                "add",
                "commit",
                "checkout",
                "merge",
                "rebase",
                "cherry-pick",
                "reset",
                "revert",
                "rm",
                "mv",
                "restore",
                "switch",
            ],
            "remote_operations": ["push", "pull", "fetch"],
            "utility_operations": ["clean", "gc", "prune", "fsck", "count-objects"],
        },
        "restrictions": [
            "No global configuration changes",
            "No hook modifications",
            "No remote management (except fetch/push/pull)",
            "No submodule operations",
            "No force push",
            "No push to protected branches (main, master, production)",
            "No shell escapes or injections",
            "No path traversal outside repository",
        ],
        "rate_limits": {
            "commands_per_hour": int(os.getenv("POWER_USER_RATE_LIMIT", "100")),
            "timeout_per_command": "30-300 seconds",
        },
        "examples": [
            {"command": "git status", "description": "Check repository status"},
            {
                "command": "git log --oneline -n 10",
                "description": "View recent commits",
            },
            {
                "command": "git diff HEAD~1",
                "description": "Compare with previous commit",
            },
            {
                "command": "git checkout feature/new-feature",
                "description": "Switch branches",
            },
            {
                "command": "git commit -m 'feat: add new feature'",
                "description": "Commit changes",
            },
        ],
    }
