import difflib
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ConflictType(Enum):
    """Types of conflicts that can occur during merging"""

    CONTENT_CONFLICT = "content_conflict"
    STRUCTURAL_CONFLICT = "structural_conflict"
    METADATA_CONFLICT = "metadata_conflict"
    FORMATTING_CONFLICT = "formatting_conflict"
    DELETION_CONFLICT = "deletion_conflict"


class ConflictSeverity(Enum):
    """Severity levels for conflicts"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConflictRange:
    """Represents a range of conflicting content"""

    start_line: int
    end_line: int
    start_char: int
    end_char: int


@dataclass
class ConflictDetail:
    """Detailed information about a conflict"""

    id: str
    type: ConflictType
    severity: ConflictSeverity
    range: ConflictRange
    base_content: str
    local_content: str
    remote_content: str
    description: str
    suggested_resolution: Optional[str] = None
    auto_resolvable: bool = False
    context_lines: List[str] = None

    def to_dict(self) -> Dict:
        """Convert conflict to dictionary for JSON serialization"""
        result = asdict(self)
        result["type"] = self.type.value
        result["severity"] = self.severity.value
        return result


class ConflictDetector:
    """Detects conflicts between different versions of documents"""

    def __init__(self):
        self.context_lines = 3
        self.similarity_threshold = 0.8

    def detect_conflicts(
        self,
        base_content: str,
        local_content: str,
        remote_content: str,
        document_type: str = "markdown",
    ) -> List[ConflictDetail]:
        """
        Detect conflicts between three versions of content (3-way merge)

        Args:
            base_content: Common ancestor version
            local_content: Local changes
            remote_content: Remote changes
            document_type: Type of document (markdown, text, etc.)

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Convert content to lines for processing
        base_lines = base_content.splitlines()
        local_lines = local_content.splitlines()
        remote_lines = remote_content.splitlines()

        # Detect line-level conflicts
        line_conflicts = self._detect_line_conflicts(
            base_lines, local_lines, remote_lines
        )
        conflicts.extend(line_conflicts)

        # Detect structural conflicts (for markdown)
        if document_type == "markdown":
            structural_conflicts = self._detect_structural_conflicts(
                base_content, local_content, remote_content
            )
            conflicts.extend(structural_conflicts)

        # Detect metadata conflicts
        metadata_conflicts = self._detect_metadata_conflicts(
            base_content, local_content, remote_content
        )
        conflicts.extend(metadata_conflicts)

        # Prioritize and deduplicate conflicts
        conflicts = self._prioritize_conflicts(conflicts)

        return conflicts

    def _detect_line_conflicts(
        self, base_lines: List[str], local_lines: List[str], remote_lines: List[str]
    ) -> List[ConflictDetail]:
        """Detect line-level conflicts using 3-way dif"""
        conflicts = []

        # Create diff sequences
        base_local_diff = list(difflib.unified_diff(base_lines, local_lines, n=0))
        base_remote_diff = list(difflib.unified_diff(base_lines, remote_lines, n=0))

        # Find overlapping changes
        local_changes = self._parse_unified_diff(base_local_diff)
        remote_changes = self._parse_unified_diff(base_remote_diff)

        # Identify conflicts
        for local_change in local_changes:
            for remote_change in remote_changes:
                if self._ranges_overlap(local_change["range"], remote_change["range"]):
                    conflict = self._create_line_conflict(
                        local_change,
                        remote_change,
                        base_lines,
                        local_lines,
                        remote_lines,
                    )
                    conflicts.append(conflict)

        return conflicts

    def _detect_structural_conflicts(
        self, base_content: str, local_content: str, remote_content: str
    ) -> List[ConflictDetail]:
        """Detect structural conflicts in markdown documents"""
        conflicts = []

        # Extract structural elements
        base_structure = self._extract_markdown_structure(base_content)
        local_structure = self._extract_markdown_structure(local_content)
        remote_structure = self._extract_markdown_structure(remote_content)

        # Compare heading structures
        heading_conflicts = self._detect_heading_conflicts(
            base_structure["headings"],
            local_structure["headings"],
            remote_structure["headings"],
        )
        conflicts.extend(heading_conflicts)

        # Compare list structures
        list_conflicts = self._detect_list_conflicts(
            base_structure["lists"], local_structure["lists"], remote_structure["lists"]
        )
        conflicts.extend(list_conflicts)

        return conflicts

    def _detect_metadata_conflicts(
        self, base_content: str, local_content: str, remote_content: str
    ) -> List[ConflictDetail]:
        """Detect metadata conflicts (frontmatter, document properties)"""
        conflicts = []

        # Extract metadata (YAML frontmatter)
        base_metadata = self._extract_frontmatter(base_content)
        local_metadata = self._extract_frontmatter(local_content)
        remote_metadata = self._extract_frontmatter(remote_content)

        if base_metadata or local_metadata or remote_metadata:
            # Compare metadata fields
            all_keys = set()
            if base_metadata:
                all_keys.update(base_metadata.keys())
            if local_metadata:
                all_keys.update(local_metadata.keys())
            if remote_metadata:
                all_keys.update(remote_metadata.keys())

            for key in all_keys:
                base_val = base_metadata.get(key) if base_metadata else None
                local_val = local_metadata.get(key) if local_metadata else None
                remote_val = remote_metadata.get(key) if remote_metadata else None

                if local_val != remote_val and (
                    local_val != base_val or remote_val != base_val
                ):
                    conflict = ConflictDetail(
                        id=self._generate_conflict_id(f"metadata_{key}"),
                        type=ConflictType.METADATA_CONFLICT,
                        severity=ConflictSeverity.MEDIUM,
                        range=ConflictRange(
                            0, 0, 0, 0
                        ),  # Metadata is at document start
                        base_content=str(base_val) if base_val else "",
                        local_content=str(local_val) if local_val else "",
                        remote_content=str(remote_val) if remote_val else "",
                        description=f"Metadata conflict in field '{key}'",
                        auto_resolvable=self._is_metadata_auto_resolvable(
                            key, local_val, remote_val
                        ),
                    )
                    conflicts.append(conflict)

        return conflicts

    def _parse_unified_diff(self, diff_lines: List[str]) -> List[Dict]:
        """Parse unified diff output to extract changes"""
        changes = []
        current_change = None

        for line in diff_lines:
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

                    current_change = {
                        "range": (old_start, old_start + old_count),
                        "old_lines": [],
                        "new_lines": [],
                    }
            elif current_change:
                if line.startswith("-"):
                    current_change["old_lines"].append(line[1:])
                elif line.startswith("+"):
                    current_change["new_lines"].append(line[1:])

        if current_change:
            changes.append(current_change)

        return changes

    def _ranges_overlap(self, range1: Tuple[int, int], range2: Tuple[int, int]) -> bool:
        """Check if two ranges overlap"""
        return not (range1[1] <= range2[0] or range2[1] <= range1[0])

    def _create_line_conflict(
        self,
        local_change: Dict,
        remote_change: Dict,
        base_lines: List[str],
        local_lines: List[str],
        remote_lines: List[str],
    ) -> ConflictDetail:
        """Create a conflict detail for overlapping line changes"""
        # Determine conflict range
        start_line = min(local_change["range"][0], remote_change["range"][0])
        end_line = max(local_change["range"][1], remote_change["range"][1])

        # Extract conflicting content
        base_content = "\n".join(base_lines[start_line - 1 : end_line])
        local_content = "\n".join(local_change["new_lines"])
        remote_content = "\n".join(remote_change["new_lines"])

        # Determine severity
        severity = self._determine_conflict_severity(local_content, remote_content)

        return ConflictDetail(
            id=self._generate_conflict_id(f"line_{start_line}_{end_line}"),
            type=ConflictType.CONTENT_CONFLICT,
            severity=severity,
            range=ConflictRange(start_line, end_line, 0, 0),
            base_content=base_content,
            local_content=local_content,
            remote_content=remote_content,
            description=f"Content conflict in lines {start_line}-{end_line}",
            auto_resolvable=self._is_content_auto_resolvable(
                local_content, remote_content
            ),
            context_lines=self._get_context_lines(base_lines, start_line, end_line),
        )

    def _extract_markdown_structure(self, content: str) -> Dict:
        """Extract structural elements from markdown content"""
        lines = content.splitlines()
        structure = {"headings": [], "lists": [], "code_blocks": [], "links": []}

        current_list = None
        in_code_block = False

        for i, line in enumerate(lines):
            # Headings
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                text = line.strip("#").strip()
                structure["headings"].append(
                    {"level": level, "text": text, "line": i + 1}
                )

            # Lists
            elif re.match(r"^\s*[-*+]\s", line) or re.match(r"^\s*\d+\.\s", line):
                if current_list is None:
                    current_list = {"start": i + 1, "items": []}
                current_list["items"].append(line.strip())
            else:
                if current_list:
                    current_list["end"] = i
                    structure["lists"].append(current_list)
                    current_list = None

            # Code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                if not in_code_block:
                    structure["code_blocks"].append({"line": i + 1})

            # Links
            link_matches = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", line)
            for text, url in link_matches:
                structure["links"].append({"text": text, "url": url, "line": i + 1})

        return structure

    def _detect_heading_conflicts(
        self,
        base_headings: List[Dict],
        local_headings: List[Dict],
        remote_headings: List[Dict],
    ) -> List[ConflictDetail]:
        """Detect conflicts in heading structure"""
        conflicts = []

        # Compare heading hierarchies
        base_hierarchy = [h["level"] for h in base_headings]
        local_hierarchy = [h["level"] for h in local_headings]
        remote_hierarchy = [h["level"] for h in remote_headings]

        if local_hierarchy != remote_hierarchy and (
            local_hierarchy != base_hierarchy or remote_hierarchy != base_hierarchy
        ):
            conflict = ConflictDetail(
                id=self._generate_conflict_id("heading_structure"),
                type=ConflictType.STRUCTURAL_CONFLICT,
                severity=ConflictSeverity.HIGH,
                range=ConflictRange(0, 0, 0, 0),
                base_content=str(base_hierarchy),
                local_content=str(local_hierarchy),
                remote_content=str(remote_hierarchy),
                description="Heading structure conflict",
                auto_resolvable=False,
            )
            conflicts.append(conflict)

        return conflicts

    def _detect_list_conflicts(
        self, base_lists: List[Dict], local_lists: List[Dict], remote_lists: List[Dict]
    ) -> List[ConflictDetail]:
        """Detect conflicts in list structure"""
        conflicts = []

        # Simple comparison - could be more sophisticated
        if len(local_lists) != len(remote_lists):
            conflict = ConflictDetail(
                id=self._generate_conflict_id("list_structure"),
                type=ConflictType.STRUCTURAL_CONFLICT,
                severity=ConflictSeverity.MEDIUM,
                range=ConflictRange(0, 0, 0, 0),
                base_content=f"{len(base_lists)} lists",
                local_content=f"{len(local_lists)} lists",
                remote_content=f"{len(remote_lists)} lists",
                description="List structure conflict",
                auto_resolvable=False,
            )
            conflicts.append(conflict)

        return conflicts

    def _extract_frontmatter(self, content: str) -> Optional[Dict]:
        """Extract YAML frontmatter from markdown content"""
        lines = content.splitlines()
        if not lines or not lines[0].strip() == "---":
            return None

        yaml_lines = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            yaml_lines.append(line)

        if yaml_lines:
            try:
                import yaml

                return yaml.safe_load("\n".join(yaml_lines))
            except ImportError:
                # Fallback: simple key-value parsing
                metadata = {}
                for line in yaml_lines:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()
                return metadata

        return None

    def _is_metadata_auto_resolvable(
        self, key: str, local_val: Any, remote_val: Any
    ) -> bool:
        """Determine if metadata conflict can be auto-resolved"""
        # Auto-resolve certain metadata fields
        if key in ["last_modified", "updated_at", "version"]:
            return True

        # Auto-resolve if one value is None/empty
        if not local_val or not remote_val:
            return True

        return False

    def _determine_conflict_severity(
        self, local_content: str, remote_content: str
    ) -> ConflictSeverity:
        """Determine severity of content conflict"""
        # Calculate similarity
        similarity = difflib.SequenceMatcher(
            None, local_content, remote_content
        ).ratio()

        if similarity > 0.8:
            return ConflictSeverity.LOW
        elif similarity > 0.5:
            return ConflictSeverity.MEDIUM
        else:
            return ConflictSeverity.HIGH

    def _is_content_auto_resolvable(
        self, local_content: str, remote_content: str
    ) -> bool:
        """Determine if content conflict can be auto-resolved"""
        # Auto-resolve if content is very similar (whitespace changes)
        local_normalized = re.sub(r"\s+", " ", local_content.strip())
        remote_normalized = re.sub(r"\s+", " ", remote_content.strip())

        return local_normalized == remote_normalized

    def _get_context_lines(self, lines: List[str], start: int, end: int) -> List[str]:
        """Get context lines around conflict"""
        context_start = max(0, start - self.context_lines - 1)
        context_end = min(len(lines), end + self.context_lines)
        return lines[context_start:context_end]

    def _generate_conflict_id(self, base: str) -> str:
        """Generate unique conflict ID"""
        timestamp = datetime.utcnow().isoformat()
        return hashlib.md5(f"{base}_{timestamp}".encode()).hexdigest()[:8]

    def _prioritize_conflicts(
        self, conflicts: List[ConflictDetail]
    ) -> List[ConflictDetail]:
        """Prioritize and deduplicate conflicts"""
        # Remove duplicates based on range overlap
        unique_conflicts = []
        for conflict in conflicts:
            is_duplicate = False
            for existing in unique_conflicts:
                if (
                    conflict.range.start_line == existing.range.start_line
                    and conflict.range.end_line == existing.range.end_line
                ):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_conflicts.append(conflict)

        # Sort by severity and line number
        severity_order = {
            ConflictSeverity.CRITICAL: 0,
            ConflictSeverity.HIGH: 1,
            ConflictSeverity.MEDIUM: 2,
            ConflictSeverity.LOW: 3,
        }

        return sorted(
            unique_conflicts,
            key=lambda c: (severity_order[c.severity], c.range.start_line),
        )
