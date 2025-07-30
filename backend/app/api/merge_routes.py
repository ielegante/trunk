from typing import List

from app.api.auth_routes import get_current_user_id
from app.merge.advanced_conflict_detection import AdvancedConflictDetector
from app.merge.conflict_detection import ConflictDetector
from app.merge.merge_algorithms import ConflictResolver, MergeStrategy, ThreeWayMerger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/merge", tags=["merge operations"])

conflict_detector = ConflictDetector()
advanced_detector = AdvancedConflictDetector()
merger = ThreeWayMerger()
resolver = ConflictResolver()


class ConflictDetectionRequest(BaseModel):
    base_content: str
    local_content: str
    remote_content: str
    document_type: str = "markdown"
    advanced_detection: bool = False


class MergeRequest(BaseModel):
    base_content: str
    local_content: str
    remote_content: str
    strategy: str = "auto"
    document_type: str = "markdown"


class ConflictResolutionRequest(BaseModel):
    conflict_id: str
    resolution: str
    content: str


class BatchConflictResolutionRequest(BaseModel):
    resolutions: List[dict]
    content: str


@router.post("/detect-conflicts")
async def detect_conflicts(
    request: ConflictDetectionRequest, user_id: str = Depends(get_current_user_id)
):
    """Detect conflicts between three versions of content"""
    try:
        if request.advanced_detection:
            conflicts = advanced_detector.detect_semantic_conflicts(
                request.base_content, request.local_content, request.remote_content
            )
        else:
            conflicts = conflict_detector.detect_conflicts(
                request.base_content,
                request.local_content,
                request.remote_content,
                request.document_type,
            )

        # Convert conflicts to JSON-serializable format
        conflicts_data = [conflict.to_dict() for conflict in conflicts]

        return {
            "success": True,
            "conflicts": conflicts_data,
            "conflict_count": len(conflicts),
            "has_conflicts": len(conflicts) > 0,
            "detection_type": "advanced" if request.advanced_detection else "standard",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conflict detection failed: {str(e)}"
        )


