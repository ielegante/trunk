"""Conflict resolution system for handling document merge conflicts."""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from .diff_visualizer import DocumentDiffVisualizer
from .google_docs import ConversionResult, DocumentElement

logger = logging.getLogger(__name__)


@dataclass
class ConflictRegion:
    """Represents a conflict region in a document."""

    conflict_id: str
    start_line: int
    end_line: int
    base_content: str
    their_content: str
    our_content: str
    conflict_type: str  # 'content', 'formatting', 'structure'
    metadata: Dict[str, Any]
    resolution_status: str = "pending"  # pending, resolved, skipped
    resolution_content: Optional[str] = None
    resolution_timestamp: Optional[str] = None
    resolver: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "conflict_id": self.conflict_id,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "base_content": self.base_content,
            "their_content": self.their_content,
            "our_content": self.our_content,
            "conflict_type": self.conflict_type,
            "metadata": self.metadata,
            "resolution_status": self.resolution_status,
            "resolution_content": self.resolution_content,
            "resolution_timestamp": self.resolution_timestamp,
            "resolver": self.resolver,
        }


@dataclass
class ConflictResolution:
    """Represents a complete conflict resolution."""

    document_id: str
    conflicts: List[ConflictRegion]
    resolved_content: str
    resolution_strategy: str
    resolution_timestamp: str
    statistics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "document_id": self.document_id,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "resolved_content": self.resolved_content,
            "resolution_strategy": self.resolution_strategy,
            "resolution_timestamp": self.resolution_timestamp,
            "statistics": self.statistics,
        }


