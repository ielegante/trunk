"""Comprehensive test suite for the document conversion pipeline."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from .accuracy_tester import AccuracyTester, AccuracyTestResult
from .change_tracker import (
    ChangeEvent,
    DocumentSnapshot,
    RealTimeChangeTracker,
    TrackingConfig,
)
from .conflict_resolver import ConflictRegion, ConflictResolver
from .diff_visualizer import DiffVisualization, DocumentDiffVisualizer
from .google_docs import (
    Comment,
    ConversionResult,
    DocumentElement,
    GoogleDocsConverter,
    Suggestion,
)


class TestGoogleDocsConverter(unittest.TestCase):
    """Test cases for GoogleDocsConverter."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_credentials = Mock()
        self.converter = GoogleDocsConverter({"credentials": self.mock_credentials})

    def test_converter_initialization(self):
        """Test converter initialization."""
        self.assertEqual(self.converter.credentials, self.mock_credentials)
        self.assertTrue(self.converter.preserve_formatting)
        self.assertTrue(self.converter.preserve_comments)
        self.assertTrue(self.converter.preserve_suggestions)

    @patch("doc_processing.converters.google_docs.build")
    def test_service_initialization(self, mock_build):
        """Test Google API service initialization."""
        mock_docs_service = Mock()
        mock_drive_service = Mock()
        mock_build.side_effect = [mock_docs_service, mock_drive_service]

        converter = GoogleDocsConverter({"credentials": self.mock_credentials})
        converter._initialize_services()

        self.assertEqual(converter.docs_service, mock_docs_service)
        self.assertEqual(converter.drive_service, mock_drive_service)

    def test_document_element_creation(self):
        """Test DocumentElement creation."""
        element = DocumentElement(
            element_type="text",
            content="Hello World",
            formatting={"bold": True},
            start_index=0,
            end_index=11,
        )

        self.assertEqual(element.element_type, "text")
        self.assertEqual(element.content, "Hello World")
        self.assertTrue(element.formatting["bold"])
        self.assertEqual(element.start_index, 0)
        self.assertEqual(element.end_index, 11)

    def test_comment_creation(self):
        """Test Comment creation."""
        comment = Comment(
            id="comment_1",
            content="This is a comment",
            author="John Doe",
            created_time="2023-01-01T00:00:00Z",
            anchor_start=0,
            anchor_end=5,
        )

        self.assertEqual(comment.id, "comment_1")
        self.assertEqual(comment.content, "This is a comment")
        self.assertEqual(comment.author, "John Doe")
        self.assertEqual(comment.anchor_start, 0)
        self.assertEqual(comment.anchor_end, 5)
        self.assertEqual(comment.replies, [])

    def test_suggestion_creation(self):
        """Test Suggestion creation."""
        suggestion = Suggestion(
            id="suggestion_1",
            suggestion_type="INSERT",
            content="New content",
            author="Jane Doe",
            created_time="2023-01-01T00:00:00Z",
            start_index=10,
            end_index=10,
        )

        self.assertEqual(suggestion.id, "suggestion_1")
        self.assertEqual(suggestion.suggestion_type, "INSERT")
        self.assertEqual(suggestion.content, "New content")
        self.assertEqual(suggestion.author, "Jane Doe")
        self.assertEqual(suggestion.state, "PENDING")

    def test_extract_text_formatting(self):
        """Test text formatting extraction."""
        text_style = {
            "bold": True,
            "italic": True,
            "fontSize": {"magnitude": 12},
            "fontFamily": "Arial",
            "foregroundColor": {"color": {"rgbColor": {"red": 0.5}}},
            "link": {"url": "https://example.com"},
        }

        formatting = self.converter._extract_text_formatting(text_style)

        self.assertTrue(formatting["bold"])
        self.assertTrue(formatting["italic"])
        self.assertEqual(formatting["font_size"], 12)
        self.assertEqual(formatting["font_family"], "Arial")
        self.assertEqual(formatting["link"], "https://example.com")

    def test_apply_markdown_formatting(self):
        """Test applying Markdown formatting."""
        text = "Hello World"
        formatting = {"bold": True, "italic": True}

        result = self.converter._apply_markdown_formatting(text, formatting)

        self.assertEqual(result, "***Hello World***")

    def test_format_markdown_table(self):
        """Test Markdown table formatting."""
        table_data = [
            ["Header 1", "Header 2"],
            ["Row 1 Col 1", "Row 1 Col 2"],
            ["Row 2 Col 1", "Row 2 Col 2"],
        ]

        result = self.converter._format_markdown_table(table_data)

        expected = [
            "| Header 1 | Header 2 |",
            "| --- | --- |",
            "| Row 1 Col 1 | Row 1 Col 2 |",
            "| Row 2 Col 1 | Row 2 Col 2 |",
        ]

        self.assertEqual(result, expected)

    def test_extract_plain_text_from_markdown(self):
        """Test extracting plain text from Markdown."""
        markdown = (
            "# Header\n\n**Bold text** and *italic text*\n\n[Link](https://example.com)"
        )

        result = self.converter._extract_plain_text_from_markdown(markdown)

        self.assertIn("Header", result)
        self.assertIn("Bold text", result)
        self.assertIn("italic text", result)
        self.assertIn("Link", result)
        self.assertNotIn("**", result)
        self.assertNotIn("*", result)
        self.assertNotIn("#", result)

    def test_conversion_result_creation(self):
        """Test ConversionResult creation."""
        elements = [
            DocumentElement(
                element_type="text",
                content="Test",
                formatting={},
                start_index=0,
                end_index=4,
            )
        ]

        result = ConversionResult(
            content="# Test Document",
            elements=elements,
            comments=[],
            suggestions=[],
            metadata={"title": "Test"},
            conversion_accuracy=0.95,
        )

        self.assertEqual(result.content, "# Test Document")
        self.assertEqual(len(result.elements), 1)
        self.assertEqual(len(result.comments), 0)
        self.assertEqual(len(result.suggestions), 0)
        self.assertEqual(result.metadata["title"], "Test")
        self.assertEqual(result.conversion_accuracy, 0.95)
        self.assertEqual(result.warnings, [])


