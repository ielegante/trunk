"""Tests for document converters."""

from pathlib import Path

import pytest

from doc_processing.converters import BaseConverter, GoogleDocsConverter, WordConverter


class TestBaseConverter:
    """Test the BaseConverter abstract base class."""

    def test_base_converter_cannot_be_instantiated(self):
        """Test that BaseConverter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseConverter()


class TestGoogleDocsConverter:
    """Test GoogleDocsConverter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.converter = GoogleDocsConverter()

    def test_converter_initialization(self):
        """Test converter initialization with default config."""
        converter = GoogleDocsConverter()
        assert converter.config == {}
        assert converter.api_key is None
        assert converter.preserve_formatting is True

    def test_converter_initialization_with_config(self):
        """Test converter initialization with custom config."""
        config = {
            "google_api_key": "test_key",
            "preserve_formatting": False,
        }
        converter = GoogleDocsConverter(config)
        assert converter.api_key == "test_key"
        assert converter.preserve_formatting is False

    def test_to_markdown_basic(self):
        """Test basic Google Docs to Markdown conversion."""
        converter = GoogleDocsConverter()
        result = converter.to_markdown("test_doc_id")
        assert "Google Docs Conversion" in result
        assert "test_doc_id" in result

    def test_from_markdown_basic(self):
        """Test basic Markdown to Google Docs conversion."""
        converter = GoogleDocsConverter()
        markdown = "# Test Document\n\nThis is a test."
        result = converter.from_markdown(markdown)
        assert "google_docs_id_placeholder" in result

    def test_validate_conversion_basic(self):
        """Test basic conversion validation."""
        converter = GoogleDocsConverter()
        assert converter.validate_conversion("original", "converted") is True
        assert converter.validate_conversion("", "converted") is False
        assert converter.validate_conversion("original", "") is False


class TestWordConverter:
    """Test WordConverter functionality."""

    def test_converter_initialization(self):
        """Test converter initialization with default config."""
        converter = WordConverter()
        assert converter.config == {}
        assert converter.preserve_xml_structure is True
        assert converter.handle_embedded_objects is True

    def test_converter_initialization_with_config(self):
        """Test converter initialization with custom config."""
        config = {
            "preserve_xml_structure": False,
            "handle_embedded_objects": False,
        }
        converter = WordConverter(config)
        assert converter.preserve_xml_structure is False
        assert converter.handle_embedded_objects is False

    def test_to_markdown_basic(self):
        """Test basic Word to Markdown conversion."""
        converter = WordConverter()
        result = converter.to_markdown("test_document.docx")
        assert "Word Document Conversion" in result
        assert "test_document.docx" in result

    def test_from_markdown_basic(self):
        """Test basic Markdown to Word conversion."""
        converter = WordConverter()
        markdown = "# Test Document\n\nThis is a test."
        result = converter.from_markdown(markdown)
        assert result.endswith(".docx")

    def test_from_markdown_with_target_path(self):
        """Test Markdown to Word conversion with target path."""
        converter = WordConverter()
        markdown = "# Test Document\n\nThis is a test."
        target_path = Path("custom_output.docx")
        result = converter.from_markdown(markdown, target_path)
        assert result == str(target_path)

    def test_validate_conversion_basic(self):
        """Test basic conversion validation."""
        converter = WordConverter()
        assert converter.validate_conversion("original", "converted") is True
        assert converter.validate_conversion("", "converted") is False
        assert converter.validate_conversion("original", "") is False

    def test_extract_xml_structure(self):
        """Test XML structure extraction."""
        converter = WordConverter()
        result = converter.extract_xml_structure(Path("test.docx"))
        assert "structure" in result
        assert "elements" in result
