import difflib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.merge.conflict_detection import (
    ConflictDetail,
    ConflictDetector,
    ConflictSeverity,
    ConflictType,
)
from diff_match_patch import diff_match_patch
from fuzzywuzzy import fuzz


class MergeStrategy(Enum):
    """Different merge strategies available"""

    AUTO = "auto"
    MANUAL = "manual"
    THEIRS = "theirs"
    OURS = "ours"
    UNION = "union"
    SMART = "smart"


class MergeResult(Enum):
    """Result of merge operation"""

    SUCCESS = "success"
    CONFLICTS = "conflicts"
    ERROR = "error"


@dataclass
class MergeOutput:
    """Result of merge operation"""

    result: MergeResult
    merged_content: str
    conflicts: List[ConflictDetail]
    statistics: Dict[str, Any]
    metadata: Dict[str, Any]


class ThreeWayMerger:
    """Implements three-way merge algorithms for document content"""

    def __init__(self):
        self.conflict_detector = ConflictDetector()
        self.dmp = diff_match_patch()

    def merge(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        strategy: MergeStrategy = MergeStrategy.AUTO,
        document_type: str = "markdown",
    ) -> MergeOutput:
        """
        Perform three-way merge

        Args:
            base_content: Common ancestor version
            local_content: Local changes
            remote_content: Remote changes
            strategy: Merge strategy to use
            document_type: Type of document being merged

        Returns:
            MergeOutput containing result and any conflicts
        """
        # Detect conflicts first
        conflicts = self.conflict_detector.detect_conflicts(
            base_content, local_content, remote_content, document_type
        )

        # Apply merge strategy
        if strategy == MergeStrategy.AUTO:
            return self._auto_merge(
                base_content, local_content, remote_content, conflicts
            )
        elif strategy == MergeStrategy.THEIRS:
            return self._theirs_merge(remote_content, conflicts)
        elif strategy == MergeStrategy.OURS:
            return self._ours_merge(local_content, conflicts)
        elif strategy == MergeStrategy.UNION:
            return self._union_merge(
                base_content, local_content, remote_content, conflicts
            )
        elif strategy == MergeStrategy.SMART:
            return self._smart_merge(
                base_content, local_content, remote_content, conflicts
            )
        else:
            return self._manual_merge(
                base_content, local_content, remote_content, conflicts
            )

    def _auto_merge(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        conflicts: List[ConflictDetail],
    ) -> MergeOutput:
        """Attempt automatic merge with conflict markers for unresolved conflicts"""

        # Filter auto-resolvable conflicts
        auto_resolvable = [c for c in conflicts if c.auto_resolvable]
        manual_conflicts = [c for c in conflicts if not c.auto_resolvable]

        # Start with base content
        merged_content = base_content

        # Apply non-conflicting changes
        merged_content = self._apply_non_conflicting_changes(
            merged_content, local_content, remote_content, conflicts
        )

        # Auto-resolve resolvable conflicts
        for conflict in auto_resolvable:
            merged_content = self._auto_resolve_conflict(merged_content, conflict)

        # Add conflict markers for manual conflicts
        for conflict in manual_conflicts:
            merged_content = self._add_conflict_markers(merged_content, conflict)

        # Determine result
        result = MergeResult.SUCCESS if not manual_conflicts else MergeResult.CONFLICTS

        return MergeOutput(
            result=result,
            merged_content=merged_content,
            conflicts=manual_conflicts,
            statistics=self._calculate_merge_statistics(
                base_content, local_content, remote_content
            ),
            metadata={
                "strategy": MergeStrategy.AUTO.value,
                "auto_resolved": len(auto_resolvable),
                "manual_conflicts": len(manual_conflicts),
            },
        )

    def _theirs_merge(
        self, remote_content: str, conflicts: List[ConflictDetail]
    ) -> MergeOutput:
        """Accept all remote changes"""
        return MergeOutput(
            result=MergeResult.SUCCESS,
            merged_content=remote_content,
            conflicts=[],
            statistics={"strategy": "theirs", "conflicts_resolved": len(conflicts)},
            metadata={"strategy": MergeStrategy.THEIRS.value},
        )

    def _ours_merge(
        self, local_content: str, conflicts: List[ConflictDetail]
    ) -> MergeOutput:
        """Accept all local changes"""
        return MergeOutput(
            result=MergeResult.SUCCESS,
            merged_content=local_content,
            conflicts=[],
            statistics={"strategy": "ours", "conflicts_resolved": len(conflicts)},
            metadata={"strategy": MergeStrategy.OURS.value},
        )

    def _union_merge(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        conflicts: List[ConflictDetail],
    ) -> MergeOutput:
        """Combine all changes (union of changes)"""

        # Use diff-match-patch for union merge
        base_lines = base_content.splitlines()
        local_lines = local_content.splitlines()
        remote_lines = remote_content.splitlines()

        # Create diffs
        local_diff = self.dmp.diff_main(base_content, local_content)
        remote_diff = self.dmp.diff_main(base_content, remote_content)

        # Merge diffs
        merged_content = self._merge_diffs(base_content, local_diff, remote_diff)

        return MergeOutput(
            result=MergeResult.SUCCESS,
            merged_content=merged_content,
            conflicts=[],
            statistics={"strategy": "union", "total_conflicts": len(conflicts)},
            metadata={"strategy": MergeStrategy.UNION.value},
        )

    def _smart_merge(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        conflicts: List[ConflictDetail],
    ) -> MergeOutput:
        """Intelligent merge using content analysis"""

        # Start with auto merge
        auto_result = self._auto_merge(
            base_content, local_content, remote_content, conflicts
        )

        # Apply smart resolution to remaining conflicts
        remaining_conflicts = []
        merged_content = auto_result.merged_content

        for conflict in auto_result.conflicts:
            smart_resolution = self._smart_resolve_conflict(conflict)
            if smart_resolution:
                merged_content = self._apply_smart_resolution(
                    merged_content, conflict, smart_resolution
                )
            else:
                remaining_conflicts.append(conflict)

        result = (
            MergeResult.SUCCESS if not remaining_conflicts else MergeResult.CONFLICTS
        )

        return MergeOutput(
            result=result,
            merged_content=merged_content,
            conflicts=remaining_conflicts,
            statistics=auto_result.statistics,
            metadata={
                "strategy": MergeStrategy.SMART.value,
                "smart_resolved": len(auto_result.conflicts) - len(remaining_conflicts),
            },
        )

    def _manual_merge(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        conflicts: List[ConflictDetail],
    ) -> MergeOutput:
        """Manual merge - just add conflict markers"""

        merged_content = base_content

        # Add conflict markers for all conflicts
        for conflict in conflicts:
            merged_content = self._add_conflict_markers(merged_content, conflict)

        return MergeOutput(
            result=MergeResult.CONFLICTS,
            merged_content=merged_content,
            conflicts=conflicts,
            statistics={"strategy": "manual", "total_conflicts": len(conflicts)},
            metadata={"strategy": MergeStrategy.MANUAL.value},
        )

    def _apply_non_conflicting_changes(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        conflicts: List[ConflictDetail],
    ) -> str:
        """Apply changes that don't conflict"""

        # Get conflict ranges
        conflict_ranges = [(c.range.start_line, c.range.end_line) for c in conflicts]

        # Create line-by-line merge
        base_lines = base_content.splitlines()
        local_lines = local_content.splitlines()
        remote_lines = remote_content.splitlines()

        # Use longest common subsequence to find non-conflicting changes
        merged_lines = []

        # Simple approach: use unified diff to find changes
        local_diff = list(difflib.unified_diff(base_lines, local_lines, n=0))
        remote_diff = list(difflib.unified_diff(base_lines, remote_lines, n=0))

        # Apply non-conflicting changes
        # This is a simplified implementation - could be more sophisticated
        merged_lines = base_lines.copy()

        return "\n".join(merged_lines)

    def _auto_resolve_conflict(self, content: str, conflict: ConflictDetail) -> str:
        """Auto-resolve a conflict based on its type and characteristics"""

        if conflict.type == ConflictType.METADATA_CONFLICT:
            # For metadata, prefer non-empty values
            if conflict.local_content and not conflict.remote_content:
                resolution = conflict.local_content
            elif conflict.remote_content and not conflict.local_content:
                resolution = conflict.remote_content
            else:
                # Use more recent timestamp if available
                resolution = conflict.remote_content  # Default to remote

        elif conflict.type == ConflictType.CONTENT_CONFLICT:
            # For content, check if it's just whitespace differences
            local_normalized = re.sub(r"\s+", " ", conflict.local_content.strip())
            remote_normalized = re.sub(r"\s+", " ", conflict.remote_content.strip())

            if local_normalized == remote_normalized:
                # Use the version with better formatting
                resolution = (
                    conflict.local_content
                    if len(conflict.local_content) > len(conflict.remote_content)
                    else conflict.remote_content
                )
            else:
                resolution = conflict.local_content  # Default to local

        else:
            resolution = conflict.local_content  # Default resolution

        # Replace conflict in content
        lines = content.splitlines()
        start_idx = max(0, conflict.range.start_line - 1)
        end_idx = min(len(lines), conflict.range.end_line)

        # Replace the conflicting lines
        lines[start_idx:end_idx] = resolution.splitlines()

        return "\n".join(lines)

    def _add_conflict_markers(self, content: str, conflict: ConflictDetail) -> str:
        """Add conflict markers to content"""

        lines = content.splitlines()
        start_idx = max(0, conflict.range.start_line - 1)
        end_idx = min(len(lines), conflict.range.end_line)

        # Create conflict markers
        conflict_markers = [
            f"<<<<<<< LOCAL ({conflict.id})",
            conflict.local_content,
            "=======",
            conflict.remote_content,
            f">>>>>>> REMOTE ({conflict.id})",
        ]

        # Replace the conflicting lines with markers
        lines[start_idx:end_idx] = conflict_markers

        return "\n".join(lines)

    def _smart_resolve_conflict(self, conflict: ConflictDetail) -> Optional[str]:
        """Apply smart resolution heuristics"""

        # Check for simple cases
        if conflict.severity == ConflictSeverity.LOW:
            # For low severity, use fuzzy matching
            similarity = fuzz.ratio(conflict.local_content, conflict.remote_content)
            if similarity > 80:
                # Choose the longer version (more content)
                return (
                    conflict.local_content
                    if len(conflict.local_content) > len(conflict.remote_content)
                    else conflict.remote_content
                )

        # Check for additive changes
        if conflict.type == ConflictType.CONTENT_CONFLICT:
            # If one side is clearly an addition to the other
            if (
                conflict.base_content in conflict.local_content
                and conflict.base_content in conflict.remote_content
            ):
                # Both sides added content - try to combine
                local_addition = conflict.local_content.replace(
                    conflict.base_content, ""
                )
                remote_addition = conflict.remote_content.replace(
                    conflict.base_content, ""
                )

                if local_addition and remote_addition:
                    # Combine additions
                    return conflict.base_content + local_addition + remote_addition

        return None

    def _apply_smart_resolution(
        self, content: str, conflict: ConflictDetail, resolution: str
    ) -> str:
        """Apply smart resolution to content"""
        lines = content.splitlines()
        start_idx = max(0, conflict.range.start_line - 1)
        end_idx = min(len(lines), conflict.range.end_line)

        # Replace the conflicting lines
        lines[start_idx:end_idx] = resolution.splitlines()

        return "\n".join(lines)

    def _merge_diffs(
        self, base_content: str, local_diff: List, remote_diff: List
    ) -> str:
        """Merge two diff lists"""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated diff merging

        result = base_content

        # Apply local changes
        self.dmp.diff_cleanupSemantic(local_diff)
        patches = self.dmp.patch_make(base_content, local_diff)
        result = self.dmp.patch_apply(patches, result)[0]

        # Apply remote changes
        self.dmp.diff_cleanupSemantic(remote_diff)
        patches = self.dmp.patch_make(base_content, remote_diff)
        result = self.dmp.patch_apply(patches, result)[0]

        return result

    def _calculate_merge_statistics(
        self, base_content: str, local_content: str, remote_content: str
    ) -> Dict[str, Any]:
        """Calculate merge statistics"""
        return {
            "base_lines": len(base_content.splitlines()),
            "local_lines": len(local_content.splitlines()),
            "remote_lines": len(remote_content.splitlines()),
            "base_chars": len(base_content),
            "local_chars": len(local_content),
            "remote_chars": len(remote_content),
            "local_similarity": difflib.SequenceMatcher(
                None, base_content, local_content
            ).ratio(),
            "remote_similarity": difflib.SequenceMatcher(
                None, base_content, remote_content
            ).ratio(),
            "local_remote_similarity": difflib.SequenceMatcher(
                None, local_content, remote_content
            ).ratio(),
        }


