"""Tests for performance optimization modules."""

import asyncio
import json
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from doc_processing.converters.google_docs import ConversionResult
from doc_processing.optimization import (
    OptimizationConfig,
    PerformanceMetrics,
    PerformanceOptimizer,
    StreamingProcessor,
    performance_monitor,
)
from doc_processing.optimization.cache_manager import (
    CacheManager,
    DocumentCache,
    FileCache,
    MemoryCache,
    cached,
)
from doc_processing.optimization.large_document_handler import (
    ChunkProcessingResult,
    DocumentChunk,
    DocumentSplitter,
    LargeDocumentHandler,
)


class TestPerformanceOptimizer(unittest.TestCase):
    """Test PerformanceOptimizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = OptimizationConfig(
            enable_chunking=True,
            chunk_size=1024,
            max_chunk_count=10,
            enable_parallel=True,
            max_workers=2,
            enable_caching=True,
        )
        self.optimizer = PerformanceOptimizer(config=self.config)

    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        self.assertIsNotNone(self.optimizer.config)
        self.assertEqual(self.optimizer.config.chunk_size, 1024)
        self.assertEqual(self.optimizer.config.max_workers, 2)
        self.assertTrue(self.optimizer.config.enable_caching)

    def test_optimize_conversion_with_cache_hit(self):
        """Test conversion optimization with cache hit."""
        # Pre-populate cache
        test_result = ConversionResult(
            content="Cached content",
            elements=[],
            comments=[],
            suggestions=[],
            metadata={"cached": True},
            conversion_accuracy=1.0,
        )

        cache_key = "test_doc_to_markdown"
        self.optimizer._cache[cache_key] = test_result
        self.optimizer._cache_timestamps[cache_key] = time.time()

        # Test cache hit
        result = self.optimizer.optimize_conversion("test_doc", "to_markdown")
        self.assertEqual(result.content, "Cached content")
        self.assertEqual(result.metadata["cached"], True)

        # Check metrics
        self.assertTrue(len(self.optimizer.metrics) > 0)
        last_metric = self.optimizer.metrics[-1]
        self.assertEqual(last_metric.cache_hits, 1)

    def test_optimize_conversion_large_document(self):
        """Test optimization for large documents."""
        # Mock large document size
        self.optimizer._estimate_document_size = Mock(
            return_value=20 * 1024 * 1024
        )  # 20MB

        # Mock chunk processing
        self.optimizer._create_document_chunks = Mock(
            return_value=[
                {"chunk_id": "chunk_0", "chunk_index": 0},
                {"chunk_id": "chunk_1", "chunk_index": 1},
            ]
        )

        mock_result = ConversionResult(
            content="Chunk content",
            elements=[],
            comments=[],
            suggestions=[],
            metadata={},
            conversion_accuracy=0.95,
        )
        self.optimizer._process_single_chunk = Mock(return_value=mock_result)

        # Test large document processing
        result = self.optimizer.optimize_conversion("large_doc", "to_markdown")

        self.assertIsNotNone(result)
        self.assertTrue(self.optimizer._create_document_chunks.called)
        self.assertEqual(self.optimizer._process_single_chunk.call_count, 2)

    def test_parallel_search(self):
        """Test parallel document search."""
        # Mock search function
        self.optimizer._search_single_document = Mock(return_value=0.8)

        # Test parallel search
        document_ids = [f"doc_{i}" for i in range(20)]
        results = self.optimizer.optimize_search("test query", document_ids)

        self.assertEqual(len(results), 20)
        self.assertTrue(all(score == 0.8 for _, score in results))

    def test_memory_optimization(self):
        """Test memory usage optimization."""
        # Add some cache entries
        for i in range(10):
            self.optimizer._cache[f"key_{i}"] = f"value_{i}"
            self.optimizer._cache_timestamps[f"key_{i}"] = time.time()

        initial_cache_size = len(self.optimizer._cache)

        # Trigger memory optimization
        self.optimizer.optimize_memory_usage()

        # Cache should still exist but may have been cleaned
        self.assertLessEqual(len(self.optimizer._cache), initial_cache_size)

    def test_performance_metrics_recording(self):
        """Test performance metrics recording."""
        self.optimizer._record_metrics(
            operation="test_operation",
            document_size=1024 * 1024,
            execution_time=1.5,
            memory_usage=2 * 1024 * 1024,
            cache_hits=2,
            cache_misses=1,
        )

        self.assertEqual(len(self.optimizer.metrics), 1)
        metric = self.optimizer.metrics[0]
        self.assertEqual(metric.operation, "test_operation")
        self.assertEqual(metric.document_size, 1024 * 1024)
        self.assertEqual(metric.execution_time, 1.5)
        self.assertEqual(metric.cache_hits, 2)
        self.assertEqual(metric.cache_misses, 1)

    def test_performance_report_generation(self):
        """Test performance report generation."""
        # Add some metrics
        for i in range(5):
            self.optimizer._record_metrics(
                operation="conversion",
                document_size=1024 * 1024,
                execution_time=0.5,
                memory_usage=1024 * 1024,
                cache_hits=i % 2,
                cache_misses=(i + 1) % 2,
            )

        report = self.optimizer.get_performance_report()

        self.assertIn("summary", report)
        self.assertIn("operations", report)
        self.assertIn("configuration", report)
        self.assertIn("detailed_metrics", report)

        self.assertEqual(report["summary"]["total_operations"], 5)
        self.assertIn("conversion", report["operations"])

    def tearDown(self):
        """Clean up resources."""
        self.optimizer.cleanup()


class TestCacheManager(unittest.TestCase):
    """Test CacheManager and related classes."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path("test_cache_dir")
        self.temp_dir.mkdir(exist_ok=True)

        self.cache_config = {
            "memory_cache_mb": 10,
            "memory_cache_entries": 100,
            "cache_dir": str(self.temp_dir),
            "file_cache_mb": 50,
        }
        self.cache_manager = CacheManager(self.cache_config)

    def test_memory_cache_operations(self):
        """Test memory cache basic operations."""
        cache = self.cache_manager.memory_cache

        # Test set and get
        self.assertTrue(cache.set("key1", "value1"))
        self.assertEqual(cache.get("key1"), "value1")

        # Test TTL
        self.assertTrue(cache.set("key2", "value2", ttl=1))
        self.assertEqual(cache.get("key2"), "value2")

        # Wait for expiration
        time.sleep(1.1)
        self.assertIsNone(cache.get("key2"))

        # Test delete
        self.assertTrue(cache.delete("key1"))
        self.assertIsNone(cache.get("key1"))

        # Test exists
        cache.set("key3", "value3")
        self.assertTrue(cache.exists("key3"))
        self.assertFalse(cache.exists("key4"))

    def test_file_cache_operations(self):
        """Test file cache operations."""
        cache = self.cache_manager.file_cache

        # Test set and get
        self.assertTrue(cache.set("file_key1", {"data": "test"}))
        result = cache.get("file_key1")
        self.assertEqual(result["data"], "test")

        # Verify file exists
        cache_file = cache._get_cache_file("file_key1")
        self.assertTrue(cache_file.exists())

        # Test delete
        self.assertTrue(cache.delete("file_key1"))
        self.assertFalse(cache_file.exists())
        self.assertIsNone(cache.get("file_key1"))

    def test_cache_manager_multilevel(self):
        """Test multilevel caching in CacheManager."""
        # Test memory + file cache
        self.assertTrue(
            self.cache_manager.set("multi_key", "multi_value", persist=True)
        )

        # Should be in memory cache
        self.assertEqual(
            self.cache_manager.memory_cache.get("multi_key"), "multi_value"
        )

        # Should also be in file cache
        self.assertEqual(self.cache_manager.file_cache.get("multi_key"), "multi_value")

        # Clear memory cache
        self.cache_manager.memory_cache.clear()

        # Should still get from file cache and promote to memory
        self.assertEqual(self.cache_manager.get("multi_key"), "multi_value")
        self.assertEqual(
            self.cache_manager.memory_cache.get("multi_key"), "multi_value"
        )

    def test_document_cache(self):
        """Test DocumentCache specialized operations."""
        doc_cache = DocumentCache(self.cache_manager)

        # Test conversion caching
        doc_cache.set_conversion(
            "doc1", "markdown", "# Document 1", {"option": "value"}
        )
        result = doc_cache.get_conversion("doc1", "markdown", {"option": "value"})
        self.assertEqual(result, "# Document 1")

        # Test metadata caching
        metadata = {"title": "Test Doc", "author": "Test Author"}
        doc_cache.set_metadata("doc1", metadata)
        cached_metadata = doc_cache.get_metadata("doc1")
        self.assertEqual(cached_metadata, metadata)

        # Test document invalidation
        count = doc_cache.invalidate_document("doc1")
        self.assertGreater(count, 0)
        self.assertIsNone(doc_cache.get_metadata("doc1"))

    def test_cache_decorator(self):
        """Test cached decorator."""
        call_count = 0

        @cached(self.cache_manager, ttl=60)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # First call should execute function
        result1 = expensive_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(call_count, 1)

        # Second call should use cache
        result2 = expensive_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(call_count, 1)

        # Different arguments should execute function
        result3 = expensive_function(2, 3)
        self.assertEqual(result3, 5)
        self.assertEqual(call_count, 2)

    def tearDown(self):
        """Clean up test resources."""
        # Clear caches
        self.cache_manager.clear()

        # Remove test directory
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