class TestChangeTracker(unittest.TestCase):
    """Test cases for RealTimeChangeTracker."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_converter = Mock(spec=GoogleDocsConverter)
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir) / "change_tracking"

        self.config = TrackingConfig(
            polling_interval=1,
            enable_content_tracking=True,
            enable_structure_tracking=True,
            enable_metadata_tracking=True,
        )

        self.tracker = RealTimeChangeTracker(
            converter=self.mock_converter,
            config=self.config,
            storage_path=self.storage_path,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        self.assertEqual(self.tracker.converter, self.mock_converter)
        self.assertEqual(self.tracker.config, self.config)
        self.assertTrue(self.tracker.storage_path.exists())
        self.assertEqual(len(self.tracker.tracked_documents), 0)
        self.assertEqual(len(self.tracker.change_history), 0)

    def test_document_snapshot_creation(self):
        """Test DocumentSnapshot creation."""
        snapshot = DocumentSnapshot(
            document_id="test_doc",
            timestamp=datetime.now(),
            content_hash="abc123",
            structure_hash="def456",
            metadata={"title": "Test"},
            elements_count=5,
            content_length=100,
        )

        self.assertEqual(snapshot.document_id, "test_doc")
        self.assertEqual(snapshot.content_hash, "abc123")
        self.assertEqual(snapshot.structure_hash, "def456")
        self.assertEqual(snapshot.elements_count, 5)
        self.assertEqual(snapshot.content_length, 100)

    def test_change_event_creation(self):
        """Test ChangeEvent creation."""
        from datetime import datetime

        event = ChangeEvent(
            document_id="test_doc",
            change_type="content",
            timestamp=datetime.now(),
            change_details={"type": "text_change"},
            author="John Doe",
        )

        self.assertEqual(event.document_id, "test_doc")
        self.assertEqual(event.change_type, "content")
        self.assertEqual(event.author, "John Doe")
        self.assertIsInstance(event.to_dict(), dict)

    def test_start_tracking(self):
        """Test starting document tracking."""
        document_ids = ["doc1", "doc2", "doc3"]

        # Mock converter response
        mock_conversion = Mock(spec=ConversionResult)
        mock_conversion.content = "# Test Document"
        mock_conversion.elements = []
        mock_conversion.metadata = {"title": "Test"}

        self.mock_converter.to_markdown.return_value = mock_conversion

        self.tracker.start_tracking(document_ids)

        self.assertEqual(len(self.tracker.tracked_documents), 3)
        self.assertIn("doc1", self.tracker.tracked_documents)
        self.assertIn("doc2", self.tracker.tracked_documents)
        self.assertIn("doc3", self.tracker.tracked_documents)

    def test_stop_tracking(self):
        """Test stopping document tracking."""
        self.tracker.tracked_documents = {"doc1", "doc2", "doc3"}

        self.tracker.stop_tracking(["doc1", "doc2"])

        self.assertEqual(len(self.tracker.tracked_documents), 1)
        self.assertIn("doc3", self.tracker.tracked_documents)

    def test_change_callback_management(self):
        """Test change callback management."""
        callback1 = Mock()
        callback2 = Mock()

        self.tracker.add_change_callback(callback1)
        self.tracker.add_change_callback(callback2)

        self.assertEqual(len(self.tracker.change_callbacks), 2)

        self.tracker.remove_change_callback(callback1)

        self.assertEqual(len(self.tracker.change_callbacks), 1)
        self.assertIn(callback2, self.tracker.change_callbacks)

    def test_tracking_config(self):
        """Test TrackingConfig functionality."""
        config = TrackingConfig(
            polling_interval=60,
            enable_content_tracking=False,
            enable_structure_tracking=True,
            webhook_endpoints=["https://example.com/webhook"],
        )

        self.assertEqual(config.polling_interval, 60)
        self.assertFalse(config.enable_content_tracking)
        self.assertTrue(config.enable_structure_tracking)
        self.assertEqual(len(config.webhook_endpoints), 1)


class TestDiffVisualizer(unittest.TestCase):
    """Test cases for DocumentDiffVisualizer."""

    def setUp(self):
        """Set up test fixtures."""
        self.visualizer = DocumentDiffVisualizer()

    def test_visualizer_initialization(self):
        """Test visualizer initialization."""
        self.assertEqual(self.visualizer.context_lines, 3)
        self.assertFalse(self.visualizer.ignore_whitespace)
        self.assertFalse(self.visualizer.ignore_case)
        self.assertTrue(self.visualizer.word_level_diff)
        self.assertTrue(self.visualizer.show_line_numbers)

    def test_create_diff(self):
        """Test creating a diff visualization."""
        old_content = "Line 1\nLine 2\nLine 3"
        new_content = "Line 1\nModified Line 2\nLine 3\nLine 4"

        diff = self.visualizer.create_diff(old_content, new_content)

        self.assertIsInstance(diff, DiffVisualization)
        self.assertTrue(len(diff.blocks) > 0)
        self.assertIsInstance(diff.statistics, dict)
        self.assertIsInstance(diff.metadata, dict)
        self.assertIsNotNone(diff.html_output)
        self.assertIsNotNone(diff.plain_output)

    def test_word_level_diff(self):
        """Test word-level diff creation."""
        old_text = "The quick brown fox"
        new_text = "The fast brown fox"

        word_changes = self.visualizer.create_word_diff(old_text, new_text)

        self.assertTrue(len(word_changes) > 0)

        # Check that changes are properly detected
        change_types = [change["type"] for change in word_changes]
        self.assertIn("removed", change_types)
        self.assertIn("added", change_types)
        self.assertIn("unchanged", change_types)

    def test_side_by_side_diff(self):
        """Test side-by-side diff creation."""
        old_content = "Original content\nLine 2"
        new_content = "Modified content\nLine 2"

        result = self.visualizer.create_side_by_side_diff(old_content, new_content)

        self.assertIsInstance(result, str)
        self.assertIn("Original content", result)
        self.assertIn("Modified content", result)

    def test_inline_diff(self):
        """Test inline diff creation."""
        old_text = "Hello world"
        new_text = "Hello beautiful world"

        result = self.visualizer.create_inline_diff(old_text, new_text)

        self.assertIsInstance(result, str)
        self.assertIn("Hello", result)
        self.assertIn("world", result)
        self.assertIn("beautiful", result)

    def test_diff_export(self):
        """Test diff export functionality."""
        old_content = "Line 1\nLine 2"
        new_content = "Line 1\nModified Line 2"

        diff = self.visualizer.create_diff(old_content, new_content)

        # Test HTML export
        html_content = self.visualizer.export_diff(diff, format="html")
        self.assertIsInstance(html_content, str)
        self.assertIn("diff-container", html_content)

        # Test plain text export
        plain_content = self.visualizer.export_diff(diff, format="plain")
        self.assertIsInstance(plain_content, str)
        self.assertIn("Document Dif", plain_content)

        # Test JSON export
        json_content = self.visualizer.export_diff(diff, format="json")
        self.assertIsInstance(json_content, str)
        parsed_json = json.loads(json_content)
        self.assertIn("blocks", parsed_json)
        self.assertIn("statistics", parsed_json)


class TestAccuracyTester(unittest.TestCase):
    """Test cases for AccuracyTester."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_converter = Mock(spec=GoogleDocsConverter)
        self.mock_diff_visualizer = Mock(spec=DocumentDiffVisualizer)
        self.tester = AccuracyTester(self.mock_converter, self.mock_diff_visualizer)

    def test_tester_initialization(self):
        """Test tester initialization."""
        self.assertEqual(self.tester.converter, self.mock_converter)
        self.assertEqual(self.tester.diff_visualizer, self.mock_diff_visualizer)
        self.assertEqual(self.tester.accuracy_threshold, 0.95)
        self.assertEqual(self.tester.content_similarity_threshold, 0.90)

    def test_accuracy_test_result_creation(self):
        """Test AccuracyTestResult creation."""
        result = AccuracyTestResult(
            test_id="test_1",
            document_id="doc_1",
            test_type="round_trip",
            passed=True,
            accuracy_score=0.97,
            metrics={"content_similarity": 0.95},
            errors=[],
            warnings=["Minor formatting issue"],
            execution_time=5.2,
            test_timestamp="2023-01-01T00:00:00",
        )

        self.assertEqual(result.test_id, "test_1")
        self.assertEqual(result.document_id, "doc_1")
        self.assertEqual(result.test_type, "round_trip")
        self.assertTrue(result.passed)
        self.assertEqual(result.accuracy_score, 0.97)
        self.assertEqual(len(result.warnings), 1)
        self.assertIsInstance(result.to_dict(), dict)

    def test_content_preservation_analysis(self):
        """Test content preservation analysis."""
        mock_conversion = Mock(spec=ConversionResult)
        mock_conversion.content = "# Header\n\nParagraph text"
        mock_conversion.elements = [Mock(element_type="text")] * 5
        mock_conversion.comments = []
        mock_conversion.suggestions = []
        mock_conversion.conversion_accuracy = 0.95

        metrics = self.tester._analyze_content_preservation(mock_conversion)

        self.assertIn("total_lines", metrics)
        self.assertIn("header_count", metrics)
        self.assertIn("paragraph_count", metrics)
        self.assertIn("total_characters", metrics)
        self.assertIn("total_words", metrics)
        self.assertIn("total_elements", metrics)
        self.assertEqual(metrics["total_elements"], 5)

    def test_formatting_preservation_analysis(self):
        """Test formatting preservation analysis."""
        mock_element = Mock()
        mock_element.formatting = {"bold": True, "italic": False}

        mock_conversion = Mock(spec=ConversionResult)
        mock_conversion.content = "**Bold text** and *italic text*"
        mock_conversion.elements = [mock_element]

        metrics = self.tester._analyze_formatting_preservation(mock_conversion)

        self.assertIn("formatted_elements", metrics)
        self.assertIn("formatting_types", metrics)
        self.assertIn("markdown_bold", metrics)
        self.assertIn("markdown_italic", metrics)

    def test_overall_accuracy_calculation(self):
        """Test overall accuracy calculation."""
        metrics = {
            "character_similarity": 0.95,
            "line_similarity": 0.90,
            "element_preservation": 0.85,
            "comment_preservation": 0.80,
            "suggestion_preservation": 0.75,
        }

        accuracy = self.tester._calculate_overall_accuracy(metrics)

        self.assertGreater(accuracy, 0.8)
        self.assertLess(accuracy, 1.0)

    def test_test_suite_creation(self):
        """Test TestSuite creation."""
        from .accuracy_tester import TestSuite

        test_results = [
            AccuracyTestResult(
                test_id="test_1",
                document_id="doc_1",
                test_type="round_trip",
                passed=True,
                accuracy_score=0.95,
                metrics={},
                errors=[],
                warnings=[],
                execution_time=1.0,
                test_timestamp="2023-01-01T00:00:00",
            )
        ]

        suite = TestSuite(
            name="Test Suite",
            description="Test description",
            tests=test_results,
            overall_score=0.95,
            pass_rate=1.0,
            execution_time=1.0,
        )

        self.assertEqual(suite.name, "Test Suite")
        self.assertEqual(len(suite.tests), 1)
        self.assertEqual(suite.overall_score, 0.95)
        self.assertEqual(suite.pass_rate, 1.0)
        self.assertIsInstance(suite.to_dict(), dict)


