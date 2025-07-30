import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

from app.docs.enhanced_converter import EnhancedDocumentConverter
from app.git_ops.repository import GitOperations
from app.word_processing.docx_processor import DocxProcessor
from app.word_processing.word_xml_parser import (
    WordDocumentStructure,
    WordElement,
    WordElementType,
)

logger = logging.getLogger(__name__)


class WordProcessingService:
    """Service for Word document processing and integration"""

    def __init__(self, storage_path: str = "./word_documents"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.docx_processor = DocxProcessor()
        self.git_ops = GitOperations()

    async def process_word_document(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        processing_options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Process a Word document with various options"""

        options = processing_options or {}
        document_id = str(uuid.uuid4())

        try:
            # Save temporary file
            temp_path = self.storage_path / f"{document_id}_{filename}"
            with open(temp_path, "wb") as f:
                f.write(file_content)

            # Extract comprehensive structure
            structure = self.docx_processor.extract_comprehensive_structure(
                str(temp_path)
            )

            # Load document for additional processing
            document = self.docx_processor.load_document(str(temp_path))

            # Extract metadata
            metadata = self.docx_processor.extract_document_metadata(document)

            # Extract styles
            styles = self.docx_processor.extract_styles(document)

            # Convert to different formats based on options
            conversions = {}

            if options.get("convert_to_markdown", True):
                conversions["markdown"] = self.docx_processor.convert_to_markdown(
                    str(temp_path)
                )

            if options.get("extract_text", True):
                conversions["text"] = self.docx_processor.extract_text_content(document)

            if options.get("extract_html", False):
                conversions["html"] = self._convert_to_html(file_content)

            # Analyze document structure
            analysis = self._analyze_document_structure(structure)

            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()

            return {
                "success": True,
                "document_id": document_id,
                "filename": filename,
                "metadata": metadata,
                "structure": self._serialize_structure(structure),
                "styles": styles,
                "conversions": conversions,
                "analysis": analysis,
                "processing_time": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to process Word document: {str(e)}")
            # Clean up on error
            temp_path = self.storage_path / f"{document_id}_{filename}"
            if temp_path.exists():
                temp_path.unlink()

            return {"success": False, "error": str(e), "document_id": document_id}

    def _convert_to_html(self, file_content: bytes) -> str:
        """Convert DOCX to HTML using mammoth"""
        try:
            import io

            import mammoth

            result = mammoth.convert_to_html(io.BytesIO(file_content))
            return result.value
        except Exception as e:
            logger.warning(f"HTML conversion failed: {str(e)}")
            return ""

    def _analyze_document_structure(
        self, structure: WordDocumentStructure
    ) -> Dict[str, Any]:
        """Analyze document structure for insights"""
        analysis = {
            "total_elements": len(structure.elements),
            "element_types": {},
            "headings": [],
            "lists": [],
            "tables": [],
            "complexity_score": 0,
            "structure_quality": "good",
        }

        # Count element types
        for element in structure.elements:
            element_type = element.element_type.value
            analysis["element_types"][element_type] = (
                analysis["element_types"].get(element_type, 0) + 1
            )

            # Extract headings with hierarchy
            if element.element_type == WordElementType.HEADING:
                analysis["headings"].append(
                    {
                        "level": element.level or 1,
                        "content": element.content[:100],  # First 100 chars
                        "style": element.style,
                    }
                )

            # Extract list information
            elif element.element_type == WordElementType.LIST:
                analysis["lists"].append(
                    {
                        "level": element.level or 0,
                        "content": element.content[:50],  # First 50 chars
                        "style": element.style,
                    }
                )

        # Calculate complexity score
        analysis["complexity_score"] = self._calculate_complexity_score(structure)

        # Assess structure quality
        analysis["structure_quality"] = self._assess_structure_quality(analysis)

        # Additional statistics
        analysis["statistics"] = {
            "heading_count": len(analysis["headings"]),
            "list_count": len(analysis["lists"]),
            "table_count": len(structure.tables),
            "image_count": len(structure.images),
            "footnote_count": len(structure.footnotes),
            "comment_count": len(structure.comments),
        }

        return analysis

    def _calculate_complexity_score(self, structure: WordDocumentStructure) -> int:
        """Calculate document complexity score"""
        score = 0

        # Base score from element count
        score += len(structure.elements) * 0.1

        # Add points for different element types
        for element in structure.elements:
            if element.element_type == WordElementType.TABLE:
                score += 5
            elif element.element_type == WordElementType.IMAGE:
                score += 3
            elif element.element_type == WordElementType.LIST:
                score += 1
            elif element.element_type == WordElementType.HEADING:
                score += 0.5

        # Add points for structural complexity
        score += len(structure.tables) * 10
        score += len(structure.images) * 5
        score += len(structure.footnotes) * 2
        score += len(structure.comments) * 1

        return int(score)

    def _assess_structure_quality(self, analysis: Dict) -> str:
        """Assess document structure quality"""
        heading_count = analysis["statistics"]["heading_count"]
        total_elements = analysis["total_elements"]

        # Check heading ratio
        heading_ratio = heading_count / max(total_elements, 1)

        if heading_ratio > 0.3:
            return "poor"  # Too many headings
        elif heading_ratio > 0.1:
            return "good"  # Good structure
        elif heading_ratio > 0.05:
            return "fair"  # Some structure
        else:
            return "poor"  # Little structure

    def _serialize_structure(self, structure: WordDocumentStructure) -> Dict:
        """Serialize document structure for JSON response"""
        return {
            "elements": [
                self._serialize_element(elem) for elem in structure.elements[:100]
            ],  # Limit to first 100
            "metadata": structure.metadata,
            "statistics": {
                "total_elements": len(structure.elements),
                "styles_count": len(structure.styles),
                "tables_count": len(structure.tables),
                "images_count": len(structure.images),
                "footnotes_count": len(structure.footnotes),
                "endnotes_count": len(structure.endnotes),
                "comments_count": len(structure.comments),
            },
        }

    def _serialize_element(self, element: WordElement) -> Dict:
        """Serialize a single element"""
        return {
            "type": element.element_type.value,
            "content": element.content[:200],  # Limit content length
            "style": element.style,
            "level": element.level,
            "properties": element.properties,
            "children_count": len(element.children) if element.children else 0,
        }

    async def sync_word_to_git(
        self,
        file_content: bytes,
        filename: str,
        repo_name: str,
        user_id: str,
        file_path: str,
        conversion_format: str = "markdown",
    ) -> Dict[str, Any]:
        """Sync Word document to git repository"""

        try:
            # Process the Word document
            processing_result = await self.process_word_document(
                file_content,
                filename,
                user_id,
                {"convert_to_markdown": True, "extract_text": True},
            )

            if not processing_result["success"]:
                return processing_result

            # Get converted content
            if conversion_format == "markdown":
                content = processing_result["conversions"]["markdown"]
                file_extension = ".md"
            else:
                content = processing_result["conversions"]["text"]
                file_extension = ".txt"

            # Ensure file path has correct extension
            if not file_path.endswith(file_extension):
                file_path = f"{file_path}{file_extension}"

            # Get repository path
            repo_path = self.git_ops.base_path / user_id / repo_name
            if not repo_path.exists():
                return {
                    "success": False,
                    "error": f"Repository {repo_name} not found for user {user_id}",
                }

            # Write content to file
            full_file_path = repo_path / file_path
            full_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Create metadata file
            metadata = {
                "original_filename": filename,
                "document_id": processing_result["document_id"],
                "conversion_format": conversion_format,
                "sync_time": datetime.utcnow().isoformat(),
                "file_path": file_path,
                "word_metadata": processing_result["metadata"],
            }

            metadata_path = (
                repo_path
                / ".trunk"
                / "word_documents"
                / f"{processing_result['document_id']}.json"
            )
            metadata_path.parent.mkdir(parents=True, exist_ok=True)

            import json

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            return {
                "success": True,
                "message": f"Word document synced to {file_path}",
                "processing_result": processing_result,
                "file_path": file_path,
                "metadata_path": str(metadata_path.relative_to(repo_path)),
            }

        except Exception as e:
            logger.error(f"Failed to sync Word document to git: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_word_from_markdown(
        self, markdown_content: str, filename: str
    ) -> bytes:
        """Create a Word document from Markdown content"""
        try:
            document = self.docx_processor.create_document_from_markdown(
                markdown_content
            )
            return self.docx_processor.save_document_to_bytes(document)
        except Exception as e:
            logger.error(f"Failed to create Word document from Markdown: {str(e)}")
            raise

    def compare_word_documents(
        self, doc1_content: bytes, doc2_content: bytes, comparison_type: str = "basic"
    ) -> Dict[str, Any]:
        """Compare two Word documents"""
        try:
            # Save temporary files
            doc1_id = str(uuid.uuid4())
            doc2_id = str(uuid.uuid4())

            doc1_path = self.storage_path / f"temp_{doc1_id}.docx"
            doc2_path = self.storage_path / f"temp_{doc2_id}.docx"

            with open(doc1_path, "wb") as f:
                f.write(doc1_content)

            with open(doc2_path, "wb") as f:
                f.write(doc2_content)

            # Perform comparison
            if comparison_type == "detailed":
                comparison = self._detailed_comparison(str(doc1_path), str(doc2_path))
            else:
                comparison = self.docx_processor.compare_documents(
                    str(doc1_path), str(doc2_path)
                )

            # Clean up
            doc1_path.unlink()
            doc2_path.unlink()

            return {"success": True, "comparison": comparison}

        except Exception as e:
            logger.error(f"Failed to compare Word documents: {str(e)}")
            return {"success": False, "error": str(e)}

    def _detailed_comparison(self, doc1_path: str, doc2_path: str) -> Dict[str, Any]:
        """Perform detailed comparison of two documents"""
        # Extract structures
        structure1 = self.docx_processor.extract_comprehensive_structure(doc1_path)
        structure2 = self.docx_processor.extract_comprehensive_structure(doc2_path)

        # Compare structures
        comparison = {
            "structure_changes": {
                "elements_added": len(structure2.elements) - len(structure1.elements),
                "tables_added": len(structure2.tables) - len(structure1.tables),
                "images_added": len(structure2.images) - len(structure1.images),
            },
            "metadata_changes": self._compare_metadata(
                structure1.metadata, structure2.metadata
            ),
            "style_changes": self._compare_styles(structure1.styles, structure2.styles),
        }

        return comparison

    def _compare_metadata(self, meta1: Dict, meta2: Dict) -> Dict:
        """Compare metadata between documents"""
        changes = {}

        all_keys = set(meta1.keys()) | set(meta2.keys())

        for key in all_keys:
            val1 = meta1.get(key)
            val2 = meta2.get(key)

            if val1 != val2:
                changes[key] = {"old": val1, "new": val2}

        return changes

    def _compare_styles(self, styles1: Dict, styles2: Dict) -> Dict:
        """Compare styles between documents"""
        changes = {"added": [], "removed": [], "modified": []}

        keys1 = set(styles1.keys())
        keys2 = set(styles2.keys())

        changes["added"] = list(keys2 - keys1)
        changes["removed"] = list(keys1 - keys2)

        # Check for modifications in common styles
        common_keys = keys1 & keys2
        for key in common_keys:
            if styles1[key] != styles2[key]:
                changes["modified"].append(key)

        return changes

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get supported input and output formats"""
        return {
            "input_formats": [".docx", ".doc"],
            "output_formats": ["markdown", "text", "html", "docx"],
            "conversion_options": [
                "preserve_formatting",
                "extract_images",
                "include_comments",
                "include_footnotes",
                "table_conversion",
            ],
        }
