"""Tests for PDF text extraction system."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from doc_processing.converters.pdf import PDFConverter


class TestPDFConverter:
    """Test cases for PDF converter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = PDFConverter()
        self.sample_pdf_path = None

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.sample_pdf_path and Path(self.sample_pdf_path).exists():
            Path(self.sample_pdf_path).unlink()

    def test_pdf_converter_initialization(self):
        """Test PDF converter initialization with various configurations."""
        # Test default configuration
        converter = PDFConverter()
        assert converter.extraction_method == "pdfplumber"
        assert converter.preserve_layout is True
        assert converter.extract_tables is True
        assert converter.extract_images is False

        # Test custom configuration
        config = {
            "extraction_method": "pymupd",
            "preserve_layout": False,
            "extract_tables": False,
            "extract_images": True,
        }
        converter = PDFConverter(config)
        assert converter.extraction_method == "pymupd"
        assert converter.preserve_layout is False
        assert converter.extract_tables is False
        assert converter.extract_images is True

    @patch("doc_processing.converters.pdf.pdfplumber.open")
    def test_pdf_to_markdown_with_pdfplumber(self, mock_pdfplumber):
        """Test PDF to markdown conversion using pdfplumber."""
        # Mock pdfplumber PDF object
        mock_pdf = MagicMock()
        mock_pdf.metadata = {
            "Title": "Test Document",
            "Author": "Test Author",
            "Subject": "Test Subject",
        }

        # Mock page object
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is test content from the PDF."
        mock_page.extract_words.return_value = [
            {"text": "This", "x0": 100, "x1": 120, "top": 50, "bottom": 60},
            {"text": "is", "x0": 125, "x1": 135, "top": 50, "bottom": 60},
            {"text": "test", "x0": 140, "x1": 160, "top": 50, "bottom": 60},
        ]
        mock_page.extract_tables.return_value = []
        mock_page.bbox = [0, 0, 612, 792]
        mock_page.width = 612
        mock_page.height = 792

        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        # Test conversion
        result = self.converter.to_markdown("dummy_path.pd")

        assert "# Test Document" in result
        assert "**Author:** Test Author" in result
        assert "This is test content from the PDF." in result
        assert "## Page 1" in result

    @patch("doc_processing.converters.pdf.fitz.open")
    def test_pdf_to_markdown_with_pymupdf(self, mock_fitz):
        """Test PDF to markdown conversion using PyMuPDF."""
        converter = PDFConverter({"extraction_method": "pymupdf"})

        # Mock PyMuPDF document
        mock_doc = MagicMock()
        mock_doc.metadata = {"title": "Test Document", "author": "Test Author"}
        mock_doc.page_count = 1

        # Mock page
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is test content from PyMuPDF."
        mock_page.get_text.return_value = "This is test content from PyMuPDF."
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.rect = [0, 0, 612, 792]

        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.return_value = mock_doc

        # Test conversion
        result = converter.to_markdown("dummy_path.pd")

        assert "This is test content from PyMuPDF." in result
        assert "## Page 1" in result

    def test_from_markdown_returns_error(self):
        """Test that from_markdown returns appropriate error message."""
        result = self.converter.from_markdown("# Test markdown", Path("output.pd"))
        assert "ERROR: PDF is a read-only format" in result

    @patch("doc_processing.converters.pdf.pdfplumber.open")
    def test_validate_conversion(self, mock_pdfplumber):
        """Test conversion validation functionality."""
        # Mock pdfplumber for validation
        mock_pdf = MagicMock()
        mock_pdf.metadata = {"Title": "Test"}
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test content"
        mock_page.extract_words.return_value = []
        mock_page.extract_tables.return_value = []
        mock_page.bbox = [0, 0, 612, 792]
        mock_page.width = 612
        mock_page.height = 792
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        # Test validation with similar content
        original = "dummy_path.pd"
        converted = "Test content"

        result = self.converter.validate_conversion(original, converted)
        assert isinstance(result, bool)

    def test_strip_markdown_formatting(self):
        """Test markdown formatting removal."""
        markdown_text = """
        # Header
        **Bold text** and *italic text*
        - List item 1
        - List item 2
        > Quote text
        `code text`
        [Link text](http://example.com)
        ---
        """

        stripped = self.converter._strip_markdown_formatting(markdown_text)

        assert "Header" in stripped
        assert "Bold text" in stripped
        assert "italic text" in stripped
        assert "List item 1" in stripped
        assert "Quote text" in stripped
        assert "code text" in stripped
        assert "Link text" in stripped

        # Markdown syntax should be removed
        assert "**" not in stripped
        assert "*" not in stripped
        assert "- " not in stripped
        assert "> " not in stripped
        assert "`" not in stripped
        assert "[" not in stripped
        assert "---" not in stripped

    def test_calculate_similarity(self):
        """Test text similarity calculation."""
        text1 = "This is a test document with some content."
        text2 = "This is a test document with some content."

        similarity = self.converter._calculate_similarity(text1, text2)
        assert similarity == 1.0

        text3 = "This is a different document with other content."
        similarity = self.converter._calculate_similarity(text1, text3)
        assert 0.5 < similarity < 1.0

    def test_classify_line_type(self):
        """Test line type classification."""
        # Test heading classification
        assert self.converter._classify_line_type("ARTICLE I", []) == "heading"
        assert self.converter._classify_line_type("Introduction:", []) == "heading"

        # Test list item classification
        assert self.converter._classify_line_type("• First item", []) == "list_item"
        assert self.converter._classify_line_type("1. Numbered item", []) == "list_item"
        assert self.converter._classify_line_type("a) Letter item", []) == "list_item"

        # Test paragraph classification
        assert (
            self.converter._classify_line_type("This is a regular paragraph.", [])
            == "paragraph"
        )

        # Test empty line
        assert self.converter._classify_line_type("", []) == "empty"
        assert self.converter._classify_line_type("   ", []) == "empty"

    def test_is_legal_citation(self):
        """Test legal citation detection."""
        # Test valid citations
        assert self.converter._is_legal_citation("123 F.3d 456")
        assert self.converter._is_legal_citation("42 U.S.C. § 1983")
        assert self.converter._is_legal_citation("123 USC 456")

        # Test invalid citations
        assert not self.converter._is_legal_citation("This is not a citation")
        assert not self.converter._is_legal_citation("123 random text")

    def test_calculate_line_bbox(self):
        """Test bounding box calculation for word lines."""
        words = [
            {"x0": 100, "x1": 120, "top": 50, "bottom": 60},
            {"x0": 125, "x1": 145, "top": 50, "bottom": 60},
            {"x0": 150, "x1": 170, "top": 50, "bottom": 60},
        ]

        bbox = self.converter._calculate_line_bbox(words)
        assert bbox == [100, 50, 170, 60]

        # Test empty words list
        empty_bbox = self.converter._calculate_line_bbox([])
        assert empty_bbox == [0, 0, 0, 0]

    @patch("doc_processing.converters.pdf.pdfplumber.open")
    def test_extract_metadata(self, mock_pdfplumber):
        """Test PDF metadata extraction."""
        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_pdf.metadata = {
            "Title": "Test Document",
            "Author": "Test Author",
            "CreationDate": "2023-01-01",
            "ModDate": "2023-01-02",
        }
        mock_pdf.pages = []
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pd", delete=False) as tmp_file:
            tmp_file.write(b"dummy pdf content")
            self.sample_pdf_path = tmp_file.name

        metadata = self.converter.extract_metadata(self.sample_pdf_path)

        assert metadata["Title"] == "Test Document"
        assert metadata["Author"] == "Test Author"
        assert metadata["extraction_method"] == "pdfplumber"
        assert "file_size" in metadata
        assert "file_hash" in metadata

    @patch("doc_processing.converters.pdf.pdfplumber.open")
    def test_get_text_statistics(self, mock_pdfplumber):
        """Test text statistics calculation."""
        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_pdf.metadata = {}

        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = (
            "This is page one content with multiple words."
        )
        mock_page1.extract_words.return_value = []
        mock_page1.extract_tables.return_value = []
        mock_page1.bbox = [0, 0, 612, 792]
        mock_page1.width = 612
        mock_page1.height = 792

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = (
            "This is page two with different content and more words."
        )
        mock_page2.extract_words.return_value = []
        mock_page2.extract_tables.return_value = []
        mock_page2.bbox = [0, 0, 612, 792]
        mock_page2.width = 612
        mock_page2.height = 792

        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pd", delete=False) as tmp_file:
            tmp_file.write(b"dummy pdf content")
            self.sample_pdf_path = tmp_file.name

        stats = self.converter.get_text_statistics(self.sample_pdf_path)

        assert stats["pages"] == 2
        assert stats["total_words"] > 0
        assert stats["avg_words_per_page"] > 0
        assert stats["extraction_quality"] in ["good", "fair", "poor", "failed"]

    def test_format_as_markdown_with_tables(self):
        """Test markdown formatting with table data."""
        content = {
            "metadata": {"title": "Test Document", "author": "Test Author", "pages": 1},
            "pages": [{"page_number": 1, "text": "Page content", "structure": []}],
            "tables": [
                {
                    "page": 1,
                    "data": [
                        ["Header 1", "Header 2", "Header 3"],
                        ["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3"],
                        ["Row 2 Col 1", "Row 2 Col 2", "Row 2 Col 3"],
                    ],
                }
            ],
        }

        result = self.converter._format_as_markdown(content)

        assert "# Test Document" in result
        assert "## Extracted Tables" in result
        assert "| Header 1 | Header 2 | Header 3 |" in result
        assert "| Row 1 Col 1 | Row 1 Col 2 | Row 1 Col 3 |" in result

    def test_format_as_markdown_with_structure(self):
        """Test markdown formatting with structured content."""
        content = {
            "metadata": {"title": "Test Document", "pages": 1},
            "pages": [
                {
                    "page_number": 1,
                    "structure": [
                        {"type": "heading", "text": "Main Title"},
                        {"type": "paragraph", "text": "This is a paragraph."},
                        {"type": "list_item", "text": "First list item"},
                        {"type": "list_item", "text": "Second list item"},
                        {"type": "citation", "text": "42 U.S.C. § 1983"},
                    ],
                }
            ],
            "tables": [],
        }

        result = self.converter._format_as_markdown(content)

        assert "### Main Title" in result
        assert "This is a paragraph." in result
        assert "- First list item" in result
        assert "- Second list item" in result
        assert "> 42 U.S.C. § 1983" in result

    def test_error_handling_invalid_pdf(self):
        """Test error handling for invalid PDF files."""
        with pytest.raises(ValueError, match="Failed to convert PDF to markdown"):
            self.converter.to_markdown("nonexistent_file.pd")

    @patch("doc_processing.converters.pdf.hashlib.sha256")
    @patch("builtins.open")
    def test_calculate_file_hash(self, mock_open, mock_sha256):
        """Test file hash calculation."""
        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.read.side_effect = [b"chunk1", b"chunk2", b""]
        mock_open.return_value = mock_file

        # Mock hashlib
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = "test_hash_value"
        mock_sha256.return_value = mock_hash

        result = self.converter._calculate_file_hash(Path("test.pd"))

        assert result == "test_hash_value"
        assert mock_hash.update.call_count == 2  # Two chunks