class TestConflictResolver(unittest.TestCase):
    """Test cases for ConflictResolver."""

    def setUp(self):
        """Set up test fixtures."""
        self.resolver = ConflictResolver()

    def test_resolver_initialization(self):
        """Test resolver initialization."""
        self.assertIsNotNone(self.resolver.diff_visualizer)
        self.assertIn("start", self.resolver.conflict_markers)
        self.assertIn("separator", self.resolver.conflict_markers)
        self.assertIn("end", self.resolver.conflict_markers)

    def test_conflict_region_creation(self):
        """Test ConflictRegion creation."""
        conflict = ConflictRegion(
            conflict_id="conflict_1",
            start_line=10,
            end_line=15,
            base_content="Base content",
            their_content="Their content",
            our_content="Our content",
            conflict_type="content",
            metadata={"author": "John Doe"},
        )

        self.assertEqual(conflict.conflict_id, "conflict_1")
        self.assertEqual(conflict.start_line, 10)
        self.assertEqual(conflict.end_line, 15)
        self.assertEqual(conflict.base_content, "Base content")
        self.assertEqual(conflict.their_content, "Their content")
        self.assertEqual(conflict.our_content, "Our content")
        self.assertEqual(conflict.conflict_type, "content")
        self.assertEqual(conflict.resolution_status, "pending")
        self.assertIsInstance(conflict.to_dict(), dict)

    def test_conflict_detection(self):
        """Test conflict detection."""
        base_content = "Line 1\nLine 2\nLine 3"
        their_content = "Line 1\nTheir Line 2\nLine 3"
        our_content = "Line 1\nOur Line 2\nLine 3"

        conflicts = self.resolver.detect_conflicts(
            base_content, their_content, our_content
        )

        self.assertTrue(len(conflicts) > 0)
        self.assertEqual(conflicts[0].conflict_type, "content")

    def test_conflict_marker_creation(self):
        """Test conflict marker creation."""
        conflict = ConflictRegion(
            conflict_id="conflict_1",
            start_line=1,
            end_line=1,
            base_content="base",
            their_content="their content",
            our_content="our content",
            conflict_type="content",
            metadata={"our_label": "ours", "their_label": "theirs"},
        )

        content = "Line 1\nLine 2\nLine 3"
        result = self.resolver.create_conflict_markers([conflict], content)

        self.assertIn("<<<<<<< ours", result)
        self.assertIn("=======", result)
        self.assertIn(">>>>>>> theirs", result)
        self.assertIn("our content", result)
        self.assertIn("their content", result)

    def test_conflict_marker_parsing(self):
        """Test conflict marker parsing."""
        content = """Line 1
<<<<<<< ours
our content
=======
their content
>>>>>>> theirs
Line 3"""

        conflicts = self.resolver.parse_conflict_markers(content)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].our_content, "our content")
        self.assertEqual(conflicts[0].their_content, "their content")

    def test_resolution_strategies(self):
        """Test different resolution strategies."""
        conflict = ConflictRegion(
            conflict_id="conflict_1",
            start_line=1,
            end_line=1,
            base_content="base",
            their_content="their content",
            our_content="our content",
            conflict_type="content",
            metadata={},
        )

        # Test "take ours" strategy
        ours_resolved = self.resolver._take_ours_resolution(conflict, "test_user")
        self.assertEqual(ours_resolved.resolution_content, "our content")
        self.assertEqual(ours_resolved.resolution_status, "resolved")

        # Test "take theirs" strategy
        theirs_resolved = self.resolver._take_theirs_resolution(conflict, "test_user")
        self.assertEqual(theirs_resolved.resolution_content, "their content")
        self.assertEqual(theirs_resolved.resolution_status, "resolved")

        # Test "merge" strategy
        merged_resolved = self.resolver._merge_resolution(conflict, "test_user")
        self.assertIn("our content", merged_resolved.resolution_content)
        self.assertIn("their content", merged_resolved.resolution_content)
        self.assertEqual(merged_resolved.resolution_status, "resolved")

    def test_conflict_resolution_creation(self):
        """Test ConflictResolution creation."""
        from .conflict_resolver import ConflictResolution

        conflicts = [
            ConflictRegion(
                conflict_id="conflict_1",
                start_line=1,
                end_line=1,
                base_content="base",
                their_content="their content",
                our_content="our content",
                conflict_type="content",
                metadata={},
                resolution_status="resolved",
                resolution_content="resolved content",
            )
        ]

        resolution = ConflictResolution(
            document_id="doc_1",
            conflicts=conflicts,
            resolved_content="Final resolved content",
            resolution_strategy="manual",
            resolution_timestamp="2023-01-01T00:00:00",
            statistics={"total_conflicts": 1, "resolved_conflicts": 1},
        )

        self.assertEqual(resolution.document_id, "doc_1")
        self.assertEqual(len(resolution.conflicts), 1)
        self.assertEqual(resolution.resolution_strategy, "manual")
        self.assertIsInstance(resolution.to_dict(), dict)

    def test_resolution_interface_creation(self):
        """Test HTML resolution interface creation."""
        conflicts = [
            ConflictRegion(
                conflict_id="conflict_1",
                start_line=1,
                end_line=1,
                base_content="base",
                their_content="their content",
                our_content="our content",
                conflict_type="content",
                metadata={},
            )
        ]

        interface = self.resolver.create_resolution_interface(conflicts)

        self.assertIsInstance(interface, str)
        self.assertIn("<!DOCTYPE html>", interface)
        self.assertIn("our content", interface)
        self.assertIn("their content", interface)
        self.assertIn("Take Ours", interface)
        self.assertIn("Take Theirs", interface)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete conversion pipeline."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir) / "test_storage"

        # Create mock services
        self.mock_converter = Mock(spec=GoogleDocsConverter)
        self.diff_visualizer = DocumentDiffVisualizer()
        self.accuracy_tester = AccuracyTester(self.mock_converter, self.diff_visualizer)
        self.conflict_resolver = ConflictResolver(self.diff_visualizer)

    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_full_conversion_pipeline(self):
        """Test the complete conversion pipeline."""
        # Mock conversion result
        mock_conversion = ConversionResult(
            content="# Test Document\n\nThis is a test document with **bold** text.",
            elements=[
                DocumentElement(
                    element_type="text",
                    content="Test Document",
                    formatting={"paragraph_style": "TITLE"},
                    start_index=0,
                    end_index=13,
                ),
                DocumentElement(
                    element_type="text",
                    content="This is a test document with bold text.",
                    formatting={"bold": True},
                    start_index=14,
                    end_index=53,
                ),
            ],
            comments=[],
            suggestions=[],
            metadata={"title": "Test Document", "author": "Test Author"},
            conversion_accuracy=0.95,
        )

        self.mock_converter.to_markdown.return_value = mock_conversion
        self.mock_converter.from_markdown.return_value = "new_doc_id"

        # Test conversion
        result = self.mock_converter.to_markdown("test_doc_id")
        self.assertIsInstance(result, ConversionResult)
        self.assertEqual(result.conversion_accuracy, 0.95)

        # Test accuracy testing
        content_test = self.accuracy_tester.test_content_preservation("test_doc_id")
        self.assertIsInstance(content_test, AccuracyTestResult)
        self.assertEqual(content_test.test_type, "content_preservation")

        # Test diff visualization
        old_content = "Original content"
        new_content = "Modified content"
        diff = self.diff_visualizer.create_diff(old_content, new_content)
        self.assertIsInstance(diff, DiffVisualization)

        # Test conflict resolution
        conflicts = self.conflict_resolver.detect_conflicts(
            "base content", "their content", "our content"
        )
        self.assertIsInstance(conflicts, list)

    def test_change_tracking_integration(self):
        """Test change tracking integration."""
        # Setup change tracker
        config = TrackingConfig(polling_interval=1)
        tracker = RealTimeChangeTracker(
            converter=self.mock_converter, config=config, storage_path=self.storage_path
        )

        # Mock conversion for snapshot creation
        mock_conversion = Mock(spec=ConversionResult)
        mock_conversion.content = "Test content"
        mock_conversion.elements = []
        mock_conversion.metadata = {"title": "Test"}

        self.mock_converter.to_markdown.return_value = mock_conversion

        # Test tracking start
        tracker.start_tracking(["test_doc"])
        self.assertIn("test_doc", tracker.tracked_documents)

        # Test document status
        status = tracker.get_document_status("test_doc")
        self.assertIn("document_id", status)
        self.assertIn("is_tracked", status)

        # Test tracking stop
        tracker.stop_tracking(["test_doc"])
        self.assertNotIn("test_doc", tracker.tracked_documents)


if __name__ == "__main__":
    unittest.main()
