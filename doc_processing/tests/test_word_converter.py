"""Tests for Word document converter."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from doc_processing.converters.word_docx import (
    TrackChange,
    WordComment,
    WordConversionResult,
    WordDocxConverter,
    WordMetadata,
    WordParagraph,
    WordStyle,
    WordTable,
)


class TestWordDocxConverter(unittest.TestCase):
    """Test WordDocxConverter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.converter = WordDocxConverter()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_test_docx(self, content_xml: str, styles_xml: str = None) -> Path:
        """Create a test .docx file.

        Args:
            content_xml: Document XML content
            styles_xml: Optional styles XML

        Returns:
            Path to created docx file
        """
        docx_path = Path(self.temp_dir) / "test.docx"

        with zipfile.ZipFile(docx_path, "w") as docx:
            # Add document.xml
            docx.writestr("word/document.xml", content_xml)

            # Add styles.xml if provided
            if styles_xml:
                docx.writestr("word/styles.xml", styles_xml)

            # Add minimal required files
            docx.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            docx.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships/>')

        return docx_path

    def test_paragraph_extraction(self):
        """Test extraction of paragraphs from Word document."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:pPr>
                        <w:pStyle w:val="Heading1"/>
                    </w:pPr>
                    <w:r>
                        <w:t>Test Heading</w:t>
                    </w:r>
                </w:p>
                <w:p>
                    <w:r>
                        <w:rPr>
                            <w:b/>
                        </w:rPr>
                        <w:t>Bold text</w:t>
                    </w:r>
                    <w:r>
                        <w:t> and normal text</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.paragraphs), 2)
        self.assertEqual(result.paragraphs[0].text, "Test Heading")
        self.assertEqual(result.paragraphs[0].style, "Heading1")
        self.assertEqual(result.paragraphs[1].text, "Bold text and normal text")
        self.assertTrue(result.paragraphs[1].formatting.get("bold"))

    def test_table_extraction(self):
        """Test extraction of tables from Word document."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:tbl>
                    <w:tr>
                        <w:tc><w:p><w:r><w:t>Header 1</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Header 2</w:t></w:r></w:p></w:tc>
                    </w:tr>
                    <w:tr>
                        <w:tc><w:p><w:r><w:t>Cell 1</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Cell 2</w:t></w:r></w:p></w:tc>
                    </w:tr>
                </w:tbl>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.tables), 1)
        table = result.tables[0]
        self.assertEqual(table.headers, ["Header 1", "Header 2"])
        self.assertEqual(table.rows, [["Cell 1", "Cell 2"]])

    def test_metadata_extraction(self):
        """Test extraction of document metadata."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>Content</w:t></w:r></w:p></w:body>
        </w:document>"""

        core_xml = """<?xml version="1.0"?>
        <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                          xmlns:dc="http://purl.org/dc/elements/1.1/"
                          xmlns:dcterms="http://purl.org/dc/terms/">
            <dc:title>Test Document</dc:title>
            <dc:creator>Test Author</dc:creator>
            <dc:subject>Test Subject</dc:subject>
            <cp:keywords>test, document</cp:keywords>
            <dcterms:created>2025-01-15T10:00:00Z</dcterms:created>
            <dcterms:modified>2025-01-15T11:00:00Z</dcterms:modified>
        </cp:coreProperties>"""

        docx_path = self.create_test_docx(document_xml)

        # Add core properties
        with zipfile.ZipFile(docx_path, "a") as docx:
            docx.writestr("docProps/core.xml", core_xml)

        result = self.converter.to_markdown(docx_path)

        self.assertEqual(result.metadata.title, "Test Document")
        self.assertEqual(result.metadata.author, "Test Author")
        self.assertEqual(result.metadata.subject, "Test Subject")
        self.assertEqual(result.metadata.keywords, "test, document")
        self.assertIsInstance(result.metadata.created, datetime)
        self.assertIsInstance(result.metadata.modified, datetime)

    def test_comment_extraction(self):
        """Test extraction of comments."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>Content with comment</w:t></w:r></w:p></w:body>
        </w:document>"""

        comments_xml = """<?xml version="1.0"?>
        <w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:comment w:id="1" w:author="John Doe" w:date="2025-01-15T10:00:00Z">
                <w:p><w:r><w:t>This needs review</w:t></w:r></w:p>
            </w:comment>
        </w:comments>"""

        docx_path = self.create_test_docx(document_xml)

        # Add comments
        with zipfile.ZipFile(docx_path, "a") as docx:
            docx.writestr("word/comments.xml", comments_xml)

        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.comments), 1)
        comment = result.comments[0]
        self.assertEqual(comment.comment_id, "1")
        self.assertEqual(comment.author, "John Doe")
        self.assertEqual(comment.text, "This needs review")

    def test_track_changes_extraction(self):
        """Test extraction of tracked changes."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r><w:t>Original text </w:t></w:r>
                    <w:ins w:id="1" w:author="Jane Smith" w:date="2025-01-15T10:00:00Z">
                        <w:r><w:t>inserted text</w:t></w:r>
                    </w:ins>
                    <w:del w:id="2" w:author="John Doe" w:date="2025-01-15T11:00:00Z">
                        <w:r><w:delText>deleted text</w:delText></w:r>
                    </w:del>
                </w:p>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.track_changes), 2)

        # Check insertion
        insertion = result.track_changes[0]
        self.assertEqual(insertion.change_type, "insertion")
        self.assertEqual(insertion.author, "Jane Smith")
        self.assertEqual(insertion.content, "inserted text")

        # Check deletion
        deletion = result.track_changes[1]
        self.assertEqual(deletion.change_type, "deletion")
        self.assertEqual(deletion.author, "John Doe")
        self.assertEqual(deletion.content, "deleted text")

    def test_markdown_conversion(self):
        """Test conversion to markdown format."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                    <w:r><w:t>Main Title</w:t></w:r>
                </w:p>
                <w:p>
                    <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
                    <w:r><w:t>Subtitle</w:t></w:r>
                </w:p>
                <w:p>
                    <w:r><w:t>Regular paragraph with </w:t></w:r>
                    <w:r><w:rPr><w:b/></w:rPr><w:t>bold</w:t></w:r>
                    <w:r><w:t> and </w:t></w:r>
                    <w:r><w:rPr><w:i/></w:rPr><w:t>italic</w:t></w:r>
                    <w:r><w:t> text.</w:t></w:r>
                </w:p>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        expected_markdown = """# Main Title

## Subtitle

Regular paragraph with **bold** and *italic* text."""

        self.assertEqual(result.content.strip(), expected_markdown)

    def test_formatting_preservation_score(self):
        """Test calculation of formatting preservation score."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Styled</w:t></w:r></w:p>
                <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Formatted</w:t></w:r></w:p>
                <w:p><w:r><w:t>Plain</w:t></w:r></w:p>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        # Should have preserved some formatting
        self.assertGreater(result.formatting_preserved, 0.5)
        self.assertLessEqual(result.formatting_preserved, 1.0)

    def test_warning_generation(self):
        """Test generation of conversion warnings."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r>
                        <w:rPr><w:b/><w:i/><w:u/><w:strike/></w:rPr>
                        <w:t>Complex formatting</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>"""

        comments_xml = """<?xml version="1.0"?>
        <w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:comment w:id="1" w:author="Test" w:date="2025-01-15T10:00:00Z">
                <w:p><w:r><w:t>Comment 1</w:t></w:r></w:p>
            </w:comment>
            <w:comment w:id="2" w:author="Test" w:date="2025-01-15T10:00:00Z">
                <w:p><w:r><w:t>Comment 2</w:t></w:r></w:p>
            </w:comment>
        </w:comments>"""

        docx_path = self.create_test_docx(document_xml)

        with zipfile.ZipFile(docx_path, "a") as docx:
            docx.writestr("word/comments.xml", comments_xml)

        result = self.converter.to_markdown(docx_path)

        # Should have warnings about comments and complex formatting
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("comments" in w for w in result.warnings))

    def test_invalid_docx_handling(self):
        """Test handling of invalid docx files."""
        # Test non-existent file
        with self.assertRaises(FileNotFoundError):
            self.converter.to_markdown("nonexistent.docx")

        # Test non-docx file
        txt_path = Path(self.temp_dir) / "test.txt"
        txt_path.write_text("Not a docx")

        with self.assertRaises(ValueError):
            self.converter.to_markdown(txt_path)

        # Test corrupted docx
        bad_docx = Path(self.temp_dir) / "bad.docx"
        bad_docx.write_bytes(b"Not a valid zip")

        with self.assertRaises(Exception):
            self.converter.to_markdown(bad_docx)

    def test_numbering_extraction(self):
        """Test extraction of numbered lists."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:pPr>
                        <w:numPr>
                            <w:ilvl w:val="0"/>
                            <w:numId w:val="1"/>
                        </w:numPr>
                    </w:pPr>
                    <w:r><w:t>First item</w:t></w:r>
                </w:p>
                <w:p>
                    <w:pPr>
                        <w:numPr>
                            <w:ilvl w:val="1"/>
                            <w:numId w:val="1"/>
                        </w:numPr>
                    </w:pPr>
                    <w:r><w:t>Nested item</w:t></w:r>
                </w:p>
            </w:body>
        </w:document>"""

        docx_path = self.create_test_docx(document_xml)
        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.paragraphs), 2)
        self.assertIsNotNone(result.paragraphs[0].numbering)
        self.assertEqual(result.paragraphs[0].numbering["level"], 0)
        self.assertEqual(result.paragraphs[1].numbering["level"], 1)

    def test_style_extraction(self):
        """Test extraction of document styles."""
        document_xml = """<?xml version="1.0"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>Content</w:t></w:r></w:p></w:body>
        </w:document>"""

        styles_xml = """<?xml version="1.0"?>
        <w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:style w:type="paragraph" w:styleId="CustomStyle">
                <w:name w:val="Custom Style"/>
                <w:basedOn w:val="Normal"/>
            </w:style>
            <w:style w:type="character" w:styleId="Emphasis">
                <w:name w:val="Emphasis"/>
            </w:style>
        </w:styles>"""

        docx_path = self.create_test_docx(document_xml, styles_xml)
        result = self.converter.to_markdown(docx_path)

        self.assertEqual(len(result.styles), 2)

        # Check custom style
        custom_style = next(s for s in result.styles if s.style_id == "CustomStyle")
        self.assertEqual(custom_style.name, "Custom Style")
        self.assertEqual(custom_style.style_type, "paragraph")
        self.assertEqual(custom_style.based_on, "Normal")


if __name__ == "__main__":
    unittest.main()
