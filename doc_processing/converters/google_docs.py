"""Google Docs to Markdown converter with round-trip accuracy."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseConverter

logger = logging.getLogger(__name__)


@dataclass
class DocumentElement:
    """Represents a parsed document element."""

    element_type: str
    content: str
    formatting: Dict[str, Any]
    start_index: int
    end_index: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Comment:
    """Represents a document comment."""

    id: str
    content: str
    author: str
    created_time: str
    anchor_start: int
    anchor_end: int
    resolved: bool = False
    replies: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.replies is None:
            self.replies = []


@dataclass
class Suggestion:
    """Represents a document suggestion."""

    id: str
    suggestion_type: str  # INSERT, DELETE, REPLACE
    content: str
    author: str
    created_time: str
    start_index: int
    end_index: int
    state: str = "PENDING"  # PENDING, ACCEPTED, REJECTED


@dataclass
class ConversionResult:
    """Result of document conversion."""

    content: str
    elements: List[DocumentElement]
    comments: List[Comment]
    suggestions: List[Suggestion]
    metadata: Dict[str, Any]
    conversion_accuracy: float
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class GoogleDocsConverter(BaseConverter):
    """Converter for Google Docs documents to/from Markdown."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Google Docs converter."""
        super().__init__(config)
        self.credentials = self.config.get("credentials")
        self.preserve_formatting = self.config.get("preserve_formatting", True)
        self.preserve_comments = self.config.get("preserve_comments", True)
        self.preserve_suggestions = self.config.get("preserve_suggestions", True)
        self.docs_service = None
        self.drive_service = None

        if self.credentials:
            self._initialize_services()

    def _initialize_services(self):
        """Initialize Google API services."""
        try:
            self.docs_service = build("docs", "v1", credentials=self.credentials)
            self.drive_service = build("drive", "v3", credentials=self.credentials)
            logger.info("Google Docs API services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google API services: {e}")
            raise

    def to_markdown(self, document_id: str) -> ConversionResult:
        """Convert Google Docs document to Markdown format.

        Args:
            document_id: Google Docs document ID

        Returns:
            ConversionResult with Markdown content and metadata
        """
        if not self.docs_service:
            raise RuntimeError("Google Docs service not initialized")

        try:
            # Get document content
            doc_result = (
                self.docs_service.documents().get(documentId=document_id).execute()
            )

            # Get document metadata
            file_metadata = (
                self.drive_service.files()
                .get(
                    fileId=document_id,
                    fields="name,createdTime,modifiedTime,lastModifyingUser",
                )
                .execute()
            )

            # Parse document structure
            elements = self._parse_document_structure(doc_result)

            # Extract comments if enabled
            comments = []
            if self.preserve_comments:
                comments = self._extract_comments(doc_result)

            # Extract suggestions if enabled
            suggestions = []
            if self.preserve_suggestions:
                suggestions = self._extract_suggestions(doc_result)

            # Convert to Markdown
            markdown_content = self._convert_to_markdown(
                elements, comments, suggestions
            )

            # Calculate conversion accuracy
            accuracy = self._calculate_accuracy(doc_result, markdown_content)

            # Build metadata
            metadata = {
                "document_id": document_id,
                "title": file_metadata.get("name", "Untitled"),
                "created_time": file_metadata.get("createdTime"),
                "modified_time": file_metadata.get("modifiedTime"),
                "last_modifying_user": file_metadata.get("lastModifyingUser", {}),
                "original_length": len(doc_result.get("body", {}).get("content", [])),
                "converted_length": len(markdown_content),
                "conversion_timestamp": logger.info(
                    "Conversion completed successfully"
                ),
            }

            return ConversionResult(
                content=markdown_content,
                elements=elements,
                comments=comments,
                suggestions=suggestions,
                metadata=metadata,
                conversion_accuracy=accuracy,
            )

        except HttpError as e:
            logger.error(f"Google Docs API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            raise

    def _parse_document_structure(
        self, doc_data: Dict[str, Any]
    ) -> List[DocumentElement]:
        """Parse Google Docs document structure into elements.

        Args:
            doc_data: Document data from Google Docs API

        Returns:
            List of DocumentElement objects
        """
        elements = []
        content = doc_data.get("body", {}).get("content", [])

        for item in content:
            if "paragraph" in item:
                paragraph_elements = self._parse_paragraph(item["paragraph"])
                elements.extend(paragraph_elements)
            elif "table" in item:
                table_elements = self._parse_table(item["table"])
                elements.extend(table_elements)
            elif "sectionBreak" in item:
                element = DocumentElement(
                    element_type="section_break",
                    content="",
                    formatting={},
                    start_index=item.get("startIndex", 0),
                    end_index=item.get("endIndex", 0),
                )
                elements.append(element)

        return elements

    def _parse_paragraph(self, paragraph_data: Dict[str, Any]) -> List[DocumentElement]:
        """Parse a paragraph into document elements.

        Args:
            paragraph_data: Paragraph data from Google Docs API

        Returns:
            List of DocumentElement objects
        """
        elements = []

        # Get paragraph style
        paragraph_style = paragraph_data.get("paragraphStyle", {})

        # Determine paragraph type
        named_style = paragraph_style.get("namedStyleType", "NORMAL_TEXT")

        # Parse elements within paragraph
        paragraph_elements = paragraph_data.get("elements", [])

        for element in paragraph_elements:
            if "textRun" in element:
                text_run = element["textRun"]
                content = text_run.get("content", "")

                # Extract formatting
                formatting = self._extract_text_formatting(
                    text_run.get("textStyle", {})
                )

                # Add paragraph-level formatting
                if named_style != "NORMAL_TEXT":
                    formatting["paragraph_style"] = named_style

                doc_element = DocumentElement(
                    element_type="text",
                    content=content,
                    formatting=formatting,
                    start_index=element.get("startIndex", 0),
                    end_index=element.get("endIndex", 0),
                )
                elements.append(doc_element)

        return elements

    def _parse_table(self, table_data: Dict[str, Any]) -> List[DocumentElement]:
        """Parse a table into document elements.

        Args:
            table_data: Table data from Google Docs API

        Returns:
            List of DocumentElement objects
        """
        elements = []

        table_rows = table_data.get("tableRows", [])

        for row_index, row in enumerate(table_rows):
            for cell_index, cell in enumerate(row.get("tableCells", [])):
                cell_content = []

                # Parse cell content
                for content_item in cell.get("content", []):
                    if "paragraph" in content_item:
                        cell_elements = self._parse_paragraph(content_item["paragraph"])
                        cell_content.extend(cell_elements)

                # Create table cell element
                cell_element = DocumentElement(
                    element_type="table_cell",
                    content="".join(elem.content for elem in cell_content),
                    formatting={"row": row_index, "col": cell_index},
                    start_index=cell.get("startIndex", 0),
                    end_index=cell.get("endIndex", 0),
                    metadata={"cell_elements": cell_content},
                )
                elements.append(cell_element)

        return elements

    def _extract_text_formatting(self, text_style: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text formatting from Google Docs text style.

        Args:
            text_style: Text style data from Google Docs API

        Returns:
            Dictionary of formatting attributes
        """
        formatting = {}

        # Basic formatting
        if text_style.get("bold"):
            formatting["bold"] = True
        if text_style.get("italic"):
            formatting["italic"] = True
        if text_style.get("underline"):
            formatting["underline"] = True
        if text_style.get("strikethrough"):
            formatting["strikethrough"] = True

        # Font and size
        if "fontSize" in text_style:
            formatting["font_size"] = text_style["fontSize"]["magnitude"]
        if "fontFamily" in text_style:
            formatting["font_family"] = text_style["fontFamily"]

        # Color
        if "foregroundColor" in text_style:
            color = text_style["foregroundColor"]
            if "color" in color:
                formatting["color"] = color["color"]

        # Links
        if "link" in text_style:
            formatting["link"] = text_style["link"]["url"]

        return formatting

    def _extract_comments(self, doc_data: Dict[str, Any]) -> List[Comment]:
        """Extract comments from Google Docs document.

        Args:
            doc_data: Document data from Google Docs API

        Returns:
            List of Comment objects
        """
        comments = []

        try:
            document_id = doc_data.get("documentId")
            if not document_id:
                return comments

            # Get comments using Drive API
            comments_response = (
                self.drive_service.comments()
                .list(
                    fileId=document_id,
                    fields="comments(id,content,author,createdTime,modifiedTime,resolved,replies,anchor)",
                )
                .execute()
            )

            for comment_data in comments_response.get("comments", []):
                # Extract anchor information
                anchor = comment_data.get("anchor", {})
                anchor_start = 0
                anchor_end = 0

                if "r" in anchor:
                    # Range anchor
                    anchor_start = anchor["r"].get("startIndex", 0)
                    anchor_end = anchor["r"].get("endIndex", 0)
                elif "h" in anchor:
                    # Header anchor
                    anchor_start = anchor["h"].get("startIndex", 0)
                    anchor_end = anchor["h"].get("endIndex", 0)

                # Extract replies
                replies = []
                for reply in comment_data.get("replies", []):
                    replies.append(
                        {
                            "id": reply.get("id"),
                            "content": reply.get("content"),
                            "author": reply.get("author", {}).get("displayName"),
                            "created_time": reply.get("createdTime"),
                            "modified_time": reply.get("modifiedTime"),
                        }
                    )

                comment = Comment(
                    id=comment_data.get("id"),
                    content=comment_data.get("content"),
                    author=comment_data.get("author", {}).get("displayName", "Unknown"),
                    created_time=comment_data.get("createdTime"),
                    anchor_start=anchor_start,
                    anchor_end=anchor_end,
                    resolved=comment_data.get("resolved", False),
                    replies=replies,
                )
                comments.append(comment)

            logger.debug(f"Extracted {len(comments)} comments from document")

        except Exception as e:
            logger.error(f"Failed to extract comments: {e}")

        return comments

    def _extract_suggestions(self, doc_data: Dict[str, Any]) -> List[Suggestion]:
        """Extract suggestions from Google Docs document.

        Args:
            doc_data: Document data from Google Docs API

        Returns:
            List of Suggestion objects
        """
        suggestions = []

        try:
            document_id = doc_data.get("documentId")
            if not document_id:
                return suggestions

            # Get document revisions to find suggestions
            revisions_response = (
                self.drive_service.revisions()
                .list(
                    fileId=document_id,
                    fields="revisions(id,modifiedTime,lastModifyingUser)",
                )
                .execute()
            )

            # For each revision, try to identify suggestions
            for revision in revisions_response.get("revisions", []):
                try:
                    # Get detailed revision info
                    revision_detail = (
                        self.drive_service.revisions()
                        .get(fileId=document_id, revisionId=revision["id"])
                        .execute()
                    )

                    # Check if this revision contains suggestions
                    # Note: Google Docs API doesn't directly expose suggestions,
                    # so we're inferring from revision history

                    # This is a simplified approach - in reality, suggestions
                    # would need more sophisticated extraction from document structure

                    if self._is_suggestion_revision(revision_detail):
                        suggestion = Suggestion(
                            id=revision["id"],
                            suggestion_type="REPLACE",  # Inferred
                            content=f"Revision {revision['id']}",
                            author=revision.get("lastModifyingUser", {}).get(
                                "displayName", "Unknown"
                            ),
                            created_time=revision.get("modifiedTime"),
                            start_index=0,  # Would need to be determined from actual changes
                            end_index=0,  # Would need to be determined from actual changes
                            state="PENDING",  # Default state
                        )
                        suggestions.append(suggestion)

                except Exception as e:
                    logger.warning(f"Failed to process revision {revision['id']}: {e}")
                    continue

            logger.debug(f"Extracted {len(suggestions)} suggestions from document")

        except Exception as e:
            logger.error(f"Failed to extract suggestions: {e}")

        return suggestions

    def _is_suggestion_revision(self, revision_detail: Dict[str, Any]) -> bool:
        """Check if a revision represents a suggestion.

        Args:
            revision_detail: Detailed revision data

        Returns:
            True if this revision appears to be a suggestion
        """
        # This is a placeholder implementation
        # In reality, we'd need to analyze the revision content
        # to determine if it represents a suggestion vs. an accepted change

        # For now, we'll consider revisions with certain characteristics as suggestions
        # This would need to be refined based on actual Google Docs API behavior

        return False  # Conservative approach for now

    def _convert_to_markdown(
        self,
        elements: List[DocumentElement],
        comments: List[Comment],
        suggestions: List[Suggestion],
    ) -> str:
        """Convert parsed elements to Markdown format.

        Args:
            elements: List of document elements
            comments: List of comments
            suggestions: List of suggestions

        Returns:
            Markdown formatted string
        """
        markdown_lines = []
        current_table = None
        table_rows = []

        for element in elements:
            if element.element_type == "text":
                # Handle different paragraph styles
                paragraph_style = element.formatting.get(
                    "paragraph_style", "NORMAL_TEXT"
                )

                if paragraph_style.startswith("HEADING_"):
                    # Extract heading level
                    level = int(paragraph_style.split("_")[1])
                    markdown_lines.append(f"{'#' * level} {element.content.strip()}")
                elif paragraph_style == "TITLE":
                    markdown_lines.append(f"# {element.content.strip()}")
                elif paragraph_style == "SUBTITLE":
                    markdown_lines.append(f"## {element.content.strip()}")
                else:
                    # Regular text with inline formatting
                    formatted_text = self._apply_markdown_formatting(
                        element.content, element.formatting
                    )
                    if formatted_text.strip():
                        markdown_lines.append(formatted_text)

            elif element.element_type == "table_cell":
                # Handle table cells
                if current_table is None:
                    current_table = []
                    table_rows = []

                # Add cell to current row
                if element.formatting.get("col") == 0:
                    # Start new row
                    if table_rows:
                        current_table.append(table_rows)
                    table_rows = [element.content.strip()]
                else:
                    table_rows.append(element.content.strip())

            elif element.element_type == "section_break":
                # Finalize any pending table
                if current_table is not None and table_rows:
                    current_table.append(table_rows)
                    markdown_lines.extend(self._format_markdown_table(current_table))
                    current_table = None
                    table_rows = []

                markdown_lines.append("")  # Section break

        # Handle any remaining table
        if current_table is not None and table_rows:
            current_table.append(table_rows)
            markdown_lines.extend(self._format_markdown_table(current_table))

        # Add comments if preservation is enabled
        if self.preserve_comments and comments:
            markdown_lines.append("\n## Comments")
            for comment in comments:
                markdown_lines.append(f"- **{comment.author}**: {comment.content}")

        # Add suggestions if preservation is enabled
        if self.preserve_suggestions and suggestions:
            markdown_lines.append("\n## Suggestions")
            for suggestion in suggestions:
                markdown_lines.append(
                    f"- **{suggestion.author}** ({suggestion.suggestion_type}): {suggestion.content}"
                )

        return "\n".join(markdown_lines)

    def _apply_markdown_formatting(self, text: str, formatting: Dict[str, Any]) -> str:
        """Apply Markdown formatting to text.

        Args:
            text: Plain text content
            formatting: Formatting attributes

        Returns:
            Markdown formatted text
        """
        formatted_text = text

        # Apply formatting in order
        if formatting.get("bold"):
            formatted_text = f"**{formatted_text}**"
        if formatting.get("italic"):
            formatted_text = f"*{formatted_text}*"
        if formatting.get("underline"):
            formatted_text = f"<u>{formatted_text}</u>"
        if formatting.get("strikethrough"):
            formatted_text = f"~~{formatted_text}~~"
        if formatting.get("link"):
            formatted_text = f"[{formatted_text}]({formatting['link']})"

        return formatted_text

    def _format_markdown_table(self, table_data: List[List[str]]) -> List[str]:
        """Format table data as Markdown table.

        Args:
            table_data: List of table rows

        Returns:
            List of Markdown table lines
        """
        if not table_data:
            return []

        lines = []

        # Header row
        if table_data:
            header = table_data[0]
            lines.append("| " + " | ".join(header) + " |")
            lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # Data rows
        for row in table_data[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return lines

    def _calculate_accuracy(
        self, original_doc: Dict[str, Any], markdown_content: str
    ) -> float:
        """Calculate conversion accuracy.

        Args:
            original_doc: Original document data
            markdown_content: Converted Markdown content

        Returns:
            Accuracy score between 0.0 and 1.0
        """
        # Simple accuracy calculation based on content length preservation
        # In a production system, this would be more sophisticated

        original_text = self._extract_plain_text(original_doc)
        converted_text = self._extract_plain_text_from_markdown(markdown_content)

        # Calculate similarity based on length and character overlap
        original_length = len(original_text)
        converted_length = len(converted_text)

        if original_length == 0:
            return 1.0 if converted_length == 0 else 0.0

        # Simple length-based accuracy
        length_accuracy = (
            1.0 - abs(original_length - converted_length) / original_length
        )

        return max(0.0, min(1.0, length_accuracy))

    def _extract_plain_text(self, doc_data: Dict[str, Any]) -> str:
        """Extract plain text from Google Docs document data.

        Args:
            doc_data: Document data from Google Docs API

        Returns:
            Plain text content
        """
        text_parts = []
        content = doc_data.get("body", {}).get("content", [])

        for item in content:
            if "paragraph" in item:
                paragraph = item["paragraph"]
                for element in paragraph.get("elements", []):
                    if "textRun" in element:
                        text_parts.append(element["textRun"].get("content", ""))

        return "".join(text_parts)

    def _extract_plain_text_from_markdown(self, markdown_content: str) -> str:
        """Extract plain text from Markdown content.

        Args:
            markdown_content: Markdown formatted text

        Returns:
            Plain text content
        """
        # Remove Markdown formatting
        text = re.sub(r"#+ ", "", markdown_content)  # Headers
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*(.*?)\*", r"\1", text)  # Italic
        text = re.sub(r"~~(.*?)~~", r"\1", text)  # Strikethrough
        text = re.sub(r"<u>(.*?)</u>", r"\1", text)  # Underline
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)  # Links
        text = re.sub(r"\|.*?\|", "", text)  # Tables

        return text

    def from_markdown(
        self, markdown: str, target_document_id: Optional[str] = None
    ) -> str:
        """Convert Markdown to Google Docs format.

        Args:
            markdown: Markdown content to convert
            target_document_id: Optional target document ID

        Returns:
            Google Docs document ID
        """
        if not self.docs_service:
            raise RuntimeError("Google Docs service not initialized")

        try:
            # Parse Markdown content
            parsed_content = self._parse_markdown(markdown)

            # Create or update document
            if target_document_id:
                # Update existing document
                document_id = self._update_document(target_document_id, parsed_content)
            else:
                # Create new document
                document_id = self._create_document(parsed_content)

            logger.info(
                f"Successfully converted Markdown to Google Docs: {document_id}"
            )
            return document_id

        except Exception as e:
            logger.error(f"Failed to convert Markdown to Google Docs: {e}")
            raise

    def _parse_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """Parse Markdown content into Google Docs format.

        Args:
            markdown: Markdown content

        Returns:
            List of document elements for Google Docs API
        """
        elements = []
        lines = markdown.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Headers
            if line.startswith("#"):
                header_level = len(line) - len(line.lstrip("#"))
                text = line.lstrip("#").strip()
                elements.append(
                    {"insertText": {"location": {"index": 1}, "text": text + "\n"}}
                )
                elements.append(
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": 1, "endIndex": len(text) + 1},
                            "paragraphStyle": {
                                "namedStyleType": f"HEADING_{header_level}"
                            },
                            "fields": "namedStyleType",
                        }
                    }
                )
            else:
                # Regular text
                elements.append(
                    {"insertText": {"location": {"index": 1}, "text": line + "\n"}}
                )

        return elements

    def _create_document(self, content_elements: List[Dict[str, Any]]) -> str:
        """Create new Google Docs document.

        Args:
            content_elements: List of document elements

        Returns:
            Created document ID
        """
        # Create empty document
        doc_result = (
            self.docs_service.documents()
            .create(body={"title": "Converted from Markdown"})
            .execute()
        )

        document_id = doc_result["documentId"]

        # Add content
        if content_elements:
            self.docs_service.documents().batchUpdate(
                documentId=document_id, body={"requests": content_elements}
            ).execute()

        return document_id

    def _update_document(
        self, document_id: str, content_elements: List[Dict[str, Any]]
    ) -> str:
        """Update existing Google Docs document.

        Args:
            document_id: Target document ID
            content_elements: List of document elements

        Returns:
            Updated document ID
        """
        # Clear existing content
        clear_request = {
            "deleteContentRange": {"range": {"startIndex": 1, "endIndex": -1}}
        }

        # Combine clear and update requests
        all_requests = [clear_request] + content_elements

        self.docs_service.documents().batchUpdate(
            documentId=document_id, body={"requests": all_requests}
        ).execute()

        return document_id

    def validate_conversion(
        self, document_id: str, markdown_content: str
    ) -> Dict[str, Any]:
        """Validate round-trip conversion accuracy.

        Args:
            document_id: Google Docs document ID
            markdown_content: Converted Markdown content

        Returns:
            Validation results dictionary
        """
        try:
            # Convert back to Markdown
            reconverted_result = self.to_markdown(document_id)

            # Compare original and reconverted content
            original_lines = markdown_content.split("\n")
            reconverted_lines = reconverted_result.content.split("\n")

            # Calculate similarity metrics
            total_lines = max(len(original_lines), len(reconverted_lines))
            matching_lines = sum(
                1
                for i in range(min(len(original_lines), len(reconverted_lines)))
                if original_lines[i] == reconverted_lines[i]
            )

            line_accuracy = matching_lines / total_lines if total_lines > 0 else 1.0

            # Character-level accuracy
            original_chars = len(markdown_content)
            reconverted_chars = len(reconverted_result.content)
            char_accuracy = 1.0 - abs(original_chars - reconverted_chars) / max(
                original_chars, reconverted_chars
            )

            return {
                "is_valid": line_accuracy > 0.9 and char_accuracy > 0.9,
                "line_accuracy": line_accuracy,
                "character_accuracy": char_accuracy,
                "original_lines": len(original_lines),
                "reconverted_lines": len(reconverted_lines),
                "original_chars": original_chars,
                "reconverted_chars": reconverted_chars,
                "conversion_accuracy": reconverted_result.conversion_accuracy,
                "warnings": reconverted_result.warnings,
            }

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "is_valid": False,
                "error": str(e),
                "line_accuracy": 0.0,
                "character_accuracy": 0.0,
            }
