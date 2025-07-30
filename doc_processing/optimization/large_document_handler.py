"""Specialized handler for large document processing."""

import asyncio
import json
import logging
import mmap
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple

from ..converters.google_docs import (
    ConversionResult,
    DocumentElement,
    GoogleDocsConverter,
)
from .performance_optimizer import (
    OptimizationConfig,
    PerformanceOptimizer,
    performance_monitor,
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of a large document."""

    chunk_id: str
    document_id: str
    chunk_index: int
    start_offset: int
    end_offset: int
    content: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class ChunkProcessingResult:
    """Result of processing a document chunk."""

    chunk_id: str
    success: bool
    content: str
    elements: List[DocumentElement]
    processing_time: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["elements"] = [elem.__dict__ for elem in self.elements]
        return data


class LargeDocumentHandler:
    """Handles processing of large documents with optimized memory usage."""

    def __init__(
        self,
        converter: Optional[GoogleDocsConverter] = None,
        optimizer: Optional[PerformanceOptimizer] = None,
        chunk_size: int = 1024 * 1024,  # 1MB default chunk size
        max_memory: int = 512 * 1024 * 1024,  # 512MB max memory
    ):
        """Initialize large document handler.

        Args:
            converter: GoogleDocsConverter instance
            optimizer: PerformanceOptimizer instance
            chunk_size: Size of each chunk in bytes
            max_memory: Maximum memory usage in bytes
        """
        self.converter = converter or GoogleDocsConverter({})
        self.optimizer = optimizer or PerformanceOptimizer(
            OptimizationConfig(
                chunk_size=chunk_size,
                max_memory_usage=max_memory,
                enable_streaming=True,
            )
        )
        self.chunk_size = chunk_size
        self.max_memory = max_memory

        # Temporary storage for processing
        self.temp_dir = Path(tempfile.gettempdir()) / "trunk_large_docs"
        self.temp_dir.mkdir(exist_ok=True)

    @performance_monitor
    async def process_large_document_async(
        self, document_id: str, output_path: Optional[Path] = None
    ) -> ConversionResult:
        """Process large document asynchronously.

        Args:
            document_id: Document identifier
            output_path: Optional output path for processed document

        Returns:
            ConversionResult from processing
        """
        logger.info(f"Starting async processing of large document {document_id}")

        # Create chunks
        chunks = await self._create_chunks_async(document_id)

        # Process chunks concurrently
        chunk_results = await self._process_chunks_async(chunks)

        # Merge results
        final_result = self._merge_chunk_results(chunk_results)

        # Save to output if specified
        if output_path:
            await self._save_result_async(final_result, output_path)

        return final_result

    def process_large_document_streaming(
        self, document_id: str, output_stream: Optional[Any] = None
    ) -> Iterator[str]:
        """Process large document with streaming output.

        Args:
            document_id: Document identifier
            output_stream: Optional output stream

        Yields:
            Processed content chunks
        """
        logger.info(f"Starting streaming processing of document {document_id}")

        # Create temporary file for document
        temp_file = self.temp_dir / f"{document_id}_temp.bin"

        try:
            # Fetch document to temporary file
            self._fetch_document_to_file(document_id, temp_file)

            # Process file with memory mapping
            with open(temp_file, "r+b") as f:
                with mmap.mmap(f.fileno(), 0) as mmapped_file:
                    yield from self._process_mmap_chunks(mmapped_file, document_id)

        finally:
            # Clean up temporary file
            if temp_file.exists():
                temp_file.unlink()

    def optimize_large_document_conversion(
        self, document_id: str, conversion_type: str = "to_markdown"
    ) -> ConversionResult:
        """Optimize conversion of large documents.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            Optimized ConversionResult
        """
        # Estimate document size
        doc_size = self._estimate_document_size(document_id)

        if doc_size > 100 * 1024 * 1024:  # > 100MB
            logger.info(
                f"Document {document_id} is very large ({doc_size / 1024 / 1024:.1f}MB), using ultra optimization"
            )
            return self._ultra_optimize_conversion(document_id, conversion_type)
        elif doc_size > 50 * 1024 * 1024:  # > 50MB
            logger.info(
                f"Document {document_id} is large ({doc_size / 1024 / 1024:.1f}MB), using high optimization"
            )
            return self._high_optimize_conversion(document_id, conversion_type)
        else:
            # Use standard optimization
            return self.optimizer.optimize_conversion(document_id, conversion_type)

    async def _create_chunks_async(self, document_id: str) -> List[DocumentChunk]:
        """Create document chunks asynchronously.

        Args:
            document_id: Document identifier

        Returns:
            List of DocumentChunk objects
        """
        # Fetch document metadata
        doc_size = self._estimate_document_size(document_id)
        chunk_count = (doc_size // self.chunk_size) + 1

        chunks = []
        for i in range(chunk_count):
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{i}",
                document_id=document_id,
                chunk_index=i,
                start_offset=i * self.chunk_size,
                end_offset=min((i + 1) * self.chunk_size, doc_size),
                content="",  # Will be populated during processing
                metadata={"chunk_size": self.chunk_size},
            )
            chunks.append(chunk)

        return chunks

    async def _process_chunks_async(
        self, chunks: List[DocumentChunk]
    ) -> List[ChunkProcessingResult]:
        """Process chunks asynchronously.

        Args:
            chunks: List of document chunks

        Returns:
            List of ChunkProcessingResult objects
        """
        # Create tasks for concurrent processing
        tasks = []
        for chunk in chunks:
            task = asyncio.create_task(self._process_single_chunk_async(chunk))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert results
        chunk_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle failed chunk
                chunk_results.append(
                    ChunkProcessingResult(
                        chunk_id=chunks[i].chunk_id,
                        success=False,
                        content="",
                        elements=[],
                        processing_time=0.0,
                        error=str(result),
                    )
                )
            else:
                chunk_results.append(result)

        return chunk_results

    async def _process_single_chunk_async(
        self, chunk: DocumentChunk
    ) -> ChunkProcessingResult:
        """Process a single chunk asynchronously.

        Args:
            chunk: Document chunk to process

        Returns:
            ChunkProcessingResult
        """
        import time

        start_time = time.time()

        try:
            # Simulate chunk processing
            # In real implementation, this would fetch and process the chunk
            await asyncio.sleep(0.1)  # Simulate processing delay

            # Create mock result
            content = f"Processed content for chunk {chunk.chunk_index}"
            elements = [
                DocumentElement(
                    element_type="text",
                    content=content,
                    formatting={},
                    start_index=chunk.start_offset,
                    end_index=chunk.end_offset,
                )
            ]

            processing_time = time.time() - start_time

            return ChunkProcessingResult(
                chunk_id=chunk.chunk_id,
                success=True,
                content=content,
                elements=elements,
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(f"Failed to process chunk {chunk.chunk_id}: {e}")
            raise

    def _merge_chunk_results(
        self, chunk_results: List[ChunkProcessingResult]
    ) -> ConversionResult:
        """Merge results from multiple chunks.

        Args:
            chunk_results: List of chunk processing results

        Returns:
            Merged ConversionResult
        """
        # Sort by chunk index
        chunk_results.sort(key=lambda r: int(r.chunk_id.split("_")[-1]))

        # Merge content
        merged_content = []
        merged_elements = []
        total_processing_time = 0.0
        failed_chunks = []

        for result in chunk_results:
            if result.success:
                merged_content.append(result.content)
                merged_elements.extend(result.elements)
                total_processing_time += result.processing_time
            else:
                failed_chunks.append(result.chunk_id)

        # Create warnings for failed chunks
        warnings = []
        if failed_chunks:
            warnings.append(f"Failed to process chunks: {', '.join(failed_chunks)}")

        return ConversionResult(
            content="\n".join(merged_content),
            elements=merged_elements,
            comments=[],
            suggestions=[],
            metadata={
                "chunk_count": len(chunk_results),
                "failed_chunks": len(failed_chunks),
                "total_processing_time": total_processing_time,
            },
            conversion_accuracy=1.0 - (len(failed_chunks) / len(chunk_results)),
            warnings=warnings,
        )

    async def _save_result_async(self, result: ConversionResult, output_path: Path):
        """Save result to file asynchronously.

        Args:
            result: ConversionResult to save
            output_path: Output file path
        """
        # Save content
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content asynchronously
        import aiofiles

        async with aiofiles.open(str(output_path), "w") as f:
            await f.write(result.content)

        # Save metadata
        metadata_path = output_path.with_suffix(".meta.json")
        async with aiofiles.open(str(metadata_path), "w") as f:
            metadata = {
                "metadata": result.metadata,
                "accuracy": result.conversion_accuracy,
                "warnings": result.warnings,
                "element_count": len(result.elements),
                "comment_count": len(result.comments),
                "suggestion_count": len(result.suggestions),
            }
            await f.write(json.dumps(metadata, indent=2))

    def _fetch_document_to_file(self, document_id: str, file_path: Path):
        """Fetch document content to a file.

        Args:
            document_id: Document identifier
            file_path: Path to save document
        """
        # In real implementation, this would fetch the document
        # For now, create mock content
        with open(file_path, "wb") as f:
            # Write mock large content
            for i in range(1000):
                f.write(f"Document {document_id} content block {i}\n".encode())

    def _process_mmap_chunks(
        self, mmapped_file: mmap.mmap, document_id: str
    ) -> Iterator[str]:
        """Process memory-mapped file in chunks.

        Args:
            mmapped_file: Memory-mapped file
            document_id: Document identifier

        Yields:
            Processed content chunks
        """
        file_size = len(mmapped_file)
        offset = 0

        while offset < file_size:
            # Read chunk
            chunk_size = min(self.chunk_size, file_size - offset)
            chunk_data = mmapped_file[offset : offset + chunk_size]

            # Process chunk (in real implementation, would apply conversion)
            processed_chunk = chunk_data.decode("utf-8", errors="ignore")

            yield processed_chunk

            offset += chunk_size

    def _estimate_document_size(self, document_id: str) -> int:
        """Estimate document size in bytes.

        Args:
            document_id: Document identifier

        Returns:
            Estimated size in bytes
        """
        # In real implementation, would query document metadata
        # For now, return mock size based on document ID hash
        return (hash(document_id) % 100 + 50) * 1024 * 1024  # 50-150MB

    def _ultra_optimize_conversion(
        self, document_id: str, conversion_type: str
    ) -> ConversionResult:
        """Ultra-optimized conversion for very large documents.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            ConversionResult
        """
        logger.info(f"Applying ultra optimization for document {document_id}")

        # Use minimal chunk size for extreme memory efficiency
        ultra_config = OptimizationConfig(
            chunk_size=256 * 1024,  # 256KB chunks
            max_chunk_count=1000,
            enable_streaming=True,
            enable_compression=True,
            enable_incremental_processing=True,
        )

        ultra_optimizer = PerformanceOptimizer(ultra_config, self.converter)
        return ultra_optimizer.optimize_conversion(document_id, conversion_type)

    def _high_optimize_conversion(
        self, document_id: str, conversion_type: str
    ) -> ConversionResult:
        """High optimization for large documents.

        Args:
            document_id: Document identifier
            conversion_type: Type of conversion

        Returns:
            ConversionResult
        """
        logger.info(f"Applying high optimization for document {document_id}")

        # Use balanced configuration
        high_config = OptimizationConfig(
            chunk_size=512 * 1024,  # 512KB chunks
            max_chunk_count=500,
            enable_streaming=True,
            enable_compression=True,
        )

        high_optimizer = PerformanceOptimizer(high_config, self.converter)
        return high_optimizer.optimize_conversion(document_id, conversion_type)

    def cleanup(self):
        """Clean up temporary files and resources."""
        # Clean up temporary directory
        if self.temp_dir.exists():
            for file in self.temp_dir.iterdir():
                try:
                    file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up {file}: {e}")

        # Clean up optimizer
        if self.optimizer:
            self.optimizer.cleanup()


class DocumentSplitter:
    """Splits large documents into manageable sections."""

    def __init__(self, section_size: int = 10000):
        """Initialize document splitter.

        Args:
            section_size: Target size for each section in characters
        """
        self.section_size = section_size

    def split_by_structure(self, content: str) -> List[Tuple[str, str]]:
        """Split document by structural elements.

        Args:
            content: Document content

        Returns:
            List of (section_title, section_content) tuples
        """
        sections = []
        current_section = []
        current_title = "Introduction"

        lines = content.splitlines()

        for line in lines:
            # Check if line is a header
            if line.strip().startswith("#"):
                # Save current section
                if current_section:
                    sections.append((current_title, "\n".join(current_section)))

                # Start new section
                current_title = line.strip("#").strip()
                current_section = [line]
            else:
                current_section.append(line)

            # Check section size
            section_text = "\n".join(current_section)
            if len(section_text) > self.section_size:
                # Split section
                sections.append((current_title, section_text))
                current_section = []
                current_title = f"{current_title} (continued)"

        # Add final section
        if current_section:
            sections.append((current_title, "\n".join(current_section)))

        return sections

    def split_by_size(self, content: str) -> List[str]:
        """Split document by size.

        Args:
            content: Document content

        Returns:
            List of content chunks
        """
        chunks = []

        # Split at paragraph boundaries when possible
        paragraphs = content.split("\n\n")
        current_chunk = []
        current_size = 0

        for paragraph in paragraphs:
            paragraph_size = len(paragraph)

            if current_size + paragraph_size > self.section_size and current_chunk:
                # Save current chunk
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
                current_size = paragraph_size
            else:
                current_chunk.append(paragraph)
                current_size += paragraph_size

        # Add final chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks
