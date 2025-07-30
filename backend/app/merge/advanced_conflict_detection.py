import difflib
import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import jellyfish
from app.merge.conflict_detection import (
    ConflictDetail,
    ConflictRange,
    ConflictSeverity,
    ConflictType,
)


class ChangeType(Enum):
    """Types of changes that can occur"""

    INSERTION = "insertion"
    DELETION = "deletion"
    MODIFICATION = "modification"
    MOVE = "move"


@dataclass
class Change:
    """Represents a single change in content"""

    type: ChangeType
    start_line: int
    end_line: int
    content: str
    original_content: str = ""
    context_before: List[str] = None
    context_after: List[str] = None

    def __post_init__(self):
        if self.context_before is None:
            self.context_before = []
        if self.context_after is None:
            self.context_after = []


@dataclass
class ConflictPattern:
    """Represents a pattern of conflicting changes"""

    pattern_type: str
    confidence: float
    description: str
    suggested_resolution: str


class AdvancedConflictDetector:
    """Advanced conflict detection with semantic analysis"""

    def __init__(self):
        self.context_window = 5
        self.similarity_threshold = 0.8
        self.move_detection_threshold = 0.9

    def detect_semantic_conflicts(
        self, base_content: str, local_content: str, remote_content: str
    ) -> List[ConflictDetail]:
        """
        Detect conflicts using semantic analysis beyond line-level differences
        """
        conflicts = []

        # Extract changes
        local_changes = self._extract_changes(base_content, local_content)
        remote_changes = self._extract_changes(base_content, remote_content)

        # Detect different types of conflicts
        conflicts.extend(
            self._detect_overlapping_changes(local_changes, remote_changes)
        )
        conflicts.extend(self._detect_move_conflicts(local_changes, remote_changes))
        conflicts.extend(self._detect_semantic_conflicts(local_changes, remote_changes))
        conflicts.extend(
            self._detect_dependency_conflicts(local_changes, remote_changes)
        )

        # Analyze conflict patterns
        patterns = self._analyze_conflict_patterns(conflicts)
        for conflict in conflicts:
            pattern = self._match_conflict_pattern(conflict, patterns)
            if pattern:
                conflict.suggested_resolution = pattern.suggested_resolution

        return conflicts

    def _extract_changes(
        self, base_content: str, modified_content: str
    ) -> List[Change]:
        """Extract individual changes from content dif"""
        changes = []

        base_lines = base_content.splitlines()
        modified_lines = modified_content.splitlines()

        # Use difflib to get detailed diff
        diff = difflib.unified_diff(
            base_lines, modified_lines, n=self.context_window, lineterm=""
        )

        current_change = None
        line_num = 0

        for line in diff:
            if line.startswith("@@"):
                # Parse range information
                range_match = re.match(
                    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
                )
                if range_match:
                    old_start = int(range_match.group(1))
                    old_count = int(range_match.group(2)) if range_match.group(2) else 1
                    new_start = int(range_match.group(3))
                    new_count = int(range_match.group(4)) if range_match.group(4) else 1

                    if current_change:
                        changes.append(current_change)

                    # Determine change type
                    if old_count == 0:
                        change_type = ChangeType.INSERTION
                    elif new_count == 0:
                        change_type = ChangeType.DELETION
                    else:
                        change_type = ChangeType.MODIFICATION

                    current_change = Change(
                        type=change_type,
                        start_line=old_start,
                        end_line=old_start + old_count,
                        content="",
                        original_content="",
                    )
                    line_num = old_start

            elif current_change:
                if line.startswith("-"):
                    current_change.original_content += line[1:] + "\n"
                elif line.startswith("+"):
                    current_change.content += line[1:] + "\n"
                elif line.startswith(" "):
                    # Context line
                    if (
                        not current_change.content
                        and not current_change.original_content
                    ):
                        current_change.context_before.append(line[1:])
                    else:
                        current_change.context_after.append(line[1:])

        if current_change:
            changes.append(current_change)

        return changes

    def _detect_overlapping_changes(
        self, local_changes: List[Change], remote_changes: List[Change]
    ) -> List[ConflictDetail]:
        """Detect conflicts where changes overlap in the same lines"""
        conflicts = []

        for local_change in local_changes:
            for remote_change in remote_changes:
                # Check if changes overlap
                if self._changes_overlap(local_change, remote_change):
                    conflict = self._create_overlap_conflict(
                        local_change, remote_change
                    )
                    conflicts.append(conflict)

        return conflicts

    def _detect_move_conflicts(
        self, local_changes: List[Change], remote_changes: List[Change]
    ) -> List[ConflictDetail]:
        """Detect conflicts where content has been moved to different locations"""
        conflicts = []

        # Find potential moves
        local_moves = self._detect_moves(local_changes)
        remote_moves = self._detect_moves(remote_changes)

        # Check for conflicting moves
        for local_move in local_moves:
            for remote_move in remote_moves:
                if self._moves_conflict(local_move, remote_move):
                    conflict = self._create_move_conflict(local_move, remote_move)
                    conflicts.append(conflict)

        return conflicts

    def _detect_semantic_conflicts(
        self, local_changes: List[Change], remote_changes: List[Change]
    ) -> List[ConflictDetail]:
        """Detect semantic conflicts based on content analysis"""
        conflicts = []

        # Group changes by semantic regions
        local_semantic_groups = self._group_changes_semantically(local_changes)
        remote_semantic_groups = self._group_changes_semantically(remote_changes)

        # Check for conflicts in semantic groups
        for local_group in local_semantic_groups:
            for remote_group in remote_semantic_groups:
                if self._semantic_groups_conflict(local_group, remote_group):
                    conflict = self._create_semantic_conflict(local_group, remote_group)
                    conflicts.append(conflict)

        return conflicts

    def _detect_dependency_conflicts(
        self, local_changes: List[Change], remote_changes: List[Change]
    ) -> List[ConflictDetail]:
        """Detect conflicts where changes have dependencies on each other"""
        conflicts = []

        # Analyze dependencies
        local_deps = self._analyze_dependencies(local_changes)
        remote_deps = self._analyze_dependencies(remote_changes)

        # Check for dependency conflicts
        for local_dep in local_deps:
            for remote_dep in remote_deps:
                if self._dependencies_conflict(local_dep, remote_dep):
                    conflict = self._create_dependency_conflict(local_dep, remote_dep)
                    conflicts.append(conflict)

        return conflicts

    def _changes_overlap(self, change1: Change, change2: Change) -> bool:
        """Check if two changes overlap in line ranges"""
        return not (
            change1.end_line <= change2.start_line
            or change2.end_line <= change1.start_line
        )

    def _create_overlap_conflict(
        self, local_change: Change, remote_change: Change
    ) -> ConflictDetail:
        """Create conflict detail for overlapping changes"""

        # Determine conflict severity based on change types and content similarity
        severity = self._calculate_overlap_severity(local_change, remote_change)

        # Calculate auto-resolvability
        auto_resolvable = self._is_overlap_auto_resolvable(local_change, remote_change)

        return ConflictDetail(
            id=self._generate_conflict_id(
                f"overlap_{local_change.start_line}_{remote_change.start_line}"
            ),
            type=ConflictType.CONTENT_CONFLICT,
            severity=severity,
            range=ConflictRange(
                min(local_change.start_line, remote_change.start_line),
                max(local_change.end_line, remote_change.end_line),
                0,
                0,
            ),
            base_content=local_change.original_content
            or remote_change.original_content,
            local_content=local_change.content,
            remote_content=remote_change.content,
            description=f"Overlapping {local_change.type.value} and {remote_change.type.value}",
            auto_resolvable=auto_resolvable,
            context_lines=local_change.context_before + local_change.context_after,
        )

    def _detect_moves(self, changes: List[Change]) -> List[Dict]:
        """Detect move operations in changes"""
        moves = []

        deletions = [c for c in changes if c.type == ChangeType.DELETION]
        insertions = [c for c in changes if c.type == ChangeType.INSERTION]

        # Match deletions with insertions that have similar content
        for deletion in deletions:
            for insertion in insertions:
                similarity = self._calculate_content_similarity(
                    deletion.original_content, insertion.content
                )

                if similarity > self.move_detection_threshold:
                    moves.append(
                        {
                            "deletion": deletion,
                            "insertion": insertion,
                            "similarity": similarity,
                        }
                    )

        return moves

    def _moves_conflict(self, local_move: Dict, remote_move: Dict) -> bool:
        """Check if two move operations conflict"""
        # Moves conflict if they involve the same original content
        local_orig = local_move["deletion"].original_content
        remote_orig = remote_move["deletion"].original_content

        return (
            self._calculate_content_similarity(local_orig, remote_orig)
            > self.similarity_threshold
        )

    def _create_move_conflict(
        self, local_move: Dict, remote_move: Dict
    ) -> ConflictDetail:
        """Create conflict detail for move conflicts"""
        return ConflictDetail(
            id=self._generate_conflict_id(f"move_{local_move['deletion'].start_line}"),
            type=ConflictType.STRUCTURAL_CONFLICT,
            severity=ConflictSeverity.MEDIUM,
            range=ConflictRange(
                local_move["deletion"].start_line, local_move["deletion"].end_line, 0, 0
            ),
            base_content=local_move["deletion"].original_content,
            local_content=f"Moved to line {local_move['insertion'].start_line}",
            remote_content=f"Moved to line {remote_move['insertion'].start_line}",
            description="Content moved to different locations",
            auto_resolvable=False,
        )

    def _group_changes_semantically(self, changes: List[Change]) -> List[List[Change]]:
        """Group changes by semantic regions (e.g., functions, paragraphs)"""
        groups = []
        current_group = []

        for change in changes:
            # Simple grouping based on proximity and content type
            if current_group and self._are_semantically_related(
                current_group[-1], change
            ):
                current_group.append(change)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [change]

        if current_group:
            groups.append(current_group)

        return groups

    def _are_semantically_related(self, change1: Change, change2: Change) -> bool:
        """Check if two changes are semantically related"""
        # Changes are related if they're close in line numbers
        line_distance = abs(change1.end_line - change2.start_line)

        # Or if they affect similar content types
        content_similarity = self._calculate_content_similarity(
            change1.content, change2.content
        )

        return line_distance <= 5 or content_similarity > 0.5

    def _semantic_groups_conflict(
        self, group1: List[Change], group2: List[Change]
    ) -> bool:
        """Check if two semantic groups conflict"""
        # Groups conflict if they overlap in line ranges
        group1_start = min(c.start_line for c in group1)
        group1_end = max(c.end_line for c in group1)
        group2_start = min(c.start_line for c in group2)
        group2_end = max(c.end_line for c in group2)

        return not (group1_end <= group2_start or group2_end <= group1_start)

    def _create_semantic_conflict(
        self, group1: List[Change], group2: List[Change]
    ) -> ConflictDetail:
        """Create conflict detail for semantic conflicts"""
        group1_content = "\n".join(c.content for c in group1)
        group2_content = "\n".join(c.content for c in group2)

        return ConflictDetail(
            id=self._generate_conflict_id(f"semantic_{group1[0].start_line}"),
            type=ConflictType.STRUCTURAL_CONFLICT,
            severity=ConflictSeverity.HIGH,
            range=ConflictRange(
                min(c.start_line for c in group1), max(c.end_line for c in group1), 0, 0
            ),
            base_content="",
            local_content=group1_content,
            remote_content=group2_content,
            description="Semantic conflict in related changes",
            auto_resolvable=False,
        )

    def _analyze_dependencies(self, changes: List[Change]) -> List[Dict]:
        """Analyze dependencies between changes"""
        dependencies = []

        for i, change in enumerate(changes):
            deps = []

            # Look for references to other changes
            for j, other_change in enumerate(changes):
                if i != j and self._changes_are_dependent(change, other_change):
                    deps.append(j)

            if deps:
                dependencies.append({"change": change, "dependencies": deps})

        return dependencies

    def _changes_are_dependent(self, change1: Change, change2: Change) -> bool:
        """Check if one change depends on another"""
        # Simple heuristic: check if content of one change references the other
        return change1.content in change2.content or change2.content in change1.content

    def _dependencies_conflict(self, dep1: Dict, dep2: Dict) -> bool:
        """Check if two dependency structures conflict"""
        # Dependencies conflict if they create circular dependencies
        # Check if change1 depends on something that depends on change1 (circular)
        change1_line = dep1["change"].start_line
        change2_line = dep2["change"].start_line

        # If dep1 depends on dep2 and dep2 depends on dep1, it's circular
        # Since we store indices, we need to check if the changes reference each other
        return any(
            dep2["change"].start_line == dep1["change"].start_line
            for _ in dep1["dependencies"]
        ) and any(
            dep1["change"].start_line == dep2["change"].start_line
            for _ in dep2["dependencies"]
        )

    def _create_dependency_conflict(self, dep1: Dict, dep2: Dict) -> ConflictDetail:
        """Create conflict detail for dependency conflicts"""
        return ConflictDetail(
            id=self._generate_conflict_id(f"dependency_{dep1['change'].start_line}"),
            type=ConflictType.STRUCTURAL_CONFLICT,
            severity=ConflictSeverity.HIGH,
            range=ConflictRange(
                dep1["change"].start_line, dep1["change"].end_line, 0, 0
            ),
            base_content="",
            local_content=dep1["change"].content,
            remote_content=dep2["change"].content,
            description="Dependency conflict between changes",
            auto_resolvable=False,
        )

    def _calculate_overlap_severity(
        self, local_change: Change, remote_change: Change
    ) -> ConflictSeverity:
        """Calculate severity of overlap conflict"""
        # Base severity on change types
        type_severity = {
            (ChangeType.INSERTION, ChangeType.INSERTION): ConflictSeverity.MEDIUM,
            (ChangeType.DELETION, ChangeType.DELETION): ConflictSeverity.HIGH,
            (ChangeType.MODIFICATION, ChangeType.MODIFICATION): ConflictSeverity.HIGH,
            (ChangeType.INSERTION, ChangeType.DELETION): ConflictSeverity.CRITICAL,
            (ChangeType.DELETION, ChangeType.INSERTION): ConflictSeverity.CRITICAL,
        }

        key = (local_change.type, remote_change.type)
        base_severity = type_severity.get(key, ConflictSeverity.MEDIUM)

        # Adjust based on content similarity
        similarity = self._calculate_content_similarity(
            local_change.content, remote_change.content
        )

        if similarity > 0.8:
            return ConflictSeverity.LOW
        elif similarity > 0.5:
            return ConflictSeverity.MEDIUM
        else:
            return base_severity

    def _is_overlap_auto_resolvable(
        self, local_change: Change, remote_change: Change
    ) -> bool:
        """Check if overlap conflict can be auto-resolved"""
        # Auto-resolvable if changes are identical
        if local_change.content == remote_change.content:
            return True

        # Auto-resolvable if one is clearly an addition to the other
        if (
            local_change.type == ChangeType.INSERTION
            and remote_change.type == ChangeType.INSERTION
        ):
            # Check if one contains the other
            return (
                local_change.content in remote_change.content
                or remote_change.content in local_change.content
            )

        return False

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings"""
        if not content1 or not content2:
            return 0.0

        # Use multiple similarity metrics
        sequence_similarity = difflib.SequenceMatcher(None, content1, content2).ratio()

        # Jaro-Winkler similarity for better handling of small changes
        jaro_similarity = jellyfish.jaro_winkler_similarity(content1, content2)

        # Weighted average
        return (sequence_similarity * 0.6) + (jaro_similarity * 0.4)

    def _analyze_conflict_patterns(
        self, conflicts: List[ConflictDetail]
    ) -> List[ConflictPattern]:
        """Analyze patterns in conflicts to suggest resolutions"""
        patterns = []

        # Pattern 1: Multiple similar conflicts
        similar_conflicts = self._find_similar_conflicts(conflicts)
        if similar_conflicts:
            patterns.append(
                ConflictPattern(
                    pattern_type="similar_conflicts",
                    confidence=0.8,
                    description="Multiple similar conflicts detected",
                    suggested_resolution="Consider applying the same resolution to all similar conflicts",
                )
            )

        # Pattern 2: Cascading conflicts
        cascading = self._find_cascading_conflicts(conflicts)
        if cascading:
            patterns.append(
                ConflictPattern(
                    pattern_type="cascading",
                    confidence=0.7,
                    description="Cascading conflicts detected",
                    suggested_resolution="Resolve conflicts in dependency order",
                )
            )

        return patterns

    def _find_similar_conflicts(
        self, conflicts: List[ConflictDetail]
    ) -> List[List[ConflictDetail]]:
        """Find groups of similar conflicts"""
        similar_groups = []
        processed = set()

        for i, conflict in enumerate(conflicts):
            if i in processed:
                continue

            similar_group = [conflict]
            processed.add(i)

            for j, other_conflict in enumerate(conflicts[i + 1 :], i + 1):
                if j in processed:
                    continue

                if self._conflicts_are_similar(conflict, other_conflict):
                    similar_group.append(other_conflict)
                    processed.add(j)

            if len(similar_group) > 1:
                similar_groups.append(similar_group)

        return similar_groups

    def _conflicts_are_similar(
        self, conflict1: ConflictDetail, conflict2: ConflictDetail
    ) -> bool:
        """Check if two conflicts are similar"""
        # Similar if same type and high content similarity
        if conflict1.type != conflict2.type:
            return False

        local_similarity = self._calculate_content_similarity(
            conflict1.local_content, conflict2.local_content
        )
        remote_similarity = self._calculate_content_similarity(
            conflict1.remote_content, conflict2.remote_content
        )

        return local_similarity > 0.7 and remote_similarity > 0.7

    def _find_cascading_conflicts(
        self, conflicts: List[ConflictDetail]
    ) -> List[List[ConflictDetail]]:
        """Find cascading conflicts that depend on each other"""
        # Sort conflicts by line number
        sorted_conflicts = sorted(conflicts, key=lambda c: c.range.start_line)

        cascading_groups = []
        current_group = []

        for conflict in sorted_conflicts:
            if current_group and self._conflicts_are_cascading(
                current_group[-1], conflict
            ):
                current_group.append(conflict)
            else:
                if len(current_group) > 1:
                    cascading_groups.append(current_group)
                current_group = [conflict]

        if len(current_group) > 1:
            cascading_groups.append(current_group)

        return cascading_groups

    def _conflicts_are_cascading(
        self, conflict1: ConflictDetail, conflict2: ConflictDetail
    ) -> bool:
        """Check if conflicts are cascading (one affects the other)"""
        # Cascading if they're close in line numbers and content references each other
        line_distance = conflict2.range.start_line - conflict1.range.end_line

        if line_distance > 10:  # Too far apart
            return False

        # Check if content references each other
        return (
            conflict1.local_content in conflict2.local_content
            or conflict1.remote_content in conflict2.remote_content
        )

    def _match_conflict_pattern(
        self, conflict: ConflictDetail, patterns: List[ConflictPattern]
    ) -> Optional[ConflictPattern]:
        """Match a conflict to a pattern"""
        for pattern in patterns:
            if pattern.confidence > 0.6:  # Threshold for pattern matching
                return pattern
        return None

    def _generate_conflict_id(self, base: str) -> str:
        """Generate unique conflict ID"""
        return hashlib.md5(base.encode()).hexdigest()[:8]