class TestLargeDocumentHandler(unittest.TestCase):
    """Test LargeDocumentHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = LargeDocumentHandler(
            chunk_size=1024, max_memory=10 * 1024 * 1024
        )

    def test_document_chunk_creation(self):
        """Test document chunk creation."""
        chunk = DocumentChunk(
            chunk_id="test_chunk_0",
            document_id="test_doc",
            chunk_index=0,
            start_offset=0,
            end_offset=1024,
            content="Test content",
            metadata={"test": True},
        )

        chunk_dict = chunk.to_dict()
        self.assertEqual(chunk_dict["chunk_id"], "test_chunk_0")
        self.assertEqual(chunk_dict["start_offset"], 0)
        self.assertEqual(chunk_dict["end_offset"], 1024)

    @patch("asyncio.sleep")
    async def test_async_document_processing(self, mock_sleep):
        """Test asynchronous document processing."""
        mock_sleep.return_value = None

        # Mock document size estimation
        self.handler._estimate_document_size = Mock(return_value=5 * 1024)  # 5KB

        # Test async processing
        result = await self.handler.process_large_document_async("test_doc")

        self.assertIsInstance(result, ConversionResult)
        self.assertIn("chunk_count", result.metadata)
        self.assertTrue(result.conversion_accuracy > 0)

    def test_streaming_document_processing(self):
        """Test streaming document processing."""
        # Mock document fetching
        self.handler._fetch_document_to_file = Mock()

        # Test streaming
        chunks = list(self.handler.process_large_document_streaming("test_doc"))

        # Should produce chunks (mocked file will be created)
        self.assertIsInstance(chunks, list)

    def test_optimization_levels(self):
        """Test different optimization levels."""
        # Test standard optimization (< 50MB)
        self.handler._estimate_document_size = Mock(return_value=10 * 1024 * 1024)
        with patch.object(
            self.handler.optimizer, "optimize_conversion"
        ) as mock_optimize:
            mock_optimize.return_value = ConversionResult(
                content="Standard optimization",
                elements=[],
                comments=[],
                suggestions=[],
                metadata={},
                conversion_accuracy=0.95,
            )

            result = self.handler.optimize_large_document_conversion("small_doc")
            self.assertTrue(mock_optimize.called)

        # Test high optimization (50-100MB)
        self.handler._estimate_document_size = Mock(return_value=60 * 1024 * 1024)
        result = self.handler.optimize_large_document_conversion("medium_doc")
        self.assertIsInstance(result, ConversionResult)

        # Test ultra optimization (> 100MB)
        self.handler._estimate_document_size = Mock(return_value=150 * 1024 * 1024)
        result = self.handler.optimize_large_document_conversion("large_doc")
        self.assertIsInstance(result, ConversionResult)

    def test_document_splitter(self):
        """Test DocumentSplitter functionality."""
        splitter = DocumentSplitter(section_size=100)

        # Test structural splitting
        content = (
            """# Header 1