class ConflictResolver:
    """Resolves conflicts between document versions."""

    def __init__(self, diff_visualizer: Optional[DocumentDiffVisualizer] = None):
        """Initialize conflict resolver.

        Args:
            diff_visualizer: Optional DocumentDiffVisualizer for visualizing conflicts
        """
        self.diff_visualizer = diff_visualizer or DocumentDiffVisualizer()
        self.conflict_markers = {
            "start": "<<<<<<< ",
            "separator": "=======",
            "end": ">>>>>>> ",
        }
        self.resolution_strategies = {
            "manual": self._manual_resolution,
            "theirs": self._take_theirs_resolution,
            "ours": self._take_ours_resolution,
            "merge": self._merge_resolution,
            "interactive": self._interactive_resolution,
        }

    def detect_conflicts(
        self,
        base_content: str,
        their_content: str,
        our_content: str,
        base_label: str = "base",
        their_label: str = "theirs",
        our_label: str = "ours",
    ) -> List[ConflictRegion]:
        """Detect conflicts between three versions of content.

        Args:
            base_content: Base version content
            their_content: Their version content
            our_content: Our version content
            base_label: Label for base version
            their_label: Label for their version
            our_label: Label for our version

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Split content into lines
        base_lines = base_content.splitlines()
        their_lines = their_content.splitlines()
        our_lines = our_content.splitlines()

        # Perform three-way diff
        conflict_regions = self._find_conflicting_regions(
            base_lines, their_lines, our_lines
        )

        # Create ConflictRegion objects
        for i, (start_line, end_line, base_chunk, their_chunk, our_chunk) in enumerate(
            conflict_regions
        ):
            conflict_id = f"conflict_{i}_{int(time.time())}"

            # Determine conflict type
            conflict_type = self._determine_conflict_type(
                base_chunk, their_chunk, our_chunk
            )

            # Create metadata
            metadata = {
                "base_label": base_label,
                "their_label": their_label,
                "our_label": our_label,
                "base_lines": len(base_chunk),
                "their_lines": len(their_chunk),
                "our_lines": len(our_chunk),
                "detected_at": datetime.now().isoformat(),
            }

            conflict = ConflictRegion(
                conflict_id=conflict_id,
                start_line=start_line,
                end_line=end_line,
                base_content="\n".join(base_chunk),
                their_content="\n".join(their_chunk),
                our_content="\n".join(our_chunk),
                conflict_type=conflict_type,
                metadata=metadata,
            )

            conflicts.append(conflict)

        logger.info(f"Detected {len(conflicts)} conflicts")
        return conflicts

    def create_conflict_markers(
        self, conflicts: List[ConflictRegion], content: str
    ) -> str:
        """Create content with conflict markers for manual resolution.

        Args:
            conflicts: List of conflicts to mark
            content: Base content

        Returns:
            Content with conflict markers
        """
        lines = content.splitlines()
        result_lines = []

        # Sort conflicts by start line (reverse order for proper insertion)
        sorted_conflicts = sorted(conflicts, key=lambda c: c.start_line, reverse=True)

        for conflict in sorted_conflicts:
            # Insert conflict markers
            start_marker = f"{self.conflict_markers['start']}{conflict.metadata.get('our_label', 'ours')}"
            end_marker = f"{self.conflict_markers['end']}{conflict.metadata.get('their_label', 'theirs')}"

            # Replace the conflict region with marked content
            before_conflict = lines[: conflict.start_line]
            after_conflict = lines[conflict.end_line :]

            conflict_content = [
                start_marker,
                conflict.our_content,
                self.conflict_markers["separator"],
                conflict.their_content,
                end_marker,
            ]

            lines = before_conflict + conflict_content + after_conflict

        return "\n".join(lines)

    def parse_conflict_markers(self, content: str) -> List[ConflictRegion]:
        """Parse content with conflict markers into ConflictRegion objects.

        Args:
            content: Content with conflict markers

        Returns:
            List of parsed conflicts
        """
        conflicts = []
        lines = content.splitlines()

        i = 0
        conflict_count = 0

        while i < len(lines):
            line = lines[i]

            # Look for conflict start marker
            if line.startswith(self.conflict_markers["start"]):
                our_label = line[len(self.conflict_markers["start"]) :].strip()
                start_line = i

                # Find our content (until separator)
                our_content_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith(
                    self.conflict_markers["separator"]
                ):
                    our_content_lines.append(lines[i])
                    i += 1

                if i >= len(lines):
                    logger.warning("Incomplete conflict marker - missing separator")
                    break

                # Find their content (until end marker)
                their_content_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith(
                    self.conflict_markers["end"]
                ):
                    their_content_lines.append(lines[i])
                    i += 1

                if i >= len(lines):
                    logger.warning("Incomplete conflict marker - missing end marker")
                    break

                # Extract their label
                their_label = lines[i][len(self.conflict_markers["end"]) :].strip()
                end_line = i

                # Create conflict region
                conflict_id = f"parsed_conflict_{conflict_count}_{int(time.time())}"
                conflict = ConflictRegion(
                    conflict_id=conflict_id,
                    start_line=start_line,
                    end_line=end_line,
                    base_content="",  # Not available in parsed conflicts
                    their_content="\n".join(their_content_lines),
                    our_content="\n".join(our_content_lines),
                    conflict_type="content",
                    metadata={
                        "our_label": our_label,
                        "their_label": their_label,
                        "parsed_at": datetime.now().isoformat(),
                    },
                )

                conflicts.append(conflict)
                conflict_count += 1

            i += 1

        logger.info(f"Parsed {len(conflicts)} conflicts from markers")
        return conflicts

    def resolve_conflicts(
        self,
        conflicts: List[ConflictRegion],
        strategy: str = "manual",
        resolver_id: Optional[str] = None,
    ) -> ConflictResolution:
        """Resolve conflicts using specified strategy.

        Args:
            conflicts: List of conflicts to resolve
            strategy: Resolution strategy ('manual', 'theirs', 'ours', 'merge', 'interactive')
            resolver_id: Optional identifier of the resolver

        Returns:
            ConflictResolution with resolved content
        """
        if strategy not in self.resolution_strategies:
            raise ValueError(f"Unknown resolution strategy: {strategy}")

        resolver_func = self.resolution_strategies[strategy]

        # Track resolution statistics
        stats = {
            "total_conflicts": len(conflicts),
            "resolved_conflicts": 0,
            "skipped_conflicts": 0,
            "resolution_strategy": strategy,
            "start_time": datetime.now().isoformat(),
        }

        # Resolve each conflict
        resolved_conflicts = []
        for conflict in conflicts:
            try:
                resolved_conflict = resolver_func(conflict, resolver_id)
                resolved_conflicts.append(resolved_conflict)

                if resolved_conflict.resolution_status == "resolved":
                    stats["resolved_conflicts"] += 1
                else:
                    stats["skipped_conflicts"] += 1

            except Exception as e:
                logger.error(f"Failed to resolve conflict {conflict.conflict_id}: {e}")
                conflict.resolution_status = "failed"
                resolved_conflicts.append(conflict)

        # Build resolved content
        resolved_content = self._build_resolved_content(resolved_conflicts)

        stats["end_time"] = datetime.now().isoformat()
        stats["success_rate"] = (
            stats["resolved_conflicts"] / stats["total_conflicts"]
            if stats["total_conflicts"] > 0
            else 0.0
        )

        return ConflictResolution(
            document_id=f"resolved_{int(time.time())}",
            conflicts=resolved_conflicts,
            resolved_content=resolved_content,
            resolution_strategy=strategy,
            resolution_timestamp=datetime.now().isoformat(),
            statistics=stats,
        )

    def _find_conflicting_regions(
        self, base_lines: List[str], their_lines: List[str], our_lines: List[str]
    ) -> List[Tuple[int, int, List[str], List[str], List[str]]]:
        """Find conflicting regions between three versions.

        Args:
            base_lines: Base version lines
            their_lines: Their version lines
            our_lines: Our version lines

        Returns:
            List of tuples (start_line, end_line, base_chunk, their_chunk, our_chunk)
        """
        import difflib

        # Create sequence matchers
        base_their_matcher = difflib.SequenceMatcher(None, base_lines, their_lines)
        base_our_matcher = difflib.SequenceMatcher(None, base_lines, our_lines)

        conflicts = []

        # Find regions where both versions differ from base
        base_their_opcodes = base_their_matcher.get_opcodes()
        base_our_opcodes = base_our_matcher.get_opcodes()

        # Simple conflict detection - areas where both versions have changes
        for bt_op in base_their_opcodes:
            if bt_op[0] != "equal":  # Their version has changes
                bt_start, bt_end = bt_op[1], bt_op[2]

                # Check if our version also has changes in overlapping region
                for bo_op in base_our_opcodes:
                    if bo_op[0] != "equal":  # Our version has changes
                        bo_start, bo_end = bo_op[1], bo_op[2]

                        # Check for overlap
                        if not (bt_end <= bo_start or bo_end <= bt_start):
                            # Found conflict
                            conflict_start = min(bt_start, bo_start)
                            conflict_end = max(bt_end, bo_end)

                            base_chunk = base_lines[conflict_start:conflict_end]
                            their_chunk = their_lines[bt_op[3] : bt_op[4]]
                            our_chunk = our_lines[bo_op[3] : bo_op[4]]

                            conflicts.append(
                                (
                                    conflict_start,
                                    conflict_end,
                                    base_chunk,
                                    their_chunk,
                                    our_chunk,
                                )
                            )

        # Remove duplicate conflicts
        unique_conflicts = []
        for conflict in conflicts:
            if conflict not in unique_conflicts:
                unique_conflicts.append(conflict)

        return unique_conflicts

    def _determine_conflict_type(
        self, base_chunk: List[str], their_chunk: List[str], our_chunk: List[str]
    ) -> str:
        """Determine the type of conflict.

        Args:
            base_chunk: Base version chunk
            their_chunk: Their version chunk
            our_chunk: Our version chunk

        Returns:
            Conflict type string
        """
        # Simple heuristics for conflict type determination
        base_text = "\n".join(base_chunk)
        their_text = "\n".join(their_chunk)
        our_text = "\n".join(our_chunk)

        # Check for formatting conflicts (markdown patterns)
        formatting_patterns = [r"\*\*", r"\*", r"#", r"\[.*\]\(.*\)", r"~~", r"<.*>"]

        has_formatting_changes = False
        for pattern in formatting_patterns:
            if re.search(pattern, their_text) != re.search(
                pattern, base_text
            ) or re.search(pattern, our_text) != re.search(pattern, base_text):
                has_formatting_changes = True
                break

        if has_formatting_changes:
            return "formatting"

        # Check for structure conflicts (headers, lists, etc.)
        if (
            any(line.startswith("#") for line in their_chunk)
            or any(line.startswith("#") for line in our_chunk)
            or any(line.startswith(("-", "*", "1.")) for line in their_chunk)
            or any(line.startswith(("-", "*", "1.")) for line in our_chunk)
        ):
            return "structure"

        return "content"

    def _manual_resolution(
        self, conflict: ConflictRegion, resolver_id: Optional[str]
    ) -> ConflictRegion:
        """Manual resolution strategy - requires human intervention.

        Args:
            conflict: Conflict to resolve
            resolver_id: Optional resolver identifier

        Returns:
            Conflict marked for manual resolution
        """
        # For manual resolution, we just mark it as needing resolution
        conflict.resolution_status = "pending"
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = resolver_id

        return conflict

    def _take_theirs_resolution(
        self, conflict: ConflictRegion, resolver_id: Optional[str]
    ) -> ConflictRegion:
        """Take theirs resolution strategy.

        Args:
            conflict: Conflict to resolve
            resolver_id: Optional resolver identifier

        Returns:
            Conflict resolved with their content
        """
        conflict.resolution_content = conflict.their_content
        conflict.resolution_status = "resolved"
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = resolver_id

        return conflict

    def _take_ours_resolution(
        self, conflict: ConflictRegion, resolver_id: Optional[str]
    ) -> ConflictRegion:
        """Take ours resolution strategy.

        Args:
            conflict: Conflict to resolve
            resolver_id: Optional resolver identifier

        Returns:
            Conflict resolved with our content
        """
        conflict.resolution_content = conflict.our_content
        conflict.resolution_status = "resolved"
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = resolver_id

        return conflict

    def _merge_resolution(
        self, conflict: ConflictRegion, resolver_id: Optional[str]
    ) -> ConflictRegion:
        """Merge resolution strategy - attempt to merge both versions.

        Args:
            conflict: Conflict to resolve
            resolver_id: Optional resolver identifier

        Returns:
            Conflict resolved with merged content
        """
        # Simple merge strategy - concatenate both versions
        merged_content = f"{conflict.our_content}\n\n{conflict.their_content}"

        conflict.resolution_content = merged_content
        conflict.resolution_status = "resolved"
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = resolver_id

        return conflict

    def _interactive_resolution(
        self, conflict: ConflictRegion, resolver_id: Optional[str]
    ) -> ConflictRegion:
        """Interactive resolution strategy - present options to user.

        Args:
            conflict: Conflict to resolve
            resolver_id: Optional resolver identifier

        Returns:
            Conflict marked for interactive resolution
        """
        # For now, just mark as pending interactive resolution
        conflict.resolution_status = "pending"
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = resolver_id
        conflict.metadata["requires_interaction"] = True

        return conflict

    def _build_resolved_content(self, conflicts: List[ConflictRegion]) -> str:
        """Build resolved content from resolved conflicts.

        Args:
            conflicts: List of resolved conflicts

        Returns:
            Resolved content string
        """
        # This is a simplified implementation
        # In practice, you'd need to reconstruct the full document
        # by applying resolutions to the original content

        resolved_parts = []

        for conflict in conflicts:
            if conflict.resolution_status == "resolved" and conflict.resolution_content:
                resolved_parts.append(f"// Resolved conflict {conflict.conflict_id}")
                resolved_parts.append(conflict.resolution_content)
                resolved_parts.append("")
            else:
                resolved_parts.append(f"// Unresolved conflict {conflict.conflict_id}")
                resolved_parts.append(self._format_unresolved_conflict(conflict))
                resolved_parts.append("")

        return "\n".join(resolved_parts)

    def _format_unresolved_conflict(self, conflict: ConflictRegion) -> str:
        """Format an unresolved conflict for display.

        Args:
            conflict: Unresolved conflict

        Returns:
            Formatted conflict string
        """
        return """
{self.conflict_markers['start']}{conflict.metadata.get('our_label', 'ours')}
{conflict.our_content}
{self.conflict_markers['separator']}
{conflict.their_content}
{self.conflict_markers['end']}{conflict.metadata.get('their_label', 'theirs')}
""".strip()

    def create_resolution_interface(self, conflicts: List[ConflictRegion]) -> str:
        """Create HTML interface for resolving conflicts.

        Args:
            conflicts: List of conflicts to resolve

        Returns:
            HTML interface string
        """
        html_parts = []

        # Add CSS and JavaScript for conflict resolution
        html_parts.append(
            """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Conflict Resolution Interface</title>
            <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .conflict { border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 5px; }
            .conflict-header { background-color: #f8f9fa; padding: 10px; margin: -15px -15px 15px -15px; font-weight: bold; }
            .conflict-content { display: flex; gap: 20px; }
            .version { flex: 1; }
            .version-header { font-weight: bold; margin-bottom: 5px; }
            .version-content { background-color: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; white-space: pre-wrap; }
            .our-version { border-left: 3px solid #007bff; }
            .their-version { border-left: 3px solid #28a745; }
            .resolution-buttons { margin-top: 15px; }
            .btn { padding: 8px 16px; margin-right: 10px; border: none; border-radius: 3px; cursor: pointer; }
            .btn-primary { background-color: #007bff; color: white; }
            .btn-success { background-color: #28a745; color: white; }
            .btn-warning { background-color: #ffc107; color: black; }
            .btn-secondary { background-color: #6c757d; color: white; }
            .resolution-area { margin-top: 10px; }
            .resolution-textarea { width: 100%; height: 100px; font-family: monospace; }
            </style>
        </head>
        <body>
            <h1>Conflict Resolution Interface</h1>
            <p>Please resolve the following conflicts:</p>
        """
        )

        # Add conflicts
        for i, conflict in enumerate(conflicts):
            html_parts.append(
                """
            <div class="conflict" id="conflict-{i}">
                <div class="conflict-header">
                    Conflict {i + 1}: {conflict.conflict_type.title()} conflict in lines {conflict.start_line}-{conflict.end_line}
                </div>

                <div class="conflict-content">
                    <div class="version our-version">
                        <div class="version-header">Our Version</div>
                        <div class="version-content">{conflict.our_content}</div>
                    </div>

                    <div class="version their-version">
                        <div class="version-header">Their Version</div>
                        <div class="version-content">{conflict.their_content}</div>
                    </div>
                </div>

                <div class="resolution-buttons">
                    <button class="btn btn-primary" onclick="takeOurs({i})">Take Ours</button>
                    <button class="btn btn-success" onclick="takeTheirs({i})">Take Theirs</button>
                    <button class="btn btn-warning" onclick="merge({i})">Merge Both</button>
                    <button class="btn btn-secondary" onclick="customResolve({i})">Custom Resolution</button>
                </div>

                <div class="resolution-area" id="resolution-{i}" style="display: none;">
                    <textarea class="resolution-textarea" id="resolution-text-{i}" placeholder="Enter your custom resolution here..."></textarea>
                    <br>
                    <button class="btn btn-primary" onclick="applyCustomResolution({i})">Apply Resolution</button>
                </div>
            </div>
            """
            )

        # Add JavaScript for conflict resolution
        html_parts.append(
            """
            <script>
            function takeOurs(conflictIndex) {
                console.log('Taking ours for conflict', conflictIndex);
                // In a real implementation, this would send the resolution to the server
                alert('Resolution applied: Take Ours');
            }

            function takeTheirs(conflictIndex) {
                console.log('Taking theirs for conflict', conflictIndex);
                alert('Resolution applied: Take Theirs');
            }

            function merge(conflictIndex) {
                console.log('Merging conflict', conflictIndex);
                alert('Resolution applied: Merge Both');
            }

            function customResolve(conflictIndex) {
                const resolutionArea = document.getElementById('resolution-' + conflictIndex);
                resolutionArea.style.display = resolutionArea.style.display === 'none' ? 'block' : 'none';
            }

            function applyCustomResolution(conflictIndex) {
                const resolutionText = document.getElementById('resolution-text-' + conflictIndex).value;
                console.log('Custom resolution for conflict', conflictIndex, ':', resolutionText);
                alert('Custom resolution applied');
            }
            </script>
        </body>
        </html>
        """
        )

        return "".join(html_parts)

    def get_resolution_statistics(
        self, resolution: ConflictResolution
    ) -> Dict[str, Any]:
        """Get detailed statistics about a conflict resolution.

        Args:
            resolution: ConflictResolution to analyze

        Returns:
            Dictionary with detailed statistics
        """
        stats = resolution.statistics.copy()

        # Add detailed conflict analysis
        conflict_types = {}
        resolution_methods = {}

        for conflict in resolution.conflicts:
            # Count conflict types
            conflict_type = conflict.conflict_type
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1

            # Count resolution methods
            if conflict.resolution_status == "resolved":
                # Infer resolution method from content
                if conflict.resolution_content == conflict.our_content:
                    method = "take_ours"
                elif conflict.resolution_content == conflict.their_content:
                    method = "take_theirs"
                else:
                    method = "custom"

                resolution_methods[method] = resolution_methods.get(method, 0) + 1

        stats.update(
            {
                "conflict_types": conflict_types,
                "resolution_methods": resolution_methods,
                "avg_conflict_size": (
                    sum(
                        len(c.our_content) + len(c.their_content)
                        for c in resolution.conflicts
                    )
                    / len(resolution.conflicts)
                    if resolution.conflicts
                    else 0
                ),
            }
        )

        return stats
