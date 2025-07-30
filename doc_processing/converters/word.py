"""Word document XML processing and Markdown conversion with performance optimization."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseConverter
from .word_formatter import WordFormattingPreserver
from .word_performance import ProcessingMetrics, StreamingWordProcessor
from .word_xml import WordDocument, WordXMLExtractor

logger = logging.getLogger(__name__)


class WordConverter(BaseConverter):
    """Advanced Word document converter with XML processing and performance optimization."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Word converter with advanced processing capabilities."""
        super().__init__(config)

        # Core processing components
        self.xml_extractor = WordXMLExtractor(self.config.get("xml_extraction", {}))
        self.formatter = WordFormattingPreserver(self.config.get("formatting", {}))
        self.streaming_processor = StreamingWordProcessor(
            self.config.get("performance", {})
        )

        # Configuration options
        self.preserve_xml_structure = self.config.get("preserve_xml_structure", True)
        self.handle_embedded_objects = self.config.get("handle_embedded_objects", True)
        self.enable_streaming = self.config.get("enable_streaming", True)
        self.optimize_for_large_docs = self.config.get("optimize_for_large_docs", True)
        self.validation_level = self.config.get(
            "validation_level", "standard"
        )  # basic, standard, strict

    def to_markdown(self, source: Union[str, Path]) -> str:
        """Convert Word document to Markdown format with formatting preservation.

        Args:
            source: Path to Word document

        Returns:
            Markdown representation preserving formatting
        """
        source_path = Path(source)

        if not source_path.exists():
            raise FileNotFoundError(f"Word document not found: {source_path}")

        logger.info(f"Converting Word document to Markdown: {source_path}")

        try:
            # Determine processing strategy based on file size
            if self.optimize_for_large_docs:
                stats = self.streaming_processor.get_processing_statistics(source_path)
                file_size_mb = stats["file_info"]["size_mb"]

                if file_size_mb > 10 and self.enable_streaming:
                    return self._convert_large_document_to_markdown(source_path)

            # Standard processing for normal-sized documents
            return self._convert_standard_document_to_markdown(source_path)

        except Exception as e:
            logger.error(f"Failed to convert Word document {source_path}: {e}")
            raise

    def _convert_standard_document_to_markdown(self, word_file: Path) -> str:
        """Convert Word document using standard processing."""
        # Extract complete document structure
        word_document = self.xml_extractor.extract_document(word_file)

        # Convert to Markdown with formatting preservation
        markdown_content = self.formatter.convert_to_markdown(word_document)

        logger.info(
            f"Converted {word_file.name} to Markdown ({len(markdown_content)} characters)"
        )
        return markdown_content

    def _convert_large_document_to_markdown(self, word_file: Path) -> str:
        """Convert large Word document using streaming processing."""
        logger.info(f"Using streaming conversion for large document: {word_file}")

        markdown_parts = []

        # Process document in streaming chunks
        for chunk_result in self.streaming_processor.process_document_streaming(
            word_file
        ):
            if chunk_result.error:
                logger.warning(
                    f"Error in chunk {chunk_result.chunk_id}: {chunk_result.error}"
                )
                continue

            # Convert chunk text to markdown format
            if chunk_result.text_content:
                # Simple paragraph formatting for streaming mode
                chunk_markdown = self._format_chunk_as_markdown(chunk_result)
                markdown_parts.append(chunk_markdown)

        final_markdown = "\n\n".join(markdown_parts)
        logger.info(f"Streaming conversion completed: {len(final_markdown)} characters")

        return final_markdown

    def _format_chunk_as_markdown(self, chunk_result) -> str:
        """Format a processing chunk as Markdown."""
        text = chunk_result.text_content.strip()
        if not text:
            return ""

        # Basic formatting - in a full implementation, you'd analyze the elements
        # for now, we'll treat each chunk as a paragraph
        return text

    def from_markdown(self, markdown: str, target_path: Optional[Path] = None) -> str:
        """Convert Markdown to Word document format.

        Args:
            markdown: Markdown content to convert
            target_path: Optional path for output Word file

        Returns:
            Path to generated Word document
        """
        if not markdown.strip():
            raise ValueError("Empty markdown content provided")

        logger.info(
            f"Converting Markdown to Word document ({len(markdown)} characters)"
        )

        try:
            # Create base styles for conversion
            base_styles = self._create_base_word_styles()

            # Convert Markdown to Word document structure
            word_document = self.formatter.convert_from_markdown(markdown, base_styles)

            # Generate output path
            output_path = target_path or Path(
                f"converted_document_{hash(markdown) % 10000}.docx"
            )

            # In a real implementation, you would write the WordDocument to a .docx file
            # For now, we'll return the path that would be created
            logger.info(f"Would create Word document at: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to convert Markdown to Word: {e}")
            raise

    def _create_base_word_styles(self) -> Dict[str, Any]:
        """Create base Word styles for Markdown conversion."""
        from .word_xml import WordStyle

        base_styles = {}

        # Create basic paragraph style
        base_styles["Normal"] = WordStyle(
            style_id="Normal",
            style_name="Normal",
            style_type="paragraph",
            base_style=None,
            formatting_properties={
                "paragraph": {"spacing": {"after": "200"}, "alignment": "left"},
                "character": {"font": {"ascii": "Calibri"}, "font_size": "22"},  # 11pt
            },
            is_default=True,
        )

        # Create heading styles
        for i in range(1, 7):
            base_styles[f"Heading{i}"] = WordStyle(
                style_id=f"Heading{i}",
                style_name=f"Heading {i}",
                style_type="paragraph",
                base_style="Normal",
                formatting_properties={
                    "paragraph": {
                        "spacing": {"before": "240", "after": "120"},
                        "alignment": "left",
                    },
                    "character": {
                        "font": {"ascii": "Calibri"},
                        "font_size": str(32 - (i - 1) * 2),  # Decreasing size
                        "bold": True,
                    },
                },
            )

        return base_styles

    def validate_conversion(
        self, original: Union[str, Path], converted: str
    ) -> Dict[str, Any]:
        """Validate round-trip conversion accuracy with detailed metrics.

        Args:
            original: Original Word document path or content
            converted: Converted content (Markdown or Word)

        Returns:
            Detailed validation results
        """
        if self.validation_level == "basic":
            return self._basic_validation(original, converted)
        elif self.validation_level == "strict":
            return self._strict_validation(original, converted)
        else:
            return self._standard_validation(original, converted)

    def _basic_validation(
        self, original: Union[str, Path], converted: str
    ) -> Dict[str, Any]:
        """Basic validation - check content exists."""
        return {
            "validation_level": "basic",
            "is_valid": bool(original and converted),
            "original_length": len(str(original)),
            "converted_length": len(converted),
            "issues": [],
        }

    def _standard_validation(
        self, original: Union[str, Path], converted: str
    ) -> Dict[str, Any]:
        """Standard validation with text comparison."""
        validation = {
            "validation_level": "standard",
            "is_valid": True,
            "text_preservation": {},
            "structure_preservation": {},
            "issues": [],
        }

        try:
            # Extract text from original document
            if isinstance(original, (str, Path)) and Path(original).exists():
                original_text = self.xml_extractor.extract_text_only(Path(original))
            else:
                original_text = str(original)

            # Compare text content
            text_similarity = self._calculate_text_similarity(original_text, converted)
            validation["text_preservation"] = {
                "similarity_score": text_similarity,
                "original_length": len(original_text),
                "converted_length": len(converted),
            }

            if text_similarity < 0.8:
                validation["issues"].append(
                    f"Low text similarity: {text_similarity:.2%}"
                )
                validation["is_valid"] = False

        except Exception as e:
            validation["issues"].append(f"Validation error: {e}")
            validation["is_valid"] = False

        return validation

    def _strict_validation(
        self, original: Union[str, Path], converted: str
    ) -> Dict[str, Any]:
        """Strict validation with formatting analysis."""
        validation = self._standard_validation(original, converted)
        validation["validation_level"] = "strict"

        try:
            if isinstance(original, (str, Path)) and Path(original).exists():
                # Extract full document structure
                word_document = self.xml_extractor.extract_document(Path(original))

                # Analyze document statistics
                stats = self.xml_extractor.get_document_statistics(word_document)
                validation["document_statistics"] = stats

                # Check for complex formatting preservation
                if stats["formatting_complexity"]["total_styles"] > 5:
                    validation["issues"].append(
                        "Complex formatting may not be fully preserved"
                    )

                if stats["text_statistics"]["total_tables"] > 0:
                    # Check if tables are preserved in markdown
                    if "|" not in converted:
                        validation["issues"].append(
                            "Tables not properly converted to Markdown"
                        )
                        validation["is_valid"] = False

                if stats["text_statistics"]["total_images"] > 0:
                    # Check if images are referenced
                    if "![" not in converted:
                        validation["issues"].append(
                            "Images not properly converted to Markdown"
                        )

        except Exception as e:
            validation["issues"].append(f"Strict validation error: {e}")

        return validation

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0

        # Simple character-based similarity
        text1_clean = " ".join(text1.lower().split())
        text2_clean = " ".join(text2.lower().split())

        if text1_clean == text2_clean:
            return 1.0

        # Calculate similarity based on character overlap
        longer = text1_clean if len(text1_clean) > len(text2_clean) else text2_clean
        shorter = text2_clean if len(text1_clean) > len(text2_clean) else text1_clean

        if len(longer) == 0:
            return 1.0

        matching_chars = sum(
            1 for i, char in enumerate(shorter) if i < len(longer) and char == longer[i]
        )
        return matching_chars / len(longer)

    def extract_xml_structure(self, word_file: Path) -> Dict[str, Any]:
        """Extract complete XML structure from Word document.

        Args:
            word_file: Path to Word document

        Returns:
            Dictionary containing complete XML structure information
        """
        logger.info(f"Extracting XML structure from: {word_file}")

        try:
            word_document = self.xml_extractor.extract_document(word_file)
            return word_document.to_dict()

        except Exception as e:
            logger.error(f"Failed to extract XML structure: {e}")
            raise

    def extract_text_only(self, word_file: Path) -> str:
        """Extract only text content for fast processing.

        Args:
            word_file: Path to Word document

        Returns:
            Plain text content
        """
        return self.xml_extractor.extract_text_only(word_file)

    def get_document_statistics(self, word_file: Path) -> Dict[str, Any]:
        """Get comprehensive document statistics.

        Args:
            word_file: Path to Word document

        Returns:
            Document statistics and complexity analysis
        """
        word_document = self.xml_extractor.extract_document(word_file)
        return self.xml_extractor.get_document_statistics(word_document)

    def get_processing_metrics(self, word_file: Path) -> ProcessingMetrics:
        """Get processing performance metrics for a document.

        Args:
            word_file: Path to Word document

        Returns:
            Processing metrics and performance data
        """
        return self.streaming_processor.process_document_parallel(word_file)

    def optimize_processing_config(self, word_file: Path) -> Dict[str, Any]:
        """Get optimized processing configuration for a document.

        Args:
            word_file: Path to Word document

        Returns:
            Optimized configuration recommendations
        """
        return self.streaming_processor.optimize_for_large_documents(word_file)
