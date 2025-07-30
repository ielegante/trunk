"""Word document (.docx) converter for Git version control."""

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class WordStyle:
    """Represents a Word document style."""

    style_id: str
    name: str
    style_type: str  # paragraph, character, table, list
    based_on: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class WordComment:
    """Represents a comment in a Word document."""

    comment_id: str
    author: str
    date: datetime
    text: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    parent_id: Optional[str] = None  # For reply threads

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["date"] = self.date.isoformat()
        return data


@dataclass
class TrackChange:
    """Represents a tracked change in a Word document."""

    change_id: str
    author: str
    date: datetime
    change_type: str  # insertion, deletion, format
    content: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["date"] = self.date.isoformat()
        return data


@dataclass
class WordParagraph:
    """Represents a paragraph in a Word document."""

    text: str
    style: Optional[str] = None
    formatting: Dict[str, Any] = field(default_factory=dict)
    numbering: Optional[Dict[str, Any]] = None
    comments: List[str] = field(default_factory=list)  # Comment IDs
    track_changes: List[str] = field(default_factory=list)  # Change IDs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class WordTable:
    """Represents a table in a Word document."""

    rows: List[List[str]]  # Table data
    headers: Optional[List[str]] = None
    style: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class WordMetadata:
    """Metadata from a Word document."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    last_modified_by: Optional[str] = None
    revision: Optional[int] = None
    category: Optional[str] = None
    company: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.created:
            data["created"] = self.created.isoformat()
        if self.modified:
            data["modified"] = self.modified.isoformat()
        return data


@dataclass
class WordConversionResult:
    """Result of Word document conversion."""

    content: str  # Markdown content
    paragraphs: List[WordParagraph]
    tables: List[WordTable]
    styles: List[WordStyle]
    comments: List[WordComment]
    track_changes: List[TrackChange]
    metadata: WordMetadata
    formatting_preserved: float  # 0.0 to 1.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content": self.content,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "tables": [t.to_dict() for t in self.tables],
            "styles": [s.to_dict() for s in self.styles],
            "comments": [c.to_dict() for c in self.comments],
            "track_changes": [tc.to_dict() for tc in self.track_changes],
            "metadata": self.metadata.to_dict(),
            "formatting_preserved": self.formatting_preserved,
            "warnings": self.warnings,
        }


class WordDocxConverter:
    """Converts Word documents to/from Git-trackable format."""

    # XML namespaces used in Word documents
    NAMESPACES = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
        "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "dcmitype": "http://purl.org/dc/dcmitype/",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Word document converter.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.preserve_formatting = self.config.get("preserve_formatting", True)
        self.extract_comments = self.config.get("extract_comments", True)
        self.extract_track_changes = self.config.get("extract_track_changes", True)
        self.include_metadata = self.config.get("include_metadata", True)

    def to_markdown(self, file_path: Union[str, Path]) -> WordConversionResult:
        """Convert Word document to markdown format.

        Args:
            file_path: Path to Word document

        Returns:
            WordConversionResult with extracted content
        """
        file_path = Path(file_path)
        logger.info(f"Converting Word document: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"Word document not found: {file_path}")

        if not file_path.suffix.lower() in [".docx", ".docm"]:
            raise ValueError(f"Not a Word document: {file_path}")

        try:
            with zipfile.ZipFile(file_path, "r") as docx:
                return self._process_docx(docx)
        except Exception as e:
            logger.error(f"Failed to process Word document: {e}")
            raise

    def from_markdown(
        self, markdown_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Convert markdown back to Word document format.

        Args:
            markdown_content: Markdown formatted text
            metadata: Optional document metadata

        Returns:
            Bytes representing the Word document
        """
        logger.info("Converting markdown to Word document")

        # This is a simplified implementation
        # In production, would use python-docx or similar library
        raise NotImplementedError("Word document generation not yet implemented")

    def _process_docx(self, docx_zip: zipfile.ZipFile) -> WordConversionResult:
        """Process Word document from zip file.

        Args:
            docx_zip: Opened docx zip file

        Returns:
            WordConversionResult with extracted content
        """
        # Extract components
        document_xml = self._read_xml(docx_zip, "word/document.xml")
        styles_xml = self._read_xml(docx_zip, "word/styles.xml")
        comments_xml = self._read_xml(docx_zip, "word/comments.xml")
        core_props_xml = self._read_xml(docx_zip, "docProps/core.xml")

        # Parse components
        paragraphs = self._extract_paragraphs(document_xml)
        tables = self._extract_tables(document_xml)
        styles = self._extract_styles(styles_xml) if styles_xml is not None else []
        comments = (
            self._extract_comments(comments_xml) if comments_xml is not None else []
        )
        track_changes = self._extract_track_changes(document_xml)
        metadata = (
            self._extract_metadata(core_props_xml)
            if core_props_xml is not None
            else WordMetadata()
        )

        # Convert to markdown
        markdown_content = self._convert_to_markdown(paragraphs, tables, styles)

        # Calculate formatting preservation score
        formatting_preserved = self._calculate_formatting_score(paragraphs, styles)

        return WordConversionResult(
            content=markdown_content,
            paragraphs=paragraphs,
            tables=tables,
            styles=styles,
            comments=comments,
            track_changes=track_changes,
            metadata=metadata,
            formatting_preserved=formatting_preserved,
            warnings=self._generate_warnings(paragraphs, comments, track_changes),
        )

    def _read_xml(self, docx_zip: zipfile.ZipFile, path: str) -> Optional[ET.Element]:
        """Read and parse XML file from docx.

        Args:
            docx_zip: Opened docx zip file
            path: Path within zip file

        Returns:
            Parsed XML element or None if file doesn't exist
        """
        try:
            with docx_zip.open(path) as f:
                return ET.parse(f).getroot()
        except KeyError:
            logger.debug(f"File not found in docx: {path}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse {path}: {e}")
            return None

    def _extract_paragraphs(self, document_xml: ET.Element) -> List[WordParagraph]:
        """Extract paragraphs from document.xml.

        Args:
            document_xml: Parsed document.xml

        Returns:
            List of WordParagraph objects
        """
        paragraphs = []

        for p_elem in document_xml.findall(".//w:p", self.NAMESPACES):
            # Extract text
            text_parts = []
            for t_elem in p_elem.findall(".//w:t", self.NAMESPACES):
                text_parts.append(t_elem.text or "")

            text = "".join(text_parts).strip()
            if not text:
                continue

            # Extract style
            style = None
            pstyle = p_elem.find(".//w:pStyle", self.NAMESPACES)
            if pstyle is not None:
                style = pstyle.get("{%s}val" % self.NAMESPACES["w"])

            # Extract formatting
            formatting = self._extract_paragraph_formatting(p_elem)

            # Extract numbering
            numbering = self._extract_numbering(p_elem)

            paragraphs.append(
                WordParagraph(
                    text=text, style=style, formatting=formatting, numbering=numbering
                )
            )

        return paragraphs

    def _extract_tables(self, document_xml: ET.Element) -> List[WordTable]:
        """Extract tables from document.xml.

        Args:
            document_xml: Parsed document.xml

        Returns:
            List of WordTable objects
        """
        tables = []

        for tbl_elem in document_xml.findall(".//w:tbl", self.NAMESPACES):
            rows = []

            for tr_elem in tbl_elem.findall(".//w:tr", self.NAMESPACES):
                row = []

                for tc_elem in tr_elem.findall(".//w:tc", self.NAMESPACES):
                    # Extract cell text
                    cell_text_parts = []
                    for t_elem in tc_elem.findall(".//w:t", self.NAMESPACES):
                        cell_text_parts.append(t_elem.text or "")

                    cell_text = "".join(cell_text_parts).strip()
                    row.append(cell_text)

                if row:
                    rows.append(row)

            if rows:
                # First row might be headers
                headers = rows[0] if len(rows) > 1 else None
                data_rows = rows[1:] if headers else rows

                tables.append(WordTable(rows=data_rows, headers=headers))

        return tables

    def _extract_styles(self, styles_xml: Optional[ET.Element]) -> List[WordStyle]:
        """Extract styles from styles.xml.

        Args:
            styles_xml: Parsed styles.xml

        Returns:
            List of WordStyle objects
        """
        if styles_xml is None:
            return []

        styles = []

        for style_elem in styles_xml.findall(".//w:style", self.NAMESPACES):
            style_id = style_elem.get("{%s}styleId" % self.NAMESPACES["w"])
            style_type = style_elem.get("{%s}type" % self.NAMESPACES["w"])

            name_elem = style_elem.find(".//w:name", self.NAMESPACES)
            name = (
                name_elem.get("{%s}val" % self.NAMESPACES["w"])
                if name_elem is not None
                else style_id
            )

            based_on_elem = style_elem.find(".//w:basedOn", self.NAMESPACES)
            based_on = (
                based_on_elem.get("{%s}val" % self.NAMESPACES["w"])
                if based_on_elem is not None
                else None
            )

            styles.append(
                WordStyle(
                    style_id=style_id,
                    name=name,
                    style_type=style_type,
                    based_on=based_on,
                )
            )

        return styles

    def _extract_comments(
        self, comments_xml: Optional[ET.Element]
    ) -> List[WordComment]:
        """Extract comments from comments.xml.

        Args:
            comments_xml: Parsed comments.xml

        Returns:
            List of WordComment objects
        """
        if comments_xml is None:
            return []

        comments = []

        for comment_elem in comments_xml.findall(".//w:comment", self.NAMESPACES):
            comment_id = comment_elem.get("{%s}id" % self.NAMESPACES["w"])
            author = comment_elem.get("{%s}author" % self.NAMESPACES["w"])
            date_str = comment_elem.get("{%s}date" % self.NAMESPACES["w"])

            # Parse date
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                date = datetime.now()

            # Extract comment text
            text_parts = []
            for t_elem in comment_elem.findall(".//w:t", self.NAMESPACES):
                text_parts.append(t_elem.text or "")

            text = "".join(text_parts).strip()

            comments.append(
                WordComment(comment_id=comment_id, author=author, date=date, text=text)
            )

        return comments

    def _extract_track_changes(self, document_xml: ET.Element) -> List[TrackChange]:
        """Extract tracked changes from document.

        Args:
            document_xml: Parsed document.xml

        Returns:
            List of TrackChange objects
        """
        track_changes = []

        # Extract insertions
        for ins_elem in document_xml.findall(".//w:ins", self.NAMESPACES):
            change_id = ins_elem.get("{%s}id" % self.NAMESPACES["w"])
            author = ins_elem.get("{%s}author" % self.NAMESPACES["w"])
            date_str = ins_elem.get("{%s}date" % self.NAMESPACES["w"])

            # Extract inserted text
            text_parts = []
            for t_elem in ins_elem.findall(".//w:t", self.NAMESPACES):
                text_parts.append(t_elem.text or "")

            content = "".join(text_parts)

            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                date = datetime.now()

            track_changes.append(
                TrackChange(
                    change_id=change_id or f"ins_{len(track_changes)}",
                    author=author or "Unknown",
                    date=date,
                    change_type="insertion",
                    content=content,
                )
            )

        # Extract deletions
        for del_elem in document_xml.findall(".//w:del", self.NAMESPACES):
            change_id = del_elem.get("{%s}id" % self.NAMESPACES["w"])
            author = del_elem.get("{%s}author" % self.NAMESPACES["w"])
            date_str = del_elem.get("{%s}date" % self.NAMESPACES["w"])

            # Extract deleted text
            text_parts = []
            for t_elem in del_elem.findall(".//w:delText", self.NAMESPACES):
                text_parts.append(t_elem.text or "")

            content = "".join(text_parts)

            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                date = datetime.now()

            track_changes.append(
                TrackChange(
                    change_id=change_id or f"del_{len(track_changes)}",
                    author=author or "Unknown",
                    date=date,
                    change_type="deletion",
                    content=content,
                )
            )

        return track_changes

    def _extract_metadata(self, core_props_xml: Optional[ET.Element]) -> WordMetadata:
        """Extract metadata from core properties.

        Args:
            core_props_xml: Parsed docProps/core.xml

        Returns:
            WordMetadata object
        """
        if core_props_xml is None:
            return WordMetadata()

        metadata = WordMetadata()

        # Extract various metadata fields
        title_elem = core_props_xml.find(".//dc:title", self.NAMESPACES)
        if title_elem is not None and title_elem.text:
            metadata.title = title_elem.text

        creator_elem = core_props_xml.find(".//dc:creator", self.NAMESPACES)
        if creator_elem is not None and creator_elem.text:
            metadata.author = creator_elem.text

        subject_elem = core_props_xml.find(".//dc:subject", self.NAMESPACES)
        if subject_elem is not None and subject_elem.text:
            metadata.subject = subject_elem.text

        keywords_elem = core_props_xml.find(".//cp:keywords", self.NAMESPACES)
        if keywords_elem is not None and keywords_elem.text:
            metadata.keywords = keywords_elem.text

        created_elem = core_props_xml.find(".//dcterms:created", self.NAMESPACES)
        if created_elem is not None and created_elem.text:
            try:
                metadata.created = datetime.fromisoformat(
                    created_elem.text.replace("Z", "+00:00")
                )
            except Exception:
                pass

        modified_elem = core_props_xml.find(".//dcterms:modified", self.NAMESPACES)
        if modified_elem is not None and modified_elem.text:
            try:
                metadata.modified = datetime.fromisoformat(
                    modified_elem.text.replace("Z", "+00:00")
                )
            except Exception:
                pass

        return metadata

    def _extract_paragraph_formatting(self, p_elem: ET.Element) -> Dict[str, Any]:
        """Extract paragraph formatting properties.

        Args:
            p_elem: Paragraph XML element

        Returns:
            Dictionary of formatting properties
        """
        formatting = {}

        # Check for bold
        if p_elem.find(".//w:b", self.NAMESPACES) is not None:
            formatting["bold"] = True

        # Check for italic
        if p_elem.find(".//w:i", self.NAMESPACES) is not None:
            formatting["italic"] = True

        # Check for underline
        if p_elem.find(".//w:u", self.NAMESPACES) is not None:
            formatting["underline"] = True

        # Check alignment
        jc_elem = p_elem.find(".//w:jc", self.NAMESPACES)
        if jc_elem is not None:
            formatting["alignment"] = jc_elem.get("{%s}val" % self.NAMESPACES["w"])

        return formatting

    def _extract_numbering(self, p_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Extract paragraph numbering information.

        Args:
            p_elem: Paragraph XML element

        Returns:
            Dictionary with numbering info or None
        """
        numpr = p_elem.find(".//w:numPr", self.NAMESPACES)
        if numpr is None:
            return None

        numbering = {}

        # Extract numbering ID
        numid = numpr.find(".//w:numId", self.NAMESPACES)
        if numid is not None:
            numbering["id"] = numid.get("{%s}val" % self.NAMESPACES["w"])

        # Extract level
        ilvl = numpr.find(".//w:ilvl", self.NAMESPACES)
        if ilvl is not None:
            numbering["level"] = int(ilvl.get("{%s}val" % self.NAMESPACES["w"]))

        return numbering

    def _convert_to_markdown(
        self,
        paragraphs: List[WordParagraph],
        tables: List[WordTable],
        styles: List[WordStyle],
    ) -> str:
        """Convert document content to markdown.

        Args:
            paragraphs: List of paragraphs
            tables: List of tables
            styles: List of styles

        Returns:
            Markdown formatted content
        """
        markdown_lines = []

        # Build style map
        style_map = {s.style_id: s for s in styles}

        # Process paragraphs
        for para in paragraphs:
            # Handle headings
            if para.style and "heading" in para.style.lower():
                # Extract heading level
                level_match = re.search(r"(\d+)", para.style)
                level = int(level_match.group(1)) if level_match else 1
                markdown_lines.append(f"{'#' * level} {para.text}")

            # Handle lists
            elif para.numbering:
                indent = "  " * para.numbering.get("level", 0)
                if "bullet" in str(para.numbering.get("id", "")).lower():
                    markdown_lines.append(f"{indent}- {para.text}")
                else:
                    markdown_lines.append(f"{indent}1. {para.text}")

            # Handle formatted text
            else:
                text = para.text

                # Apply formatting
                if para.formatting.get("bold"):
                    text = f"**{text}**"
                if para.formatting.get("italic"):
                    text = f"*{text}*"
                if para.formatting.get("underline"):
                    text = f"_{text}_"

                markdown_lines.append(text)

            markdown_lines.append("")  # Empty line between paragraphs

        # Process tables
        for table in tables:
            if table.headers:
                # Add headers
                markdown_lines.append("| " + " | ".join(table.headers) + " |")
                markdown_lines.append(
                    "|" + "|".join(["---"] * len(table.headers)) + "|"
                )

            # Add rows
            for row in table.rows:
                markdown_lines.append("| " + " | ".join(row) + " |")

            markdown_lines.append("")  # Empty line after table

        return "\n".join(markdown_lines).strip()

    def _calculate_formatting_score(
        self, paragraphs: List[WordParagraph], styles: List[WordStyle]
    ) -> float:
        """Calculate how well formatting is preserved.

        Args:
            paragraphs: List of paragraphs
            styles: List of styles

        Returns:
            Score from 0.0 to 1.0
        """
        if not paragraphs:
            return 1.0

        preserved_count = 0
        total_count = len(paragraphs)

        for para in paragraphs:
            # Check if style is preserved
            if para.style:
                preserved_count += 0.5

            # Check if formatting is preserved
            if para.formatting:
                preserved_count += 0.5

        return min(preserved_count / total_count, 1.0)

    def _generate_warnings(
        self,
        paragraphs: List[WordParagraph],
        comments: List[WordComment],
        track_changes: List[TrackChange],
    ) -> List[str]:
        """Generate warnings about conversion.

        Args:
            paragraphs: List of paragraphs
            comments: List of comments
            track_changes: List of track changes

        Returns:
            List of warning messages
        """
        warnings = []

        if comments:
            warnings.append(
                f"Document contains {len(comments)} comments that may need review"
            )

        if track_changes:
            warnings.append(f"Document contains {len(track_changes)} tracked changes")

        # Check for complex formatting
        complex_formatting_count = sum(1 for p in paragraphs if len(p.formatting) > 2)
        if complex_formatting_count > 0:
            warnings.append(
                f"{complex_formatting_count} paragraphs have complex formatting that may be simplified"
            )

        return warnings
