import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
import PyPDF2

logger = logging.getLogger(__name__)


@dataclass
class PDFMetadata:
    """PDF document metadata"""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    file_size: int = 0
    content_hash: Optional[str] = None


@dataclass
class PDFPage:
    """Individual PDF page content"""

    page_number: int
    text: str
    text_length: int
    has_images: bool = False
    has_tables: bool = False


@dataclass
class PDFContent:
    """Complete PDF content extraction result"""

    metadata: PDFMetadata
    pages: List[PDFPage]
    full_text: str
    text_length: int
    extraction_method: str
    extraction_timestamp: datetime
    success: bool = True
    error_message: Optional[str] = None


class PDFExtractor:
    """PDF text extraction service with multiple fallback methods"""

    def __init__(self):
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit

    def extract_from_file(self, file_path: str) -> PDFContent:
        """Extract text and metadata from PDF file path"""
        try:
            with open(file_path, "rb") as file:
                return self.extract_from_bytes(file.read(), Path(file_path).name)
        except Exception as e:
            logger.error(f"Failed to read PDF file {file_path}: {e}")
            return PDFContent(
                metadata=PDFMetadata(),
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="file_error",
                extraction_timestamp=datetime.utcnow(),
                success=False,
                error_message=str(e),
            )

    def extract_from_bytes(
        self, pdf_bytes: bytes, filename: str = "unknown.pd"
    ) -> PDFContent:
        """Extract text and metadata from PDF bytes"""

        # Check file size
        if len(pdf_bytes) > self.max_file_size:
            return PDFContent(
                metadata=PDFMetadata(file_size=len(pdf_bytes)),
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="size_error",
                extraction_timestamp=datetime.utcnow(),
                success=False,
                error_message=f"PDF file too large: {len(pdf_bytes)} bytes",
            )

        # Calculate content hash
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Try pdfplumber first (better text extraction)
        result = self._extract_with_pdfplumber(pdf_bytes, content_hash)

        if not result.success:
            # Fallback to PyPDF2
            logger.info(f"pdfplumber failed for {filename}, trying PyPDF2")
            result = self._extract_with_pypdf2(pdf_bytes, content_hash)

        if not result.success:
            # Last resort - basic metadata only
            logger.warning(f"All extraction methods failed for {filename}")
            result = self._extract_metadata_only(pdf_bytes, content_hash)

        return result

    def _extract_with_pdfplumber(
        self, pdf_bytes: bytes, content_hash: str
    ) -> PDFContent:
        """Extract using pdfplumber (preferred method)"""
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                metadata = self._extract_metadata_pdfplumber(
                    pdf, len(pdf_bytes), content_hash
                )
                pages = []
                full_text_parts = []

                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text() or ""

                        # Check for tables and images
                        has_tables = bool(page.extract_tables())
                        has_images = bool(page.images)

                        pdf_page = PDFPage(
                            page_number=page_num,
                            text=text,
                            text_length=len(text),
                            has_images=has_images,
                            has_tables=has_tables,
                        )

                        pages.append(pdf_page)
                        full_text_parts.append(text)

                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                        # Add empty page to maintain page numbering
                        pages.append(
                            PDFPage(
                                page_number=page_num,
                                text="",
                                text_length=0,
                                has_images=False,
                                has_tables=False,
                            )
                        )

                full_text = "\n\n".join(full_text_parts)

                return PDFContent(
                    metadata=metadata,
                    pages=pages,
                    full_text=full_text,
                    text_length=len(full_text),
                    extraction_method="pdfplumber",
                    extraction_timestamp=datetime.utcnow(),
                    success=True,
                )

        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return PDFContent(
                metadata=PDFMetadata(
                    content_hash=content_hash, file_size=len(pdf_bytes)
                ),
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="pdfplumber_error",
                extraction_timestamp=datetime.utcnow(),
                success=False,
                error_message=str(e),
            )

    def _extract_with_pypdf2(self, pdf_bytes: bytes, content_hash: str) -> PDFContent:
        """Extract using PyPDF2 (fallback method)"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))

            metadata = self._extract_metadata_pypdf2(
                pdf_reader, len(pdf_bytes), content_hash
            )
            pages = []
            full_text_parts = []

            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    text = page.extract_text()

                    pdf_page = PDFPage(
                        page_number=page_num,
                        text=text,
                        text_length=len(text),
                        has_images=False,  # PyPDF2 doesn't easily detect images
                        has_tables=False,  # PyPDF2 doesn't detect tables
                    )

                    pages.append(pdf_page)
                    full_text_parts.append(text)

                except Exception as e:
                    logger.warning(
                        f"Failed to extract page {page_num} with PyPDF2: {e}"
                    )
                    pages.append(
                        PDFPage(
                            page_number=page_num,
                            text="",
                            text_length=0,
                            has_images=False,
                            has_tables=False,
                        )
                    )

            full_text = "\n\n".join(full_text_parts)

            return PDFContent(
                metadata=metadata,
                pages=pages,
                full_text=full_text,
                text_length=len(full_text),
                extraction_method="pypdf2",
                extraction_timestamp=datetime.utcnow(),
                success=True,
            )

        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            return PDFContent(
                metadata=PDFMetadata(
                    content_hash=content_hash, file_size=len(pdf_bytes)
                ),
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="pypdf2_error",
                extraction_timestamp=datetime.utcnow(),
                success=False,
                error_message=str(e),
            )

    def _extract_metadata_only(self, pdf_bytes: bytes, content_hash: str) -> PDFContent:
        """Extract basic metadata when text extraction fails"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            metadata = self._extract_metadata_pypdf2(
                pdf_reader, len(pdf_bytes), content_hash
            )

            return PDFContent(
                metadata=metadata,
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="metadata_only",
                extraction_timestamp=datetime.utcnow(),
                success=True,
                error_message="Text extraction failed, metadata only",
            )
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return PDFContent(
                metadata=PDFMetadata(
                    content_hash=content_hash, file_size=len(pdf_bytes)
                ),
                pages=[],
                full_text="",
                text_length=0,
                extraction_method="complete_failure",
                extraction_timestamp=datetime.utcnow(),
                success=False,
                error_message=str(e),
            )

    def _extract_metadata_pdfplumber(
        self, pdf, file_size: int, content_hash: str
    ) -> PDFMetadata:
        """Extract metadata using pdfplumber"""
        metadata = pdf.metadata or {}

        return PDFMetadata(
            title=metadata.get("Title"),
            author=metadata.get("Author"),
            subject=metadata.get("Subject"),
            creator=metadata.get("Creator"),
            producer=metadata.get("Producer"),
            creation_date=self._parse_pdf_date(metadata.get("CreationDate")),
            modification_date=self._parse_pdf_date(metadata.get("ModDate")),
            page_count=len(pdf.pages),
            file_size=file_size,
            content_hash=content_hash,
        )

    def _extract_metadata_pypdf2(
        self, pdf_reader, file_size: int, content_hash: str
    ) -> PDFMetadata:
        """Extract metadata using PyPDF2"""
        metadata = pdf_reader.metadata or {}

        return PDFMetadata(
            title=metadata.get("/Title"),
            author=metadata.get("/Author"),
            subject=metadata.get("/Subject"),
            creator=metadata.get("/Creator"),
            producer=metadata.get("/Producer"),
            creation_date=self._parse_pdf_date(metadata.get("/CreationDate")),
            modification_date=self._parse_pdf_date(metadata.get("/ModDate")),
            page_count=len(pdf_reader.pages),
            file_size=file_size,
            content_hash=content_hash,
        )

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse PDF date string to datetime"""
        if not date_str:
            return None

        try:
            # PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
            if date_str.startswith("D:"):
                date_str = date_str[2:]

            # Extract just the basic date/time part
            if len(date_str) >= 14:
                date_part = date_str[:14]
                return datetime.strptime(date_part, "%Y%m%d%H%M%S")
            elif len(date_str) >= 8:
                date_part = date_str[:8]
                return datetime.strptime(date_part, "%Y%m%d")
        except Exception as e:
            logger.warning(f"Failed to parse PDF date '{date_str}': {e}")

        return None


class PDFProcessor:
    """High-level PDF processing service"""

    def __init__(self, extractor: PDFExtractor):
        self.extractor = extractor

    def process_for_git_tracking(
        self, pdf_content: PDFContent, file_path: str
    ) -> Dict[str, Any]:
        """Process PDF content for git tracking"""

        # Create git-trackable representation
        git_data = {
            "file_path": file_path,
            "content_type": "pd",
            "extracted_text": pdf_content.full_text,
            "metadata": {
                "title": pdf_content.metadata.title,
                "author": pdf_content.metadata.author,
                "page_count": pdf_content.metadata.page_count,
                "file_size": pdf_content.metadata.file_size,
                "content_hash": pdf_content.metadata.content_hash,
                "creation_date": (
                    pdf_content.metadata.creation_date.isoformat()
                    if pdf_content.metadata.creation_date
                    else None
                ),
                "modification_date": (
                    pdf_content.metadata.modification_date.isoformat()
                    if pdf_content.metadata.modification_date
                    else None
                ),
                "extraction_method": pdf_content.extraction_method,
                "extraction_timestamp": pdf_content.extraction_timestamp.isoformat(),
                "text_length": pdf_content.text_length,
            },
            "pages": [
                {
                    "page_number": page.page_number,
                    "text_length": page.text_length,
                    "has_images": page.has_images,
                    "has_tables": page.has_tables,
                }
                for page in pdf_content.pages
            ],
            "processing_info": {
                "success": pdf_content.success,
                "error_message": pdf_content.error_message,
            },
        }

        return git_data

    def create_markdown_summary(self, pdf_content: PDFContent, file_path: str) -> str:
        """Create a markdown summary of the PDF for git tracking"""

        lines = [
            f"# PDF Document: {Path(file_path).name}",
            "",
            "## Metadata",
            f"- **Title**: {pdf_content.metadata.title or 'Unknown'}",
            f"- **Author**: {pdf_content.metadata.author or 'Unknown'}",
            f"- **Pages**: {pdf_content.metadata.page_count}",
            f"- **File Size**: {pdf_content.metadata.file_size:,} bytes",
            f"- **Content Hash**: {pdf_content.metadata.content_hash}",
            f"- **Extraction Method**: {pdf_content.extraction_method}",
            f"- **Text Length**: {pdf_content.text_length:,} characters",
            "",
            "## Content",
            "",
        ]

        if pdf_content.success and pdf_content.full_text:
            # Add truncated content for git tracking
            if len(pdf_content.full_text) > 10000:
                lines.extend(
                    [
                        "*Note: Content truncated for git tracking*",
                        "",
                        pdf_content.full_text[:10000],
                        "",
                        "...[Content truncated]...",
                    ]
                )
            else:
                lines.append(pdf_content.full_text)
        else:
            lines.extend(
                [
                    "*Text extraction failed or no text content available*",
                    f"Error: {pdf_content.error_message}",
                ]
            )

        return "\n".join(lines)