@pytest.fixture
def sample_pdf_content():
    """Fixture providing sample PDF content structure."""
    return {
        "metadata": {"title": "Legal Document", "author": "Law Firm", "pages": 2},
        "pages": [
            {
                "page_number": 1,
                "text": "LEGAL AGREEMENT\n\nThis is the first page of a legal document.",
                "structure": [
                    {"type": "heading", "text": "LEGAL AGREEMENT"},
                    {
                        "type": "paragraph",
                        "text": "This is the first page of a legal document.",
                    },
                ],
            },
            {
                "page_number": 2,
                "text": "TERMS AND CONDITIONS\n\n1. First term\n2. Second term",
                "structure": [
                    {"type": "heading", "text": "TERMS AND CONDITIONS"},
                    {"type": "list_item", "text": "1. First term"},
                    {"type": "list_item", "text": "2. Second term"},
                ],
            },
        ],
        "tables": [],
    }


class TestPDFConverterIntegration:
    """Integration tests for PDF converter."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.converter = PDFConverter()

    def test_full_conversion_workflow(self, sample_pdf_content):
        """Test complete PDF conversion workflow."""
        # Test markdown formatting
        markdown = self.converter._format_as_markdown(sample_pdf_content)

        # Verify expected content
        assert "# Legal Document" in markdown
        assert "**Author:** Law Firm" in markdown
        assert "## Page 1" in markdown
        assert "## Page 2" in markdown
        assert "### LEGAL AGREEMENT" in markdown
        assert "### TERMS AND CONDITIONS" in markdown
        assert "- 1. First term" in markdown
        assert "- 2. Second term" in markdown

    def test_validation_workflow(self, sample_pdf_content):
        """Test validation workflow."""
        markdown = self.converter._format_as_markdown(sample_pdf_content)
        stripped = self.converter._strip_markdown_formatting(markdown)

        # Verify stripped content maintains essential text
        assert "Legal Document" in stripped
        assert "LEGAL AGREEMENT" in stripped
        assert "first page" in stripped
        assert "TERMS AND CONDITIONS" in stripped

    def test_statistics_calculation(self, sample_pdf_content):
        """Test statistics calculation from content."""
        full_text = (
            sample_pdf_content["pages"][0]["text"]
            + "\n\n"
            + sample_pdf_content["pages"][1]["text"]
        )

        # Manual calculation for verification
        total_words = len(full_text.split())
        total_lines = len(full_text.splitlines())
        pages = len(sample_pdf_content["pages"])

        assert total_words > 0
        assert total_lines > 0
        assert pages == 2


if __name__ == "__main__":
    pytest.main([__file__])
