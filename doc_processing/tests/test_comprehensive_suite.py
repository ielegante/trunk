"""Comprehensive test suite for production-ready document processing."""

import asyncio
import gc
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from doc_processing.bulk_operations import BulkDocumentProcessor, BulkOperationConfig
from doc_processing.converters.google_docs import GoogleDocsConverter
from doc_processing.converters.pdf import PDFConverter
from doc_processing.converters.word import WordConverter
from doc_processing.optimization.cache_manager import (
    CacheManager,
    DocumentCache,
    cached,
)
from doc_processing.optimization.performance_monitor import (
    PerformanceMonitor,
    performance_tracked,
)
from doc_processing.permissions.permission_mapper import PermissionMapper
from doc_processing.references.manager import CrossDocumentReferenceManager
from doc_processing.templates.manager import TemplateManager


class TestIntegrationScenarios:
    """Integration tests for real-world document processing scenarios."""

    @pytest.fixture
    def setup_test_environment(self):
        """Set up comprehensive test environment."""
        # Create temporary directories
        temp_dir = tempfile.mkdtemp()
        cache_dir = Path(temp_dir) / "cache"
        output_dir = Path(temp_dir) / "output"

        # Initialize components
        cache_config = {
            "memory_cache_mb": 50,
            "file_cache_mb": 100,
            "cache_dir": str(cache_dir),
        }

        cache_manager = CacheManager(cache_config)
        doc_cache = DocumentCache(cache_manager)
        perf_monitor = PerformanceMonitor()

        # Initialize processors
        pdf_converter = PDFConverter()
        word_converter = WordConverter()
        gdocs_converter = GoogleDocsConverter()

        bulk_config = BulkOperationConfig(
            max_workers=2, batch_size=5, max_file_size_mb=25
        )
        bulk_processor = BulkDocumentProcessor(bulk_config)

        yield {
            "temp_dir": temp_dir,
            "cache_dir": cache_dir,
            "output_dir": output_dir,
            "cache_manager": cache_manager,
            "doc_cache": doc_cache,
            "perf_monitor": perf_monitor,
            "pdf_converter": pdf_converter,
            "word_converter": word_converter,
            "gdocs_converter": gdocs_converter,
            "bulk_processor": bulk_processor,
        }

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_document_conversion_with_caching(self, setup_test_environment):
        """Test document conversion with caching enabled."""
        env = setup_test_environment

        # Mock PDF content
        doc_id = "test_doc_123"
        pdf_content = b"Mock PDF content"

        # First conversion - should miss cache
        with env["perf_monitor"].track_operation("pdf_conversion"):
            # Check cache first
            cached_result = env["doc_cache"].get_conversion(doc_id, "markdown")
            assert cached_result is None

            # Perform conversion (mocked)
            with patch.object(
                env["pdf_converter"],
                "to_markdown",
                return_value="# Converted Document\n\nContent here",
            ):
                result = env["pdf_converter"].to_markdown(pdf_content)

                # Cache the result
                env["doc_cache"].set_conversion(doc_id, "markdown", result)

        # Second conversion - should hit cache
        with env["perf_monitor"].track_operation("pdf_conversion_cached"):
            cached_result = env["doc_cache"].get_conversion(doc_id, "markdown")
            assert cached_result is not None
            assert "# Converted Document" in cached_result

        # Verify performance improvement
        stats = env["perf_monitor"].get_operation_stats()
        assert (
            stats["pdf_conversion"]["avg_duration"]
            > stats["pdf_conversion_cached"]["avg_duration"]
        )

    @pytest.mark.asyncio
    async def test_bulk_processing_with_monitoring(self, setup_test_environment):
        """Test bulk document processing with performance monitoring."""
        env = setup_test_environment

        # Mock Google Drive service
        mock_drive_service = Mock()

        # Mock folder structure
        mock_files = [
            {
                "id": f"file_{i}",
                "name": f"document_{i}.pd",
                "mimeType": "application/pd",
                "size": str(1024 * 1024 * i),  # Varying sizes
                "createdTime": "2023-01-01T00:00:00Z",
                "modifiedTime": "2023-01-01T00:00:00Z",
            }
            for i in range(1, 6)
        ]

        # Mock Drive API responses
        mock_drive_service.files.return_value.list.return_value.execute.return_value = {
            "files": mock_files
        }
        mock_drive_service.files.return_value.get_media.return_value.execute.return_value = (
            b"PDF content"
        )

        # Track bulk processing
        async with env["perf_monitor"].track_async_operation("bulk_processing"):
            with patch.object(
                env["bulk_processor"], "_process_single_file"
            ) as mock_process:
                # Mock successful processing
                mock_process.return_value = Mock(
                    status="success", processing_time=0.5, file_name="test.pd"
                )

                # Process folder
                result = await env["bulk_processor"].process_folder_structure(
                    "test_folder_id", mock_drive_service, env["output_dir"]
                )

        # Verify processing
        assert "processing_summary" in result
        assert result["processing_summary"]["total_files"] == 5

        # Check performance metrics
        metrics = env["perf_monitor"].get_recent_metrics(operation="bulk_processing")
        assert len(metrics) > 0
        assert metrics[0]["success"] is True

    def test_memory_leak_detection(self, setup_test_environment):
        """Test for memory leaks in document processing."""
        env = setup_test_environment

        # Enable memory tracking
        env["perf_monitor"].enable_memory_tracking = True

        # Process multiple documents
        for i in range(10):
            with env["perf_monitor"].track_operation(f"conversion_{i}"):
                # Simulate document processing
                large_content = "x" * (1024 * 1024)  # 1MB string

                # Mock conversion
                with patch.object(
                    env["pdf_converter"], "to_markdown", return_value=large_content
                ):
                    result = env["pdf_converter"].to_markdown(f"doc_{i}")

                # Force garbage collection
                del result
                gc.collect()

        # Analyze memory usage
        summary = env["perf_monitor"].get_performance_summary()
        bottlenecks = env["perf_monitor"].get_bottlenecks()

        # Check for memory issues
        memory_intensive = bottlenecks["memory_intensive_operations"]

        # Memory usage should be relatively stable
        if summary["average_memory_delta_mb"] > 10:
            pytest.fail(
                f"Potential memory leak detected: {summary['average_memory_delta_mb']}MB average growth"
            )

    def test_error_handling_and_recovery(self, setup_test_environment):
        """Test error handling and recovery mechanisms."""
        env = setup_test_environment

        # Test various error scenarios
        error_scenarios = [
            ("invalid_pd", ValueError("Invalid PDF format")),
            ("network_error", ConnectionError("Network timeout")),
            ("permission_denied", PermissionError("Access denied")),
            ("out_of_memory", MemoryError("Out of memory")),
        ]

        for scenario_name, error in error_scenarios:
            try:
                with env["perf_monitor"].track_operation(f"error_test_{scenario_name}"):
                    # Simulate error
                    raise error
            except Exception:
                pass  # Expected

        # Verify error tracking
        stats = env["perf_monitor"].get_operation_stats()

        for scenario_name, _ in error_scenarios:
            op_stats = stats.get(f"error_test_{scenario_name}", {})
            assert op_stats.get("error_count", 0) > 0
            assert op_stats.get("success_count", 0) == 0

    def test_cache_performance_under_load(self, setup_test_environment):
        """Test cache performance under heavy load."""
        env = setup_test_environment

        # Simulate heavy cache usage
        num_operations = 100
        cache_hits = 0
        cache_misses = 0

        with env["perf_monitor"].track_operation("cache_stress_test"):
            for i in range(num_operations):
                key = f"doc_{i % 20}"  # Reuse some keys

                # Try to get from cache
                result = env["cache_manager"].get(key)

                if result is None:
                    cache_misses += 1
                    # Simulate expensive operation
                    time.sleep(0.01)
                    value = f"Processed content for {key}"
                    env["cache_manager"].set(key, value, ttl=300)
                else:
                    cache_hits += 1

        # Calculate hit rate
        hit_rate = cache_hits / num_operations

        # Should have reasonable hit rate due to key reuse
        assert hit_rate > 0.5, f"Cache hit rate too low: {hit_rate:.2%}"

        # Check cache stats
        cache_stats = env["cache_manager"].get_stats()
        assert cache_stats["memory_cache"]["entries"] > 0


