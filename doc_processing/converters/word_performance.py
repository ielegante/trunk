"""Performance optimization and streaming processing for large Word documents."""

import gc
import logging
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for document processing performance."""

    start_time: float
    end_time: Optional[float] = None
    memory_peak_mb: float = 0.0
    elements_processed: int = 0
    processing_rate_elements_per_sec: float = 0.0
    file_size_mb: float = 0.0
    chunk_count: int = 0

    def calculate_final_metrics(self):
        """Calculate final performance metrics."""
        if self.end_time:
            duration = self.end_time - self.start_time
            self.processing_rate_elements_per_sec = (
                self.elements_processed / duration if duration > 0 else 0.0
            )


@dataclass
class ChunkProcessingResult:
    """Result from processing a document chunk."""

    chunk_id: str
    elements: List[Any]
    text_content: str
    processing_time: float
    memory_used_mb: float
    error: Optional[str] = None


class MemoryMonitor:
    """Monitor memory usage during document processing."""

    def __init__(self):
        self.peak_memory = 0.0
        self.current_memory = 0.0
        self.monitoring = False
        self._monitor_thread = None

    def start_monitoring(self):
        """Start memory monitoring in background thread."""
        self.monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_memory)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def stop_monitoring(self) -> float:
        """Stop monitoring and return peak memory usage."""
        self.monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        return self.peak_memory

    def _monitor_memory(self):
        """Background memory monitoring loop."""
        try:
            import psutil

            process = psutil.Process()

            while self.monitoring:
                memory_info = process.memory_info()
                self.current_memory = memory_info.rss / 1024 / 1024  # MB
                self.peak_memory = max(self.peak_memory, self.current_memory)
                time.sleep(0.1)  # Check every 100ms
        except ImportError:
            logger.warning("psutil not available for memory monitoring")
        except Exception as e:
            logger.error(f"Memory monitoring error: {e}")


class StreamingWordProcessor:
    """High-performance streaming processor for large Word documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize streaming processor.

        Args:
            config: Configuration for performance optimization
        """
        self.config = config or {}

        # Performance settings
        self.chunk_size = self.config.get("chunk_size", 1000)  # Elements per chunk
        self.max_workers = self.config.get("max_workers", 4)
        self.memory_limit_mb = self.config.get("memory_limit_mb", 512)
        self.enable_caching = self.config.get("enable_caching", True)
        self.lazy_loading = self.config.get("lazy_loading", True)

        # Processing state
        self.style_cache = {} if self.enable_caching else None
        self.memory_monitor = MemoryMonitor()

        # XML namespaces for efficient parsing
        self.namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }

    def process_document_streaming(
        self, word_file: Path
    ) -> Iterator[ChunkProcessingResult]:
        """Process Word document in streaming chunks for memory efficiency.

        Args:
            word_file: Path to Word document

        Yields:
            ChunkProcessingResult objects for each processed chunk
        """
        if not word_file.exists():
            raise FileNotFoundError(f"Word document not found: {word_file}")

        file_size_mb = word_file.stat().st_size / 1024 / 1024
        logger.info(
            f"Starting streaming processing of {word_file} ({file_size_mb:.2f} MB)"
        )

        self.memory_monitor.start_monitoring()

        try:
            with zipfile.ZipFile(word_file, "r") as zip_file:
                # Process document in chunks
                yield from self._process_document_chunks(zip_file, file_size_mb)

        finally:
            peak_memory = self.memory_monitor.stop_monitoring()
            logger.info(f"Peak memory usage: {peak_memory:.2f} MB")

    def _process_document_chunks(
        self, zip_file: zipfile.ZipFile, file_size_mb: float
    ) -> Iterator[ChunkProcessingResult]:
        """Process document content in manageable chunks."""
        try:
            with zip_file.open("word/document.xml") as doc_file:
                # Use iterparse for memory-efficient XML processing
                chunk_id = 0
                current_chunk = []

                for event, elem in ET.iterparse(doc_file, events=("start", "end")):
                    if event == "end":
                        # Check if this is a significant element
                        if self._is_processable_element(elem):
                            current_chunk.append(elem)

                            # Process chunk when it reaches target size
                            if len(current_chunk) >= self.chunk_size:
                                yield self._process_chunk(
                                    current_chunk, chunk_id, file_size_mb
                                )
                                chunk_id += 1
                                current_chunk = []

                                # Check memory usage
                                if (
                                    self.memory_monitor.current_memory
                                    > self.memory_limit_mb
                                ):
                                    logger.warning(
                                        f"Memory limit exceeded: {self.memory_monitor.current_memory:.2f} MB"
                                    )
                                    gc.collect()  # Force garbage collection

                        # Clear processed element to free memory
                        elem.clear()

                # Process remaining elements
                if current_chunk:
                    yield self._process_chunk(current_chunk, chunk_id, file_size_mb)

        except Exception as e:
            logger.error(f"Error processing document chunks: {e}")
            yield ChunkProcessingResult(
                chunk_id="error",
                elements=[],
                text_content="",
                processing_time=0.0,
                memory_used_mb=0.0,
                error=str(e),
            )

    def _is_processable_element(self, elem: ET.Element) -> bool:
        """Check if element should be processed."""
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        return tag_name in ["p", "tbl", "tr", "tc", "r", "t"]

    def _process_chunk(
        self, elements: List[ET.Element], chunk_id: int, file_size_mb: float
    ) -> ChunkProcessingResult:
        """Process a chunk of elements."""
        start_time = time.time()
        start_memory = self.memory_monitor.current_memory

        try:
            # Extract text content efficiently
            text_content = self._extract_text_from_elements(elements)

            # Process elements into structured format
            processed_elements = self._convert_elements_to_structure(elements)

            processing_time = time.time() - start_time
            memory_used = self.memory_monitor.current_memory - start_memory

            logger.debug(
                f"Processed chunk {chunk_id}: {len(elements)} elements in {processing_time:.3f}s"
            )

            return ChunkProcessingResult(
                chunk_id=str(chunk_id),
                elements=processed_elements,
                text_content=text_content,
                processing_time=processing_time,
                memory_used_mb=memory_used,
            )

        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id}: {e}")
            return ChunkProcessingResult(
                chunk_id=str(chunk_id),
                elements=[],
                text_content="",
                processing_time=time.time() - start_time,
                memory_used_mb=0.0,
                error=str(e),
            )

    def _extract_text_from_elements(self, elements: List[ET.Element]) -> str:
        """Extract text content from elements efficiently."""
        text_parts = []

        for elem in elements:
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag_name == "t" and elem.text:
                text_parts.append(elem.text)
            elif tag_name in ["p", "tc"]:
                # Extract text from child elements
                for text_elem in elem.findall(".//w:t", self.namespaces):
                    if text_elem.text:
                        text_parts.append(text_elem.text)

        return "".join(text_parts)

    def _convert_elements_to_structure(
        self, elements: List[ET.Element]
    ) -> List[Dict[str, Any]]:
        """Convert XML elements to structured format efficiently."""
        structured_elements = []

        for elem in elements:
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            element_data = {
                "type": tag_name,
                "text": elem.text or "",
                "attributes": dict(elem.attrib),
                "children_count": len(list(elem)),
            }

            # Add specific processing for important elements
            if tag_name == "p":
                element_data.update(self._process_paragraph_efficiently(elem))
            elif tag_name == "tbl":
                element_data.update(self._process_table_efficiently(elem))

            structured_elements.append(element_data)

        return structured_elements

    def _process_paragraph_efficiently(self, para_elem: ET.Element) -> Dict[str, Any]:
        """Process paragraph element efficiently."""
        para_data = {
            "paragraph_type": "normal",
            "run_count": 0,
            "has_formatting": False,
        }

        # Quick check for runs and formatting
        runs = para_elem.findall("w:r", self.namespaces)
        para_data["run_count"] = len(runs)

        # Check for paragraph properties
        p_pr = para_elem.find("w:pPr", self.namespaces)
        if p_pr is not None:
            para_data["has_formatting"] = True

            # Check for style
            style = p_pr.find("w:pStyle", self.namespaces)
            if style is not None:
                style_val = style.get(f"{{{self.namespaces['w']}}}val")
                if style_val and "heading" in style_val.lower():
                    para_data["paragraph_type"] = "heading"

        return para_data

    def _process_table_efficiently(self, table_elem: ET.Element) -> Dict[str, Any]:
        """Process table element efficiently."""
        table_data = {"table_type": "data", "row_count": 0, "column_count": 0}

        # Count rows
        rows = table_elem.findall("w:tr", self.namespaces)
        table_data["row_count"] = len(rows)

        # Count columns from first row
        if rows:
            cells = rows[0].findall("w:tc", self.namespaces)
            table_data["column_count"] = len(cells)

        return table_data

    def process_document_parallel(self, word_file: Path) -> ProcessingMetrics:
        """Process Word document using parallel workers for large documents.

        Args:
            word_file: Path to Word document

        Returns:
            ProcessingMetrics with performance data
        """
        metrics = ProcessingMetrics(
            start_time=time.time(), file_size_mb=word_file.stat().st_size / 1024 / 1024
        )

        self.memory_monitor.start_monitoring()

        try:
            # Collect chunks for parallel processing
            chunks = list(self.process_document_streaming(word_file))
            metrics.chunk_count = len(chunks)

            # Process chunks in parallel
            results = self._process_chunks_parallel(chunks)

            # Aggregate results
            total_elements = sum(
                len(result.elements) for result in results if not result.error
            )
            metrics.elements_processed = total_elements

            logger.info(
                f"Parallel processing completed: {total_elements} elements in {len(chunks)} chunks"
            )

        finally:
            metrics.memory_peak_mb = self.memory_monitor.stop_monitoring()
            metrics.end_time = time.time()
            metrics.calculate_final_metrics()

        return metrics

    def _process_chunks_parallel(
        self, chunks: List[ChunkProcessingResult]
    ) -> List[ChunkProcessingResult]:
        """Process chunks using parallel workers."""
        results = []

        # Create work queue
        work_queue = Queue()
        for chunk in chunks:
            work_queue.put(chunk)

        # Process with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit processing tasks
            futures = []
            for i in range(min(self.max_workers, len(chunks))):
                future = executor.submit(self._parallel_worker, work_queue)
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    worker_results = future.result()
                    results.extend(worker_results)
                except Exception as e:
                    logger.error(f"Parallel worker error: {e}")

        return results

    def _parallel_worker(self, work_queue: Queue) -> List[ChunkProcessingResult]:
        """Worker function for parallel chunk processing."""
        worker_results = []

        while not work_queue.empty():
            try:
                chunk = work_queue.get_nowait()

                # Perform additional processing on the chunk
                enhanced_chunk = self._enhance_chunk_processing(chunk)
                worker_results.append(enhanced_chunk)

                work_queue.task_done()

            except Exception as e:
                logger.error(f"Worker processing error: {e}")
                break

        return worker_results

    def _enhance_chunk_processing(
        self, chunk: ChunkProcessingResult
    ) -> ChunkProcessingResult:
        """Enhance chunk processing with additional analysis."""
        if chunk.error:
            return chunk

        start_time = time.time()

        # Add text analysis
        enhanced_text = self._analyze_text_content(chunk.text_content)

        # Update processing time
        additional_time = time.time() - start_time
        chunk.processing_time += additional_time

        return chunk

    def _analyze_text_content(self, text: str) -> str:
        """Analyze and potentially enhance text content."""
        if not text:
            return text

        # Simple text cleaning and analysis
        cleaned_text = text.strip()

        # Remove excessive whitespace
        cleaned_text = " ".join(cleaned_text.split())

        return cleaned_text

    def extract_text_streaming(self, word_file: Path) -> Generator[str, None, None]:
        """Extract text content in streaming fashion for memory efficiency.

        Args:
            word_file: Path to Word document

        Yields:
            Text content chunks
        """
        logger.info(f"Starting streaming text extraction from {word_file}")

        try:
            with zipfile.ZipFile(word_file, "r") as zip_file:
                with zip_file.open("word/document.xml") as doc_file:
                    current_text = []
                    text_chunk_size = 1000  # Characters per chunk

                    for event, elem in ET.iterparse(doc_file, events=("end",)):
                        if elem.tag.endswith("}t") and elem.text:
                            current_text.append(elem.text)

                            # Yield chunk when it reaches target size
                            current_length = sum(len(text) for text in current_text)
                            if current_length >= text_chunk_size:
                                yield "".join(current_text)
                                current_text = []

                        # Clear element to free memory
                        elem.clear()

                    # Yield remaining text
                    if current_text:
                        yield "".join(current_text)

        except Exception as e:
            logger.error(f"Error in streaming text extraction: {e}")
            raise

    def get_processing_statistics(self, word_file: Path) -> Dict[str, Any]:
        """Get statistics about document processing requirements.

        Args:
            word_file: Path to Word document

        Returns:
            Dictionary with processing statistics and recommendations
        """
        stats = {"file_info": {}, "estimated_processing": {}, "recommendations": {}}

        # File information
        file_stat = word_file.stat()
        stats["file_info"] = {
            "size_mb": file_stat.st_size / 1024 / 1024,
            "size_bytes": file_stat.st_size,
            "file_name": word_file.name,
        }

        # Quick analysis of document structure
        try:
            with zipfile.ZipFile(word_file, "r") as zip_file:
                # Count elements in document.xml
                with zip_file.open("word/document.xml") as doc_file:
                    element_count = 0
                    text_length = 0

                    for event, elem in ET.iterparse(doc_file, events=("end",)):
                        element_count += 1
                        if elem.tag.endswith("}t") and elem.text:
                            text_length += len(elem.text)
                        elem.clear()

                    stats["estimated_processing"] = {
                        "total_elements": element_count,
                        "estimated_text_length": text_length,
                        "estimated_chunks": (element_count // self.chunk_size) + 1,
                        "estimated_processing_time_seconds": element_count
                        / 1000,  # Rough estimate
                        "estimated_memory_mb": max(
                            50, element_count / 100
                        ),  # Rough estimate
                    }

        except Exception as e:
            logger.warning(f"Could not analyze document structure: {e}")
            stats["estimated_processing"] = {"error": str(e)}

        # Recommendations based on file size and complexity
        file_size_mb = stats["file_info"]["size_mb"]
        estimated_elements = stats["estimated_processing"].get("total_elements", 0)

        recommendations = []

        if file_size_mb > 50:
            recommendations.append("Use streaming processing for large file")
            recommendations.append("Enable parallel processing")
            recommendations.append("Increase memory limit")

        if estimated_elements > 10000:
            recommendations.append("Use chunked processing")
            recommendations.append("Enable lazy loading")
            recommendations.append("Consider text-only extraction for initial analysis")

        if file_size_mb > 100:
            recommendations.append("Process in background thread")
            recommendations.append("Implement progress tracking")
            recommendations.append("Enable aggressive memory management")

        stats["recommendations"] = recommendations

        return stats

    def optimize_for_large_documents(self, word_file: Path) -> Dict[str, Any]:
        """Optimize processing configuration for large documents.

        Args:
            word_file: Path to Word document

        Returns:
            Optimized configuration and processing plan
        """
        stats = self.get_processing_statistics(word_file)
        file_size_mb = stats["file_info"]["size_mb"]
        estimated_elements = stats["estimated_processing"].get("total_elements", 0)

        # Adaptive configuration based on document size
        optimized_config = {
            "chunk_size": self.chunk_size,
            "max_workers": self.max_workers,
            "memory_limit_mb": self.memory_limit_mb,
            "processing_strategy": "standard",
        }

        if file_size_mb > 10:
            optimized_config.update(
                {
                    "chunk_size": max(500, self.chunk_size // 2),
                    "memory_limit_mb": min(1024, self.memory_limit_mb * 2),
                    "processing_strategy": "streaming",
                }
            )

        if file_size_mb > 50:
            optimized_config.update(
                {
                    "chunk_size": 200,
                    "max_workers": min(8, self.max_workers * 2),
                    "memory_limit_mb": 2048,
                    "processing_strategy": "parallel_streaming",
                }
            )

        if estimated_elements > 50000:
            optimized_config.update(
                {
                    "chunk_size": 100,
                    "enable_aggressive_gc": True,
                    "processing_strategy": "memory_optimized",
                }
            )

        processing_plan = {
            "recommended_config": optimized_config,
            "estimated_time_minutes": (estimated_elements / 10000)
            * (file_size_mb / 10),
            "estimated_peak_memory_mb": optimized_config["memory_limit_mb"] * 0.8,
            "processing_steps": [
                "Initialize streaming processor with optimized config",
                "Start memory monitoring",
                "Process document in chunks",
                "Aggregate results with memory management",
                "Generate performance report",
            ],
        }

        logger.info(
            f"Optimized configuration for {word_file.name}: {optimized_config['processing_strategy']}"
        )

        return processing_plan


class WordDocumentCache:
    """Caching system for frequently accessed Word document components."""

    def __init__(self, max_size: int = 100):
        """Initialize document cache.

        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self.lock:
            if key in self.cache:
                self.access_times[key] = time.time()
                return self.cache[key]
            return None

    def put(self, key: str, value: Any):
        """Put item in cache."""
        with self.lock:
            # Remove oldest items if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.access_times.keys(), key=self.access_times.get)
                del self.cache[oldest_key]
                del self.access_times[oldest_key]

            self.cache[key] = value
            self.access_times[key] = time.time()

    def clear(self):
        """Clear all cached items."""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_rate": 0.0,  # Would need hit/miss tracking
                "keys": list(self.cache.keys()),
            }