@router.post("/merge")
async def merge_content(
    request: MergeRequest, user_id: str = Depends(get_current_user_id)
):
    """Perform three-way merge of content"""
    try:
        # Convert strategy string to enum
        strategy_map = {
            "auto": MergeStrategy.AUTO,
            "manual": MergeStrategy.MANUAL,
            "theirs": MergeStrategy.THEIRS,
            "ours": MergeStrategy.OURS,
            "union": MergeStrategy.UNION,
            "smart": MergeStrategy.SMART,
        }

        strategy = strategy_map.get(request.strategy.lower(), MergeStrategy.AUTO)

        # Perform merge
        merge_result = merger.merge(
            request.base_content,
            request.local_content,
            request.remote_content,
            strategy,
            request.document_type,
        )

        # Convert conflicts to JSON-serializable format
        conflicts_data = [conflict.to_dict() for conflict in merge_result.conflicts]

        return {
            "success": True,
            "result": merge_result.result.value,
            "merged_content": merge_result.merged_content,
            "conflicts": conflicts_data,
            "statistics": merge_result.statistics,
            "metadata": merge_result.metadata,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@router.post("/resolve-conflict")
async def resolve_conflict(
    request: ConflictResolutionRequest, user_id: str = Depends(get_current_user_id)
):
    """Resolve a specific conflict"""
    try:
        # This is a simplified implementation
        # In practice, you'd need to reconstruct the ConflictDetail from stored data

        # For now, perform simple text replacement
        # resolved_content = (
        #     request.content.replace(f"<<<<<<< LOCAL ({request.conflict_id})", "")
        #     .replace(f">>>>>>> REMOTE ({request.conflict_id})", "")
        #     .replace("=======", "")
        # )  # TODO: Use for actual resolution logic

        # Insert resolution
        # lines = resolved_content.splitlines()  # TODO: Use for more sophisticated resolution
        # This is a simplified approach - would need more sophisticated logic

        return {
            "success": True,
            "resolved_content": request.resolution,
            "message": f"Conflict {request.conflict_id} resolved",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conflict resolution failed: {str(e)}"
        )


@router.post("/batch-resolve")
async def batch_resolve_conflicts(
    request: BatchConflictResolutionRequest, user_id: str = Depends(get_current_user_id)
):
    """Resolve multiple conflicts in batch"""
    try:
        resolved_content = request.content
        resolved_count = 0

        # Apply each resolution
        for resolution in request.resolutions:
            conflict_id = resolution.get("conflict_id")
            resolution_content = resolution.get("resolution")

            if conflict_id and resolution_content:
                # Apply resolution (simplified)
                resolved_content = (
                    resolved_content.replace(
                        f"<<<<<<< LOCAL ({conflict_id})", resolution_content
                    )
                    .replace(f">>>>>>> REMOTE ({conflict_id})", "")
                    .replace("=======", "")
                )
                resolved_count += 1

        return {
            "success": True,
            "resolved_content": resolved_content,
            "resolved_count": resolved_count,
            "message": f"Resolved {resolved_count} conflicts",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Batch resolution failed: {str(e)}"
        )


@router.get("/conflict-preview/{conflict_id}")
async def get_conflict_preview(
    conflict_id: str, user_id: str = Depends(get_current_user_id)
):
    """Get detailed preview of a conflict for UI"""
    try:
        # This would typically fetch from storage
        # For now, return a mock response

        return {
            "success": True,
            "conflict_id": conflict_id,
            "preview": {
                "type": "content_conflict",
                "severity": "medium",
                "description": "Content conflict in document",
                "local_content": "Local version of content",
                "remote_content": "Remote version of content",
                "base_content": "Base version of content",
                "context_lines": ["Context line 1", "Context line 2"],
                "suggested_resolution": "Suggested resolution content",
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/analyze-merge-feasibility")
async def analyze_merge_feasibility(
    request: ConflictDetectionRequest, user_id: str = Depends(get_current_user_id)
):
    """Analyze if merge is feasible and provide recommendations"""
    try:
        # Detect conflicts
        conflicts = conflict_detector.detect_conflicts(
            request.base_content,
            request.local_content,
            request.remote_content,
            request.document_type,
        )

        # Analyze merge feasibility
        total_conflicts = len(conflicts)
        auto_resolvable = sum(1 for c in conflicts if c.auto_resolvable)
        manual_conflicts = total_conflicts - auto_resolvable

        # Calculate complexity score
        complexity_score = 0
        for conflict in conflicts:
            if conflict.severity.value == "low":
                complexity_score += 1
            elif conflict.severity.value == "medium":
                complexity_score += 3
            elif conflict.severity.value == "high":
                complexity_score += 5
            elif conflict.severity.value == "critical":
                complexity_score += 10

        # Determine feasibility
        if total_conflicts == 0:
            feasibility = "easy"
            recommendation = "No conflicts detected. Merge can proceed automatically."
        elif auto_resolvable == total_conflicts:
            feasibility = "easy"
            recommendation = "All conflicts can be auto-resolved. Merge can proceed with minimal intervention."
        elif manual_conflicts <= 3 and complexity_score <= 15:
            feasibility = "moderate"
            recommendation = (
                "Some manual resolution required. Review conflicts carefully."
            )
        else:
            feasibility = "difficult"
            recommendation = "Complex conflicts detected. Consider breaking down changes or resolving conflicts manually."

        return {
            "success": True,
            "feasibility": feasibility,
            "recommendation": recommendation,
            "analysis": {
                "total_conflicts": total_conflicts,
                "auto_resolvable": auto_resolvable,
                "manual_conflicts": manual_conflicts,
                "complexity_score": complexity_score,
                "suggested_strategy": "smart" if manual_conflicts > 0 else "auto",
            },
            "conflicts": [conflict.to_dict() for conflict in conflicts],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Feasibility analysis failed: {str(e)}"
        )


@router.get("/merge-strategies")
async def get_merge_strategies(user_id: str = Depends(get_current_user_id)):
    """Get available merge strategies and their descriptions"""
    strategies = {
        "auto": {
            "name": "Automatic Merge",
            "description": "Automatically resolve conflicts where possible, mark others for manual resolution",
            "recommended_for": "Most common use case with moderate conflicts",
        },
        "manual": {
            "name": "Manual Merge",
            "description": "Mark all conflicts for manual resolution",
            "recommended_for": "Complex conflicts requiring human judgment",
        },
        "theirs": {
            "name": "Accept Remote Changes",
            "description": "Accept all remote changes, ignore local changes",
            "recommended_for": "When remote version is authoritative",
        },
        "ours": {
            "name": "Accept Local Changes",
            "description": "Accept all local changes, ignore remote changes",
            "recommended_for": "When local version is authoritative",
        },
        "union": {
            "name": "Union Merge",
            "description": "Combine all changes from both sides",
            "recommended_for": "Additive changes that don't conflict semantically",
        },
        "smart": {
            "name": "Smart Merge",
            "description": "Use intelligent heuristics to resolve conflicts",
            "recommended_for": "Complex scenarios with semantic analysis",
        },
    }

    return {"success": True, "strategies": strategies}