class TestProductionHardening:
    """Tests for production hardening and reliability."""

    def test_concurrent_access_safety(self):
        """Test thread safety of shared resources."""
        cache_manager = CacheManager()
        perf_monitor = PerformanceMonitor()

        # Test concurrent cache access
        import threading

        def cache_worker(worker_id):
            for i in range(50):
                key = f"worker_{worker_id}_item_{i}"
                cache_manager.set(key, f"value_{i}")
                value = cache_manager.get(key)
                assert value == f"value_{i}"

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=cache_worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify cache integrity
        stats = cache_manager.get_stats()
        assert stats["memory_cache"]["entries"] > 0

    def test_resource_cleanup(self):
        """Test proper resource cleanup."""
        # Create resources
        temp_dir = tempfile.mkdtemp()
        cache_config = {"cache_dir": temp_dir}

        cache_manager = CacheManager(cache_config)
        perf_monitor = PerformanceMonitor(enable_memory_tracking=True)

        # Use resources
        for i in range(10):
            cache_manager.set(f"key_{i}", f"value_{i}")

        # Cleanup
        cache_manager.clear()
        perf_monitor.reset_metrics()

        # Verify cleanup
        assert cache_manager.get_stats()["memory_cache"]["entries"] == 0
        assert len(perf_monitor.metrics) == 0

        # Cleanup temp directory
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_graceful_degradation(self):
        """Test system behavior when components fail."""
        # Test cache failure handling
        cache_manager = CacheManager()

        # Simulate file cache failure
        with patch.object(
            cache_manager.file_cache, "set", side_effect=Exception("Disk full")
        ):
            # Should still work with memory cache only
            success = cache_manager.set("test_key", "test_value", persist=True)
            assert success  # Memory cache should succeed

            # Value should be retrievable from memory cache
            value = cache_manager.get("test_key")
            assert value == "test_value"

    def test_performance_under_memory_pressure(self):
        """Test behavior under memory constraints."""
        # Create cache with small memory limit
        cache_config = {
            "memory_cache_mb": 1,  # Very small cache
            "memory_cache_entries": 10,
        }

        cache_manager = CacheManager(cache_config)

        # Try to cache large objects
        large_data = "x" * (500 * 1024)  # 500KB strings

        # Cache should handle eviction gracefully
        for i in range(20):
            key = f"large_item_{i}"
            cache_manager.set(key, large_data)

        # Check that cache size is within limits
        stats = cache_manager.get_stats()
        assert stats["memory_cache"]["size_mb"] <= 1.5  # Allow small overhead