This is section 1 content.

# Header 2
This is section 2 content that is much longer and should potentially be split.
"""
            * 10
        )

        sections = splitter.split_by_structure(content)
        self.assertGreater(len(sections), 0)
        self.assertTrue(all(isinstance(s, tuple) for s in sections))
        self.assertTrue(all(len(s) == 2 for s in sections))

        # Test size-based splitting
        chunks = splitter.split_by_size(content)
        self.assertGreater(len(chunks), 0)
        self.assertTrue(all(isinstance(c, str) for c in chunks))

    def tearDown(self):
        """Clean up resources."""
        self.handler.cleanup()


class TestPerformanceMonitorDecorator(unittest.TestCase):
    """Test performance_monitor decorator."""

    def test_performance_monitoring(self):
        """Test function performance monitoring."""

        @performance_monitor
        def test_function(x, y):
            time.sleep(0.1)
            return x + y

        with patch(
            "doc_processing.optimization.performance_optimizer.logger"
        ) as mock_logger:
            result = test_function(1, 2)

            self.assertEqual(result, 3)
            # Check that debug was called with performance info
            self.assertTrue(mock_logger.debug.called)
            debug_call = mock_logger.debug.call_args[0][0]
            self.assertIn("test_function", debug_call)
            self.assertIn("Time:", debug_call)

    def test_performance_monitoring_with_exception(self):
        """Test performance monitoring with exception."""

        @performance_monitor
        def failing_function():
            raise ValueError("Test error")

        with patch(
            "doc_processing.optimization.performance_optimizer.logger"
        ) as mock_logger:
            with self.assertRaises(ValueError):
                failing_function()

            # Check that error was logged
            self.assertTrue(mock_logger.error.called)
            error_call = mock_logger.error.call_args[0][0]
            self.assertIn("failing_function failed", error_call)


class TestStreamingProcessor(unittest.TestCase):
    """Test StreamingProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.processor = StreamingProcessor(buffer_size=1024)

    async def test_async_streaming(self):
        """Test asynchronous document streaming."""

        def process_func(chunk):
            return chunk.upper()

        chunks = []
        async for chunk in self.processor.process_document_stream(
            "test_doc", process_func
        ):
            chunks.append(chunk)

        self.assertEqual(len(chunks), 10)  # Mock produces 10 chunks
        self.assertTrue(all("DOCUMENT CHUNK" in c for c in chunks))

    def test_file_streaming(self):
        """Test file streaming processing."""
        # Create test files
        input_file = Path("test_input.txt")
        output_file = Path("test_output.txt")

        with open(input_file, "w") as f:
            f.write("test content " * 100)

        def process_func(chunk):
            return chunk.upper()

        try:
            self.processor.process_large_file(input_file, output_file, process_func)

            self.assertTrue(output_file.exists())
            with open(output_file, "r") as f:
                content = f.read()
                self.assertEqual(content, ("test content " * 100).upper())

        finally:
            # Clean up
            if input_file.exists():
                input_file.unlink()
            if output_file.exists():
                output_file.unlink()


if __name__ == "__main__":
    unittest.main()
