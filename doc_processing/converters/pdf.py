"""PDF text extraction converter for read-only document tracking."""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pdfplumber
from pdfplumber.page import Page

from .base import BaseConverter

logger = logging.getLogger(__name__)


class PDFConverter(BaseConverter):
    """PDF text extraction converter with metadata preservation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize PDF converter with configuration."""
        super().__init__(config)
        self.extraction_method = (
            config.get("extraction_method", "pdfplumber") if config else "pdfplumber"
        )
        self.preserve_layout = config.get("preserve_layout", True) if config else True
        self.extract_tables = config.get("extract_tables", True) if config else True
        self.extract_images = config.get("extract_images", False) if config else False

    def to_markdown(self, source: str) -> str:
        """
        Convert PDF to Markdown format.

        Args:
            source: Path to PDF file or PDF bytes

        Returns:
            Markdown representation of PDF content
        """
        try:
            if isinstance(source, str) and Path(source).exists():
                pdf_path = Path(source)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
            else:
                pdf_bytes = source if isinstance(source, bytes) else source.encode()
                pdf_path = None

            # Extract content using preferred method
            if self.extraction_method == "pymupd":
                content = self._extract_with_pymupdf(pdf_bytes, pdf_path)
            else:
                content = self._extract_with_pdfplumber(pdf_bytes, pdf_path)

            return self._format_as_markdown(content)

        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise ValueError(f"Failed to convert PDF to markdown: {e}")

    def from_markdown(self, markdown: str, target_path: Optional[Path] = None) -> str:
        """
        PDF is read-only format - conversion from markdown not supported.

        Args:
            markdown: Markdown content
            target_path: Target file path (unused)

        Returns:
            Error message explaining read-only nature
        """
        return "ERROR: PDF is a read-only format. Cannot convert from markdown to PDF."

    def validate_conversion(self, original: str, converted: str) -> bool:
        """
        Validate PDF text extraction accuracy.

        Args:
            original: Original PDF file path or content
            converted: Converted markdown content

        Returns:
            True if conversion appears accurate
        """
        try:
            # Re-extract text and compare with converted markdown
            re_extracted = self.to_markdown(original)

            # Remove markdown formatting for comparison
            original_text = self._strip_markdown_formatting(re_extracted)
            converted_text = self._strip_markdown_formatting(converted)

            # Calculate similarity (simple character-based comparison)
            similarity = self._calculate_similarity(original_text, converted_text)

            logger.info(f"PDF conversion validation similarity: {similarity:.2%}")
            return similarity > 0.95  # 95% similarity threshold

        except Exception as e:
            logger.error(f"PDF validation failed: {e}")
            return False

    def _extract_with_pdfplumber(
        self, pdf_bytes: bytes, pdf_path: Optional[Path]
    ) -> Dict[str, Any]:
        """Extract PDF content using pdfplumber library."""
        content = {
            "text": "",
            "metadata": {},
            "pages": [],
            "tables": [],
            "structure": [],
        }

        try:
            # Use path if available, otherwise use bytes
            if pdf_path:
                with pdfplumber.open(pdf_path) as pdf:
                    content = self._process_pdf_with_plumber(pdf, content)
            else:
                import io

                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    content = self._process_pdf_with_plumber(pdf, content)

        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            raise

        return content

    def _process_pdf_with_plumber(self, pdf, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF using pdfplumber and extract structured content."""
        # Extract metadata
        content["metadata"] = {
            "title": pdf.metadata.get("Title", ""),
            "author": pdf.metadata.get("Author", ""),
            "subject": pdf.metadata.get("Subject", ""),
            "creator": pdf.metadata.get("Creator", ""),
            "producer": pdf.metadata.get("Producer", ""),
            "creation_date": pdf.metadata.get("CreationDate", ""),
            "modification_date": pdf.metadata.get("ModDate", ""),
            "pages": len(pdf.pages),
        }

        # Process each page
        for page_num, page in enumerate(pdf.pages, 1):
            page_content = self._extract_page_content(page, page_num)
            content["pages"].append(page_content)
            content["text"] += page_content["text"] + "\n\n"

            # Extract tables if enabled
            if self.extract_tables:
                tables = page.extract_tables()
                for table in tables:
                    content["tables"].append(
                        {
                            "page": page_num,
                            "data": table,
                            "bbox": getattr(table, "bbox", None),
                        }
                    )

        return content

    def _extract_page_content(self, page: Page, page_num: int) -> Dict[str, Any]:
        """Extract content from a single PDF page."""
        page_content = {
            "page_number": page_num,
            "text": "",
            "bbox": page.bbox,
            "width": page.width,
            "height": page.height,
        }

        try:
            # Extract text with layout preservation
            if self.preserve_layout:
                page_content["text"] = page.extract_text(layout=True) or ""
            else:
                page_content["text"] = page.extract_text() or ""

            # Extract words with positions for better structure analysis
            words = page.extract_words()
            page_content["words"] = len(words)

            # Analyze text structure (headings, paragraphs)
            page_content["structure"] = self._analyze_text_structure(words)

        except Exception as e:
            logger.warning(f"Failed to extract content from page {page_num}: {e}")
            page_content["text"] = f"[Page {page_num} extraction failed]"

        return page_content

    def _extract_with_pymupdf(
        self, pdf_bytes: bytes, pdf_path: Optional[Path]
    ) -> Dict[str, Any]:
        """Extract PDF content using PyMuPDF library."""
        content = {
            "text": "",
            "metadata": {},
            "pages": [],
            "tables": [],
            "structure": [],
        }

        try:
            # Open PDF document
            if pdf_path:
                doc = fitz.open(pdf_path)
            else:
                doc = fitz.open(stream=pdf_bytes, filetype="pd")

            # Extract metadata
            content["metadata"] = doc.metadata
            content["metadata"]["pages"] = doc.page_count

            # Process each page
            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_content = self._extract_pymupdf_page_content(page, page_num + 1)
                content["pages"].append(page_content)
                content["text"] += page_content["text"] + "\n\n"

            doc.close()

        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            raise

        return content

    def _extract_pymupdf_page_content(self, page, page_num: int) -> Dict[str, Any]:
        """Extract content from a single PDF page using PyMuPDF."""
        page_content = {
            "page_number": page_num,
            "text": "",
            "bbox": page.rect,
            "width": page.rect.width,
            "height": page.rect.height,
        }

        try:
            # Extract text with formatting information
            text_dict = page.get_text("dict")
            page_content["text"] = page.get_text()

            # Extract structure information from text dictionary
            page_content["structure"] = self._analyze_pymupdf_structure(text_dict)

        except Exception as e:
            logger.warning(
                f"Failed to extract PyMuPDF content from page {page_num}: {e}"
            )
            page_content["text"] = f"[Page {page_num} extraction failed]"

        return page_content

    def _analyze_text_structure(self, words: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze text structure from word positions."""
        structure = []

        if not words:
            return structure

        # Group words by approximate line (similar y-coordinates)
        lines = []
        current_line = []
        last_y = None

        for word in words:
            word_y = word.get("top", 0)

            if last_y is None or abs(word_y - last_y) < 5:  # Same line threshold
                current_line.append(word)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [word]

            last_y = word_y

        if current_line:
            lines.append(current_line)

        # Analyze each line for structure
        for line in lines:
            line_text = " ".join(word.get("text", "") for word in line)
            line_structure = {
                "text": line_text,
                "type": self._classify_line_type(line_text, line),
                "bbox": self._calculate_line_bbox(line),
            }
            structure.append(line_structure)

        return structure

    def _analyze_pymupdf_structure(self, text_dict: Dict) -> List[Dict[str, Any]]:
        """Analyze text structure from PyMuPDF text dictionary."""
        structure = []

        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")

                    if line_text.strip():
                        line_structure = {
                            "text": line_text,
                            "type": self._classify_line_type(
                                line_text, line.get("spans", [])
                            ),
                            "bbox": line.get("bbox", []),
                        }
                        structure.append(line_structure)

        return structure

    def _classify_line_type(self, text: str, elements: List[Dict]) -> str:
        """Classify text line type (heading, paragraph, list item, etc.)."""
        text_stripped = text.strip()

        if not text_stripped:
            return "empty"

        # Check for heading patterns
        if len(text_stripped) < 100 and (
            text_stripped.isupper()
            or text_stripped.endswith(":")
            or any(
                text_stripped.startswith(prefix)
                for prefix in ["ARTICLE", "SECTION", "CHAPTER"]
            )
        ):
            return "heading"

        # Check for list items
        if text_stripped.startswith(("•", "-", "○", "▪")) or (
            len(text_stripped) > 1
            and text_stripped[0].isdigit()
            and text_stripped[1] in ".):"
        ):
            return "list_item"

        # Check for legal citations
        if self._is_legal_citation(text_stripped):
            return "citation"

        return "paragraph"

    def _is_legal_citation(self, text: str) -> bool:
        """Check if text appears to be a legal citation."""
        citation_patterns = [
            r"\d+\s+[A-Z][a-z]+\.?\s+\d+",  # e.g., "123 F.3d 456"
            r"[A-Z]\.?[A-Z]\.?\s*§\s*\d+",  # e.g., "U.S.C. § 123"
            r"\d+\s+[A-Z]+\s+\d+",  # e.g., "123 USC 456"
        ]

        import re

        return any(re.search(pattern, text) for pattern in citation_patterns)

    def _calculate_line_bbox(self, words: List[Dict]) -> List[float]:
        """Calculate bounding box for a line of words."""
        if not words:
            return [0, 0, 0, 0]

        x0 = min(word.get("x0", 0) for word in words)
        x1 = max(word.get("x1", 0) for word in words)
        top = min(word.get("top", 0) for word in words)
        bottom = max(word.get("bottom", 0) for word in words)

        return [x0, top, x1, bottom]

    def _format_as_markdown(self, content: Dict[str, Any]) -> str:
        """Format extracted PDF content as Markdown."""
        markdown = []

        # Add metadata header
        metadata = content.get("metadata", {})
        if metadata.get("title"):
            markdown.append(f"# {metadata['title']}\n")

        if metadata.get("author"):
            markdown.append(f"**Author:** {metadata['author']}\n")

        if metadata.get("subject"):
            markdown.append(f"**Subject:** {metadata['subject']}\n")

        markdown.append(f"**Pages:** {metadata.get('pages', 'Unknown')}\n")
        markdown.append("---\n")

        # Process pages with structure awareness
        for page in content.get("pages", []):
            page_num = page.get("page_number", 1)
            markdown.append(f"\n## Page {page_num}\n")

            # Use structured content if available
            structure = page.get("structure", [])
            if structure:
                for element in structure:
                    element_type = element.get("type", "paragraph")
                    text = element.get("text", "").strip()

                    if not text:
                        continue

                    if element_type == "heading":
                        markdown.append(f"\n### {text}\n")
                    elif element_type == "list_item":
                        markdown.append(f"- {text}\n")
                    elif element_type == "citation":
                        markdown.append(f"> {text}\n")
                    else:
                        markdown.append(f"{text}\n\n")
            else:
                # Fallback to plain text
                page_text = page.get("text", "").strip()
                if page_text:
                    markdown.append(f"{page_text}\n\n")

        # Add tables if extracted
        tables = content.get("tables", [])
        if tables:
            markdown.append("\n## Extracted Tables\n")
            for i, table in enumerate(tables, 1):
                markdown.append(
                    f"\n### Table {i} (Page {table.get('page', 'Unknown')})\n"
                )
                table_data = table.get("data", [])
                if table_data:
                    # Format as markdown table
                    if len(table_data) > 0:
                        # Header row
                        header = table_data[0]
                        markdown.append(
                            "| "
                            + " | ".join(str(cell) if cell else "" for cell in header)
                            + " |\n"
                        )
                        markdown.append(
                            "| " + " | ".join("---" for _ in header) + " |\n"
                        )

                        # Data rows
                        for row in table_data[1:]:
                            markdown.append(
                                "| "
                                + " | ".join(str(cell) if cell else "" for cell in row)
                                + " |\n"
                            )
                    markdown.append("\n")

        return "".join(markdown)

    def _strip_markdown_formatting(self, text: str) -> str:
        """Remove markdown formatting for comparison."""
        import re

        # Remove markdown syntax
        text = re.sub(r"#{1,6}\s+", "", text)  # Headers
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*(.*?)\*", r"\1", text)  # Italic
        text = re.sub(r"`(.*?)`", r"\1", text)  # Code
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # Lists
        text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)  # Quotes
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # Links
        text = re.sub(r"^\s*---+\s*$", "", text, flags=re.MULTILINE)  # Horizontal rules

        # Normalize whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)

        return text.strip()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        from difflib import SequenceMatcher

        # Normalize both texts
        text1 = " ".join(text1.split())
        text2 = " ".join(text2.split())

        # Calculate similarity using SequenceMatcher
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    def extract_metadata(self, source: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from PDF.

        Args:
            source: Path to PDF file

        Returns:
            Dictionary containing PDF metadata
        """
        try:
            if isinstance(source, str) and Path(source).exists():
                pdf_path = Path(source)
            else:
                raise ValueError("PDF metadata extraction requires file path")

            metadata = {}

            # Try pdfplumber first
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    metadata.update(pdf.metadata or {})
                    metadata["pages"] = len(pdf.pages)
                    metadata["extraction_method"] = "pdfplumber"
            except Exception:
                # Fallback to PyMuPDF
                doc = fitz.open(pdf_path)
                metadata.update(doc.metadata or {})
                metadata["pages"] = doc.page_count
                metadata["extraction_method"] = "pymupd"
                doc.close()

            # Add file information
            metadata["file_size"] = pdf_path.stat().st_size
            metadata["file_path"] = str(pdf_path)
            metadata["file_hash"] = self._calculate_file_hash(pdf_path)

            return metadata

        except Exception as e:
            logger.error(f"PDF metadata extraction failed: {e}")
            return {"error": str(e)}

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of PDF file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def get_text_statistics(self, source: str) -> Dict[str, Any]:
        """
        Get statistical information about PDF text content.

        Args:
            source: Path to PDF file

        Returns:
            Dictionary with text statistics
        """
        try:
            content = self._extract_with_pdfplumber(
                open(source, "rb").read() if isinstance(source, str) else source,
                Path(source) if isinstance(source, str) else None,
            )

            full_text = content.get("text", "")

            stats = {
                "total_characters": len(full_text),
                "total_words": len(full_text.split()),
                "total_lines": len(full_text.splitlines()),
                "pages": len(content.get("pages", [])),
                "tables": len(content.get("tables", [])),
                "avg_words_per_page": 0,
                "extraction_quality": "good",
            }

            if stats["pages"] > 0:
                stats["avg_words_per_page"] = stats["total_words"] / stats["pages"]

            # Assess extraction quality
            if stats["total_words"] == 0:
                stats["extraction_quality"] = "failed"
            elif stats["avg_words_per_page"] < 50:
                stats["extraction_quality"] = "poor"
            elif stats["avg_words_per_page"] < 200:
                stats["extraction_quality"] = "fair"

            return stats

        except Exception as e:
            logger.error(f"PDF statistics calculation failed: {e}")
            return {"error": str(e)}
