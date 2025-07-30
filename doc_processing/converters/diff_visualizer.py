"""Diff visualization system for document changes."""

import difflib
import html
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class DiffLine:
    """Represents a single line in a diff."""

    line_type: str  # 'unchanged', 'added', 'removed', 'modified'
    content: str
    line_number_old: Optional[int] = None
    line_number_new: Optional[int] = None
    change_details: Optional[Dict[str, Any]] = None


@dataclass
class DiffBlock:
    """Represents a block of related changes in a diff."""

    block_type: str  # 'unchanged', 'added', 'removed', 'modified'
    lines: List[DiffLine]
    start_line_old: int
    start_line_new: int
    context_before: List[str] = None
    context_after: List[str] = None

    def __post_init__(self):
        if self.context_before is None:
            self.context_before = []
        if self.context_after is None:
            self.context_after = []


@dataclass
class DiffVisualization:
    """Complete diff visualization with metadata."""

    blocks: List[DiffBlock]
    statistics: Dict[str, Any]
    metadata: Dict[str, Any]
    html_output: Optional[str] = None
    plain_output: Optional[str] = None


class DocumentDiffVisualizer:
    """Visualizes differences between document versions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize diff visualizer.

        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.context_lines = self.config.get("context_lines", 3)
        self.ignore_whitespace = self.config.get("ignore_whitespace", False)
        self.ignore_case = self.config.get("ignore_case", False)
        self.word_level_diff = self.config.get("word_level_dif", True)
        self.show_line_numbers = self.config.get("show_line_numbers", True)
        self.highlight_style = self.config.get("highlight_style", "html")

    def create_diff(
        self,
        old_content: str,
        new_content: str,
        old_label: str = "Original",
        new_label: str = "Modified",
    ) -> DiffVisualization:
        """Create a comprehensive diff visualization.

        Args:
            old_content: Original document content
            new_content: Modified document content
            old_label: Label for original content
            new_label: Label for modified content

        Returns:
            DiffVisualization object with complete diff analysis
        """
        # Preprocess content if needed
        old_lines = self._preprocess_content(old_content)
        new_lines = self._preprocess_content(new_content)

        # Create unified diff
        unified_diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=old_label,
                tofile=new_label,
                n=self.context_lines,
            )
        )

        # Parse diff into blocks
        blocks = self._parse_diff_blocks(unified_diff, old_lines, new_lines)

        # Calculate statistics
        statistics = self._calculate_statistics(blocks, old_lines, new_lines)

        # Create visualizations
        html_output = self._create_html_visualization(blocks, statistics)
        plain_output = self._create_plain_visualization(blocks, statistics)

        # Build metadata
        metadata = {
            "old_label": old_label,
            "new_label": new_label,
            "old_length": len(old_lines),
            "new_length": len(new_lines),
            "config": self.config,
        }

        return DiffVisualization(
            blocks=blocks,
            statistics=statistics,
            metadata=metadata,
            html_output=html_output,
            plain_output=plain_output,
        )

    def create_word_diff(self, old_text: str, new_text: str) -> List[Dict[str, Any]]:
        """Create word-level diff for inline changes.

        Args:
            old_text: Original text
            new_text: Modified text

        Returns:
            List of word-level changes
        """
        if not self.word_level_diff:
            return []

        # Split into words
        old_words = re.findall(r"\S+|\s+", old_text)
        new_words = re.findall(r"\S+|\s+", new_text)

        # Create sequence matcher
        matcher = difflib.SequenceMatcher(None, old_words, new_words)

        word_changes = []

        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "equal":
                # Unchanged words
                for i, word in enumerate(old_words[i1:i2]):
                    word_changes.append(
                        {
                            "type": "unchanged",
                            "content": word,
                            "old_pos": i1 + i,
                            "new_pos": j1 + i,
                        }
                    )
            elif opcode == "delete":
                # Deleted words
                for i, word in enumerate(old_words[i1:i2]):
                    word_changes.append(
                        {
                            "type": "removed",
                            "content": word,
                            "old_pos": i1 + i,
                            "new_pos": None,
                        }
                    )
            elif opcode == "insert":
                # Inserted words
                for i, word in enumerate(new_words[j1:j2]):
                    word_changes.append(
                        {
                            "type": "added",
                            "content": word,
                            "old_pos": None,
                            "new_pos": j1 + i,
                        }
                    )
            elif opcode == "replace":
                # Replaced words
                for i, word in enumerate(old_words[i1:i2]):
                    word_changes.append(
                        {
                            "type": "removed",
                            "content": word,
                            "old_pos": i1 + i,
                            "new_pos": None,
                        }
                    )
                for i, word in enumerate(new_words[j1:j2]):
                    word_changes.append(
                        {
                            "type": "added",
                            "content": word,
                            "old_pos": None,
                            "new_pos": j1 + i,
                        }
                    )

        return word_changes

    def _preprocess_content(self, content: str) -> List[str]:
        """Preprocess content for diff generation.

        Args:
            content: Raw content string

        Returns:
            List of processed lines
        """
        lines = content.splitlines()

        if self.ignore_whitespace:
            lines = [line.strip() for line in lines]

        if self.ignore_case:
            lines = [line.lower() for line in lines]

        return lines

    def _parse_diff_blocks(
        self, unified_diff: List[str], old_lines: List[str], new_lines: List[str]
    ) -> List[DiffBlock]:
        """Parse unified diff into structured blocks.

        Args:
            unified_diff: Unified diff output
            old_lines: Original content lines
            new_lines: Modified content lines

        Returns:
            List of DiffBlock objects
        """
        blocks = []
        current_block = None
        old_line_num = 0
        new_line_num = 0

        for line in unified_diff:
            if line.startswith("@@"):
                # Parse hunk header
                match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1

                    old_line_num = old_start
                    new_line_num = new_start

                    # Start new block
                    if current_block:
                        blocks.append(current_block)

                    current_block = DiffBlock(
                        block_type="hunk",
                        lines=[],
                        start_line_old=old_start,
                        start_line_new=new_start,
                    )

            elif line.startswith("-"):
                # Removed line
                if current_block:
                    diff_line = DiffLine(
                        line_type="removed",
                        content=line[1:],
                        line_number_old=old_line_num,
                        line_number_new=None,
                    )
                    current_block.lines.append(diff_line)
                    old_line_num += 1

            elif line.startswith("+"):
                # Added line
                if current_block:
                    diff_line = DiffLine(
                        line_type="added",
                        content=line[1:],
                        line_number_old=None,
                        line_number_new=new_line_num,
                    )
                    current_block.lines.append(diff_line)
                    new_line_num += 1

            elif line.startswith(" ") or line == "":
                # Unchanged line
                if current_block:
                    diff_line = DiffLine(
                        line_type="unchanged",
                        content=line[1:] if line.startswith(" ") else line,
                        line_number_old=old_line_num,
                        line_number_new=new_line_num,
                    )
                    current_block.lines.append(diff_line)
                    old_line_num += 1
                    new_line_num += 1

        # Add final block
        if current_block:
            blocks.append(current_block)

        return blocks

    def _calculate_statistics(
        self, blocks: List[DiffBlock], old_lines: List[str], new_lines: List[str]
    ) -> Dict[str, Any]:
        """Calculate diff statistics.

        Args:
            blocks: List of diff blocks
            old_lines: Original content lines
            new_lines: Modified content lines

        Returns:
            Dictionary with diff statistics
        """
        stats = {
            "lines_added": 0,
            "lines_removed": 0,
            "lines_modified": 0,
            "lines_unchanged": 0,
            "total_changes": 0,
            "similarity_ratio": 0.0,
            "change_density": 0.0,
            "blocks_count": len(blocks),
        }

        for block in blocks:
            for line in block.lines:
                if line.line_type == "added":
                    stats["lines_added"] += 1
                elif line.line_type == "removed":
                    stats["lines_removed"] += 1
                elif line.line_type == "unchanged":
                    stats["lines_unchanged"] += 1

        # Calculate modified lines (pairs of add/remove)
        stats["lines_modified"] = min(stats["lines_added"], stats["lines_removed"])

        # Calculate total changes
        stats["total_changes"] = stats["lines_added"] + stats["lines_removed"]

        # Calculate similarity ratio
        total_lines = max(len(old_lines), len(new_lines))
        if total_lines > 0:
            unchanged_ratio = stats["lines_unchanged"] / total_lines
            stats["similarity_ratio"] = unchanged_ratio

        # Calculate change density
        if len(old_lines) > 0:
            stats["change_density"] = stats["total_changes"] / len(old_lines)

        return stats

    def _create_html_visualization(
        self, blocks: List[DiffBlock], statistics: Dict[str, Any]
    ) -> str:
        """Create HTML visualization of the diff.

        Args:
            blocks: List of diff blocks
            statistics: Diff statistics

        Returns:
            HTML string representation
        """
        html_parts = []

        # Add CSS styles
        html_parts.append(
            """
        <style>
        .diff-container {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }
        .diff-header {
            background-color: #f8f9fa;
            padding: 10px;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
        }
        .diff-stats {
            background-color: #e9ecef;
            padding: 8px;
            border-bottom: 1px solid #ddd;
            font-size: 11px;
        }
        .diff-block {
            border-bottom: 1px solid #eee;
        }
        .diff-line {
            display: flex;
            line-height: 1.4;
        }
        .line-number {
            background-color: #f8f9fa;
            color: #666;
            padding: 2px 8px;
            border-right: 1px solid #ddd;
            text-align: right;
            min-width: 40px;
            user-select: none;
        }
        .line-content {
            padding: 2px 8px;
            flex: 1;
            white-space: pre-wrap;
        }
        .line-added {
            background-color: #d4edda;
            color: #155724;
        }
        .line-removed {
            background-color: #f8d7da;
            color: #721c24;
        }
        .line-unchanged {
            background-color: #fff;
            color: #212529;
        }
        .line-added .line-content::before {
            content: '+';
            color: #28a745;
            font-weight: bold;
            margin-right: 4px;
        }
        .line-removed .line-content::before {
            content: '-';
            color: #dc3545;
            font-weight: bold;
            margin-right: 4px;
        }
        .line-unchanged .line-content::before {
            content: ' ';
            margin-right: 4px;
        }
        </style>
        """
        )

        # Start container
        html_parts.append('<div class="diff-container">')

        # Add header
        html_parts.append(
            '<div class="diff-header">' "Document Diff Visualization" "</div>"
        )

        # Add statistics
        html_parts.append(
            '<div class="diff-stats">'
            f'Lines: +{statistics["lines_added"]} -{statistics["lines_removed"]} '
            f'(~{statistics["lines_unchanged"]} unchanged) | '
            f'Similarity: {statistics["similarity_ratio"]:.1%} | '
            f'Blocks: {statistics["blocks_count"]}'
            "</div>"
        )

        # Add diff blocks
        for block in blocks:
            html_parts.append('<div class="diff-block">')

            for line in block.lines:
                line_class = f"line-{line.line_type}"

                # Line numbers
                old_num = str(line.line_number_old) if line.line_number_old else ""
                new_num = str(line.line_number_new) if line.line_number_new else ""

                html_parts.append(
                    f'<div class="diff-line {line_class}">'
                    f'<div class="line-number">{old_num}</div>'
                    f'<div class="line-number">{new_num}</div>'
                    f'<div class="line-content">{html.escape(line.content)}</div>'
                    "</div>"
                )

            html_parts.append("</div>")

        # End container
        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_plain_visualization(
        self, blocks: List[DiffBlock], statistics: Dict[str, Any]
    ) -> str:
        """Create plain text visualization of the diff.

        Args:
            blocks: List of diff blocks
            statistics: Diff statistics

        Returns:
            Plain text representation
        """
        lines = []

        # Add header
        lines.append("=" * 60)
        lines.append("Document Diff Visualization")
        lines.append("=" * 60)

        # Add statistics
        lines.append(f"Lines added: {statistics['lines_added']}")
        lines.append(f"Lines removed: {statistics['lines_removed']}")
        lines.append(f"Lines unchanged: {statistics['lines_unchanged']}")
        lines.append(f"Similarity: {statistics['similarity_ratio']:.1%}")
        lines.append(f"Blocks: {statistics['blocks_count']}")
        lines.append("-" * 60)

        # Add diff blocks
        for block in blocks:
            for line in block.lines:
                prefix = {"added": "+", "removed": "-", "unchanged": " "}.get(
                    line.line_type, " "
                )

                if self.show_line_numbers:
                    old_num = str(line.line_number_old or "").ljust(4)
                    new_num = str(line.line_number_new or "").ljust(4)
                    lines.append(f"{old_num} {new_num} {prefix}{line.content}")
                else:
                    lines.append(f"{prefix}{line.content}")

        return "\n".join(lines)

    def create_side_by_side_diff(
        self,
        old_content: str,
        new_content: str,
        old_label: str = "Original",
        new_label: str = "Modified",
    ) -> str:
        """Create side-by-side diff visualization.

        Args:
            old_content: Original content
            new_content: Modified content
            old_label: Label for original content
            new_label: Label for modified content

        Returns:
            HTML string with side-by-side comparison
        """
        old_lines = self._preprocess_content(old_content)
        new_lines = self._preprocess_content(new_content)

        # Create HTML diff
        html_diff = difflib.HtmlDiff(tabsize=4, wrapcolumn=80)

        side_by_side = html_diff.make_table(
            old_lines,
            new_lines,
            fromdesc=old_label,
            todesc=new_label,
            context=True,
            numlines=self.context_lines,
        )

        return side_by_side

    def create_inline_diff(self, old_text: str, new_text: str) -> str:
        """Create inline diff with word-level highlighting.

        Args:
            old_text: Original text
            new_text: Modified text

        Returns:
            HTML string with inline highlighting
        """
        word_changes = self.create_word_diff(old_text, new_text)

        html_parts = []
        html_parts.append('<div class="inline-dif">')

        for change in word_changes:
            content = html.escape(change["content"])

            if change["type"] == "added":
                html_parts.append(f'<span class="added">{content}</span>')
            elif change["type"] == "removed":
                html_parts.append(f'<span class="removed">{content}</span>')
            else:
                html_parts.append(content)

        html_parts.append("</div>")

        # Add CSS for inline diff
        css = """
        <style>
        .inline-diff {
            font-family: 'Courier New', monospace;
            line-height: 1.5;
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .inline-diff .added {
            background-color: #d4edda;
            color: #155724;
            text-decoration: none;
        }
        .inline-diff .removed {
            background-color: #f8d7da;
            color: #721c24;
            text-decoration: line-through;
        }
        </style>
        """

        return css + "".join(html_parts)

    def export_diff(
        self,
        diff_visualization: DiffVisualization,
        format: str = "html",
        output_path: Optional[str] = None,
    ) -> Union[str, bytes]:
        """Export diff visualization to file or return as string.

        Args:
            diff_visualization: DiffVisualization object
            format: Export format ('html', 'plain', 'json')
            output_path: Optional path to save file

        Returns:
            Exported content as string or bytes
        """
        if format == "html":
            content = diff_visualization.html_output
        elif format == "plain":
            content = diff_visualization.plain_output
        elif format == "json":
            import json

            content = json.dumps(
                {
                    "blocks": [
                        {
                            "block_type": block.block_type,
                            "start_line_old": block.start_line_old,
                            "start_line_new": block.start_line_new,
                            "lines": [
                                {
                                    "line_type": line.line_type,
                                    "content": line.content,
                                    "line_number_old": line.line_number_old,
                                    "line_number_new": line.line_number_new,
                                }
                                for line in block.lines
                            ],
                        }
                        for block in diff_visualization.blocks
                    ],
                    "statistics": diff_visualization.statistics,
                    "metadata": diff_visualization.metadata,
                },
                indent=2,
            )
        else:
            raise ValueError(f"Unsupported format: {format}")

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Diff exported to {output_path}")

        return content
