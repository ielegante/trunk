"""Performance optimization for document processing."""

from .benchmarks import BenchmarkResult, PerformanceBenchmark, run_quick_benchmark
from .cache_manager import CacheManager, DocumentCache, FileCache, MemoryCache, cached
from .large_document_handler import (
    ChunkProcessingResult,
    DocumentChunk,
    DocumentSplitter,
    LargeDocumentHandler,
)
from .performance_optimizer import (
    OptimizationConfig,
    PerformanceMetrics,
    PerformanceOptimizer,
    StreamingProcessor,
    performance_monitor,
)

__all__ = [
    # Performance optimizer
    "PerformanceOptimizer",
    "PerformanceMetrics",
    "OptimizationConfig",
    "performance_monitor",
    "StreamingProcessor",
    # Cache management
    "CacheManager",
    "DocumentCache",
    "MemoryCache",
    "FileCache",
    "cached",
    # Large document handling
    "LargeDocumentHandler",
    "DocumentChunk",
    "ChunkProcessingResult",
    "DocumentSplitter",
    # Benchmarking
    "PerformanceBenchmark",
    "BenchmarkResult",
    "run_quick_benchmark",
]
