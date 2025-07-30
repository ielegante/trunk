"""Comprehensive tests for Word document processing pipeline."""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from doc_processing.converters.word import WordConverter
from doc_processing.converters.word_formatter import WordFormattingPreserver
from doc_processing.converters.word_performance import (
    ProcessingMetrics,
    StreamingWordProcessor,
)
from doc_processing.converters.word_xml import (
    WordDocument,
    WordElement,
    WordStyle,
    WordXMLExtractor,
)


class TestWordXMLExtractor:
    """Tests for Word XML extraction functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = WordXMLExtractor()

    def test_extract_text_only_with_mock_document(self):
        """Test text extraction from mock Word document."""
        # Create a mock Word document
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

            # Create minimal valid Word document structure
            with zipfile.ZipFile(tmp_path, "w") as zip_file:
                # Add minimal document.xml
                document_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r>
                <w:t>Hello World</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:r>
                <w:t>This is a test document.</w:t>
            </w:r>
        </w:p>
    </w:body>
</w:document>"""
                zip_file.writestr("word/document.xml", document_xml)

        try:
            # Test text extraction
            text = self.extractor.extract_text_only(tmp_path)
            assert "Hello World" in text
            assert "This is a test document." in text
        finally:
            tmp_path.unlink()

    def test_extract_document_structure_validation(self):
        """Test document structure extraction validation."""
        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            self.extractor.extract_document(Path("nonexistent.docx"))

        # Test with invalid file format
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(b"Not a Word document")

        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                self.extractor.extract_document(tmp_path)
        finally:
            tmp_path.unlink()

    def test_get_document_statistics(self):
        """Test document statistics calculation."""
        # Create mock WordDocument
        mock_elements = [
            WordElement(
                element_type="paragraph",
                element_id="p1",
                text_content="Test paragraph",
                formatting={},
                position={"index": 0},
                children=[],
                attributes={},
            ),
            WordElement(
                element_type="table",
                element_id="t1",
                text_content="",
                formatting={},
                position={"index": 1},
                children=[],
                attributes={},
            ),
        ]

        mock_styles = {
            "Normal": WordStyle(
                style_id="Normal",
                style_name="Normal",
                style_type="paragraph",
                base_style=None,
                formatting_properties={},
                is_default=True,
            )
        }

        word_doc = WordDocument(
            document_properties={},
            styles=mock_styles,
            elements=mock_elements,
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

        stats = self.extractor.get_document_statistics(word_doc)

        assert stats["total_elements"] == 2
        assert stats["element_types"]["paragraph"] == 1
        assert stats["element_types"]["table"] == 1
        assert stats["text_statistics"]["total_paragraphs"] == 1
        assert stats["text_statistics"]["total_tables"] == 1


class TestWordFormattingPreserver:
    """Tests for Word formatting preservation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = WordFormattingPreserver()

    def test_convert_to_markdown_basic(self):
        """Test basic Word to Markdown conversion."""
        # Create mock WordDocument with simple content
        mock_elements = [
            WordElement(
                element_type="paragraph",
                element_id="p1",
                text_content="Hello World",
                formatting={},
                position={"index": 0},
                children=[
                    WordElement(
                        element_type="run",
                        element_id="r1",
                        text_content="Hello World",
                        formatting={},
                        position={"index": 0},
                        children=[],
                        attributes={},
                    )
                ],
                attributes={},
            )
        ]

        word_doc = WordDocument(
            document_properties={"core_title": "Test Document"},
            styles={},
            elements=mock_elements,
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

        markdown = self.formatter.convert_to_markdown(word_doc)

        assert "# Test Document" in markdown
        assert "Hello World" in markdown

    def test_convert_heading_to_markdown(self):
        """Test heading conversion to Markdown."""
        # Create heading element
        heading_element = WordElement(
            element_type="paragraph",
            element_id="h1",
            text_content="Main Heading",
            formatting={"paragraph": {"style": "Heading 1"}},
            position={"index": 0},
            children=[
                WordElement(
                    element_type="run",
                    element_id="r1",
                    text_content="Main Heading",
                    formatting={"character": {"bold": True, "font_size": "28"}},
                    position={"index": 0},
                    children=[],
                    attributes={},
                )
            ],
            attributes={},
        )

        word_doc = WordDocument(
            document_properties={},
            styles={},
            elements=[heading_element],
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

        markdown = self.formatter.convert_to_markdown(word_doc)
        assert "# Main Heading" in markdown

    def test_convert_from_markdown(self):
        """Test Markdown to Word conversion."""
        markdown_content = """# Main Heading

This is a **bold** paragraph with *italic* text.

## Sub Heading

- List item 1
- List item 2

| Column 1 | Column 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""

        base_styles = {}
        word_doc = self.formatter.convert_from_markdown(markdown_content, base_styles)

        assert isinstance(word_doc, WordDocument)
        assert len(word_doc.elements) > 0

        # Check that headings are properly converted
        heading_elements = [
            e
            for e in word_doc.elements
            if e.element_type == "paragraph" and "Heading" in str(e.formatting)
        ]
        assert len(heading_elements) >= 1

    def test_parse_inline_formatting(self):
        """Test inline formatting parsing."""
        text = "This is **bold** and *italic* and `code` text."
        runs = self.formatter._parse_inline_formatting(text)

        assert len(runs) > 1

        # Check that formatting is applied
        bold_runs = [r for r in runs if r.formatting.get("character", {}).get("bold")]
        italic_runs = [
            r for r in runs if r.formatting.get("character", {}).get("italic")
        ]

        assert len(bold_runs) > 0
        assert len(italic_runs) > 0

    def test_validation_formatting_preservation(self):
        """Test formatting preservation validation."""
        # Create mock original and converted documents
        original_elements = [
            WordElement(
                element_type="paragraph",
                element_id="p1",
                text_content="Test content",
                formatting={},
                position={"index": 0},
                children=[],
                attributes={},
            )
        ]

        converted_elements = [
            WordElement(
                element_type="paragraph",
                element_id="p1",
                text_content="Test content",
                formatting={},
                position={"index": 0},
                children=[],
                attributes={},
            )
        ]

        original_doc = WordDocument(
            document_properties={},
            styles={},
            elements=original_elements,
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

        converted_doc = WordDocument(
            document_properties={},
            styles={},
            elements=converted_elements,
            relationships={},
            content_types={},
            numbering={},
            themes={},
            settings={},
        )

        validation = self.formatter.validate_formatting_preservation(
            original_doc, converted_doc
        )

        assert "overall_score" in validation
        assert "element_preservation" in validation
        assert validation["overall_score"] > 0.5


class TestStreamingWordProcessor:
    """Tests for streaming Word document processing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = StreamingWordProcessor()

    def test_get_processing_statistics(self):
        """Test processing statistics calculation."""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(b"Mock Word document content")

        try:
            stats = self.processor.get_processing_statistics(tmp_path)

            assert "file_info" in stats
            assert "estimated_processing" in stats
            assert "recommendations" in stats
            assert stats["file_info"]["size_bytes"] > 0
        finally:
            tmp_path.unlink()

    def test_optimize_for_large_documents(self):
        """Test optimization configuration for large documents."""
        # Create temporary large file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            # Write enough data to trigger large document optimization
            tmp_file.write(b"x" * (50 * 1024 * 1024))  # 50MB

        try:
            optimization = self.processor.optimize_for_large_documents(tmp_path)

            assert "recommended_config" in optimization
            assert "processing_steps" in optimization
            assert optimization["recommended_config"]["processing_strategy"] in [
                "streaming",
                "parallel_streaming",
            ]
        finally:
            tmp_path.unlink()

    @patch(
        "doc_processing.converters.word_performance.StreamingWordProcessor.process_document_streaming"
    )
    def test_process_document_parallel_mock(self, mock_streaming):
        """Test parallel document processing with mocked streaming."""
        # Mock streaming results
        from doc_processing.converters.word_performance import ChunkProcessingResult

        mock_chunks = [
            ChunkProcessingResult(
                chunk_id="chunk_1",
                elements=[{"type": "paragraph", "text": "Test content"}],
                text_content="Test content",
                processing_time=0.1,
                memory_used_mb=10.0,
            )
        ]

        mock_streaming.return_value = mock_chunks

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            metrics = self.processor.process_document_parallel(tmp_path)

            assert isinstance(metrics, ProcessingMetrics)
            assert metrics.elements_processed >= 0
            assert metrics.chunk_count > 0
        finally:
            tmp_path.unlink()


class TestWordConverter:
    """Tests for complete Word converter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = WordConverter()

    def test_converter_initialization(self):
        """Test Word converter initialization."""
        assert self.converter.xml_extractor is not None
        assert self.converter.formatter is not None
        assert self.converter.streaming_processor is not None
        assert self.converter.preserve_xml_structure is True
        assert self.converter.enable_streaming is True

    def test_converter_with_custom_config(self):
        """Test Word converter with custom configuration."""
        config = {
            "preserve_xml_structure": False,
            "enable_streaming": False,
            "validation_level": "strict",
            "xml_extraction": {"preserve_formatting": False},
            "formatting": {"convert_to_markdown": False},
            "performance": {"chunk_size": 500},
        }

        converter = WordConverter(config)

        assert converter.preserve_xml_structure is False
        assert converter.enable_streaming is False
        assert converter.validation_level == "strict"

    @patch("doc_processing.converters.word.WordXMLExtractor.extract_document")
    @patch("doc_processing.converters.word.WordFormattingPreserver.convert_to_markdown")
    def test_to_markdown_standard_processing(self, mock_convert, mock_extract):
        """Test standard Word to Markdown conversion."""
        # Mock document extraction
        mock_word_doc = Mock()
        mock_extract.return_value = mock_word_doc

        # Mock markdown conversion
        mock_convert.return_value = "# Test Document\n\nTest content"

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            result = self.converter.to_markdown(tmp_path)

            assert "Test Document" in result
            assert "Test content" in result
            mock_extract.assert_called_once()
            mock_convert.assert_called_once()
        finally:
            tmp_path.unlink()

    def test_to_markdown_file_not_found(self):
        """Test Word to Markdown conversion with non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.converter.to_markdown(Path("nonexistent.docx"))

    @patch(
        "doc_processing.converters.word.WordFormattingPreserver.convert_from_markdown"
    )
    def test_from_markdown(self, mock_convert):
        """Test Markdown to Word conversion."""
        markdown_content = "# Test Document\n\nTest content"

        # Mock word document creation
        mock_word_doc = Mock()
        mock_convert.return_value = mock_word_doc

        result = self.converter.from_markdown(markdown_content)

        assert result.endswith(".docx")
        mock_convert.assert_called_once()

    def test_from_markdown_empty_content(self):
        """Test Markdown to Word conversion with empty content."""
        with pytest.raises(ValueError, match="Empty markdown content"):
            self.converter.from_markdown("")

    def test_basic_validation(self):
        """Test basic validation functionality."""
        original = "test content"
        converted = "test content converted"

        validation = self.converter._basic_validation(original, converted)

        assert validation["validation_level"] == "basic"
        assert validation["is_valid"] is True
        assert validation["original_length"] > 0
        assert validation["converted_length"] > 0

    @patch("doc_processing.converters.word.WordXMLExtractor.extract_text_only")
    def test_standard_validation(self, mock_extract_text):
        """Test standard validation with text comparison."""
        mock_extract_text.return_value = "Original text content"

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            converted = "Original text content"

            validation = self.converter._standard_validation(tmp_path, converted)

            assert validation["validation_level"] == "standard"
            assert "text_preservation" in validation
            assert validation["text_preservation"]["similarity_score"] == 1.0
        finally:
            tmp_path.unlink()

    @patch("doc_processing.converters.word.WordXMLExtractor.extract_document")
    @patch("doc_processing.converters.word.WordXMLExtractor.get_document_statistics")
    def test_strict_validation(self, mock_stats, mock_extract):
        """Test strict validation with formatting analysis."""
        # Mock document extraction
        mock_word_doc = Mock()
        mock_extract.return_value = mock_word_doc

        # Mock document statistics
        mock_stats.return_value = {
            "formatting_complexity": {"total_styles": 3},
            "text_statistics": {"total_tables": 1, "total_images": 0},
        }

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            converted = "| Table | Content |\n|-------|---------|"

            validation = self.converter._strict_validation(tmp_path, converted)

            assert validation["validation_level"] == "strict"
            assert "document_statistics" in validation
            # Table should be properly converted (contains |)
            assert validation["is_valid"] is True
        finally:
            tmp_path.unlink()

    def test_text_similarity_calculation(self):
        """Test text similarity calculation."""
        # Identical texts
        similarity = self.converter._calculate_text_similarity(
            "hello world", "hello world"
        )
        assert similarity == 1.0

        # Empty texts
        similarity = self.converter._calculate_text_similarity("", "")
        assert similarity == 1.0

        # One empty text
        similarity = self.converter._calculate_text_similarity("hello", "")
        assert similarity == 0.0

        # Similar texts
        similarity = self.converter._calculate_text_similarity(
            "hello world", "hello earth"
        )
        assert 0.0 < similarity < 1.0

    @patch("doc_processing.converters.word.WordXMLExtractor.extract_text_only")
    def test_extract_text_only(self, mock_extract):
        """Test text-only extraction."""
        mock_extract.return_value = "Extracted text content"

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            result = self.converter.extract_text_only(tmp_path)
            assert result == "Extracted text content"
            mock_extract.assert_called_once_with(tmp_path)
        finally:
            tmp_path.unlink()

    @patch(
        "doc_processing.converters.word.StreamingWordProcessor.get_processing_statistics"
    )
    def test_large_document_detection(self, mock_stats):
        """Test large document detection and processing strategy."""
        # Mock large document statistics
        mock_stats.return_value = {
            "file_info": {"size_mb": 50.0},  # Large document
            "estimated_processing": {"total_elements": 10000},
        }

        # Create temporary test file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            # Should trigger large document processing
            with patch.object(
                self.converter, "_convert_large_document_to_markdown"
            ) as mock_large:
                mock_large.return_value = "Large document markdown"

                result = self.converter.to_markdown(tmp_path)

                mock_large.assert_called_once()
                assert result == "Large document markdown"
        finally:
            tmp_path.unlink()


class TestWordProcessingIntegration:
    """Integration tests for complete Word processing pipeline."""

    def test_end_to_end_processing_mock(self):
        """Test end-to-end processing with mocked dependencies."""
        # Create minimal Word document structure for testing
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

            with zipfile.ZipFile(tmp_path, "w") as zip_file:
                # Add minimal required files
                zip_file.writestr(
                    "[Content_Types].xml", '<?xml version="1.0"?><Types/>'
                )
                zip_file.writestr(
                    "_rels/.rels", '<?xml version="1.0"?><Relationships/>'
                )
                zip_file.writestr(
                    "word/_rels/document.xml.rels",
                    '<?xml version="1.0"?><Relationships/>',
                )

                # Add minimal document
                document_xml = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p><w:r><w:t>Test Document</w:t></w:r></w:p>
        <w:p><w:r><w:t>This is test content.</w:t></w:r></w:p>
    </w:body>
</w:document>"""
                zip_file.writestr("word/document.xml", document_xml)

                # Add empty styles
                zip_file.writestr(
                    "word/styles.xml",
                    """<?xml version="1.0"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>""",
                )

        try:
            converter = WordConverter()

            # Test conversion to markdown
            markdown = converter.to_markdown(tmp_path)
            assert len(markdown) > 0
            assert "Test Document" in markdown or "This is test content" in markdown

            # Test validation
            validation = converter.validate_conversion(tmp_path, markdown)
            assert "validation_level" in validation

            # Test statistics
            stats = converter.get_document_statistics(tmp_path)
            assert "total_elements" in stats

        finally:
            tmp_path.unlink()

    def test_performance_optimization_pipeline(self):
        """Test performance optimization pipeline."""
        converter = WordConverter(
            {
                "performance": {
                    "chunk_size": 100,
                    "max_workers": 2,
                    "memory_limit_mb": 256,
                }
            }
        )

        # Create test document
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(b"x" * 1024)  # 1KB test file

        try:
            # Test optimization configuration
            optimization = converter.optimize_processing_config(tmp_path)

            assert "recommended_config" in optimization
            assert "processing_steps" in optimization

        finally:
            tmp_path.unlink()


# Fixtures for testing
@pytest.fixture
def sample_word_document():
    """Create a sample WordDocument for testing."""
    elements = [
        WordElement(
            element_type="paragraph",
            element_id="p1",
            text_content="Sample paragraph",
            formatting={},
            position={"index": 0},
            children=[],
            attributes={},
        )
    ]

    return WordDocument(
        document_properties={"core_title": "Sample Document"},
        styles={},
        elements=elements,
        relationships={},
        content_types={},
        numbering={},
        themes={},
        settings={},
    )


@pytest.fixture
def sample_markdown():
    """Create sample Markdown content for testing."""
    return """# Sample Document

This is a **sample** document with *formatting*.

## Section 2

- List item 1
- List item 2

| Table | Content |
|-------|---------|
| Cell  | Data    |
"""
