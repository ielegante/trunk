"""Document workflow management system."""

from .merge_workflow import (
    BranchInfo,
    DocumentMergeWorkflow,
    MergeRequest,
    MergeResult,
    MergeStrategy,
)

__all__ = [
    "DocumentMergeWorkflow",
    "BranchInfo",
    "MergeRequest",
    "MergeStrategy",
    "MergeResult",
]
