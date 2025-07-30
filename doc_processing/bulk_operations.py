"""Bulk operations for processing existing folder structures in Google Drive."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .converters.google_docs import GoogleDocsConverter
from .converters.pdf import PDFConverter
from .converters.word import WordConverter

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single document."""

    file_id: str
    file_name: str
    file_type: str
    status: str  # 'success', 'error', 'skipped'
    message: str
    processing_time: float
    extracted_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None


@dataclass
class BulkOperationConfig:
    """Configuration for bulk processing operations."""

    max_workers: int = 5
    batch_size: int = 10
    supported_extensions: Set[str] = None
    skip_large_files: bool = True
    max_file_size_mb: int = 50
    progress_callback: Optional[Callable[[str, int, int], None]] = None
    error_callback: Optional[Callable[[str, Exception], None]] = None
    include_pdf: bool = True
    include_word: bool = True
    include_google_docs: bool = True
    preserve_folder_structure: bool = True
    create_git_repos: bool = True

    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = {
                ".pd",
                ".docx",
                ".doc",
                ".gdoc",
                ".gsheet",
                ".gslides",
            }


class BulkDocumentProcessor:
    """Handles bulk processing of document folders for git tracking setup."""

    def __init__(self, config: Optional[BulkOperationConfig] = None):
        """Initialize bulk processor with configuration."""
        self.config = config or BulkOperationConfig()
        self.converters = self._initialize_converters()
        self.processed_count = 0
        self.error_count = 0
        self.skipped_count = 0

    def _initialize_converters(self) -> Dict[str, Any]:
        """Initialize document converters."""
        converters = {}

        if self.config.include_google_docs:
            converters["google_docs"] = GoogleDocsConverter()

        if self.config.include_word:
            converters["word"] = WordConverter()

        if self.config.include_pdf:
            converters["pd"] = PDFConverter()

        return converters

    async def process_folder_structure(
        self, folder_id: str, drive_service: Any, output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Process entire Google Drive folder structure for git tracking.

        Args:
            folder_id: Google Drive folder ID to process
            drive_service: Google Drive API service instance
            output_path: Local path for processed content

        Returns:
            Dictionary with processing results and statistics
        """
        start_time = datetime.now()

        try:
            # Discover folder structure
            folder_structure = await self._discover_folder_structure(
                folder_id, drive_service
            )

            # Process documents in batches
            all_results = []
            total_files = sum(
                len(folder["files"]) for folder in folder_structure.values()
            )

            self._call_progress_callback("Starting bulk processing", 0, total_files)

            for folder_path, folder_info in folder_structure.items():
                folder_results = await self._process_folder_batch(
                    folder_info["files"],
                    drive_service,
                    output_path / folder_path if output_path else None,
                )
                all_results.extend(folder_results)

                # Update progress
                processed_so_far = len(all_results)
                self._call_progress_callback(
                    f"Processed folder: {folder_path}", processed_so_far, total_files
                )

            # Generate summary
            processing_time = (datetime.now() - start_time).total_seconds()
            summary = self._generate_processing_summary(all_results, processing_time)

            # Create git repositories if requested
            if self.config.create_git_repos and output_path:
                git_setup_results = await self._setup_git_repositories(
                    folder_structure, output_path
                )
                summary["git_setup"] = git_setup_results

            return summary

        except Exception as e:
            logger.error(f"Bulk folder processing failed: {e}")
            self._call_error_callback("Bulk processing failed", e)
            raise

    async def _discover_folder_structure(
        self, root_folder_id: str, drive_service: Any
    ) -> Dict[str, Dict[str, Any]]:
        """
        Discover and map Google Drive folder structure.

        Args:
            root_folder_id: Root folder ID to scan
            drive_service: Google Drive API service

        Returns:
            Dictionary mapping folder paths to folder information
        """
        folder_structure = {}
        folders_to_process = [(root_folder_id, "")]

        while folders_to_process:
            folder_id, current_path = folders_to_process.pop(0)

            try:
                # Get folder contents
                query = f"'{folder_id}' in parents and trashed = false"
                results = (
                    drive_service.files()
                    .list(
                        q=query,
                        fields="files(id,name,mimeType,size,modifiedTime,createdTime)",
                    )
                    .execute()
                )

                files = results.get("files", [])
                folder_files = []

                for file_info in files:
                    if file_info["mimeType"] == "application/vnd.google-apps.folder":
                        # Add subfolder to processing queue
                        subfolder_path = (
                            f"{current_path}/{file_info['name']}"
                            if current_path
                            else file_info["name"]
                        )
                        folders_to_process.append((file_info["id"], subfolder_path))
                    else:
                        # Check if file should be processed
                        if self._should_process_file(file_info):
                            folder_files.append(file_info)

                if folder_files:
                    folder_key = current_path if current_path else "root"
                    folder_structure[folder_key] = {
                        "id": folder_id,
                        "path": current_path,
                        "files": folder_files,
                        "file_count": len(folder_files),
                    }

            except Exception as e:
                logger.error(f"Failed to process folder {folder_id}: {e}")
                self._call_error_callback(f"Folder discovery failed: {current_path}", e)
                continue

        return folder_structure

    def _should_process_file(self, file_info: Dict[str, Any]) -> bool:
        """
        Determine if a file should be processed based on configuration.

        Args:
            file_info: Google Drive file information

        Returns:
            True if file should be processed
        """
        mime_type = file_info.get("mimeType", "")
        file_name = file_info.get("name", "")
        file_size = int(file_info.get("size", 0))

        # Check file size limits
        if self.config.skip_large_files:
            max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
            if file_size > max_size_bytes:
                return False

        # Check supported file types
        if mime_type in [
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
        ]:
            return self.config.include_google_docs

        if mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]:
            return self.config.include_word

        if mime_type == "application/pd":
            return self.config.include_pdf

        # Check by file extension as fallback
        file_extension = Path(file_name).suffix.lower()
        return file_extension in self.config.supported_extensions

    async def _process_folder_batch(
        self,
        files: List[Dict[str, Any]],
        drive_service: Any,
        output_folder: Optional[Path] = None,
    ) -> List[ProcessingResult]:
        """
        Process a batch of files from a single folder.

        Args:
            files: List of file information dictionaries
            drive_service: Google Drive API service
            output_folder: Local output folder path

        Returns:
            List of processing results
        """
        results = []

        # Process files in smaller batches to avoid overwhelming the API
        for i in range(0, len(files), self.config.batch_size):
            batch = files[i : i + self.config.batch_size]

            # Use ThreadPoolExecutor for concurrent processing
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self._process_single_file,
                        file_info,
                        drive_service,
                        output_folder,
                    ): file_info
                    for file_info in batch
                }

                for future in as_completed(future_to_file):
                    file_info = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)

                        if result.status == "success":
                            self.processed_count += 1
                        elif result.status == "error":
                            self.error_count += 1
                        else:
                            self.skipped_count += 1

                    except Exception as e:
                        logger.error(
                            f"Processing failed for {file_info.get('name', 'unknown')}: {e}"
                        )
                        error_result = ProcessingResult(
                            file_id=file_info.get("id", ""),
                            file_name=file_info.get("name", "unknown"),
                            file_type=file_info.get("mimeType", ""),
                            status="error",
                            message=f"Processing exception: {str(e)}",
                            processing_time=0.0,
                            error_details=str(e),
                        )
                        results.append(error_result)
                        self.error_count += 1
                        self._call_error_callback(
                            f"File processing failed: {file_info.get('name')}", e
                        )

            # Small delay between batches to be respectful to API limits
            await asyncio.sleep(0.1)

        return results

    def _process_single_file(
        self,
        file_info: Dict[str, Any],
        drive_service: Any,
        output_folder: Optional[Path] = None,
    ) -> ProcessingResult:
        """
        Process a single file for git tracking.

        Args:
            file_info: File information from Google Drive
            drive_service: Google Drive API service
            output_folder: Local output folder path

        Returns:
            Processing result for the file
        """
        start_time = datetime.now()
        file_id = file_info.get("id", "")
        file_name = file_info.get("name", "unknown")
        mime_type = file_info.get("mimeType", "")

        try:
            # Determine converter to use
            converter = self._get_converter_for_file(mime_type, file_name)
            if not converter:
                return ProcessingResult(
                    file_id=file_id,
                    file_name=file_name,
                    file_type=mime_type,
                    status="skipped",
                    message="No suitable converter found",
                    processing_time=0.0,
                )

            # Download or access file content
            file_content = self._get_file_content(file_info, drive_service)

            # Convert to markdown
            markdown_content = converter.to_markdown(file_content)

            # Extract metadata
            metadata = self._extract_file_metadata(file_info, converter, file_content)

            # Save to output folder if specified
            if output_folder:
                self._save_converted_file(
                    output_folder, file_name, markdown_content, metadata
                )

            processing_time = (datetime.now() - start_time).total_seconds()

            return ProcessingResult(
                file_id=file_id,
                file_name=file_name,
                file_type=mime_type,
                status="success",
                message="Successfully converted to markdown",
                processing_time=processing_time,
                extracted_content=(
                    markdown_content[:500] + "..."
                    if len(markdown_content) > 500
                    else markdown_content
                ),
                metadata=metadata,
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to process file {file_name}: {e}")

            return ProcessingResult(
                file_id=file_id,
                file_name=file_name,
                file_type=mime_type,
                status="error",
                message=f"Conversion failed: {str(e)}",
                processing_time=processing_time,
                error_details=str(e),
            )

    def _get_converter_for_file(self, mime_type: str, file_name: str) -> Optional[Any]:
        """Get appropriate converter for file type."""
        if mime_type.startswith("application/vnd.google-apps."):
            return self.converters.get("google_docs")
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]:
            return self.converters.get("word")
        elif mime_type == "application/pd":
            return self.converters.get("pd")

        # Fallback to file extension
        extension = Path(file_name).suffix.lower()
        if extension in [".docx", ".doc"]:
            return self.converters.get("word")
        elif extension == ".pd":
            return self.converters.get("pd")

        return None

    def _get_file_content(self, file_info: Dict[str, Any], drive_service: Any) -> str:
        """
        Download or get file content from Google Drive.

        Args:
            file_info: File information dictionary
            drive_service: Google Drive API service

        Returns:
            File content as string or bytes
        """
        file_id = file_info.get("id")
        mime_type = file_info.get("mimeType", "")

        if mime_type.startswith("application/vnd.google-apps."):
            # Google Docs files - return file ID for API access
            return file_id
        else:
            # Regular files - download content
            file_content = drive_service.files().get_media(fileId=file_id).execute()
            return file_content

    def _extract_file_metadata(
        self, file_info: Dict[str, Any], converter: Any, file_content: Any
    ) -> Dict[str, Any]:
        """Extract comprehensive metadata from file."""
        metadata = {
            "drive_metadata": {
                "id": file_info.get("id"),
                "name": file_info.get("name"),
                "mimeType": file_info.get("mimeType"),
                "size": file_info.get("size"),
                "createdTime": file_info.get("createdTime"),
                "modifiedTime": file_info.get("modifiedTime"),
            }
        }

        # Extract converter-specific metadata
        try:
            if hasattr(converter, "extract_metadata"):
                converter_metadata = converter.extract_metadata(file_content)
                metadata["converter_metadata"] = converter_metadata
        except Exception as e:
            logger.warning(f"Failed to extract converter metadata: {e}")
            metadata["converter_metadata"] = {"error": str(e)}

        return metadata

    def _save_converted_file(
        self,
        output_folder: Path,
        file_name: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Save converted file and metadata to local filesystem."""
        output_folder.mkdir(parents=True, exist_ok=True)

        # Save markdown content
        base_name = Path(file_name).stem
        markdown_path = output_folder / f"{base_name}.md"
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Save metadata
        metadata_path = output_folder / f"{base_name}.metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

    async def _setup_git_repositories(
        self, folder_structure: Dict[str, Dict[str, Any]], base_path: Path
    ) -> Dict[str, Any]:
        """
        Set up git repositories for processed folder structure.

        Args:
            folder_structure: Discovered folder structure
            base_path: Base path for git repositories

        Returns:
            Git setup results
        """
        import subprocess

        git_results = {
            "repositories_created": 0,
            "repositories_failed": 0,
            "errors": [],
        }

        for folder_path, folder_info in folder_structure.items():
            try:
                repo_path = (
                    base_path / folder_path if folder_path != "root" else base_path
                )
                repo_path.mkdir(parents=True, exist_ok=True)

                # Initialize git repository
                result = subprocess.run(
                    ["git", "init"], cwd=repo_path, capture_output=True, text=True
                )

                if result.returncode == 0:
                    # Create initial commit
                    subprocess.run(["git", "add", "."], cwd=repo_path)
                    subprocess.run(
                        [
                            "git",
                            "commit",
                            "-m",
                            f'docs: initial bulk import of {len(folder_info["files"])} documents',
                        ],
                        cwd=repo_path,
                    )

                    git_results["repositories_created"] += 1
                else:
                    git_results["repositories_failed"] += 1
                    git_results["errors"].append(
                        f"Failed to init {folder_path}: {result.stderr}"
                    )

            except Exception as e:
                git_results["repositories_failed"] += 1
                git_results["errors"].append(
                    f"Error setting up git for {folder_path}: {str(e)}"
                )
                logger.error(f"Git setup failed for {folder_path}: {e}")

        return git_results

    def _generate_processing_summary(
        self, results: List[ProcessingResult], total_time: float
    ) -> Dict[str, Any]:
        """Generate comprehensive processing summary."""
        successful_results = [r for r in results if r.status == "success"]
        error_results = [r for r in results if r.status == "error"]
        skipped_results = [r for r in results if r.status == "skipped"]

        # Calculate statistics
        total_files = len(results)
        avg_processing_time = (
            sum(r.processing_time for r in results) / total_files
            if total_files > 0
            else 0
        )

        # Group by file type
        file_types = {}
        for result in results:
            file_type = result.file_type
            if file_type not in file_types:
                file_types[file_type] = {
                    "total": 0,
                    "success": 0,
                    "error": 0,
                    "skipped": 0,
                }

            file_types[file_type]["total"] += 1
            file_types[file_type][result.status] += 1

        summary = {
            "processing_summary": {
                "total_files": total_files,
                "successful": len(successful_results),
                "errors": len(error_results),
                "skipped": len(skipped_results),
                "success_rate": (
                    len(successful_results) / total_files if total_files > 0 else 0
                ),
                "total_processing_time": total_time,
                "average_file_processing_time": avg_processing_time,
            },
            "file_type_breakdown": file_types,
            "error_details": [
                {
                    "file_name": r.file_name,
                    "error_message": r.message,
                    "error_details": r.error_details,
                }
                for r in error_results
            ],
            "performance_metrics": {
                "fastest_file": (
                    min(results, key=lambda x: x.processing_time).processing_time
                    if results
                    else 0
                ),
                "slowest_file": (
                    max(results, key=lambda x: x.processing_time).processing_time
                    if results
                    else 0
                ),
                "files_per_second": total_files / total_time if total_time > 0 else 0,
            },
        }

        return summary

    def _call_progress_callback(self, message: str, current: int, total: int) -> None:
        """Call progress callback if configured."""
        if self.config.progress_callback:
            try:
                self.config.progress_callback(message, current, total)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _call_error_callback(self, message: str, error: Exception) -> None:
        """Call error callback if configured."""
        if self.config.error_callback:
            try:
                self.config.error_callback(message, error)
            except Exception as e:
                logger.warning(f"Error callback failed: {e}")


class FolderStructureAnalyzer:
    """Analyzes Google Drive folder structures for bulk processing planning."""

    def __init__(self, drive_service: Any):
        """Initialize analyzer with Drive service."""
        self.drive_service = drive_service

    async def analyze_folder_complexity(self, folder_id: str) -> Dict[str, Any]:
        """
        Analyze folder structure complexity and estimate processing requirements.

        Args:
            folder_id: Google Drive folder ID to analyze

        Returns:
            Analysis results with complexity metrics and recommendations
        """
        analysis = {
            "folder_metrics": {},
            "file_distribution": {},
            "processing_estimates": {},
            "recommendations": [],
        }

        try:
            # Get folder statistics
            folder_stats = await self._get_folder_statistics(folder_id)
            analysis["folder_metrics"] = folder_stats

            # Analyze file distribution
            file_distribution = self._analyze_file_distribution(folder_stats)
            analysis["file_distribution"] = file_distribution

            # Generate processing estimates
            estimates = self._calculate_processing_estimates(folder_stats)
            analysis["processing_estimates"] = estimates

            # Generate recommendations
            recommendations = self._generate_recommendations(folder_stats, estimates)
            analysis["recommendations"] = recommendations

        except Exception as e:
            logger.error(f"Folder analysis failed: {e}")
            analysis["error"] = str(e)

        return analysis

    async def _get_folder_statistics(self, folder_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics about folder structure."""
        stats = {
            "total_folders": 0,
            "total_files": 0,
            "max_depth": 0,
            "file_types": {},
            "size_distribution": {},
            "largest_files": [],
        }

        folders_to_process = [(folder_id, 0)]
        processed_folders = set()

        while folders_to_process:
            current_folder_id, depth = folders_to_process.pop(0)

            if current_folder_id in processed_folders:
                continue

            processed_folders.add(current_folder_id)
            stats["total_folders"] += 1
            stats["max_depth"] = max(stats["max_depth"], depth)

            try:
                query = f"'{current_folder_id}' in parents and trashed = false"
                results = (
                    self.drive_service.files()
                    .list(
                        q=query,
                        fields="files(id,name,mimeType,size,modifiedTime)",
                        pageSize=1000,
                    )
                    .execute()
                )

                files = results.get("files", [])

                for file_info in files:
                    if file_info["mimeType"] == "application/vnd.google-apps.folder":
                        folders_to_process.append((file_info["id"], depth + 1))
                    else:
                        stats["total_files"] += 1

                        # Track file type
                        mime_type = file_info["mimeType"]
                        if mime_type not in stats["file_types"]:
                            stats["file_types"][mime_type] = 0
                        stats["file_types"][mime_type] += 1

                        # Track file size
                        file_size = int(file_info.get("size", 0))
                        size_category = self._categorize_file_size(file_size)
                        if size_category not in stats["size_distribution"]:
                            stats["size_distribution"][size_category] = 0
                        stats["size_distribution"][size_category] += 1

                        # Track largest files
                        if len(stats["largest_files"]) < 10:
                            stats["largest_files"].append(
                                (file_info["name"], file_size)
                            )
                        else:
                            min_size = min(stats["largest_files"], key=lambda x: x[1])
                            if file_size > min_size[1]:
                                stats["largest_files"].remove(min_size)
                                stats["largest_files"].append(
                                    (file_info["name"], file_size)
                                )

            except Exception as e:
                logger.warning(f"Failed to process folder {current_folder_id}: {e}")
                continue

        # Sort largest files
        stats["largest_files"].sort(key=lambda x: x[1], reverse=True)

        return stats

    def _categorize_file_size(self, size_bytes: int) -> str:
        """Categorize file size into buckets."""
        mb = size_bytes / (1024 * 1024)

        if mb < 1:
            return "small (<1MB)"
        elif mb < 10:
            return "medium (1-10MB)"
        elif mb < 50:
            return "large (10-50MB)"
        else:
            return "very_large (>50MB)"

    def _analyze_file_distribution(
        self, folder_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze the distribution of file types and sizes."""
        total_files = folder_stats["total_files"]

        if total_files == 0:
            return {"message": "No files found"}

        # Calculate percentages for file types
        file_type_percentages = {}
        for mime_type, count in folder_stats["file_types"].items():
            file_type_percentages[mime_type] = (count / total_files) * 100

        # Calculate size distribution percentages
        size_percentages = {}
        for size_category, count in folder_stats["size_distribution"].items():
            size_percentages[size_category] = (count / total_files) * 100

        return {
            "file_type_percentages": file_type_percentages,
            "size_distribution_percentages": size_percentages,
            "complexity_score": self._calculate_complexity_score(folder_stats),
        }

    def _calculate_complexity_score(self, folder_stats: Dict[str, Any]) -> float:
        """Calculate complexity score based on folder statistics."""
        # Base score from number of files and folders
        base_score = min(folder_stats["total_files"] / 1000, 1.0) * 50

        # Add complexity from folder depth
        depth_score = min(folder_stats["max_depth"] / 10, 1.0) * 20

        # Add complexity from file type diversity
        type_diversity = len(folder_stats["file_types"])
        diversity_score = min(type_diversity / 10, 1.0) * 15

        # Add complexity from large files
        large_files = folder_stats["size_distribution"].get("very_large (>50MB)", 0)
        large_file_score = min(large_files / 100, 1.0) * 15

        return base_score + depth_score + diversity_score + large_file_score

    def _calculate_processing_estimates(
        self, folder_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate estimated processing time and resource requirements."""
        total_files = folder_stats["total_files"]

        # Estimate processing time (seconds per file based on type)
        type_processing_times = {
            "application/pd": 5.0,
            "application/vnd.google-apps.document": 3.0,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 4.0,
            "application/msword": 4.0,
            "default": 2.0,
        }

        total_estimated_time = 0
        for mime_type, count in folder_stats["file_types"].items():
            processing_time = type_processing_times.get(
                mime_type, type_processing_times["default"]
            )
            total_estimated_time += count * processing_time

        # Estimate memory requirements (MB per file)
        estimated_memory = total_files * 10  # Conservative estimate

        # Estimate storage requirements
        estimated_storage_mb = total_files * 2  # Markdown files + metadata

        return {
            "estimated_processing_time_seconds": total_estimated_time,
            "estimated_processing_time_hours": total_estimated_time / 3600,
            "estimated_memory_mb": estimated_memory,
            "estimated_storage_mb": estimated_storage_mb,
            "recommended_batch_size": min(max(10, total_files // 100), 50),
            "recommended_workers": min(max(2, total_files // 1000), 10),
        }

    def _generate_recommendations(
        self, folder_stats: Dict[str, Any], estimates: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations for bulk processing."""
        recommendations = []

        total_files = folder_stats["total_files"]
        processing_hours = estimates["estimated_processing_time_hours"]

        # File count recommendations
        if total_files > 10000:
            recommendations.append(
                "Consider processing in multiple stages due to large file count"
            )

        # Processing time recommendations
        if processing_hours > 8:
            recommendations.append(
                f"Estimated processing time is {processing_hours:.1f} hours - consider overnight processing"
            )

        # Large file recommendations
        large_files = folder_stats["size_distribution"].get("very_large (>50MB)", 0)
        if large_files > 50:
            recommendations.append(
                f"Found {large_files} very large files - consider separate processing or exclusion"
            )

        # Memory recommendations
        if estimates["estimated_memory_mb"] > 4000:
            recommendations.append(
                "High memory usage expected - ensure adequate system resources"
            )

        # Depth recommendations
        if folder_stats["max_depth"] > 10:
            recommendations.append(
                "Deep folder structure detected - verify folder mapping is correct"
            )

        # File type recommendations
        unsupported_types = 0
        supported_types = {
            "application/pd",
            "application/vnd.google-apps.document",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }

        for mime_type in folder_stats["file_types"]:
            if mime_type not in supported_types:
                unsupported_types += folder_stats["file_types"][mime_type]

        if unsupported_types > 0:
            recommendations.append(
                f"{unsupported_types} files with unsupported types will be skipped"
            )

        return recommendations
