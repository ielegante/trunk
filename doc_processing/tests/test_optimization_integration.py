"""Integration tests for performance optimization with conversion pipeline."""

import asyncio
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from doc_processing.converters.google_docs import ConversionResult, GoogleDocsConverter
from doc_processing.optimization import (
    CacheManager,
    DocumentCache,
    LargeDocumentHandler,
    OptimizationConfig,
    PerformanceBenchmark,
    PerformanceOptimizer,
)


class TestOptimizationIntegration(unittest.TestCase):
    """Integration tests for optimization components."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up cache manager
        self.cache_config = {
            "memory_cache_mb": 50,
            "memory_cache_entries": 100,
            "cache_dir": "test_cache",
            "file_cache_mb": 100,
        }
        self.cache_manager = CacheManager(self.cache_config)

        # Set up Google Docs converter
        self.converter = GoogleDocsConverter({})

        # Set up optimization config
        self.opt_config = OptimizationConfig(
            enable_chunking=True,
            chunk_size=1024 * 1024,  # 1MB
            enable_parallel=True,
            max_workers=4,
            enable_caching=True,
            cache_size=128,
            enable_streaming=True,
        )

        # Set up performance optimizer
        self.optimizer = PerformanceOptimizer(self.opt_config, self.converter)

        # Set up large document handler
        self.large_handler = LargeDocumentHandler(
            converter=self.converter, optimizer=self.optimizer
        )

    def test_cached_conversion_pipeline(self):
        """Test conversion pipeline with caching."""
        # Create document cache
        doc_cache = DocumentCache(self.cache_manager)

        # Mock converter response
        mock_result = ConversionResult(
            content="# Test Document\n\nThis is test content.",
            elements=[],
            comments=[],
            suggestions=[],
            metadata={"title": "Test Doc"},
            conversion_accuracy=0.98,
        )

        with patch.object(self.converter, "to_markdown", return_value=mock_result):
            # First conversion - should hit converter
            start_time = time.time()
            result1 = self.optimizer.optimize_conversion("test_doc_1", "to_markdown")
            first_time = time.time() - start_time

            self.assertEqual(result1.content, mock_result.content)
            self.assertEqual(self.converter.to_markdown.call_count, 1)

            # Second conversion - should hit cache
            start_time = time.time()
            result2 = self.optimizer.optimize_conversion("test_doc_1", "to_markdown")
            cached_time = time.time() - start_time

            self.assertEqual(result2.content, mock_result.content)
            # Converter should not be called again
            self.assertEqual(self.converter.to_markdown.call_count, 1)

            # Cache should be faster
            self.assertLess(cached_time, first_time)

            # Check metrics
            metrics = self.optimizer.metrics
            self.assertGreater(len(metrics), 1)

            # Find cache hit metric
            cache_hit_metrics = [m for m in metrics if m.cache_hits > 0]
            self.assertGreater(len(cache_hit_metrics), 0)

    def test_large_document_optimization(self):
        """Test optimization for large documents."""
        # Mock large document
        large_content = (
            "# Large Document\n\n" + ("This is a paragraph. " * 1000 + "\n\n") * 100
        )

        mock_result = ConversionResult(
            content=large_content,
            elements=[],
            comments=[],
            suggestions=[],
            metadata={"size": len(large_content)},
            conversion_accuracy=0.95,
        )

        # Mock document size estimation
        self.optimizer._estimate_document_size = Mock(return_value=len(large_content))

        # Mock chunk processing
        def mock_process_chunk(chunk, conv_type):
            return ConversionResult(
                content=f"Processed chunk {chunk['chunk_index']}",
                elements=[],
                comments=[],
                suggestions=[],
                metadata={"chunk": chunk["chunk_index"]},
                conversion_accuracy=0.95,
            )

        self.optimizer._process_single_chunk = mock_process_chunk

        # Process large document
        result = self.optimizer.optimize_conversion("large_doc", "to_markdown")

        self.assertIsNotNone(result)
        self.assertIn("chunk_count", result.metadata)
        self.assertGreater(result.metadata["chunk_count"], 1)

    async def test_async_document_processing(self):
        """Test asynchronous document processing."""

        # Mock async processing
        async def mock_process_chunk(chunk):
            await asyncio.sleep(0.01)  # Simulate processing
            return ChunkProcessingResult(
                chunk_id=chunk.chunk_id,
                success=True,
                content=f"Async processed {chunk.chunk_index}",
                elements=[],
                processing_time=0.01,
            )

        self.large_handler._process_single_chunk_async = mock_process_chunk

        # Process document asynchronously
        result = await self.large_handler.process_large_document_async("async_test_doc")

        self.assertIsInstance(result, ConversionResult)
        self.assertGreater(result.conversion_accuracy, 0)
        self.assertIn("chunk_count", result.metadata)

    def test_optimization_levels(self):
        """Test different optimization levels based on document size."""
        # Small document (< 50MB)
        self.large_handler._estimate_document_size = Mock(return_value=10 * 1024 * 1024)

        with patch.object(self.optimizer, "optimize_conversion") as mock_optimize:
            mock_optimize.return_value = ConversionResult(
                content="Small doc",
                elements=[],
                comments=[],
                suggestions=[],
                metadata={},
                conversion_accuracy=0.99,
            )

            result = self.large_handler.optimize_large_document_conversion("small_doc")
            self.assertTrue(mock_optimize.called)

        # Medium document (50-100MB)
        self.large_handler._estimate_document_size = Mock(return_value=75 * 1024 * 1024)
        result = self.large_handler.optimize_large_document_conversion("medium_doc")
        self.assertIsInstance(result, ConversionResult)

        # Large document (> 100MB)
        self.large_handler._estimate_document_size = Mock(
            return_value=150 * 1024 * 1024
        )
        result = self.large_handler.optimize_large_document_conversion("large_doc")
        self.assertIsInstance(result, ConversionResult)

    def test_streaming_processing(self):
        """Test streaming document processing."""
        # Test streaming processor
        from doc_processing.optimization import StreamingProcessor

        processor = StreamingProcessor(buffer_size=1024)

        # Create test content
        test_content = "Test content for streaming. " * 100

        def process_func(chunk):
            return chunk.upper()

        # Test file streaming
        input_file = Path("test_stream_input.txt")
        output_file = Path("test_stream_output.txt")

        try:
            # Write test input
            with open(input_file, "w") as f:
                f.write(test_content)

            # Process with streaming
            processor.process_large_file(input_file, output_file, process_func)

            # Verify output
            self.assertTrue(output_file.exists())
            with open(output_file, "r") as f:
                output_content = f.read()
                self.assertEqual(output_content, test_content.upper())

        finally:
            # Clean up
            if input_file.exists():
                input_file.unlink()
            if output_file.exists():
                output_file.unlink()

    def test_performance_metrics_collection(self):
        """Test comprehensive performance metrics collection."""
        # Process several documents
        for i in range(5):
            doc_id = f"metric_test_doc_{i}"

            # Vary document sizes
            doc_size = (i + 1) * 1024 * 1024  # 1MB to 5MB
            self.optimizer._estimate_document_size = Mock(return_value=doc_size)

            self.optimizer.optimize_conversion(doc_id, "to_markdown")

        # Get performance report
        report = self.optimizer.get_performance_report()

        self.assertIn("summary", report)
        self.assertIn("operations", report)
        self.assertIn("configuration", report)

        # Check summary statistics
        summary = report["summary"]
        self.assertEqual(summary["total_operations"], 5)
        self.assertGreater(summary["avg_execution_time"], 0)

        # Check operation breakdown
        operations = report["operations"]
        self.assertIn("to_markdown", operations)

    def test_cache_invalidation(self):
        """Test cache invalidation for documents."""
        doc_cache = DocumentCache(self.cache_manager)

        # Cache some data
        doc_cache.set_conversion("doc1", "markdown", "# Document 1")
        doc_cache.set_metadata("doc1", {"title": "Document 1"})

        # Verify cached
        self.assertEqual(doc_cache.get_conversion("doc1", "markdown"), "# Document 1")
        self.assertIsNotNone(doc_cache.get_metadata("doc1"))

        # Invalidate document
        invalidated_count = doc_cache.invalidate_document("doc1")
        self.assertGreater(invalidated_count, 0)

        # Verify cleared
        self.assertIsNone(doc_cache.get_conversion("doc1", "markdown"))
        self.assertIsNone(doc_cache.get_metadata("doc1"))

    def test_benchmark_execution(self):
        """Test benchmark execution."""
        # Create minimal benchmark
        benchmark = PerformanceBenchmark()
        benchmark.test_sizes_mb = [1]  # Only test 1MB
        benchmark.test_configs = [
            OptimizationConfig(
                enable_chunking=False, enable_parallel=False, enable_caching=False
            )
        ]

        # Mock document processing
        with patch.object(PerformanceOptimizer, "optimize_conversion") as mock_optimize:
            mock_optimize.return_value = ConversionResult(
                content="Benchmark result",
                elements=[],
                comments=[],
                suggestions=[],
                metadata={},
                conversion_accuracy=0.95,
            )

            # Run benchmark
            results = benchmark.run_full_benchmark()

            self.assertIn("summary", results)
            self.assertIn("by_document_size", results)
            self.assertIn("recommendations", results)

            # Check results
            self.assertEqual(results["summary"]["total_tests"], 1)

    def tearDown(self):
        """Clean up test resources."""
        # Clear caches
        self.cache_manager.clear()

        # Clean up optimizer
        self.optimizer.cleanup()

        # Clean up large document handler
        self.large_handler.cleanup()

        # Remove test cache directory
        import shutil

        cache_dir = Path(self.cache_config["cache_dir"])
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


if __name__ == "__main__":
    # Run async tests
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "async":
        # Run async test
        async def run_async_test():
            test = TestOptimizationIntegration()
            test.setUp()
            await test.test_async_document_processing()
            test.tearDown()

        asyncio.run(run_async_test())
    else:
        # Run normal tests
        unittest.main()