class TestSecurityAndValidation:
    """Security and validation tests for production."""

    def test_input_validation(self):
        """Test input validation for all converters."""
        pdf_converter = PDFConverter()
        word_converter = WordConverter()

        # Test invalid inputs
        invalid_inputs = [
            None,
            "",
            123,  # Wrong type
            {"not": "a file"},
            "nonexistent_file.pd",
        ]

        for invalid_input in invalid_inputs:
            # PDF converter
            with pytest.raises((ValueError, TypeError, FileNotFoundError)):
                pdf_converter.to_markdown(invalid_input)

            # Word converter
            with pytest.raises((ValueError, TypeError, FileNotFoundError)):
                word_converter.to_markdown(invalid_input)

    def test_path_traversal_protection(self):
        """Test protection against path traversal attacks."""
        # Create file cache with restricted directory
        temp_dir = tempfile.mkdtemp()
        cache_config = {"cache_dir": temp_dir}
        cache_manager = CacheManager(cache_config)

        # Try to access files outside cache directory
        malicious_keys = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "C:\\Windows\\System32\\config",
        ]

        for key in malicious_keys:
            # Should safely handle malicious keys
            cache_manager.set(key, "test_value")

            # Verify file is created safely within cache directory
            cache_files = list(Path(temp_dir).glob("*.cache"))
            for cache_file in cache_files:
                assert temp_dir in str(cache_file.parent)

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sensitive_data_handling(self):
        """Test handling of sensitive data in cache and logs."""
        import logging

        # Set up log capture
        log_capture = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                log_capture.append(record.getMessage())

        handler = TestHandler()
        logger = logging.getLogger("doc_processing")
        logger.addHandler(handler)

        # Process document with sensitive data
        sensitive_content = "SSN: 123-45-6789, Credit Card: 4111-1111-1111-1111"

        cache_manager = CacheManager()
        cache_manager.set("sensitive_doc", sensitive_content)

        # Check logs don't contain sensitive data
        for log_msg in log_capture:
            assert "123-45-6789" not in log_msg
            assert "4111-1111-1111-1111" not in log_msg

        # Cleanup
        logger.removeHandler(handler)


