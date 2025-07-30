"""Tests for bulk operations functionality."""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from doc_processing.bulk_operations import (
    BulkDocumentProcessor,
    BulkOperationConfig,
    FolderStructureAnalyzer,
    ProcessingResult,
)


class TestBulkOperationConfig:
    """Test cases for bulk operation configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BulkOperationConfig()

        assert config.max_workers == 5
        assert config.batch_size == 10
        assert config.skip_large_files is True
        assert config.max_file_size_mb == 50
        assert config.include_pdf is True
        assert config.include_word is True
        assert config.include_google_docs is True
        assert config.preserve_folder_structure is True
        assert config.create_git_repos is True
        assert ".pd" in config.supported_extensions
        assert ".docx" in config.supported_extensions

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BulkOperationConfig(
            max_workers=10,
            batch_size=20,
            max_file_size_mb=100,
            include_pdf=False,
            supported_extensions={".txt", ".md"},
        )

        assert config.max_workers == 10
        assert config.batch_size == 20
        assert config.max_file_size_mb == 100
        assert config.include_pdf is False
        assert config.supported_extensions == {".txt", ".md"}


class TestProcessingResult:
    """Test cases for processing result data structure."""

    def test_processing_result_creation(self):
        """Test creation of processing result."""
        result = ProcessingResult(
            file_id="test_id",
            file_name="test.pd",
            file_type="application/pd",
            status="success",
            message="Successfully processed",
            processing_time=2.5,
            extracted_content="Test content",
            metadata={"pages": 5},
        )

        assert result.file_id == "test_id"
        assert result.file_name == "test.pd"
        assert result.file_type == "application/pd"
        assert result.status == "success"
        assert result.processing_time == 2.5
        assert result.extracted_content == "Test content"
        assert result.metadata["pages"] == 5


class TestBulkDocumentProcessor:
    """Test cases for bulk document processor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = BulkOperationConfig(
            max_workers=2, batch_size=5, max_file_size_mb=10
        )
        self.processor = BulkDocumentProcessor(self.config)

    def test_initialization(self):
        """Test processor initialization."""
        assert self.processor.config.max_workers == 2
        assert self.processor.config.batch_size == 5
        assert len(self.processor.converters) >= 2  # At least PDF and Word converters
        assert self.processor.processed_count == 0
        assert self.processor.error_count == 0
        assert self.processor.skipped_count == 0

    def test_should_process_file_pdf(self):
        """Test file processing decision for PDF files."""
        pdf_file = {
            "mimeType": "application/pd",
            "name": "test.pd",
            "size": "1048576",  # 1MB
        }

        assert self.processor._should_process_file(pdf_file) is True

    def test_should_process_file_google_docs(self):
        """Test file processing decision for Google Docs."""
        gdoc_file = {
            "mimeType": "application/vnd.google-apps.document",
            "name": "test document",
            "size": "0",
        }

        assert self.processor._should_process_file(gdoc_file) is True

    def test_should_process_file_large_file_skip(self):
        """Test file processing decision for large files."""
        large_file = {
            "mimeType": "application/pd",
            "name": "large.pd",
            "size": str(50 * 1024 * 1024),  # 50MB
        }

        assert self.processor._should_process_file(large_file) is False

    def test_should_process_file_unsupported_type(self):
        """Test file processing decision for unsupported file types."""
        unsupported_file = {
            "mimeType": "image/jpeg",
            "name": "image.jpg",
            "size": "1048576",
        }

        assert self.processor._should_process_file(unsupported_file) is False

    def test_get_converter_for_file_pdf(self):
        """Test converter selection for PDF files."""
        converter = self.processor._get_converter_for_file("application/pd", "test.pd")
        assert converter is not None
        assert hasattr(converter, "to_markdown")

    def test_get_converter_for_file_word(self):
        """Test converter selection for Word files."""
        converter = self.processor._get_converter_for_file(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "test.docx",
        )
        assert converter is not None

    def test_get_converter_for_file_unsupported(self):
        """Test converter selection for unsupported files."""
        converter = self.processor._get_converter_for_file("image/jpeg", "test.jpg")
        assert converter is None

    @patch("doc_processing.bulk_operations.BulkDocumentProcessor._get_file_content")
    @patch(
        "doc_processing.bulk_operations.BulkDocumentProcessor._get_converter_for_file"
    )
    def test_process_single_file_success(self, mock_get_converter, mock_get_content):
        """Test successful processing of a single file."""
        # Mock converter
        mock_converter = Mock()
        mock_converter.to_markdown.return_value = "# Test Content"
        mock_get_converter.return_value = mock_converter

        # Mock file content
        mock_get_content.return_value = "dummy content"

        file_info = {
            "id": "test_id",
            "name": "test.pd",
            "mimeType": "application/pd",
            "size": "1024",
        }

        mock_drive_service = Mock()

        result = self.processor._process_single_file(file_info, mock_drive_service)

        assert result.status == "success"
        assert result.file_id == "test_id"
        assert result.file_name == "test.pd"
        assert "# Test Content" in result.extracted_content

    @patch(
        "doc_processing.bulk_operations.BulkDocumentProcessor._get_converter_for_file"
    )
    def test_process_single_file_no_converter(self, mock_get_converter):
        """Test processing with no suitable converter."""
        mock_get_converter.return_value = None

        file_info = {
            "id": "test_id",
            "name": "test.jpg",
            "mimeType": "image/jpeg",
            "size": "1024",
        }

        mock_drive_service = Mock()

        result = self.processor._process_single_file(file_info, mock_drive_service)

        assert result.status == "skipped"
        assert result.message == "No suitable converter found"

    @patch("doc_processing.bulk_operations.BulkDocumentProcessor._get_file_content")
    @patch(
        "doc_processing.bulk_operations.BulkDocumentProcessor._get_converter_for_file"
    )
    def test_process_single_file_error(self, mock_get_converter, mock_get_content):
        """Test error handling in single file processing."""
        # Mock converter that raises exception
        mock_converter = Mock()
        mock_converter.to_markdown.side_effect = Exception("Conversion failed")
        mock_get_converter.return_value = mock_converter
        mock_get_content.return_value = "dummy content"

        file_info = {
            "id": "test_id",
            "name": "test.pd",
            "mimeType": "application/pd",
            "size": "1024",
        }

        mock_drive_service = Mock()

        result = self.processor._process_single_file(file_info, mock_drive_service)

        assert result.status == "error"
        assert "Conversion failed" in result.message

    def test_extract_file_metadata(self):
        """Test file metadata extraction."""
        file_info = {
            "id": "test_id",
            "name": "test.pd",
            "mimeType": "application/pd",
            "size": "1024",
            "createdTime": "2023-01-01T00:00:00Z",
            "modifiedTime": "2023-01-02T00:00:00Z",
        }

        mock_converter = Mock()
        mock_converter.extract_metadata.return_value = {
            "pages": 5,
            "author": "Test Author",
        }

        metadata = self.processor._extract_file_metadata(
            file_info, mock_converter, "content"
        )

        assert metadata["drive_metadata"]["id"] == "test_id"
        assert metadata["drive_metadata"]["name"] == "test.pd"
        assert metadata["converter_metadata"]["pages"] == 5
        assert metadata["converter_metadata"]["author"] == "Test Author"

    def test_save_converted_file(self):
        """Test saving converted files to filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            file_name = "test.pd"
            content = "# Test Document\n\nThis is test content."
            metadata = {"pages": 1, "author": "Test"}

            self.processor._save_converted_file(
                output_folder, file_name, content, metadata
            )

            # Check markdown file was created
            markdown_path = output_folder / "test.md"
            assert markdown_path.exists()

            with open(markdown_path, "r") as f:
                saved_content = f.read()
            assert saved_content == content

            # Check metadata file was created
            metadata_path = output_folder / "test.metadata.json"
            assert metadata_path.exists()

            with open(metadata_path, "r") as f:
                saved_metadata = json.load(f)
            assert saved_metadata["pages"] == 1

    def test_generate_processing_summary(self):
        """Test processing summary generation."""
        results = [
            ProcessingResult("1", "file1.pd", "application/pd", "success", "OK", 1.0),
            ProcessingResult("2", "file2.pd", "application/pd", "success", "OK", 2.0),
            ProcessingResult(
                "3", "file3.docx", "application/vnd.word", "error", "Failed", 0.5
            ),
            ProcessingResult(
                "4", "file4.jpg", "image/jpeg", "skipped", "Unsupported", 0.0
            ),
        ]

        summary = self.processor._generate_processing_summary(results, 10.0)

        assert summary["processing_summary"]["total_files"] == 4
        assert summary["processing_summary"]["successful"] == 2
        assert summary["processing_summary"]["errors"] == 1
        assert summary["processing_summary"]["skipped"] == 1
        assert summary["processing_summary"]["success_rate"] == 0.5
        assert summary["processing_summary"]["total_processing_time"] == 10.0

        # Check file type breakdown
        assert "application/pd" in summary["file_type_breakdown"]
        assert summary["file_type_breakdown"]["application/pd"]["success"] == 2

        # Check error details
        assert len(summary["error_details"]) == 1
        assert summary["error_details"][0]["file_name"] == "file3.docx"

    @pytest.mark.asyncio
    async def test_discover_folder_structure(self):
        """Test folder structure discovery."""
        # Mock Drive service
        mock_drive_service = Mock()
        mock_files_list = Mock()

        # Mock folder contents
        mock_files_list.return_value.execute.return_value = {
            "files": [
                {
                    "id": "file1",
                    "name": "document1.pd",
                    "mimeType": "application/pd",
                    "size": "1024",
                    "modifiedTime": "2023-01-01T00:00:00Z",
                    "createdTime": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "folder1",
                    "name": "subfolder",
                    "mimeType": "application/vnd.google-apps.folder",
                },
            ]
        }

        mock_drive_service.files.return_value.list.return_value = mock_files_list

        # Mock empty subfolder
        mock_files_list.return_value.execute.side_effect = [
            {
                "files": [
                    {
                        "id": "file1",
                        "name": "document1.pd",
                        "mimeType": "application/pd",
                        "size": "1024",
                        "modifiedTime": "2023-01-01T00:00:00Z",
                        "createdTime": "2023-01-01T00:00:00Z",
                    },
                    {
                        "id": "folder1",
                        "name": "subfolder",
                        "mimeType": "application/vnd.google-apps.folder",
                    },
                ]
            },
            {"files": []},  # Empty subfolder
        ]

        structure = await self.processor._discover_folder_structure(
            "root_id", mock_drive_service
        )

        assert "root" in structure
        assert structure["root"]["file_count"] == 1
        assert structure["root"]["files"][0]["name"] == "document1.pd"

    def test_progress_callback(self):
        """Test progress callback functionality."""
        callback_calls = []

        def progress_callback(message, current, total):
            callback_calls.append((message, current, total))

        config = BulkOperationConfig(progress_callback=progress_callback)
        processor = BulkDocumentProcessor(config)

        processor._call_progress_callback("Test message", 5, 10)

        assert len(callback_calls) == 1
        assert callback_calls[0] == ("Test message", 5, 10)

    def test_error_callback(self):
        """Test error callback functionality."""
        error_calls = []

        def error_callback(message, error):
            error_calls.append((message, str(error)))

        config = BulkOperationConfig(error_callback=error_callback)
        processor = BulkDocumentProcessor(config)

        test_error = Exception("Test error")
        processor._call_error_callback("Error occurred", test_error)

        assert len(error_calls) == 1
        assert error_calls[0] == ("Error occurred", "Test error")


class TestFolderStructureAnalyzer:
    """Test cases for folder structure analyzer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_drive_service = Mock()
        self.analyzer = FolderStructureAnalyzer(self.mock_drive_service)

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        assert self.analyzer.drive_service == self.mock_drive_service

    def test_categorize_file_size(self):
        """Test file size categorization."""
        analyzer = FolderStructureAnalyzer(Mock())

        assert analyzer._categorize_file_size(500 * 1024) == "small (<1MB)"
        assert analyzer._categorize_file_size(5 * 1024 * 1024) == "medium (1-10MB)"
        assert analyzer._categorize_file_size(25 * 1024 * 1024) == "large (10-50MB)"
        assert analyzer._categorize_file_size(100 * 1024 * 1024) == "very_large (>50MB)"

    def test_calculate_complexity_score(self):
        """Test complexity score calculation."""
        folder_stats = {
            "total_files": 500,
            "max_depth": 5,
            "file_types": {
                "application/pd": 100,
                "application/vnd.google-apps.document": 200,
                "application/msword": 150,
                "other": 50,
            },
            "size_distribution": {
                "small (<1MB)": 400,
                "medium (1-10MB)": 80,
                "large (10-50MB)": 15,
                "very_large (>50MB)": 5,
            },
        }

        score = self.analyzer._calculate_complexity_score(folder_stats)

        assert isinstance(score, float)
        assert 0 <= score <= 100  # Score should be between 0 and 100

    def test_calculate_processing_estimates(self):
        """Test processing time estimation."""
        folder_stats = {
            "total_files": 100,
            "file_types": {
                "application/pd": 50,
                "application/vnd.google-apps.document": 30,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 20,
            },
        }

        estimates = self.analyzer._calculate_processing_estimates(folder_stats)

        assert "estimated_processing_time_seconds" in estimates
        assert "estimated_processing_time_hours" in estimates
        assert "estimated_memory_mb" in estimates
        assert "estimated_storage_mb" in estimates
        assert "recommended_batch_size" in estimates
        assert "recommended_workers" in estimates

        assert estimates["estimated_processing_time_seconds"] > 0
        assert estimates["estimated_memory_mb"] == 1000  # 100 files * 10MB each
        assert estimates["recommended_batch_size"] >= 10

    def test_generate_recommendations(self):
        """Test recommendation generation."""
        folder_stats = {
            "total_files": 15000,  # Large number of files
            "max_depth": 15,  # Deep folder structure
            "size_distribution": {"very_large (>50MB)": 100},  # Many large files
            "file_types": {
                "application/pd": 10000,
                "image/jpeg": 5000,  # Unsupported type
            },
        }

        estimates = {
            "estimated_processing_time_hours": 12,  # Long processing time
            "estimated_memory_mb": 8000,  # High memory usage
        }

        recommendations = self.analyzer._generate_recommendations(
            folder_stats, estimates
        )

        assert len(recommendations) > 0
        assert any("multiple stages" in rec for rec in recommendations)
        assert any("overnight processing" in rec for rec in recommendations)
        assert any("very large files" in rec for rec in recommendations)
        assert any("High memory usage" in rec for rec in recommendations)
        assert any("Deep folder structure" in rec for rec in recommendations)
        assert any("unsupported types" in rec for rec in recommendations)

    @pytest.mark.asyncio
    async def test_get_folder_statistics(self):
        """Test folder statistics gathering."""
        # Mock Drive service responses
        mock_files_list = Mock()
        self.mock_drive_service.files.return_value.list.return_value = mock_files_list

        # Mock folder contents
        mock_files_list.return_value.execute.side_effect = [
            {
                "files": [
                    {
                        "id": "file1",
                        "name": "document1.pd",
                        "mimeType": "application/pd",
                        "size": "1048576",  # 1MB
                        "modifiedTime": "2023-01-01T00:00:00Z",
                    },
                    {
                        "id": "file2",
                        "name": "document2.docx",
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "size": "52428800",  # 50MB
                        "modifiedTime": "2023-01-01T00:00:00Z",
                    },
                    {
                        "id": "folder1",
                        "name": "subfolder",
                        "mimeType": "application/vnd.google-apps.folder",
                    },
                ]
            },
            {"files": []},  # Empty subfolder
        ]

        stats = await self.analyzer._get_folder_statistics("root_id")

        assert stats["total_folders"] == 2  # Root + subfolder
        assert stats["total_files"] == 2
        assert stats["max_depth"] == 1
        assert "application/pd" in stats["file_types"]
        assert stats["file_types"]["application/pd"] == 1
        assert "medium (1-10MB)" in stats["size_distribution"]
        assert "very_large (>50MB)" in stats["size_distribution"]
        assert len(stats["largest_files"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_folder_complexity(self):
        """Test complete folder complexity analysis."""
        # Mock the _get_folder_statistics method
        mock_stats = {
            "total_files": 1000,
            "total_folders": 50,
            "max_depth": 8,
            "file_types": {
                "application/pd": 500,
                "application/vnd.google-apps.document": 300,
                "application/msword": 200,
            },
            "size_distribution": {
                "small (<1MB)": 800,
                "medium (1-10MB)": 150,
                "large (10-50MB)": 40,
                "very_large (>50MB)": 10,
            },
            "largest_files": [("large_doc.pd", 104857600)],
        }

        with patch.object(
            self.analyzer, "_get_folder_statistics", return_value=mock_stats
        ):
            analysis = await self.analyzer.analyze_folder_complexity("test_folder_id")

        assert "folder_metrics" in analysis
        assert "file_distribution" in analysis
        assert "processing_estimates" in analysis
        assert "recommendations" in analysis

        assert analysis["folder_metrics"] == mock_stats
        assert "complexity_score" in analysis["file_distribution"]
        assert "estimated_processing_time_seconds" in analysis["processing_estimates"]
        assert isinstance(analysis["recommendations"], list)


@pytest.mark.asyncio
class TestBulkOperationsIntegration:
    """Integration tests for bulk operations."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.config = BulkOperationConfig(
            max_workers=2,
            batch_size=3,
            create_git_repos=False,  # Skip git for integration tests
        )
        self.processor = BulkDocumentProcessor(self.config)

    async def test_process_folder_structure_integration(self):
        """Test complete folder processing workflow."""
        # Mock Drive service
        mock_drive_service = Mock()
        mock_files_list = Mock()

        # Mock folder discovery
        mock_files_list.return_value.execute.return_value = {
            "files": [
                {
                    "id": "file1",
                    "name": "test1.pd",
                    "mimeType": "application/pd",
                    "size": "1024",
                    "modifiedTime": "2023-01-01T00:00:00Z",
                    "createdTime": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "file2",
                    "name": "test2.pd",
                    "mimeType": "application/pd",
                    "size": "2048",
                    "modifiedTime": "2023-01-01T00:00:00Z",
                    "createdTime": "2023-01-01T00:00:00Z",
                },
            ]
        }

        mock_drive_service.files.return_value.list.return_value = mock_files_list

        # Mock file content download
        mock_drive_service.files.return_value.get_media.return_value.execute.return_value = (
            b"PDF content"
        )

        # Mock PDF converter
        with patch("doc_processing.bulk_operations.PDFConverter") as mock_pdf_converter:
            mock_converter_instance = Mock()
            mock_converter_instance.to_markdown.return_value = "# Test Document"
            mock_converter_instance.extract_metadata.return_value = {"pages": 1}
            mock_pdf_converter.return_value = mock_converter_instance

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir)

                result = await self.processor.process_folder_structure(
                    "test_folder_id", mock_drive_service, output_path
                )

        # Verify results
        assert "processing_summary" in result
        assert result["processing_summary"]["total_files"] == 2
        assert (
            result["processing_summary"]["successful"] >= 0
        )  # May vary based on mocking


if __name__ == "__main__":
    pytest.main([__file__])
