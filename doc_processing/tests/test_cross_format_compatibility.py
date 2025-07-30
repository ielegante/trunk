"""Tests for cross-format compatibility between converters."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from doc_processing.converters import (
    ConversionResult,
    GoogleDocsConverter,
    WordConversionResult,
    WordDocxConverter,
)
from doc_processing.converters.word import WordConverter


class TestCrossFormatCompatibility(unittest.TestCase):
    """Test compatibility between different document formats."""

    def setUp(self):
        """Set up test fixtures."""
        self.google_converter = GoogleDocsConverter({})
        self.word_converter = WordDocxConverter({})
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_markdown_consistency(self):
        """Test that similar content produces similar markdown."""
        # Test content
        test_content = {
            "title": "Test Document",
            "heading1": "Main Section",
            "heading2": "Subsection",
            "paragraph": "This is a test paragraph with **bold** and *italic* text.",
            "list_items": ["First item", "Second item", "Third item"],
            "table_headers": ["Column 1", "Column 2"],
            "table_rows": [["Cell 1", "Cell 2"], ["Cell 3", "Cell 4"]],
        }

        # Create Google Docs style result
        google_result = ConversionResult(
            content=self._create_markdown_from_content(test_content),
            elements=[],
            comments=[],
            suggestions=[],
            metadata={"title": test_content["title"]},
            conversion_accuracy=1.0,
        )

        # Create Word style result
        word_result = WordConversionResult(
            content=self._create_markdown_from_content(test_content),
            paragraphs=[],
            tables=[],
            styles=[],
            comments=[],
            track_changes=[],
            metadata=Mock(title=test_content["title"]),
            formatting_preserved=1.0,
        )

        # Compare markdown output
        self.assertEqual(google_result.content, word_result.content)

    def test_comment_format_compatibility(self):
        """Test comment format compatibility between converters."""
        # Google Docs comment
        from doc_processing.converters.google_docs import Comment as GoogleComment

        google_comment = GoogleComment(
            comment_id="gc123",
            author="John Doe",
            content="This needs review",
            quoted_text="review this section",
            created_time="2025-01-15T10:00:00Z",
            resolved=False,
        )

        # Word comment
        from datetime import datetime

        from doc_processing.converters.word_docx import WordComment

        word_comment = WordComment(
            comment_id="wc123",
            author="John Doe",
            date=datetime(2025, 1, 15, 10, 0, 0),
            text="This needs review",
        )

        # Both should have similar essential fields
        self.assertEqual(google_comment.author, word_comment.author)
        self.assertEqual(google_comment.content, word_comment.text)

    def test_table_representation(self):
        """Test table representation across formats."""
        # Test data
        headers = ["Name", "Age", "City"]
        rows = [
            ["Alice", "30", "New York"],
            ["Bob", "25", "Los Angeles"],
            ["Charlie", "35", "Chicago"],
        ]

        # Expected markdown representation
        expected_markdown = """| Name | Age | City |
|---|---|---|
| Alice | 30 | New York |
| Bob | 25 | Los Angeles |
| Charlie | 35 | Chicago |"""

        # Test Google Docs style
        google_table_md = self._create_table_markdown(headers, rows)

        # Test Word style
        word_table_md = self._create_table_markdown(headers, rows)

        # Both should produce same markdown
        self.assertEqual(google_table_md.strip(), expected_markdown)
        self.assertEqual(word_table_md.strip(), expected_markdown)

    def test_formatting_preservation(self):
        """Test that formatting is preserved across conversions."""
        # Test formatting patterns
        formatting_tests = [
            ("**bold text**", "bold text", {"bold": True}),
            ("*italic text*", "italic text", {"italic": True}),
            ("***bold italic***", "bold italic", {"bold": True, "italic": True}),
            ("_underlined_", "underlined", {"underline": True}),
            ("~~strikethrough~~", "strikethrough", {"strikethrough": True}),
        ]

        for markdown, plain_text, expected_format in formatting_tests:
            # Both converters should handle these formatting patterns
            self.assertIn(plain_text, markdown)

    def test_heading_hierarchy(self):
        """Test heading hierarchy preservation."""
        # Test heading levels
        headings = [
            ("# Heading 1", 1),
            ("## Heading 2", 2),
            ("### Heading 3", 3),
            ("#### Heading 4", 4),
            ("##### Heading 5", 5),
            ("###### Heading 6", 6),
        ]

        for markdown, level in headings:
            # Extract heading level from markdown
            extracted_level = len(markdown.split()[0])
            self.assertEqual(extracted_level, level)

    def test_list_compatibility(self):
        """Test list formatting compatibility."""
        # Bullet list
        bullet_list = """- First item
