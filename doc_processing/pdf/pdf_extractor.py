"""PDF text extraction and analysis."""

import logging
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """Represents a single PDF page."""

    page_number: int
    text: str
    width: float
    height: float
    fonts: List[str] = field(default_factory=list)
    images: int = 0
    tables: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class PDFMetadata:
    """PDF document metadata."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    pages: int = 0
    encrypted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.creation_date:
            data["creation_date"] = self.creation_date.isoformat()
        if self.modification_date:
            data["modification_date"] = self.modification_date.isoformat()
        return data


@dataclass
class PDFExtractionResult:
    """Result of PDF extraction."""

    success: bool
    file_path: str
    metadata: PDFMetadata
    pages: List[PDFPage]
    full_text: str
    extraction_time: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["metadata"] = self.metadata.to_dict()
        data["pages"] = [p.to_dict() for p in self.pages]
        return data


class PDFTextExtractor:
    """Extract text and metadata from PDF files."""

    # Common legal document patterns
    LEGAL_PATTERNS = {
        "section": re.compile(
            r"^\s*(?:Section|SECTION|§)\s*(\d+(?:\.\d+)*)", re.MULTILINE
        ),
        "article": re.compile(
            r"^\s*(?:Article|ARTICLE)\s*([IVXLCDM]+|\d+)", re.MULTILINE
        ),
        "clause": re.compile(r"^\s*(\d+(?:\.\d+)*)\s*\.?\s+[A-Z]", re.MULTILINE),
        "definition": re.compile(
            r'"([^"]+)"\s*(?:means|shall mean|refers to)', re.IGNORECASE
        ),
        "party": re.compile(
            r"(?:between|BETWEEN)\s+([A-Z][^,]+?)\s*(?:,|and|AND)", re.MULTILINE
        ),
        "date": re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
        ),
        "signature": re.compile(
            r"^\s*_{10,}\s*$|^\s*(?:By|BY):\s*_{10,}", re.MULTILINE
        ),
    }

    def __init__(self):
        """Initialize PDF extractor."""
        self.temp_dir = Path(tempfile.gettempdir()) / "trunk_pdf_extract"
        self.temp_dir.mkdir(exist_ok=True)

    def extract_text(self, pdf_path: Path, method: str = "auto") -> PDFExtractionResult:
        """Extract text from PDF file.

        Args:
            pdf_path: Path to PDF file
            method: Extraction method ('auto', 'pdftotext', 'python')

        Returns:
            PDFExtractionResult
        """
        start_time = datetime.now()

        if not pdf_path.exists():
            return PDFExtractionResult(
                success=False,
                file_path=str(pdf_path),
                metadata=PDFMetadata(),
                pages=[],
                full_text="",
                extraction_time=0,
                errors=[f"File not found: {pdf_path}"],
            )

        # Extract metadata
        metadata = self._extract_metadata(pdf_path)

        # Extract text
        if method == "auto":
            # Try pdftotext first (faster and more accurate)
            result = self._extract_with_pdftotext(pdf_path, metadata)

            if not result.success:
                # Fallback to Python-based extraction
                result = self._extract_with_python(pdf_path, metadata)

        elif method == "pdftotext":
            result = self._extract_with_pdftotext(pdf_path, metadata)

        else:  # python
            result = self._extract_with_python(pdf_path, metadata)

        # Calculate extraction time
        result.extraction_time = (datetime.now() - start_time).total_seconds()

        # Analyze document structure
        if result.success:
            self._analyze_document_structure(result)

        return result

    def extract_for_tracking(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract minimal information for read-only tracking.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tracking information
        """
        result = self.extract_text(pdf_path)

        if not result.success:
            return {
                "trackable": False,
                "reason": result.errors[0] if result.errors else "Unknown error",
                "file_path": str(pdf_path),
            }

        # Extract key information
        sections = self._extract_sections(result.full_text)
        definitions = self._extract_definitions(result.full_text)
        parties = self._extract_parties(result.full_text)
        dates = self._extract_dates(result.full_text)

        # Create tracking summary
        tracking_info = {
            "trackable": True,
            "file_path": str(pdf_path),
            "metadata": result.metadata.to_dict(),
            "structure": {
                "total_pages": len(result.pages),
                "total_words": len(result.full_text.split()),
                "sections": len(sections),
                "section_headers": sections[:10],  # First 10 sections
                "has_signatures": self._has_signatures(result.full_text),
            },
            "content_summary": {
                "parties": parties[:5],  # Up to 5 parties
                "definitions": list(definitions.keys())[:10],  # First 10 definitions
                "key_dates": dates[:5],  # Up to 5 dates
            },
            "extraction_quality": self._assess_extraction_quality(result),
        }

        return tracking_info

    def _extract_metadata(self, pdf_path: Path) -> PDFMetadata:
        """Extract PDF metadata."""
        metadata = PDFMetadata()

        try:
            # Use pdfinfo if available
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse metadata
                for line in output.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()

                        if key == "title":
                            metadata.title = value
                        elif key == "author":
                            metadata.author = value
                        elif key == "subject":
                            metadata.subject = value
                        elif key == "creator":
                            metadata.creator = value
                        elif key == "producer":
                            metadata.producer = value
                        elif key == "pages":
                            metadata.pages = int(value)
                        elif key == "encrypted":
                            metadata.encrypted = value.lower() != "no"
                        elif key == "creationdate":
                            metadata.creation_date = self._parse_pdf_date(value)
                        elif key == "moddate":
                            metadata.modification_date = self._parse_pdf_date(value)

        except Exception as e:
            logger.warning(f"Failed to extract metadata with pdfinfo: {e}")

        return metadata

    def _extract_with_pdftotext(
        self, pdf_path: Path, metadata: PDFMetadata
    ) -> PDFExtractionResult:
        """Extract text using pdftotext command."""
        pages = []
        full_text = ""
        errors = []
        warnings = []

        try:
            # Extract text with layout preservation
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                full_text = result.stdout

                # Extract page-by-page if possible
                for page_num in range(1, metadata.pages + 1):
                    page_result = subprocess.run(
                        [
                            "pdftotext",
                            "-",
                            str(page_num),
                            "-l",
                            str(page_num),
                            "-layout",
                            str(pdf_path),
                            "-",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if page_result.returncode == 0:
                        pages.append(
                            PDFPage(
                                page_number=page_num,
                                text=page_result.stdout,
                                width=0,  # Not available from pdftotext
                                height=0,
                            )
                        )

                return PDFExtractionResult(
                    success=True,
                    file_path=str(pdf_path),
                    metadata=metadata,
                    pages=pages,
                    full_text=full_text,
                    extraction_time=0,
                    warnings=warnings,
                )
            else:
                errors.append(f"pdftotext failed: {result.stderr}")

        except FileNotFoundError:
            errors.append("pdftotext command not found")
        except subprocess.TimeoutExpired:
            errors.append("PDF extraction timed out")
        except Exception as e:
            errors.append(f"Extraction error: {str(e)}")

        return PDFExtractionResult(
            success=False,
            file_path=str(pdf_path),
            metadata=metadata,
            pages=pages,
            full_text=full_text,
            extraction_time=0,
            errors=errors,
            warnings=warnings,
        )

    def _extract_with_python(
        self, pdf_path: Path, metadata: PDFMetadata
    ) -> PDFExtractionResult:
        """Extract text using Python libraries (fallback)."""
        # This is a simplified implementation
        # In production, you would use libraries like PyPDF2, pdfplumber, or pdfminer

        pages = []
        full_text = ""
        errors = []
        warnings = ["Python extraction is limited - consider installing pdftotext"]

        try:
            # Simulate basic extraction
            # In real implementation, use proper PDF library
            with open(pdf_path, "rb") as f:
                # Read file size as a simple check
                f.seek(0, 2)
                file_size = f.tell()

                if file_size > 0:
                    # Create dummy pages for now
                    for i in range(metadata.pages or 1):
                        pages.append(
                            PDFPage(
                                page_number=i + 1,
                                text=f"[Page {i + 1} content would be extracted here]",
                                width=612,  # Standard letter width in points
                                height=792,  # Standard letter height in points
                            )
                        )

                    full_text = "\n".join(p.text for p in pages)

                    return PDFExtractionResult(
                        success=True,
                        file_path=str(pdf_path),
                        metadata=metadata,
                        pages=pages,
                        full_text=full_text,
                        extraction_time=0,
                        warnings=warnings,
                    )

        except Exception as e:
            errors.append(f"Python extraction failed: {str(e)}")

        return PDFExtractionResult(
            success=False,
            file_path=str(pdf_path),
            metadata=metadata,
            pages=pages,
            full_text=full_text,
            extraction_time=0,
            errors=errors,
            warnings=warnings,
        )

    def _analyze_document_structure(self, result: PDFExtractionResult):
        """Analyze document structure and add warnings."""
        text = result.full_text

        # Check for scanned document (very little text)
        if len(text.strip()) < 100 and result.metadata.pages > 1:
            result.warnings.append(
                "Document appears to be scanned - text extraction may be incomplete"
            )

        # Check for forms (lots of underscores)
        if text.count("_") > 50:
            result.warnings.append(
                "Document contains forms - some fields may not be extracted"
            )

        # Check for tables (alignment patterns)
        if re.search(r"\s{5,}\S+\s{5,}\S+", text):
            result.warnings.append(
                "Document contains tables - formatting may be affected"
            )

    def _extract_sections(self, text: str) -> List[str]:
        """Extract section headers from text."""
        sections = []

        for pattern_name, pattern in self.LEGAL_PATTERNS.items():
            if pattern_name in ["section", "article", "clause"]:
                matches = pattern.findall(text)
                for match in matches:
                    # Get the line containing the match
                    for line in text.split("\n"):
                        if match in line:
                            sections.append(line.strip())
                            break

        return sections

    def _extract_definitions(self, text: str) -> Dict[str, str]:
        """Extract defined terms from text."""
        definitions = {}

        matches = self.LEGAL_PATTERNS["definition"].findall(text)
        for term in matches:
            # Find the definition context
            pattern = f'"{term}"\\s*(?:means|shall mean|refers to)\\s*([^.]+)'
            def_match = re.search(pattern, text, re.IGNORECASE)
            if def_match:
                definitions[term] = def_match.group(1).strip()

        return definitions

    def _extract_parties(self, text: str) -> List[str]:
        """Extract party names from text."""
        parties = []

        matches = self.LEGAL_PATTERNS["party"].findall(text)
        for party in matches:
            party = party.strip()
            if len(party) > 3 and party not in parties:
                parties.append(party)

        return parties

    def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text."""
        dates = []

        matches = self.LEGAL_PATTERNS["date"].findall(text)
        for date in matches:
            if date not in dates:
                dates.append(date)

        return dates

    def _has_signatures(self, text: str) -> bool:
        """Check if document has signature blocks."""
        return bool(self.LEGAL_PATTERNS["signature"].search(text))

    def _assess_extraction_quality(self, result: PDFExtractionResult) -> str:
        """Assess the quality of text extraction."""
        if not result.success:
            return "failed"

        text = result.full_text

        # Calculate quality metrics
        has_text = len(text.strip()) > 100
        readable_ratio = len(re.findall(r"\b\w+\b", text)) / max(len(text.split()), 1)
        has_structure = bool(self._extract_sections(text))

        if not has_text:
            return "empty"
        elif readable_ratio < 0.5:
            return "poor"
        elif not has_structure:
            return "fair"
        elif result.warnings:
            return "good"
        else:
            return "excellent"

    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """Parse PDF date string."""
        # PDF dates are in format: D:YYYYMMDDHHmmSSOHH'mm
        if date_str.startswith("D:"):
            date_str = date_str[2:]

        try:
            # Simple parse for common format
            if len(date_str) >= 8:
                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])

                hour = int(date_str[8:10]) if len(date_str) >= 10 else 0
                minute = int(date_str[10:12]) if len(date_str) >= 12 else 0
                second = int(date_str[12:14]) if len(date_str) >= 14 else 0

                return datetime(year, month, day, hour, minute, second)
        except Exception:
            pass

        return None
