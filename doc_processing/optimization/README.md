# Performance Optimization Module

This module provides comprehensive performance optimization for document processing operations, particularly focused on handling large legal documents efficiently.

## Key Components

### 1. PerformanceOptimizer
The main optimization engine that provides:
- Document chunking for large files
- Parallel processing with configurable workers
- Multi-level caching (memory + disk)
- Streaming support for memory efficiency
- Performance metrics collection

```python
from doc_processing.optimization import PerformanceOptimizer, OptimizationConfig

# Configure optimization
config = OptimizationConfig(
    enable_chunking=True,
    chunk_size=1024 * 1024,  # 1MB chunks
    enable_parallel=True,
    max_workers=4,
    enable_caching=True,
    cache_size=256
)

# Create optimizer
optimizer = PerformanceOptimizer(config)

# Optimize document conversion
result = optimizer.optimize_conversion("document_id", "to_markdown")
```

### 2. CacheManager
Provides multi-level caching with automatic promotion between cache levels:
- **MemoryCache**: Fast in-memory LRU cache
- **FileCache**: Persistent disk-based cache
- **DocumentCache**: Specialized cache for document operations

```python
from doc_processing.optimization import CacheManager, DocumentCache

# Initialize cache manager
cache_manager = CacheManager({
    "memory_cache_mb": 100,
    "file_cache_mb": 1000,
    "cache_dir": ".cache"
})

# Use document cache
doc_cache = DocumentCache(cache_manager)
doc_cache.set_conversion("doc_id", "markdown", converted_content)
cached_content = doc_cache.get_conversion("doc_id", "markdown")
```

### 3. LargeDocumentHandler
Specialized handler for documents exceeding standard memory limits:
- Asynchronous processing with configurable concurrency
- Memory-mapped file support
- Streaming output for minimal memory footprint
- Adaptive optimization based on document size

```python
from doc_processing.optimization import LargeDocumentHandler

handler = LargeDocumentHandler(
    chunk_size=1024 * 1024,  # 1MB
    max_memory=512 * 1024 * 1024  # 512MB
)

# Async processing
result = await handler.process_large_document_async("large_doc_id")

# Streaming processing
for chunk in handler.process_large_document_streaming("huge_doc_id"):
    process_chunk(chunk)
```

### 4. Performance Benchmarking
Comprehensive benchmarking system for optimization tuning:

```python
from doc_processing.optimization import PerformanceBenchmark

benchmark = PerformanceBenchmark()

# Run full benchmark suite
results = benchmark.run_full_benchmark()

# Test specific optimizations
cache_results = benchmark.benchmark_cache_effectiveness()
async_results = await benchmark.benchmark_async_processing()
memory_results = benchmark.benchmark_memory_usage()
```

## Optimization Strategies

### Document Size-Based Optimization

| Document Size | Strategy | Configuration |
|--------------|----------|---------------|
| < 10MB | Standard | No chunking, optional caching |
| 10-50MB | Optimized | Chunking enabled, parallel processing |
| 50-100MB | High | Smaller chunks, streaming enabled |
| > 100MB | Ultra | Minimal chunks, full streaming, compression |

### Performance Guidelines

1. **For Frequent Access**: Enable caching for up to 90% performance improvement
2. **For Large Documents**: Enable chunking and parallel processing
3. **For Memory Constraints**: Use streaming mode with small buffer sizes
4. **For Batch Processing**: Use async processing with appropriate concurrency

## Configuration Options

```python
OptimizationConfig(
    # Chunking
    enable_chunking=True,
    chunk_size=1048576,  # 1MB
    max_chunk_count=100,

    # Parallel Processing
    enable_parallel=True,
    max_workers=4,
    use_multiprocessing=False,  # Threading by default

    # Caching
    enable_caching=True,
    cache_size=128,
    cache_ttl=3600,  # 1 hour

    # Memory Management
    max_memory_usage=536870912,  # 512MB
    enable_streaming=True,
    buffer_size=8192,  # 8KB

    # Advanced
    enable_lazy_loading=True,
    enable_compression=True,
    enable_incremental_processing=True
)
```

## Performance Metrics

The optimizer collects detailed performance metrics:

```python
# Get performance report
report = optimizer.get_performance_report()

# Report includes:
# - Operation counts and timings
# - Cache hit rates
# - Memory usage patterns
# - CPU utilization
# - Per-operation breakdowns
```

## Best Practices

1. **Profile First**: Run benchmarks to determine optimal configuration
2. **Monitor Memory**: Use `optimize_memory_usage()` periodically
3. **Clean Up**: Always call `cleanup()` when done
4. **Cache Wisely**: Balance cache size with available memory
5. **Chunk Appropriately**: Larger chunks for sequential access, smaller for parallel

## Example: Complete Optimization Pipeline

```python
import asyncio
from doc_processing.optimization import (
    PerformanceOptimizer,
    OptimizationConfig,
    CacheManager,
    LargeDocumentHandler,
    run_quick_benchmark
)

async def optimize_document_pipeline():
    # Run benchmark to determine best config
    benchmark_results = run_quick_benchmark()

    # Configure based on results
    config = OptimizationConfig(
        enable_chunking=True,
        enable_parallel=True,
        enable_caching=True
    )

    # Set up components
    cache_manager = CacheManager()
    optimizer = PerformanceOptimizer(config)
    large_handler = LargeDocumentHandler(optimizer=optimizer)

    # Process document
    doc_id = "legal_contract_100mb"

    # Check document size
    if is_large_document(doc_id):
        # Use async processing for large docs
        result = await large_handler.process_large_document_async(doc_id)
    else:
        # Use standard optimization
        result = optimizer.optimize_conversion(doc_id, "to_markdown")

    # Get performance stats
    stats = optimizer.get_performance_report()
    print(f"Processed in {stats['summary']['avg_execution_time']:.2f}s")

    # Clean up
    optimizer.cleanup()

    return result

# Run the pipeline
result = asyncio.run(optimize_document_pipeline())
```

## Troubleshooting

### High Memory Usage
- Enable streaming mode
- Reduce chunk size
- Increase memory cleanup frequency
- Use file-based caching instead of memory

### Slow Performance
- Enable parallel processing
- Increase worker count
- Enable caching
- Run performance benchmark to identify bottlenecks

### Cache Misses
- Increase cache size
- Extend cache TTL
- Use persistent file cache
- Implement cache warming strategies
