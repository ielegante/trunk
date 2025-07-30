"""Word document formatting preservation and conversion engine."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .word_xml import WordDocument, WordElement, WordStyle

logger = logging.getLogger(__name__)


@dataclass
class FormattingContext:
    """Context for maintaining formatting state during conversion."""

    current_styles: Dict[str, WordStyle]
    numbering_context: Dict[str, Any]
    table_context: Optional[Dict[str, Any]] = None
    list_stack: List[Dict[str, Any]] = None
    formatting_stack: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.list_stack is None:
            self.list_stack = []
        if self.formatting_stack is None:
            self.formatting_stack = []


@dataclass
class ConversionMapping:
    """Mapping between Word formatting and target format."""

    source_format: str
    target_format: str
    properties_map: Dict[str, str]
    conversion_function: Optional[str] = None
    priority: int = 0  # Higher priority mappings take precedence


class WordFormattingPreserver:
    """Advanced formatting preservation engine for Word documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize formatting preserver.

        Args:
            config: Configuration for formatting preservation
        """
        self.config = config or {}
        self.preserve_styles = self.config.get("preserve_styles", True)
        self.preserve_numbering = self.config.get("preserve_numbering", True)
        self.preserve_tables = self.config.get("preserve_tables", True)
        self.preserve_images = self.config.get("preserve_images", True)
        self.preserve_hyperlinks = self.config.get("preserve_hyperlinks", True)
        self.convert_to_markdown = self.config.get("convert_to_markdown", True)

        # Initialize conversion mappings
        self.format_mappings = self._initialize_format_mappings()
        self.style_cache = {}

    def _initialize_format_mappings(self) -> Dict[str, ConversionMapping]:
        """Initialize formatting conversion mappings."""
        mappings = {}

        # Character formatting mappings
        mappings["bold"] = ConversionMapping(
            source_format="character.bold",
            target_format="markdown.bold",
            properties_map={"bold": "**text**"},
            priority=1,
        )

        mappings["italic"] = ConversionMapping(
            source_format="character.italic",
            target_format="markdown.italic",
            properties_map={"italic": "*text*"},
            priority=1,
        )

        mappings["underline"] = ConversionMapping(
            source_format="character.underline",
            target_format="markdown.underline",
            properties_map={"underline": "<u>text</u>"},
            priority=1,
        )

        # Paragraph formatting mappings
        mappings["heading"] = ConversionMapping(
            source_format="paragraph.style",
            target_format="markdown.heading",
            properties_map={
                "Heading 1": "# ",
                "Heading 2": "## ",
                "Heading 3": "### ",
                "Heading 4": "#### ",
                "Heading 5": "##### ",
                "Heading 6": "###### ",
            },
            priority=3,
        )

        mappings["alignment"] = ConversionMapping(
            source_format="paragraph.alignment",
            target_format="html.alignment",
            properties_map={
                "center": '<div align="center">content</div>',
                "right": '<div align="right">content</div>',
                "justify": '<div align="justify">content</div>',
            },
            priority=2,
        )

        # List formatting mappings
        mappings["bullet_list"] = ConversionMapping(
            source_format="paragraph.numbering.bullet",
            target_format="markdown.list",
            properties_map={"bullet": "- "},
            priority=2,
        )

        mappings["numbered_list"] = ConversionMapping(
            source_format="paragraph.numbering.decimal",
            target_format="markdown.list",
            properties_map={"decimal": "1. "},
            priority=2,
        )

        # Table formatting mappings
        mappings["table"] = ConversionMapping(
            source_format="table",
            target_format="markdown.table",
            properties_map={"table": "| cell | cell |\n|------|------|"},
            priority=3,
        )

        return mappings

    def convert_to_markdown(self, word_document: WordDocument) -> str:
        """Convert Word document to Markdown with formatting preservation.

        Args:
            word_document: WordDocument object

        Returns:
            Markdown representation with preserved formatting
        """
        context = FormattingContext(
            current_styles=word_document.styles,
            numbering_context=word_document.numbering,
        )

        markdown_lines = []

        # Add document title if available
        title = word_document.document_properties.get("core_title")
        if title:
            markdown_lines.append(f"# {title}\n")

        # Process document elements
        for element in word_document.elements:
            element_markdown = self._convert_element_to_markdown(element, context)
            if element_markdown:
                markdown_lines.append(element_markdown)

        return "\n".join(markdown_lines)

    def _convert_element_to_markdown(
        self, element: WordElement, context: FormattingContext
    ) -> str:
        """Convert a single Word element to Markdown.

        Args:
            element: WordElement to convert
            context: Current formatting context

        Returns:
            Markdown representation of the element
        """
        if element.element_type == "paragraph":
            return self._convert_paragraph_to_markdown(element, context)
        elif element.element_type == "table":
            return self._convert_table_to_markdown(element, context)
        elif element.element_type == "drawing":
            return self._convert_image_to_markdown(element, context)
        elif element.element_type == "hyperlink":
            return self._convert_hyperlink_to_markdown(element, context)
        else:
            # Process children for container elements
            child_content = []
            for child in element.children:
                child_markdown = self._convert_element_to_markdown(child, context)
                if child_markdown:
                    child_content.append(child_markdown)
            return "".join(child_content)

    def _convert_paragraph_to_markdown(
        self, paragraph: WordElement, context: FormattingContext
    ) -> str:
        """Convert paragraph to Markdown with formatting."""
        if not paragraph.text_content.strip():
            return ""

        # Determine paragraph style
        style_info = self._analyze_paragraph_style(paragraph, context)

        # Convert runs (character formatting)
        formatted_text = self._convert_runs_to_markdown(paragraph.children, context)

        # Apply paragraph-level formatting
        if style_info["is_heading"]:
            level = style_info["heading_level"]
            return f"{'#' * level} {formatted_text}\n"
        elif style_info["is_list_item"]:
            return self._format_list_item(formatted_text, style_info, context)
        elif style_info["alignment"] and style_info["alignment"] != "left":
            return "<div align=\"{style_info['alignment']}\">{formatted_text}</div>\n"
        else:
            return f"{formatted_text}\n"

    def _analyze_paragraph_style(
        self, paragraph: WordElement, context: FormattingContext
    ) -> Dict[str, Any]:
        """Analyze paragraph style and formatting."""
        style_info = {
            "is_heading": False,
            "heading_level": 0,
            "is_list_item": False,
            "list_type": None,
            "list_level": 0,
            "alignment": "left",
            "indent": 0,
            "spacing": {},
        }

        formatting = paragraph.formatting

        # Check for paragraph style
        if "paragraph" in formatting:
            para_format = formatting["paragraph"]

            # Check alignment
            if "alignment" in para_format:
                style_info["alignment"] = para_format["alignment"]

            # Check numbering (lists)
            if "numbering" in para_format:
                numbering = para_format["numbering"]
                if numbering.get("id"):
                    style_info["is_list_item"] = True
                    style_info["list_level"] = int(numbering.get("level", 0))

                    # Determine list type from numbering definition
                    num_id = numbering["id"]
                    if num_id in context.numbering_context:
                        num_def = context.numbering_context[num_id]
                        if "bullet" in str(num_def).lower():
                            style_info["list_type"] = "bullet"
                        else:
                            style_info["list_type"] = "numbered"

            # Check indentation
            if "indentation" in para_format:
                indent = para_format["indentation"]
                if indent.get("left"):
                    style_info["indent"] = (
                        int(indent["left"]) // 720
                    )  # Convert twips to approximate level

        # Check if it's a heading by examining style or formatting
        if self._is_heading_paragraph(paragraph, context):
            style_info["is_heading"] = True
            style_info["heading_level"] = self._determine_heading_level(
                paragraph, context
            )

        return style_info

    def _is_heading_paragraph(
        self, paragraph: WordElement, context: FormattingContext
    ) -> bool:
        """Determine if paragraph is a heading."""
        # Check for heading style names
        formatting = paragraph.formatting
        if "paragraph" in formatting and "style" in formatting["paragraph"]:
            style_name = formatting["paragraph"]["style"].lower()
            return "heading" in style_name or "title" in style_name

        # Check for heading-like formatting (large, bold text)
        if paragraph.children:
            first_run = paragraph.children[0]
            if first_run.element_type == "run" and "character" in first_run.formatting:
                char_format = first_run.formatting["character"]
                font_size = char_format.get("font_size")
                is_bold = char_format.get("bold", False)

                if (
                    font_size and int(font_size) > 24 and is_bold
                ):  # Size > 12pt and bold
                    return True

        return False

    def _determine_heading_level(
        self, paragraph: WordElement, context: FormattingContext
    ) -> int:
        """Determine heading level (1-6)."""
        formatting = paragraph.formatting

        # Check style name for explicit level
        if "paragraph" in formatting and "style" in formatting["paragraph"]:
            style_name = formatting["paragraph"]["style"].lower()
            for i in range(1, 7):
                if f"heading {i}" in style_name or f"heading{i}" in style_name:
                    return i

        # Determine by font size
        if paragraph.children:
            first_run = paragraph.children[0]
            if first_run.element_type == "run" and "character" in first_run.formatting:
                char_format = first_run.formatting["character"]
                font_size = char_format.get("font_size")

                if font_size:
                    size = int(font_size)
                    if size >= 32:  # 16pt+
                        return 1
                    elif size >= 28:  # 14pt+
                        return 2
                    elif size >= 26:  # 13pt+
                        return 3
                    elif size >= 24:  # 12pt+
                        return 4
                    elif size >= 22:  # 11pt+
                        return 5
                    else:
                        return 6

        return 1  # Default to H1

    def _convert_runs_to_markdown(
        self, runs: List[WordElement], context: FormattingContext
    ) -> str:
        """Convert runs (character formatting) to Markdown."""
        formatted_parts = []

        for run in runs:
            if run.element_type != "run":
                continue

            text = run.text_content
            if not text:
                continue

            # Apply character formatting
            if "character" in run.formatting:
                char_format = run.formatting["character"]

                # Apply formatting in order of precedence
                if char_format.get("bold"):
                    text = f"**{text}**"

                if char_format.get("italic"):
                    text = f"*{text}*"

                if char_format.get("underline"):
                    text = f"<u>{text}</u>"

                # Handle code formatting (monospace fonts)
                font_family = char_format.get("font", {}).get("ascii", "")
                if any(
                    mono_font in font_family.lower()
                    for mono_font in ["courier", "consolas", "monaco", "menlo"]
                ):
                    text = f"`{text}`"

                # Handle highlighting
                if char_format.get("highlight"):
                    text = f"<mark>{text}</mark>"

            formatted_parts.append(text)

        return "".join(formatted_parts)

    def _format_list_item(
        self, text: str, style_info: Dict[str, Any], context: FormattingContext
    ) -> str:
        """Format list item with proper indentation and markers."""
        level = style_info["list_level"]
        list_type = style_info["list_type"]

        # Create indentation
        indent = "  " * level

        # Choose marker
        if list_type == "bullet":
            marker = "- "
        else:
            # For numbered lists, we'll use a simple numbering
            # In a real implementation, you'd track the actual number
            marker = "1. "

        return f"{indent}{marker}{text}\n"

    def _convert_table_to_markdown(
        self, table: WordElement, context: FormattingContext
    ) -> str:
        """Convert table to Markdown format."""
        if not table.children:
            return ""

        rows = []
        headers_processed = False

        for row_element in table.children:
            if row_element.element_type != "table_row":
                continue

            cells = []
            for cell_element in row_element.children:
                if cell_element.element_type == "table_cell":
                    # Extract cell content
                    cell_content = []
                    for para in cell_element.children:
                        if para.element_type == "paragraph":
                            para_text = self._convert_runs_to_markdown(
                                para.children, context
                            )
                            cell_content.append(para_text.strip())

                    # Join multiple paragraphs with <br>
                    cell_text = (
                        "<br>".join(cell_content)
                        if len(cell_content) > 1
                        else (cell_content[0] if cell_content else "")
                    )
                    cells.append(cell_text)

            if cells:
                rows.append(cells)

                # Add header separator after first row
                if not headers_processed:
                    separator = ["-" * max(3, len(cell)) for cell in cells]
                    rows.append(separator)
                    headers_processed = True

        if not rows:
            return ""

        # Format as Markdown table
        table_lines = []
        for row in rows:
            table_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(table_lines) + "\n"

    def _convert_image_to_markdown(
        self, image: WordElement, context: FormattingContext
    ) -> str:
        """Convert image to Markdown format."""
        # In a real implementation, you would extract the image
        # and save it to a file, then reference it
        image_ref = image.attributes.get("src", "image")
        alt_text = image.attributes.get("alt", "Image")

        return f"![{alt_text}]({image_ref})\n"

    def _convert_hyperlink_to_markdown(
        self, hyperlink: WordElement, context: FormattingContext
    ) -> str:
        """Convert hyperlink to Markdown format."""
        link_text = self._convert_runs_to_markdown(hyperlink.children, context)
        link_url = hyperlink.attributes.get("hre", "#")

        return f"[{link_text}]({link_url})"

    def convert_from_markdown(
        self, markdown: str, base_styles: Dict[str, WordStyle]
    ) -> WordDocument:
        """Convert Markdown back to Word document structure.

        Args:
            markdown: Markdown content
            base_styles: Base styles to use for conversion

        Returns:
            WordDocument object
        """
        elements = []
        lines = markdown.split("\n")
        current_element_index = 0

        # Parse markdown line by line
        i = 0
        while i < len(lines):
            line = lines[i]

            if not line.strip():
                # Empty line - add paragraph break
                i += 1
                continue

            # Process different markdown elements
            if line.startswith("#"):
                # Heading
                element = self._parse_markdown_heading(line, current_element_index)
                elements.append(element)
                current_element_index += 1

            elif (
                line.startswith("- ")
                or line.startswith("* ")
                or re.match(r"^\d+\. ", line)
            ):
                # List - process consecutive list items
                list_lines = []
                while i < len(lines) and (
                    lines[i].startswith("- ")
                    or lines[i].startswith("* ")
                    or re.match(r"^\d+\. ", lines[i])
                ):
                    list_lines.append(lines[i])
                    i += 1

                list_elements = self._parse_markdown_list(
                    list_lines, current_element_index
                )
                elements.extend(list_elements)
                current_element_index += len(list_elements)
                continue

            elif line.startswith("|") and "|" in line[1:]:
                # Table - process consecutive table rows
                table_lines = []
                while i < len(lines) and lines[i].startswith("|"):
                    table_lines.append(lines[i])
                    i += 1

                table_element = self._parse_markdown_table(
                    table_lines, current_element_index
                )
                if table_element:
                    elements.append(table_element)
                    current_element_index += 1
                continue

            else:
                # Regular paragraph
                element = self._parse_markdown_paragraph(line, current_element_index)
                elements.append(element)
                current_element_index += 1

            i += 1

        # Create WordDocument
        return WordDocument(
            document_properties={},
            styles=base_styles,
            elements=elements,
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

    def _parse_markdown_heading(self, line: str, position: int) -> WordElement:
        """Parse markdown heading into WordElement."""
        # Count heading level
        level = 0
        for char in line:
            if char == "#":
                level += 1
            else:
                break

        text = line[level:].strip()

        # Create heading formatting
        formatting = {
            "paragraph": {
                "style": f"Heading {level}",
                "spacing": {"after": "240"},  # 12pt spacing after
            }
        }

        # Create run for text
        run = WordElement(
            element_type="run",
            element_id=None,
            text_content=text,
            formatting={
                "character": {
                    "bold": True,
                    "font_size": str(28 - (level - 1) * 2),  # Decreasing size by level
                }
            },
            position={"index": 0},
            children=[],
            attributes={},
        )

        return WordElement(
            element_type="paragraph",
            element_id=None,
            text_content=text,
            formatting=formatting,
            position={"index": position},
            children=[run],
            attributes={},
        )

    def _parse_markdown_paragraph(self, line: str, position: int) -> WordElement:
        """Parse markdown paragraph into WordElement."""
        # Parse inline formatting
        runs = self._parse_inline_formatting(line)

        return WordElement(
            element_type="paragraph",
            element_id=None,
            text_content=line,
            formatting={},
            position={"index": position},
            children=runs,
            attributes={},
        )

    def _parse_inline_formatting(self, text: str) -> List[WordElement]:
        """Parse inline markdown formatting into runs."""
        runs = []
        current_pos = 0
        run_index = 0

        # Pattern to match markdown formatting
        patterns = [
            (r"\*\*(.*?)\*\*", "bold"),  # **bold**
            (r"\*(.*?)\*", "italic"),  # *italic*
            (r"`(.*?)`", "code"),  # `code`
            (r"<u>(.*?)</u>", "underline"),  # <u>underline</u>
            (r"<mark>(.*?)</mark>", "highlight"),  # <mark>highlight</mark>
        ]

        # Find all formatting matches
        matches = []
        for pattern, format_type in patterns:
            for match in re.finditer(pattern, text):
                matches.append(
                    (match.start(), match.end(), match.group(1), format_type)
                )

        # Sort matches by position
        matches.sort(key=lambda x: x[0])

        # Process text with formatting
        last_end = 0
        for start, end, content, format_type in matches:
            # Add text before this match
            if start > last_end:
                plain_text = text[last_end:start]
                if plain_text:
                    runs.append(self._create_text_run(plain_text, {}, run_index))
                    run_index += 1

            # Add formatted text
            formatting = self._get_character_formatting(format_type)
            runs.append(self._create_text_run(content, formatting, run_index))
            run_index += 1

            last_end = end

        # Add remaining text
        if last_end < len(text):
            remaining_text = text[last_end:]
            if remaining_text:
                runs.append(self._create_text_run(remaining_text, {}, run_index))

        return runs if runs else [self._create_text_run(text, {}, 0)]

    def _create_text_run(
        self, text: str, formatting: Dict[str, Any], position: int
    ) -> WordElement:
        """Create a text run WordElement."""
        return WordElement(
            element_type="run",
            element_id=None,
            text_content=text,
            formatting={"character": formatting} if formatting else {},
            position={"index": position},
            children=[],
            attributes={},
        )

    def _get_character_formatting(self, format_type: str) -> Dict[str, Any]:
        """Get character formatting properties for format type."""
        formatting = {}

        if format_type == "bold":
            formatting["bold"] = True
        elif format_type == "italic":
            formatting["italic"] = True
        elif format_type == "underline":
            formatting["underline"] = "single"
        elif format_type == "code":
            formatting["font"] = {"ascii": "Courier New"}
        elif format_type == "highlight":
            formatting["highlight"] = "yellow"

        return formatting

    def _parse_markdown_list(
        self, list_lines: List[str], start_position: int
    ) -> List[WordElement]:
        """Parse markdown list into WordElements."""
        elements = []

        for i, line in enumerate(list_lines):
            # Determine list type and content
            if line.startswith("- ") or line.startswith("* "):
                list_type = "bullet"
                content = line[2:].strip()
            else:
                list_type = "numbered"
                content = re.sub(r"^\d+\. ", "", line).strip()

            # Create list item formatting
            formatting = {"paragraph": {"numbering": {"id": "1", "level": "0"}}}

            # Parse inline formatting in content
            runs = self._parse_inline_formatting(content)

            element = WordElement(
                element_type="paragraph",
                element_id=None,
                text_content=content,
                formatting=formatting,
                position={"index": start_position + i},
                children=runs,
                attributes={"list_type": list_type},
            )

            elements.append(element)

        return elements

    def _parse_markdown_table(
        self, table_lines: List[str], position: int
    ) -> Optional[WordElement]:
        """Parse markdown table into WordElement."""
        if len(table_lines) < 2:
            return None

        # Remove separator line (usually second line with dashes)
        content_lines = []
        for line in table_lines:
            if not re.match(r"^\|[\s\-\|]+\|$", line):
                content_lines.append(line)

        if not content_lines:
            return None

        # Parse table rows
        rows = []
        for line in content_lines:
            # Split by | and clean up
            cells = [
                cell.strip() for cell in line.split("|")[1:-1]
            ]  # Remove empty first/last
            if cells:
                rows.append(cells)

        if not rows:
            return None

        # Create table structure
        table_rows = []
        for row_index, row_data in enumerate(rows):
            cells = []
            for cell_index, cell_text in enumerate(row_data):
                # Parse cell content
                runs = self._parse_inline_formatting(cell_text)

                # Create paragraph for cell
                cell_paragraph = WordElement(
                    element_type="paragraph",
                    element_id=None,
                    text_content=cell_text,
                    formatting={},
                    position={"index": 0},
                    children=runs,
                    attributes={},
                )

                # Create table cell
                cell = WordElement(
                    element_type="table_cell",
                    element_id=None,
                    text_content=cell_text,
                    formatting={},
                    position={"index": cell_index},
                    children=[cell_paragraph],
                    attributes={},
                )

                cells.append(cell)

            # Create table row
            table_row = WordElement(
                element_type="table_row",
                element_id=None,
                text_content="",
                formatting={},
                position={"index": row_index},
                children=cells,
                attributes={},
            )

            table_rows.append(table_row)

        # Create table element
        return WordElement(
            element_type="table",
            element_id=None,
            text_content="",
            formatting={
                "table": {
                    "width": {"value": "5000", "type": "pct"},
                    "alignment": "left",
                }
            },
            position={"index": position},
            children=table_rows,
            attributes={},
        )

    def validate_formatting_preservation(
        self, original: WordDocument, converted: WordDocument
    ) -> Dict[str, Any]:
        """Validate that formatting is preserved during conversion.

        Args:
            original: Original WordDocument
            converted: Converted WordDocument

        Returns:
            Validation results with metrics and issues
        """
        validation = {
            "overall_score": 0.0,
            "element_preservation": {},
            "formatting_preservation": {},
            "structure_preservation": {},
            "issues": [],
        }

        # Compare element counts
        orig_stats = self._get_element_statistics(original.elements)
        conv_stats = self._get_element_statistics(converted.elements)

        element_scores = {}
        for elem_type in set(orig_stats.keys()) | set(conv_stats.keys()):
            orig_count = orig_stats.get(elem_type, 0)
            conv_count = conv_stats.get(elem_type, 0)

            if orig_count == 0 and conv_count == 0:
                score = 1.0
            elif orig_count == 0:
                score = 0.0  # Added elements
            else:
                score = min(conv_count / orig_count, 1.0)

            element_scores[elem_type] = score

            if score < 0.9:
                validation["issues"].append(
                    f"Element type '{elem_type}' preservation: {score:.2%}"
                )

        validation["element_preservation"] = element_scores

        # Compare text content
        orig_text = self._extract_all_text(original.elements)
        conv_text = self._extract_all_text(converted.elements)

        text_similarity = self._calculate_text_similarity(orig_text, conv_text)
        validation["structure_preservation"]["text_similarity"] = text_similarity

        if text_similarity < 0.95:
            validation["issues"].append(
                f"Text content similarity: {text_similarity:.2%}"
            )

        # Calculate overall score
        scores = list(element_scores.values()) + [text_similarity]
        validation["overall_score"] = sum(scores) / len(scores) if scores else 0.0

        return validation

    def _get_element_statistics(self, elements: List[WordElement]) -> Dict[str, int]:
        """Get statistics about element types."""
        stats = {}

        def count_elements(elems: List[WordElement]):
            for elem in elems:
                stats[elem.element_type] = stats.get(elem.element_type, 0) + 1
                if elem.children:
                    count_elements(elem.children)

        count_elements(elements)
        return stats

    def _extract_all_text(self, elements: List[WordElement]) -> str:
        """Extract all text content from elements."""
        text_parts = []

        def extract_text(elems: List[WordElement]):
            for elem in elems:
                if elem.text_content:
                    text_parts.append(elem.text_content)
                if elem.children:
                    extract_text(elem.children)

        extract_text(elements)
        return " ".join(text_parts)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0

        # Simple character-based similarity
        # In a real implementation, you might use more sophisticated algorithms
        text1_clean = re.sub(r"\s+", " ", text1.lower().strip())
        text2_clean = re.sub(r"\s+", " ", text2.lower().strip())

        if text1_clean == text2_clean:
            return 1.0

        # Calculate similarity based on character overlap
        longer = text1_clean if len(text1_clean) > len(text2_clean) else text2_clean
        shorter = text2_clean if len(text1_clean) > len(text2_clean) else text1_clean

        if len(longer) == 0:
            return 1.0

        # Simple edit distance approximation
        matching_chars = sum(
            1 for i, char in enumerate(shorter) if i < len(longer) and char == longer[i]
        )
        return matching_chars / len(longer)