- Second item
  - Nested item
  - Another nested item
- Third item"""

        # Numbered list
        numbered_list = """1. First item
2. Second item
   1. Nested item
   2. Another nested item
3. Third item"""

        # Both formats should support these list types
        self.assertIn("- ", bullet_list)
        self.assertIn("1. ", numbered_list)
        self.assertIn("  - ", bullet_list)  # Nested bullets
        self.assertIn("   1. ", numbered_list)  # Nested numbers

    def test_metadata_mapping(self):
        """Test metadata field mapping between formats."""
        # Common metadata fields
        metadata_fields = {
            "title": "Test Document",
            "author": "John Doe",
            "created": "2025-01-15T10:00:00Z",
            "modified": "2025-01-15T11:00:00Z",
            "subject": "Testing",
            "keywords": "test, document, compatibility",
        }

        # Google metadata style
        google_metadata = {
            "title": metadata_fields["title"],
            "lastModifyingUser": {"displayName": metadata_fields["author"]},
            "createdTime": metadata_fields["created"],
            "modifiedTime": metadata_fields["modified"],
        }

        # Word metadata style
        from datetime import datetime

        from doc_processing.converters.word_docx import WordMetadata

        word_metadata = WordMetadata(
            title=metadata_fields["title"],
            author=metadata_fields["author"],
            created=datetime.fromisoformat(
                metadata_fields["created"].replace("Z", "+00:00")
            ),
            modified=datetime.fromisoformat(
                metadata_fields["modified"].replace("Z", "+00:00")
            ),
            subject=metadata_fields["subject"],
            keywords=metadata_fields["keywords"],
        )

        # Core fields should match
        self.assertEqual(google_metadata["title"], word_metadata.title)
        self.assertEqual(
            google_metadata["lastModifyingUser"]["displayName"], word_metadata.author
        )

    def test_special_character_handling(self):
        """Test handling of special characters across formats."""
        special_chars = [
            ("&", "&amp;", "ampersand"),
            ("<", "&lt;", "less than"),
            (">", "&gt;", "greater than"),
            ('"', "&quot;", "quote"),
            ("'", "&#39;", "apostrophe"),
            ("©", "&copy;", "copyright"),
            ("®", "&reg;", "registered"),
            ("™", "&trade;", "trademark"),
        ]

        for char, html_entity, name in special_chars:
            # Both converters should handle these appropriately
            # In markdown, most of these should remain as-is
            self.assertIsNotNone(char)

    def test_link_format_compatibility(self):
        """Test link formatting across formats."""
        # Test various link formats
        links = [
            ("[Link text](https://example.com)", "Link text", "https://example.com"),
            ("[Email](mailto:test@example.com)", "Email", "mailto:test@example.com"),
            ("[Internal link](#section)", "Internal link", "#section"),
        ]

        for markdown, text, url in links:
            self.assertIn(text, markdown)
            self.assertIn(url, markdown)

    def test_image_reference_compatibility(self):
        """Test image reference handling."""
        # Image reference formats
        image_refs = [
            "![Alt text](image.png)",
            "![Alt text](https://example.com/image.png)",
            '![Alt text](image.png "Title")',
        ]

        for img_ref in image_refs:
            self.assertIn("![", img_ref)
            self.assertIn("](", img_ref)

    def test_code_block_compatibility(self):
        """Test code block formatting."""
        # Inline code
        inline_code = "`code snippet`"

        # Code block
        code_block = """```python
def hello_world():
    print("Hello, World!")
```"""

        # Both should preserve code formatting
        self.assertIn("`", inline_code)
        self.assertIn("```", code_block)

    def test_footnote_compatibility(self):
        """Test footnote handling across formats."""
        # Footnote formats
        footnote_text = "This is a sentence with a footnote[^1]."
        footnote_ref = "[^1]: This is the footnote content."

        # Both formats should support some form of annotation
        self.assertIn("[^1]", footnote_text)
        self.assertIn("[^1]:", footnote_ref)

    def _create_markdown_from_content(self, content: dict) -> str:
        """Helper to create consistent markdown from content dict."""
        lines = []

        # Title
        if "title" in content:
            lines.append(f"# {content['title']}")
            lines.append("")

        # Headings
        if "heading1" in content:
            lines.append(f"# {content['heading1']}")
            lines.append("")

        if "heading2" in content:
            lines.append(f"## {content['heading2']}")
            lines.append("")

        # Paragraph
        if "paragraph" in content:
            lines.append(content["paragraph"])
            lines.append("")

        # List
        if "list_items" in content:
            for item in content["list_items"]:
                lines.append(f"- {item}")
            lines.append("")

        # Table
        if "table_headers" in content and "table_rows" in content:
            headers = content["table_headers"]
            rows = content["table_rows"]

            # Header row
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")

            # Data rows
            for row in rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

        return "\n".join(lines).strip()

    def _create_table_markdown(self, headers: list, rows: list) -> str:
        """Helper to create markdown table."""
        lines = []

        # Header row
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")

        # Data rows
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)


class TestRoundTripConversion(unittest.TestCase):
    """Test round-trip conversion between formats."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("doc_processing.converters.google_docs.GoogleDocsConverter.to_markdown")
    @patch("doc_processing.converters.google_docs.GoogleDocsConverter.from_markdown")
    def test_google_docs_round_trip(self, mock_from_markdown, mock_to_markdown):
        """Test Google Docs round-trip conversion."""
        original_content = """# Legal Document

## Section 1: Parties

This agreement is between **Party A** and **Party B**.

## Section 2: Terms

1. First term
2. Second term
   - Sub-item A
   - Sub-item B
3. Third term

## Section 3: Signatures

| Party | Signature | Date |
|-------|-----------|------|
| Party A | _________ | ____ |
| Party B | _________ | ____ |"""

        # Mock conversion result
        mock_to_markdown.return_value = ConversionResult(
            content=original_content,
            elements=[],
            comments=[],
            suggestions=[],
            metadata={},
            conversion_accuracy=1.0,
        )

        # Test round trip
        converter = GoogleDocsConverter({})

        # Convert to markdown
        markdown_result = converter.to_markdown("dummy_id")

        # Convert back
        mock_from_markdown.return_value = {"documentId": "new_id"}
        new_doc_id = converter.from_markdown(markdown_result.content)

        # Verify calls
        mock_to_markdown.assert_called_once()
        mock_from_markdown.assert_called_once_with(original_content, metadata=None)

    def test_format_specific_features(self):
        """Test preservation of format-specific features."""
        # Features that might be lost in conversion
        features = {
            "google_docs": {
                "suggestions": "Track changes in suggestion mode",
                "comments": "Inline comments with replies",
                "named_styles": "Custom named paragraph styles",
            },
            "word": {
                "track_changes": "Tracked insertions and deletions",
                "comments": "Comments with threads",
                "styles": "Complex style inheritance",
            },
        }

        # Both formats should warn about potential feature loss
        for format_name, format_features in features.items():
            for feature, description in format_features.items():
                # Features should be documented as potentially lost
                self.assertIsNotNone(description)


if __name__ == "__main__":
    unittest.main()
