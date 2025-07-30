"""Bulk operations for document management."""

import asyncio
import logging
import shutil
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BulkOperation:
    """Represents a bulk operation."""

    operation_id: str
    operation_type: str  # 'import', 'convert', 'organize', 'analyze'
    source_path: Path
    target_path: Optional[Path] = None
    options: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # 'pending', 'running', 'completed', 'failed'
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["source_path"] = str(self.source_path)
        if self.target_path:
            data["target_path"] = str(self.target_path)
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data


@dataclass
class BulkOperationResult:
    """Result of a bulk operation."""

    operation_id: str
    success: bool
    total_items: int
    processed_items: int
    failed_items: int
    skipped_items: int
    duration_seconds: float
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class FolderStructure:
    """Represents analyzed folder structure."""

    root_path: Path
    total_files: int
    total_folders: int
    file_types: Dict[str, int]
    size_bytes: int
    depth: int
    structure: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["root_path"] = str(self.root_path)
        return data


class BulkOperationsManager:
    """Manage bulk operations on document folders."""

    SUPPORTED_FORMATS = {
        ".md": "markdown",
        ".docx": "word",
        ".doc": "word",
        ".pd": "pd",
        ".txt": "text",
        ".rt": "rich_text",
    }

    def __init__(self, repo_path: Path, converters: Optional[Dict[str, Any]] = None):
        """Initialize bulk operations manager.

        Args:
            repo_path: Path to repository
            converters: Optional document converters
        """
        self.repo_path = Path(repo_path)
        self.converters = converters or {}
        self.operations: Dict[str, BulkOperation] = {}
        self.results: Dict[str, BulkOperationResult] = {}

    async def import_folder_structure(
        self,
        source_folder: Path,
        target_folder: Optional[Path] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> BulkOperationResult:
        """Import existing folder structure into repository.

        Args:
            source_folder: Source folder to import
            target_folder: Target folder in repository
            options: Import options

        Returns:
            BulkOperationResult
        """
        from uuid import uuid4

        operation_id = str(uuid4())[:8]
        target_folder = target_folder or self.repo_path / source_folder.name

        options = options or {}
        preserve_structure = options.get("preserve_structure", True)
        convert_documents = options.get("convert_documents", True)
        organize_by_type = options.get("organize_by_type", False)

        operation = BulkOperation(
            operation_id=operation_id,
            operation_type="import",
            source_path=source_folder,
            target_path=target_folder,
            options=options,
            status="running",
            started_at=datetime.now(),
        )

        self.operations[operation_id] = operation

        # Analyze folder structure
        structure = self._analyze_folder_structure(source_folder)

        results = []
        errors = []
        processed = 0
        failed = 0
        skipped = 0

        # Process files
        for file_path in self._iterate_files(source_folder):
            try:
                # Determine target path
                if preserve_structure:
                    rel_path = file_path.relative_to(source_folder)
                    target_path = target_folder / rel_path
                elif organize_by_type:
                    file_type = self._get_file_type(file_path)
                    target_path = target_folder / file_type / file_path.name
                else:
                    target_path = target_folder / file_path.name

                # Process file
                result = await self._process_single_file(
                    file_path, target_path, convert_documents
                )

                results.append(result)

                if result["success"]:
                    processed += 1
                elif result["skipped"]:
                    skipped += 1
                else:
                    failed += 1
                    errors.append(result.get("error", "Unknown error"))

            except Exception as e:
                failed += 1
                errors.append(f"Error processing {file_path}: {str(e)}")
                logger.error(f"Failed to process {file_path}: {e}")

        # Complete operation
        operation.status = "completed"
        operation.completed_at = datetime.now()
        duration = (operation.completed_at - operation.started_at).total_seconds()

        result = BulkOperationResult(
            operation_id=operation_id,
            success=failed == 0,
            total_items=structure.total_files,
            processed_items=processed,
            failed_items=failed,
            skipped_items=skipped,
            duration_seconds=duration,
            results=results,
            errors=errors,
            summary={
                "source_structure": structure.to_dict(),
                "files_by_type": self._summarize_results_by_type(results),
            },
        )

        self.results[operation_id] = result
        return result

    async def convert_folder(
        self,
        folder_path: Path,
        target_format: str = "markdown",
        options: Optional[Dict[str, Any]] = None,
    ) -> BulkOperationResult:
        """Convert all documents in a folder to target format.

        Args:
            folder_path: Folder containing documents
            target_format: Target format for conversion
            options: Conversion options

        Returns:
            BulkOperationResult
        """
        from uuid import uuid4

        operation_id = str(uuid4())[:8]
        options = options or {}

        operation = BulkOperation(
            operation_id=operation_id,
            operation_type="convert",
            source_path=folder_path,
            options={"target_format": target_format, **options},
            status="running",
            started_at=datetime.now(),
        )

        self.operations[operation_id] = operation

        results = []
        errors = []
        processed = 0
        failed = 0
        skipped = 0
        total = 0

        # Process files
        for file_path in self._iterate_files(folder_path):
            total += 1

            try:
                # Check if file needs conversion
                if self._get_file_type(file_path) == target_format:
                    skipped += 1
                    results.append(
                        {
                            "file": str(file_path),
                            "success": True,
                            "skipped": True,
                            "reason": "Already in target format",
                        }
                    )
                    continue

                # Convert file
                result = await self._convert_single_file(
                    file_path, target_format, options
                )

                results.append(result)

                if result["success"]:
                    processed += 1
                else:
                    failed += 1
                    errors.append(result.get("error", "Unknown error"))

            except Exception as e:
                failed += 1
                errors.append(f"Error converting {file_path}: {str(e)}")
                logger.error(f"Failed to convert {file_path}: {e}")

        # Complete operation
        operation.status = "completed"
        operation.completed_at = datetime.now()
        duration = (operation.completed_at - operation.started_at).total_seconds()

        result = BulkOperationResult(
            operation_id=operation_id,
            success=failed == 0,
            total_items=total,
            processed_items=processed,
            failed_items=failed,
            skipped_items=skipped,
            duration_seconds=duration,
            results=results,
            errors=errors,
            summary={
                "target_format": target_format,
                "conversion_rate": processed / max(total, 1),
            },
        )

        self.results[operation_id] = result
        return result

    async def organize_documents(
        self,
        source_folder: Path,
        organization_scheme: str = "by_type",
        options: Optional[Dict[str, Any]] = None,
    ) -> BulkOperationResult:
        """Organize documents according to a scheme.

        Args:
            source_folder: Folder to organize
            organization_scheme: How to organize ('by_type', 'by_date', 'by_matter')
            options: Organization options

        Returns:
            BulkOperationResult
        """
        from uuid import uuid4

        operation_id = str(uuid4())[:8]
        options = options or {}

        operation = BulkOperation(
            operation_id=operation_id,
            operation_type="organize",
            source_path=source_folder,
            options={"scheme": organization_scheme, **options},
            status="running",
            started_at=datetime.now(),
        )

        self.operations[operation_id] = operation

        results = []
        errors = []
        processed = 0
        failed = 0
        total = 0

        # Collect all files
        files_to_organize = list(self._iterate_files(source_folder))
        total = len(files_to_organize)

        # Organize based on scheme
        if organization_scheme == "by_type":
            organized = self._organize_by_type(files_to_organize)
        elif organization_scheme == "by_date":
            organized = self._organize_by_date(files_to_organize)
        elif organization_scheme == "by_matter":
            organized = self._organize_by_matter(files_to_organize, options)
        else:
            organized = {"unknown": files_to_organize}

        # Move files to organized structure
        for category, files in organized.items():
            target_dir = source_folder / category
            target_dir.mkdir(exist_ok=True)

            for file_path in files:
                try:
                    target_path = target_dir / file_path.name

                    # Handle duplicates
                    if target_path.exists():
                        base = target_path.stem
                        ext = target_path.suffix
                        counter = 1
                        while target_path.exists():
                            target_path = target_dir / f"{base}_{counter}{ext}"
                            counter += 1

                    # Move file
                    shutil.move(str(file_path), str(target_path))

                    results.append(
                        {
                            "file": str(file_path),
                            "success": True,
                            "new_location": str(target_path),
                            "category": category,
                        }
                    )
                    processed += 1

                except Exception as e:
                    failed += 1
                    errors.append(f"Error moving {file_path}: {str(e)}")
                    results.append(
                        {"file": str(file_path), "success": False, "error": str(e)}
                    )

        # Complete operation
        operation.status = "completed"
        operation.completed_at = datetime.now()
        duration = (operation.completed_at - operation.started_at).total_seconds()

        result = BulkOperationResult(
            operation_id=operation_id,
            success=failed == 0,
            total_items=total,
            processed_items=processed,
            failed_items=failed,
            skipped_items=0,
            duration_seconds=duration,
            results=results,
            errors=errors,
            summary={
                "organization_scheme": organization_scheme,
                "categories_created": list(organized.keys()),
                "files_per_category": {k: len(v) for k, v in organized.items()},
            },
        )

        self.results[operation_id] = result
        return result

    def analyze_folder_structure(self, folder_path: Path) -> FolderStructure:
        """Analyze folder structure without modifying.

        Args:
            folder_path: Folder to analyze

        Returns:
            FolderStructure analysis
        """
        return self._analyze_folder_structure(folder_path)

    async def parallel_process(
        self, items: List[Any], processor: Callable, max_workers: int = 4
    ) -> List[Any]:
        """Process items in parallel.

        Args:
            items: Items to process
            processor: Async function to process each item
            max_workers: Maximum concurrent workers

        Returns:
            List of results
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def process_with_semaphore(item):
            async with semaphore:
                return await processor(item)

        tasks = [process_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks)

    def _analyze_folder_structure(self, folder_path: Path) -> FolderStructure:
        """Analyze folder structure."""
        total_files = 0
        total_folders = 0
        file_types = defaultdict(int)
        size_bytes = 0
        max_depth = 0

        structure = {"name": folder_path.name, "path": str(folder_path), "children": []}

        def analyze_recursive(path: Path, parent_dict: Dict[str, Any], depth: int = 0):
            nonlocal total_files, total_folders, size_bytes, max_depth

            max_depth = max(max_depth, depth)

            for item in sorted(path.iterdir()):
                if item.is_file():
                    total_files += 1
                    size_bytes += item.stat().st_size

                    ext = item.suffix.lower()
                    file_type = self.SUPPORTED_FORMATS.get(ext, "other")
                    file_types[file_type] += 1

                    parent_dict["children"].append(
                        {
                            "name": item.name,
                            "type": "file",
                            "size": item.stat().st_size,
                            "format": file_type,
                        }
                    )

                elif item.is_dir() and not item.name.startswith("."):
                    total_folders += 1

                    child_dict = {"name": item.name, "type": "folder", "children": []}

                    parent_dict["children"].append(child_dict)
                    analyze_recursive(item, child_dict, depth + 1)

        analyze_recursive(folder_path, structure)

        return FolderStructure(
            root_path=folder_path,
            total_files=total_files,
            total_folders=total_folders,
            file_types=dict(file_types),
            size_bytes=size_bytes,
            depth=max_depth,
            structure=structure,
        )

    def _iterate_files(self, folder_path: Path) -> List[Path]:
        """Iterate through all files in folder."""
        files = []

        for item in folder_path.rglob("*"):
            if item.is_file() and not any(part.startswith(".") for part in item.parts):
                files.append(item)

        return files

    def _get_file_type(self, file_path: Path) -> str:
        """Get file type category."""
        ext = file_path.suffix.lower()
        return self.SUPPORTED_FORMATS.get(ext, "other")

    async def _process_single_file(
        self, source_path: Path, target_path: Path, convert: bool
    ) -> Dict[str, Any]:
        """Process a single file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if convert and source_path.suffix.lower() in self.SUPPORTED_FORMATS:
                # Convert if converter available
                file_type = self._get_file_type(source_path)
                if file_type in self.converters:
                    converter = self.converters[file_type]
                    await converter.convert(source_path, target_path)
                    return {
                        "file": str(source_path),
                        "success": True,
                        "converted": True,
                        "target": str(target_path),
                    }

            # Copy file
            shutil.copy2(source_path, target_path)
            return {
                "file": str(source_path),
                "success": True,
                "converted": False,
                "target": str(target_path),
            }

        except Exception as e:
            return {"file": str(source_path), "success": False, "error": str(e)}

    async def _convert_single_file(
        self, file_path: Path, target_format: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert a single file."""
        try:
            file_type = self._get_file_type(file_path)

            if file_type not in self.converters:
                return {
                    "file": str(file_path),
                    "success": False,
                    "error": f"No converter for {file_type}",
                }

            converter = self.converters[file_type]

            # Determine output path
            output_path = file_path.with_suffix(
                self._get_extension_for_format(target_format)
            )

            # Convert
            await converter.convert_to_format(
                file_path, output_path, target_format, options
            )

            return {
                "file": str(file_path),
                "success": True,
                "output": str(output_path),
                "format": target_format,
            }

        except Exception as e:
            return {"file": str(file_path), "success": False, "error": str(e)}

    def _organize_by_type(self, files: List[Path]) -> Dict[str, List[Path]]:
        """Organize files by type."""
        organized = defaultdict(list)

        for file_path in files:
            file_type = self._get_file_type(file_path)
            organized[file_type].append(file_path)

        return dict(organized)

    def _organize_by_date(self, files: List[Path]) -> Dict[str, List[Path]]:
        """Organize files by modification date."""
        organized = defaultdict(list)

        for file_path in files:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            date_key = mtime.strftime("%Y-%m")
            organized[date_key].append(file_path)

        return dict(organized)

    def _organize_by_matter(
        self, files: List[Path], options: Dict[str, Any]
    ) -> Dict[str, List[Path]]:
        """Organize files by matter/project."""
        organized = defaultdict(list)
        matter_patterns = options.get("matter_patterns", {})

        for file_path in files:
            matter = "general"

            # Check patterns
            for pattern_name, pattern in matter_patterns.items():
                if pattern in file_path.name.lower():
                    matter = pattern_name
                    break

            organized[matter].append(file_path)

        return dict(organized)

    def _summarize_results_by_type(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Summarize results by file type."""
        summary = defaultdict(int)

        for result in results:
            if result.get("success"):
                file_path = Path(result["file"])
                file_type = self._get_file_type(file_path)
                summary[file_type] += 1

        return dict(summary)

    def _get_extension_for_format(self, format_name: str) -> str:
        """Get file extension for format."""
        format_extensions = {
            "markdown": ".md",
            "word": ".docx",
            "pd": ".pd",
            "text": ".txt",
            "rich_text": ".rt",
        }
        return format_extensions.get(format_name, ".txt")