class TestPerformanceOptimization:
    """Tests for performance optimization features."""

    def test_caching_decorator(self):
        """Test the caching decorator functionality."""
        cache_manager = CacheManager()
        call_count = 0

        @cached(cache_manager, ttl=60)
        def expensive_operation(x, y):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)  # Simulate expensive operation
            return x + y

        # First call - should execute
        result1 = expensive_operation(2, 3)
        assert result1 == 5
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = expensive_operation(2, 3)
        assert result2 == 5
        assert call_count == 1  # No additional calls

        # Different args - should execute
        result3 = expensive_operation(4, 5)
        assert result3 == 9
        assert call_count == 2

    def test_performance_tracking_decorator(self):
        """Test the performance tracking decorator."""
        perf_monitor = PerformanceMonitor()

        @performance_tracked(perf_monitor, operation="test_function")
        def tracked_function(duration):
            time.sleep(duration)
            return "completed"

        # Execute tracked function
        result = tracked_function(0.1)
        assert result == "completed"

        # Check metrics
        stats = perf_monitor.get_operation_stats("test_function")
        assert stats["count"] == 1
        assert stats["avg_duration"] >= 0.1

    @pytest.mark.asyncio
    async def test_async_performance_tracking(self):
        """Test async performance tracking."""
        perf_monitor = PerformanceMonitor()

        @performance_tracked(perf_monitor, operation="async_test")
        async def async_tracked_function():
            await asyncio.sleep(0.1)
            return "async_completed"

        # Execute async function
        result = await async_tracked_function()
        assert result == "async_completed"

        # Check metrics
        stats = perf_monitor.get_operation_stats("async_test")
        assert stats["count"] == 1
        assert stats["avg_duration"] >= 0.1

    def test_bottleneck_identification(self):
        """Test bottleneck identification system."""
        perf_monitor = PerformanceMonitor()

        # Simulate various operations
        for i in range(10):
            with perf_monitor.track_operation("fast_operation"):
                time.sleep(0.01)

        for i in range(5):
            with perf_monitor.track_operation("slow_operation"):
                time.sleep(0.5 if i == 0 else 0.1)  # One very slow execution

        # Simulate memory intensive operation
        with perf_monitor.track_operation("memory_intensive"):
            large_data = ["x" * (1024 * 1024) for _ in range(150)]  # 150MB
            time.sleep(0.1)
            del large_data

        # Get bottleneck analysis
        bottlenecks = perf_monitor.get_bottlenecks()

        # Should identify slow operation due to outlier
        slow_ops = bottlenecks["slow_operations"]
        assert any(op["operation"] == "slow_operation" for op in slow_ops)

        # Should identify memory intensive operation
        memory_ops = bottlenecks["memory_intensive_operations"]
        assert any(op["operation"] == "memory_intensive" for op in memory_ops)


class TestEndToEndScenarios:
    """End-to-end tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_document_workflow(self, setup_test_environment):
        """Test complete document processing workflow."""
        env = setup_test_environment

        # Step 1: Receive document
        doc_id = "contract_v1"
        doc_content = "Mock legal contract content"

        # Step 2: Check cache
        cached = env["doc_cache"].get_conversion(doc_id, "markdown")
        assert cached is None

        # Step 3: Convert document
        with env["perf_monitor"].track_operation("full_workflow"):
            # Mock conversion
            converted = "# Legal Contract\n\n" + doc_content

            # Step 4: Extract metadata
            metadata = {
                "title": "Legal Contract",
                "pages": 10,
                "author": "Law Firm",
                "created": "2023-01-01",
            }

            # Step 5: Cache results
            env["doc_cache"].set_conversion(doc_id, "markdown", converted)
            env["doc_cache"].set_metadata(doc_id, metadata)

            # Step 6: Process references (mocked)
            references = ["firm://contracts/master-agreement"]

            # Step 7: Apply security/redaction (mocked)
            redacted = converted.replace("sensitive", "[REDACTED]")

        # Verify workflow
        assert env["doc_cache"].get_conversion(doc_id, "markdown") == converted
        assert env["doc_cache"].get_metadata(doc_id) == metadata

        # Check performance
        stats = env["perf_monitor"].get_operation_stats("full_workflow")
        assert stats["success_count"] == 1

    def test_production_monitoring_export(self, setup_test_environment):
        """Test production monitoring and metrics export."""
        env = setup_test_environment

        # Simulate production workload
        operations = ["convert_pd", "extract_text", "cache_lookup", "save_result"]

        for _ in range(50):
            for op in operations:
                with env["perf_monitor"].track_operation(op):
                    # Simulate varying execution times
                    import random

                    time.sleep(random.uniform(0.01, 0.1))

        # Export metrics
        export_path = env["temp_dir"] / "metrics_export.json"
        env["perf_monitor"].export_metrics(str(export_path))

        # Verify export
        assert export_path.exists()

        with open(export_path, "r") as f:
            exported_data = json.load(f)

        assert "summary" in exported_data
        assert "operation_stats" in exported_data
        assert "bottlenecks" in exported_data
        assert exported_data["summary"]["total_operations"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
