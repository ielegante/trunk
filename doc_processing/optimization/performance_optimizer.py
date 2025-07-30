"""Performance optimization for large document processing."""

import asyncio
import logging
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple, Union

try:
    import psutil
except ImportError:
    # Fallback if psutil is not available
    psutil = None

from ..converters.google_docs import ConversionResult, GoogleDocsConverter

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for document processing."""

    operation: str
    document_size: int  # bytes
    execution_time: float  # seconds
    memory_usage: int  # bytes
    cpu_usage: float  # percentage
    chunk_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""

    # Chunking configuration
    enable_chunking: bool = True
    chunk_size: int = 1024 * 1024  # 1MB chunks
    max_chunk_count: int = 100

    # Parallel processing configuration
    enable_parallel: bool = True
    max_workers: int = 4
    use_multiprocessing: bool = False  # Use threading by default

    # Caching configuration
    enable_caching: bool = True
    cache_size: int = 128  # Number of cached items
    cache_ttl: int = 3600  # Cache time-to-live in seconds

    # Memory management
    max_memory_usage: int = 512 * 1024 * 1024  # 512MB
    enable_streaming: bool = True
    buffer_size: int = 8192  # 8KB buffer

    # Optimization strategies
    enable_lazy_loading: bool = True
    enable_compression: bool = True
    enable_incremental_processing: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class PerformanceOptimizer:
    """Optimizes document processing performance for large documents."""

    def __init__(
        self,
        config: Optional[OptimizationConfig] = None,
        converter: Optional[GoogleDocsConverter] = None,
    ):
        """Initialize performance optimizer.

        Args:
            config: Optimization configuration
            converter: GoogleDocsConverter instance
        """
        self.config = config or OptimizationConfig()
        self.converter = converter or GoogleDocsConverter({})

        # Performance tracking
        self.metrics: List[PerformanceMetrics] = []
        self._cache = {}
        self._cache_timestamps = {}

        # Thread/Process pools
        self._thread_pool = None
        self._process_pool = None

        # Initialize pools if parallel processing is enabled
        if self.config.enable_parallel:
            self._initialize_pools()

    def _initialize_pools(self):
        """Initialize thread and process pools."""
        if self.config.use_multiprocessing:
            self._process_pool = ProcessPoolExecutor(
                max_workers=self.config.max_workers
            )
        else:
            self._thread_pool = ThreadPoolExecutor(max_workers=self.config.max_workers)

    def optimize_conversion(
        self, document_id: str, conversion_type: str = "to_markdown"
    ) -> ConversionResult:
        """Optimize document conversion with performance enhancements.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            ConversionResult with optimized performance
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()

        # Check cache first
        cache_key = f"{document_id}_{conversion_type}"
        if self.config.enable_caching:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self._record_metrics(
                    operation=f"cached_{conversion_type}",
                    document_size=len(cached_result.content.encode()),
                    execution_time=time.time() - start_time,
                    memory_usage=self._get_memory_usage() - start_memory,
                    cache_hits=1,
                )
                return cached_result

        # Get document size estimate
        document_size = self._estimate_document_size(document_id)

        # Choose optimization strategy based on document size
        if document_size > self.config.chunk_size * 10:  # Large document
            result = self._process_large_document(document_id, conversion_type)
        else:  # Small to medium document
            result = self._process_standard_document(document_id, conversion_type)

        # Cache result
        if self.config.enable_caching:
            self._cache_result(cache_key, result)

        # Record metrics
        self._record_metrics(
            operation=conversion_type,
            document_size=document_size,
            execution_time=time.time() - start_time,
            memory_usage=self._get_memory_usage() - start_memory,
            cache_misses=1,
        )

        return result

    def _process_large_document(
        self, document_id: str, conversion_type: str
    ) -> ConversionResult:
        """Process large document with chunking and parallel processing.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            ConversionResult from optimized processing
        """
        logger.info(f"Processing large document {document_id} with optimization")

        if self.config.enable_chunking:
            # Process document in chunks
            chunks = self._create_document_chunks(document_id)

            if self.config.enable_parallel and len(chunks) > 1:
                # Process chunks in parallel
                results = self._process_chunks_parallel(chunks, conversion_type)
            else:
                # Process chunks sequentially
                results = self._process_chunks_sequential(chunks, conversion_type)

            # Merge chunk results
            final_result = self._merge_chunk_results(results)

            # Update metrics
            if self.metrics:
                self.metrics[-1].chunk_count = len(chunks)

            return final_result
        else:
            # Fall back to standard processing
            return self._process_standard_document(document_id, conversion_type)

    def _process_standard_document(
        self, document_id: str, conversion_type: str
    ) -> ConversionResult:
        """Process standard document without chunking.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            ConversionResult from standard processing
        """
        if conversion_type == "to_markdown":
            return self.converter.to_markdown(document_id)
        else:
            raise ValueError(f"Unknown conversion type: {conversion_type}")

    def _create_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Create chunks from a document for parallel processing.

        Args:
            document_id: Document identifier

        Returns:
            List of document chunks
        """
        # In a real implementation, this would fetch the document and split it
        # For now, create mock chunks based on estimated size
        document_size = self._estimate_document_size(document_id)
        chunk_count = min(
            (document_size // self.config.chunk_size) + 1, self.config.max_chunk_count
        )

        chunks = []
        for i in range(chunk_count):
            chunk = {
                "chunk_id": f"{document_id}_chunk_{i}",
                "document_id": document_id,
                "chunk_index": i,
                "start_offset": i * self.config.chunk_size,
                "end_offset": min((i + 1) * self.config.chunk_size, document_size),
            }
            chunks.append(chunk)

        logger.debug(f"Created {len(chunks)} chunks for document {document_id}")
        return chunks

    def _process_chunks_parallel(
        self, chunks: List[Dict[str, Any]], conversion_type: str
    ) -> List[ConversionResult]:
        """Process chunks in parallel.

        Args:
            chunks: List of document chunks
            conversion_type: Type of conversion

        Returns:
            List of ConversionResult for each chunk
        """
        executor = (
            self._process_pool if self.config.use_multiprocessing else self._thread_pool
        )

        if not executor:
            # Fall back to sequential processing
            return self._process_chunks_sequential(chunks, conversion_type)

        # Submit chunk processing tasks
        futures = []
        for chunk in chunks:
            future = executor.submit(self._process_single_chunk, chunk, conversion_type)
            futures.append(future)

        # Collect results
        results = []
        for future in futures:
            try:
                result = future.result(timeout=60)  # 1 minute timeout per chunk
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process chunk: {e}")
                # Create empty result for failed chunk
                results.append(
                    ConversionResult(
                        content="",
                        elements=[],
                        comments=[],
                        suggestions=[],
                        metadata={},
                        conversion_accuracy=0.0,
                        warnings=[f"Chunk processing failed: {str(e)}"],
                    )
                )

        return results

    def _process_chunks_sequential(
        self, chunks: List[Dict[str, Any]], conversion_type: str
    ) -> List[ConversionResult]:
        """Process chunks sequentially.

        Args:
            chunks: List of document chunks
            conversion_type: Type of conversion

        Returns:
            List of ConversionResult for each chunk
        """
        results = []
        for chunk in chunks:
            result = self._process_single_chunk(chunk, conversion_type)
            results.append(result)

            # Check memory usage and clean up if needed
            if self._get_memory_usage() > self.config.max_memory_usage:
                self._cleanup_memory()

        return results

    def _process_single_chunk(
        self, chunk: Dict[str, Any], conversion_type: str
    ) -> ConversionResult:
        """Process a single document chunk.

        Args:
            chunk: Document chunk information
            conversion_type: Type of conversion

        Returns:
            ConversionResult for the chunk
        """
        # In a real implementation, this would process the specific chunk
        # For now, create a mock result
        chunk_content = f"Chunk {chunk['chunk_index']} content"

        return ConversionResult(
            content=chunk_content,
            elements=[],
            comments=[],
            suggestions=[],
            metadata={
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["chunk_index"],
            },
            conversion_accuracy=0.95,
        )

    def _merge_chunk_results(self, results: List[ConversionResult]) -> ConversionResult:
        """Merge results from multiple chunks.

        Args:
            results: List of chunk results

        Returns:
            Merged ConversionResult
        """
        # Merge content
        merged_content = "\n".join(result.content for result in results)

        # Merge elements
        merged_elements = []
        for result in results:
            merged_elements.extend(result.elements)

        # Merge comments and suggestions
        merged_comments = []
        merged_suggestions = []
        for result in results:
            merged_comments.extend(result.comments)
            merged_suggestions.extend(result.suggestions)

        # Merge metadata
        merged_metadata = {
            "chunk_count": len(results),
            "chunks_processed": [
                r.metadata.get("chunk_id") for r in results if r.metadata
            ],
        }

        # Calculate average accuracy
        accuracies = [
            r.conversion_accuracy for r in results if r.conversion_accuracy > 0
        ]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0

        # Collect warnings
        merged_warnings = []
        for result in results:
            merged_warnings.extend(result.warnings)

        return ConversionResult(
            content=merged_content,
            elements=merged_elements,
            comments=merged_comments,
            suggestions=merged_suggestions,
            metadata=merged_metadata,
            conversion_accuracy=avg_accuracy,
            warnings=merged_warnings,
        )

    @lru_cache(maxsize=128)
    def optimize_search(
        self, query: str, document_ids: List[str]
    ) -> List[Tuple[str, float]]:
        """Optimize document search with caching and parallel processing.

        Args:
            query: Search query
            document_ids: List of document IDs to search

        Returns:
            List of (document_id, relevance_score) tuples
        """
        start_time = time.time()

        if self.config.enable_parallel and len(document_ids) > 10:
            # Parallel search for many documents
            results = self._parallel_search(query, document_ids)
        else:
            # Sequential search for few documents
            results = self._sequential_search(query, document_ids)

        # Sort by relevance score
        results.sort(key=lambda x: x[1], reverse=True)

        # Record metrics
        self._record_metrics(
            operation="search",
            document_size=len(document_ids),
            execution_time=time.time() - start_time,
            memory_usage=0,
        )

        return results

    def _parallel_search(
        self, query: str, document_ids: List[str]
    ) -> List[Tuple[str, float]]:
        """Perform parallel search across documents.

        Args:
            query: Search query
            document_ids: List of document IDs

        Returns:
            List of (document_id, relevance_score) tuples
        """
        executor = self._thread_pool or ThreadPoolExecutor(
            max_workers=self.config.max_workers
        )

        futures = []
        for doc_id in document_ids:
            future = executor.submit(self._search_single_document, query, doc_id)
            futures.append((doc_id, future))

        results = []
        for doc_id, future in futures:
            try:
                score = future.result(timeout=5)  # 5 second timeout per document
                results.append((doc_id, score))
            except Exception as e:
                logger.error(f"Search failed for document {doc_id}: {e}")
                results.append((doc_id, 0.0))

        return results

    def _sequential_search(
        self, query: str, document_ids: List[str]
    ) -> List[Tuple[str, float]]:
        """Perform sequential search across documents.

        Args:
            query: Search query
            document_ids: List of document IDs

        Returns:
            List of (document_id, relevance_score) tuples
        """
        results = []
        for doc_id in document_ids:
            score = self._search_single_document(query, doc_id)
            results.append((doc_id, score))

        return results

    def _search_single_document(self, query: str, document_id: str) -> float:
        """Search a single document and return relevance score.

        Args:
            query: Search query
            document_id: Document ID

        Returns:
            Relevance score (0.0 to 1.0)
        """
        # In a real implementation, this would search the document
        # For now, return a mock relevance score
        return 0.5

    def optimize_memory_usage(self):
        """Optimize memory usage by cleaning up caches and unused resources."""
        # Clear old cache entries
        if self.config.enable_caching:
            self._cleanup_cache()

        # Force garbage collection
        import gc

        gc.collect()

        # Log memory usage
        memory_usage = self._get_memory_usage()
        logger.info(
            f"Memory usage after optimization: {memory_usage / 1024 / 1024:.2f} MB"
        )

    def _get_cached_result(self, cache_key: str) -> Optional[ConversionResult]:
        """Get cached result if available and not expired.

        Args:
            cache_key: Cache key

        Returns:
            Cached ConversionResult or None
        """
        if cache_key not in self._cache:
            return None

        # Check if cache entry is expired
        timestamp = self._cache_timestamps.get(cache_key, 0)
        if time.time() - timestamp > self.config.cache_ttl:
            # Expired, remove from cache
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None

        return self._cache[cache_key]

    def _cache_result(self, cache_key: str, result: ConversionResult):
        """Cache a conversion result.

        Args:
            cache_key: Cache key
            result: Result to cache
        """
        # Enforce cache size limit
        if len(self._cache) >= self.config.cache_size:
            # Remove oldest entry
            oldest_key = min(
                self._cache_timestamps.keys(), key=self._cache_timestamps.get
            )
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()

    def _cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = time.time()
        expired_keys = []

        for key, timestamp in self._cache_timestamps.items():
            if current_time - timestamp > self.config.cache_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            del self._cache_timestamps[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _cleanup_memory(self):
        """Clean up memory by removing unnecessary data."""
        # Clear some cache entries
        if len(self._cache) > self.config.cache_size // 2:
            # Remove half of the oldest entries
            sorted_keys = sorted(
                self._cache_timestamps.keys(), key=self._cache_timestamps.get
            )
            for key in sorted_keys[: len(sorted_keys) // 2]:
                del self._cache[key]
                del self._cache_timestamps[key]

        # Force garbage collection
        import gc

        gc.collect()

    def _estimate_document_size(self, document_id: str) -> int:
        """Estimate document size in bytes.

        Args:
            document_id: Document identifier

        Returns:
            Estimated size in bytes
        """
        # In a real implementation, this would query document metadata
        # For now, return a mock size
        return 1024 * 1024 * 5  # 5MB

    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes.

        Returns:
            Memory usage in bytes
        """
        if psutil:
            try:
                process = psutil.Process()
                return process.memory_info().rss
            except Exception:
                return 0
        return 0

    def _record_metrics(
        self,
        operation: str,
        document_size: int,
        execution_time: float,
        memory_usage: int,
        cache_hits: int = 0,
        cache_misses: int = 0,
    ):
        """Record performance metrics.

        Args:
            operation: Operation name
            document_size: Document size in bytes
            execution_time: Execution time in seconds
            memory_usage: Memory usage in bytes
            cache_hits: Number of cache hits
            cache_misses: Number of cache misses
        """
        cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 0.0

        metrics = PerformanceMetrics(
            operation=operation,
            document_size=document_size,
            execution_time=execution_time,
            memory_usage=memory_usage,
            cpu_usage=cpu_percent,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

        self.metrics.append(metrics)

        # Log performance info
        logger.debug(
            f"Performance: {operation} - "
            f"Size: {document_size / 1024 / 1024:.2f}MB, "
            f"Time: {execution_time:.2f}s, "
            f"Memory: {memory_usage / 1024 / 1024:.2f}MB, "
            f"CPU: {cpu_percent:.1f}%"
        )

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report.

        Returns:
            Dictionary with performance statistics
        """
        if not self.metrics:
            return {"message": "No performance data available"}

        # Calculate aggregate statistics
        total_operations = len(self.metrics)
        avg_execution_time = (
            sum(m.execution_time for m in self.metrics) / total_operations
        )
        avg_memory_usage = sum(m.memory_usage for m in self.metrics) / total_operations
        avg_cpu_usage = sum(m.cpu_usage for m in self.metrics) / total_operations

        total_cache_hits = sum(m.cache_hits for m in self.metrics)
        total_cache_misses = sum(m.cache_misses for m in self.metrics)
        cache_hit_rate = (
            total_cache_hits / (total_cache_hits + total_cache_misses)
            if (total_cache_hits + total_cache_misses) > 0
            else 0
        )

        # Group by operation
        operations = {}
        for metric in self.metrics:
            if metric.operation not in operations:
                operations[metric.operation] = {
                    "count": 0,
                    "total_time": 0,
                    "avg_size": 0,
                    "avg_memory": 0,
                }

            op_stats = operations[metric.operation]
            op_stats["count"] += 1
            op_stats["total_time"] += metric.execution_time
            op_stats["avg_size"] = (
                op_stats["avg_size"] * (op_stats["count"] - 1) + metric.document_size
            ) / op_stats["count"]
            op_stats["avg_memory"] = (
                op_stats["avg_memory"] * (op_stats["count"] - 1) + metric.memory_usage
            ) / op_stats["count"]

        return {
            "summary": {
                "total_operations": total_operations,
                "avg_execution_time": avg_execution_time,
                "avg_memory_usage": avg_memory_usage,
                "avg_cpu_usage": avg_cpu_usage,
                "cache_hit_rate": cache_hit_rate,
            },
            "operations": operations,
            "configuration": self.config.to_dict(),
            "detailed_metrics": [
                m.to_dict() for m in self.metrics[-100:]
            ],  # Last 100 metrics
        }

    def cleanup(self):
        """Clean up resources."""
        # Shutdown thread/process pools
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
        if self._process_pool:
            self._process_pool.shutdown(wait=True)

        # Clear caches
        self._cache.clear()
        self._cache_timestamps.clear()

        logger.info("Performance optimizer cleaned up")


def performance_monitor(func: Callable) -> Callable:
    """Decorator to monitor function performance.

    Args:
        func: Function to monitor

    Returns:
        Wrapped function with performance monitoring
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = 0
        if psutil:
            try:
                start_memory = psutil.Process().memory_info().rss
            except Exception:
                pass

        try:
            result = func(*args, **kwargs)

            # Log performance metrics
            execution_time = time.time() - start_time
            memory_used = 0
            if psutil and start_memory > 0:
                try:
                    memory_used = psutil.Process().memory_info().rss - start_memory
                except Exception:
                    pass

            logger.debug(
                f"{func.__name__} - Time: {execution_time:.2f}s, "
                f"Memory: {memory_used / 1024 / 1024:.2f}MB"
            )

            return result

        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            raise

    return wrapper


class StreamingProcessor:
    """Processes large documents in a streaming fashion to minimize memory usage."""

    def __init__(self, buffer_size: int = 8192):
        """Initialize streaming processor.

        Args:
            buffer_size: Buffer size for streaming
        """
        self.buffer_size = buffer_size

    async def process_document_stream(
        self, document_id: str, process_func: Callable[[str], str]
    ) -> AsyncIterator[str]:
        """Process document in streaming fashion.

        Args:
            document_id: Document identifier
            process_func: Function to process each chunk

        Yields:
            Processed chunks
        """
        # In a real implementation, this would stream from the document source
        # For now, simulate streaming with mock data
        for i in range(10):
            chunk = f"Document chunk {i} for {document_id}"
            processed_chunk = process_func(chunk)
            yield processed_chunk

            # Simulate processing delay
            await asyncio.sleep(0.1)

    def process_large_file(
        self, file_path: Path, output_path: Path, process_func: Callable[[str], str]
    ):
        """Process large file with streaming.

        Args:
            file_path: Input file path
            output_path: Output file path
            process_func: Function to process each chunk
        """
        with open(file_path, "r", encoding="utf-8") as infile:
            with open(output_path, "w", encoding="utf-8") as outfile:
                while True:
                    chunk = infile.read(self.buffer_size)
                    if not chunk:
                        break

                    processed_chunk = process_func(chunk)
                    outfile.write(processed_chunk)

        logger.info(f"Processed {file_path} to {output_path} with streaming")