class ConflictResolver:
    """Handles conflict resolution operations"""

    def __init__(self):
        self.merger = ThreeWayMerger()

    def resolve_conflict(
        self, conflict: ConflictDetail, resolution: str, content: str
    ) -> str:
        """
        Resolve a specific conflict with provided resolution

        Args:
            conflict: The conflict to resolve
            resolution: The resolution content
            content: The current content with conflict markers

        Returns:
            Content with conflict resolved
        """
        lines = content.splitlines()

        # Find conflict markers
        start_marker = f"<<<<<<< LOCAL ({conflict.id})"
        end_marker = f">>>>>>> REMOTE ({conflict.id})"

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if start_marker in line:
                start_idx = i
            elif end_marker in line:
                end_idx = i
                break

        if start_idx is not None and end_idx is not None:
            # Replace conflict markers with resolution
            lines[start_idx : end_idx + 1] = resolution.splitlines()

        return "\n".join(lines)

    def accept_local(self, conflict: ConflictDetail, content: str) -> str:
        """Accept local version of conflict"""
        return self.resolve_conflict(conflict, conflict.local_content, content)

    def accept_remote(self, conflict: ConflictDetail, content: str) -> str:
        """Accept remote version of conflict"""
        return self.resolve_conflict(conflict, conflict.remote_content, content)

    def accept_both(self, conflict: ConflictDetail, content: str) -> str:
        """Accept both versions (union)"""
        combined = conflict.local_content + "\n" + conflict.remote_content
        return self.resolve_conflict(conflict, combined, content)

    def get_conflict_preview(self, conflict: ConflictDetail) -> Dict[str, Any]:
        """Get preview of conflict for UI"""
        return {
            "id": conflict.id,
            "type": conflict.type.value,
            "severity": conflict.severity.value,
            "description": conflict.description,
            "local_content": conflict.local_content,
            "remote_content": conflict.remote_content,
            "base_content": conflict.base_content,
            "context_lines": conflict.context_lines,
            "auto_resolvable": conflict.auto_resolvable,
            "suggested_resolution": conflict.suggested_resolution,
        }
