import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class EnhancedDocumentConverter:
    """Enhanced document converter with improved formatting and structure preservation"""

    @staticmethod
    def convert_to_markdown(document: Dict) -> str:
        """Convert Google Docs document to Markdown with enhanced formatting"""
        content = document.get("body", {}).get("content", [])
        markdown_parts = []

        # Track document structure
        list_stack = []
        table_count = 0

        for element in content:
            if "paragraph" in element:
                paragraph = element["paragraph"]
                markdown_text = (
                    EnhancedDocumentConverter._convert_paragraph_to_markdown(
                        paragraph, list_stack
                    )
                )
                if markdown_text.strip():
                    markdown_parts.append(markdown_text)

            elif "table" in element:
                table_count += 1
                table_markdown = EnhancedDocumentConverter._convert_table_to_markdown(
                    element["table"], table_count
                )
                if table_markdown.strip():
                    markdown_parts.append(table_markdown)

            elif "sectionBreak" in element:
                # Add section break
                markdown_parts.append("\n---\n")

        return "\n\n".join(markdown_parts)

    @staticmethod
    def _convert_paragraph_to_markdown(paragraph: Dict, list_stack: List) -> str:
        """Convert paragraph to Markdown with enhanced formatting"""
        elements = paragraph.get("elements", [])
        text_parts = []

        # Process text elements
        for element in elements:
            if "textRun" in element:
                text_run = element["textRun"]
                content = text_run.get("content", "")
                text_style = text_run.get("textStyle", {})

                # Apply text formatting
                formatted_content = EnhancedDocumentConverter._apply_text_formatting(
                    content, text_style
                )
                text_parts.append(formatted_content)

            elif "inlineObjectElement" in element:
                # Handle inline objects (images, etc.)
                obj_id = element["inlineObjectElement"].get("inlineObjectId", "")
                text_parts.append(f"![Inline Object]({obj_id})")

        paragraph_text = "".join(text_parts)

        # Handle paragraph styling
        paragraph_style = paragraph.get("paragraphStyle", {})
        return EnhancedDocumentConverter._apply_paragraph_formatting(
            paragraph_text, paragraph_style, list_stack
        )

    @staticmethod
    def _apply_text_formatting(content: str, text_style: Dict) -> str:
        """Apply text-level formatting"""
        if not content.strip():
            return content

        # Bold
        if text_style.get("bold"):
            content = f"**{content}**"

        # Italic
        if text_style.get("italic"):
            content = f"*{content}*"

        # Underline (using HTML since Markdown doesn't support it natively)
        if text_style.get("underline"):
            content = f"<u>{content}</u>"

        # Strikethrough
        if text_style.get("strikethrough"):
            content = f"~~{content}~~"

        # Superscript/Subscript
        if text_style.get("baselineOffset") == "SUPERSCRIPT":
            content = f"<sup>{content}</sup>"
        elif text_style.get("baselineOffset") == "SUBSCRIPT":
            content = f"<sub>{content}</sub>"

        # Font family and size (as HTML comments for reference)
        font_family = text_style.get("weightedFontFamily", {}).get("fontFamily")
        font_size = text_style.get("fontSize", {}).get("magnitude")

        if font_family and font_family != "Arial":
            content = f"<!-- font: {font_family} -->{content}"

        # Links
        if "link" in text_style:
            link_url = text_style["link"].get("url", "")
            if link_url:
                content = f"[{content.strip('*_~')}]({link_url})"

        return content

    @staticmethod
    def _apply_paragraph_formatting(
        paragraph_text: str, paragraph_style: Dict, list_stack: List
    ) -> str:
        """Apply paragraph-level formatting"""
        if not paragraph_text.strip():
            return paragraph_text

        # Handle named styles (headings)
        named_style = paragraph_style.get("namedStyleType", "")

        if named_style == "HEADING_1":
            return f"# {paragraph_text.strip()}"
        elif named_style == "HEADING_2":
            return f"## {paragraph_text.strip()}"
        elif named_style == "HEADING_3":
            return f"### {paragraph_text.strip()}"
        elif named_style == "HEADING_4":
            return f"#### {paragraph_text.strip()}"
        elif named_style == "HEADING_5":
            return f"##### {paragraph_text.strip()}"
        elif named_style == "HEADING_6":
            return f"###### {paragraph_text.strip()}"

        # Handle lists
        bullet = paragraph_style.get("bullet")
        if bullet:
            list_id = bullet.get("listId", "")
            nesting_level = bullet.get("nestingLevel", 0)

            # Manage list stack
            while len(list_stack) <= nesting_level:
                list_stack.append({"type": "UNORDERED", "count": 0})

            # Trim stack if we've moved to a higher level
            list_stack = list_stack[: nesting_level + 1]

            # Determine list type
            glyph_type = bullet.get("glyphType", "GLYPH_TYPE_UNSPECIFIED")

            if glyph_type in ["DECIMAL", "ALPHA", "ROMAN"]:
                list_stack[nesting_level]["type"] = "ORDERED"
                list_stack[nesting_level]["count"] += 1
                bullet_symbol = f"{list_stack[nesting_level]['count']}."
            else:
                list_stack[nesting_level]["type"] = "UNORDERED"
                bullet_symbol = "-"

            # Create indentation
            indent = "  " * nesting_level
            return f"{indent}{bullet_symbol} {paragraph_text.strip()}"

        # Handle alignment
        alignment = paragraph_style.get("alignment", "START")
        if alignment == "CENTER":
            return f"<center>{paragraph_text.strip()}</center>"
        elif alignment == "END":
            return f"<div align='right'>{paragraph_text.strip()}</div>"

        # Handle quotes (indented paragraphs)
        indent_first_line = paragraph_style.get("indentFirstLine", {}).get(
            "magnitude", 0
        )
        indent_start = paragraph_style.get("indentStart", {}).get("magnitude", 0)

        if indent_start > 36:  # Significant indentation indicates quote
            return f"> {paragraph_text.strip()}"

        return paragraph_text

    @staticmethod
    def _convert_table_to_markdown(table: Dict, table_number: int) -> str:
        """Convert table to Markdown with enhanced formatting"""
        rows = table.get("tableRows", [])
        if not rows:
            return ""

        markdown_rows = []

        # Add table caption
        markdown_rows.append(f"**Table {table_number}**\n")

        for i, row in enumerate(rows):
            cells = row.get("tableCells", [])
            cell_contents = []

            for cell in cells:
                cell_content = cell.get("content", [])
                cell_text_parts = []

                for element in cell_content:
                    if "paragraph" in element:
                        # Use simplified paragraph processing for table cells
                        paragraph_text = (
                            EnhancedDocumentConverter._extract_paragraph_text(
                                element["paragraph"]
                            )
                        )
                        if paragraph_text.strip():
                            cell_text_parts.append(paragraph_text.strip())

                # Clean up cell content
                cell_text = " ".join(cell_text_parts).replace("\n", " ").strip()
                cell_contents.append(cell_text or " ")

            # Create markdown row
            markdown_row = f"| {' | '.join(cell_contents)} |"
            markdown_rows.append(markdown_row)

            # Add header separator after first row
            if i == 0:
                separator = f"| {' | '.join(['---'] * len(cell_contents))} |"
                markdown_rows.append(separator)

        return "\n".join(markdown_rows)

    @staticmethod
    def _extract_paragraph_text(paragraph: Dict) -> str:
        """Extract plain text from paragraph (helper method)"""
        elements = paragraph.get("elements", [])
        text_parts = []

        for element in elements:
            if "textRun" in element:
                text_content = element["textRun"].get("content", "")
                text_parts.append(text_content)

        return "".join(text_parts)

    @staticmethod
    def extract_document_metadata(document: Dict) -> Dict:
        """Extract comprehensive metadata from document"""
        metadata = {
            "title": document.get("title", ""),
            "document_id": document.get("documentId", ""),
            "revision_id": document.get("revisionId", ""),
            "created_time": None,
            "modified_time": None,
            "word_count": 0,
            "page_count": 0,
            "headings": [],
            "tables_count": 0,
            "images_count": 0,
            "links": [],
        }

        # Extract content statistics
        content = document.get("body", {}).get("content", [])
        word_count = 0
        headings = []
        tables_count = 0
        images_count = 0
        links = []

        for element in content:
            if "paragraph" in element:
                paragraph = element["paragraph"]
                paragraph_text = EnhancedDocumentConverter._extract_paragraph_text(
                    paragraph
                )
                word_count += len(paragraph_text.split())

                # Extract headings
                style = paragraph.get("paragraphStyle", {})
                named_style = style.get("namedStyleType", "")
                if "HEADING" in named_style:
                    level = int(named_style.split("_")[1]) if "_" in named_style else 1
                    headings.append(
                        {
                            "level": level,
                            "text": paragraph_text.strip(),
                            "style": named_style,
                        }
                    )

                # Extract links
                for elem in paragraph.get("elements", []):
                    if "textRun" in elem:
                        text_style = elem["textRun"].get("textStyle", {})
                        if "link" in text_style:
                            link_url = text_style["link"].get("url", "")
                            if link_url:
                                links.append(
                                    {
                                        "url": link_url,
                                        "text": elem["textRun"]
                                        .get("content", "")
                                        .strip(),
                                    }
                                )

            elif "table" in element:
                tables_count += 1

            elif "inlineObjectElement" in element:
                images_count += 1

        metadata.update(
            {
                "word_count": word_count,
                "headings": headings,
                "tables_count": tables_count,
                "images_count": images_count,
                "links": links,
            }
        )

        return metadata

    @staticmethod
    def generate_document_summary(document: Dict) -> str:
        """Generate a summary of the document"""
        metadata = EnhancedDocumentConverter.extract_document_metadata(document)

        summary_parts = [
            f"# Document Summary: {metadata['title']}",
            "",
            "**Statistics:**",
            f"- Word Count: {metadata['word_count']}",
            f"- Headings: {len(metadata['headings'])}",
            f"- Tables: {metadata['tables_count']}",
            f"- Images: {metadata['images_count']}",
            f"- Links: {len(metadata['links'])}",
            "",
        ]

        if metadata["headings"]:
            summary_parts.append("**Document Structure:**")
            for heading in metadata["headings"]:
                indent = "  " * (heading["level"] - 1)
                summary_parts.append(f"{indent}- {heading['text']}")
            summary_parts.append("")

        if metadata["links"]:
            summary_parts.append("**External Links:**")
            for link in metadata["links"][:5]:  # Limit to first 5 links
                summary_parts.append(f"- [{link['text']}]({link['url']})")
            if len(metadata["links"]) > 5:
                summary_parts.append(
                    f"- ... and {len(metadata['links']) - 5} more links"
                )
            summary_parts.append("")

        summary_parts.append(
            f"*Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*"
        )

        return "\n".join(summary_parts)
