"""PDF tracking for read-only document management."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .pdf_extractor import PDFTextExtractor

logger = logging.getLogger(__name__)


@dataclass
class PDFDocument:
    """Represents a tracked PDF document."""

    document_id: str
    file_path: str
    file_hash: str
    file_size: int
    metadata: Dict[str, Any]
    tracking_info: Dict[str, Any]
    added_date: datetime
    last_verified: datetime
    status: str  # 'active', 'modified', 'missing'
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["added_date"] = self.added_date.isoformat()
        data["last_verified"] = self.last_verified.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PDFDocument":
        """Create from dictionary representation."""
        data["added_date"] = datetime.fromisoformat(data["added_date"])
        data["last_verified"] = datetime.fromisoformat(data["last_verified"])
        return cls(**data)


@dataclass
class PDFChangeEvent:
    """Event for PDF document changes."""

    event_id: str
    document_id: str
    event_type: str  # 'added', 'modified', 'deleted', 'moved'
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class PDFTracker:
    """Track PDF documents in repository for read-only management."""

    def __init__(self, repo_path: Path):
        """Initialize PDF tracker.

        Args:
            repo_path: Path to repository
        """
        self.repo_path = Path(repo_path)
        self.trunk_dir = self.repo_path / ".trunk"
        self.trunk_dir.mkdir(exist_ok=True)

        # Storage paths
        self.pdf_index_file = self.trunk_dir / "pdf_index.json"
        self.pdf_events_file = self.trunk_dir / "pdf_events.json"

        # In-memory index
        self.pdf_index: Dict[str, PDFDocument] = {}
        self.events: List[PDFChangeEvent] = []

        # PDF extractor
        self.extractor = PDFTextExtractor()

        # Load existing data
        self._load_index()

    def track_pdf(
        self, pdf_path: Path, tags: Optional[List[str]] = None
    ) -> Tuple[bool, PDFDocument, str]:
        """Track a PDF document.

        Args:
            pdf_path: Path to PDF file
            tags: Optional tags for categorization

        Returns:
            Tuple of (success, document, message)
        """
        if not pdf_path.exists():
            return False, None, f"PDF file not found: {pdf_path}"

        # Calculate relative path
        try:
            rel_path = pdf_path.relative_to(self.repo_path)
        except ValueError:
            return False, None, "PDF must be within repository"

        # Check if already tracked
        existing = self._find_by_path(str(rel_path))
        if existing:
            # Verify if changed
            current_hash = self._calculate_file_hash(pdf_path)
            if current_hash == existing.file_hash:
                return True, existing, "PDF already tracked and unchanged"
            else:
                # Update tracking
                return self._update_tracked_pdf(existing, pdf_path)

        # Extract tracking information
        tracking_info = self.extractor.extract_for_tracking(pdf_path)

        if not tracking_info["trackable"]:
            return (
                False,
                None,
                f"Cannot track PDF: {tracking_info.get('reason', 'Unknown error')}",
            )

        # Create document record
        doc = PDFDocument(
            document_id=self._generate_document_id(str(rel_path)),
            file_path=str(rel_path),
            file_hash=self._calculate_file_hash(pdf_path),
            file_size=pdf_path.stat().st_size,
            metadata=tracking_info.get("metadata", {}),
            tracking_info=tracking_info,
            added_date=datetime.now(),
            last_verified=datetime.now(),
            status="active",
            tags=tags or [],
        )

        # Add to index
        self.pdf_index[doc.document_id] = doc
        self._save_index()

        # Record event
        self._record_event(
            PDFChangeEvent(
                event_id=self._generate_event_id(),
                document_id=doc.document_id,
                event_type="added",
                timestamp=datetime.now(),
                details={"file_path": doc.file_path, "size": doc.file_size},
            )
        )

        logger.info(f"Tracked PDF: {doc.file_path}")
        return True, doc, "PDF tracked successfully"

    def verify_all_pdfs(self) -> Dict[str, List[PDFDocument]]:
        """Verify all tracked PDFs.

        Returns:
            Dictionary with verification results
        """
        results = {"active": [], "modified": [], "missing": []}

        for doc in list(self.pdf_index.values()):
            pdf_path = self.repo_path / doc.file_path

            if not pdf_path.exists():
                doc.status = "missing"
                results["missing"].append(doc)

                self._record_event(
                    PDFChangeEvent(
                        event_id=self._generate_event_id(),
                        document_id=doc.document_id,
                        event_type="deleted",
                        timestamp=datetime.now(),
                        details={"last_known_path": doc.file_path},
                    )
                )

            else:
                current_hash = self._calculate_file_hash(pdf_path)
                if current_hash != doc.file_hash:
                    doc.status = "modified"
                    results["modified"].append(doc)

                    self._record_event(
                        PDFChangeEvent(
                            event_id=self._generate_event_id(),
                            document_id=doc.document_id,
                            event_type="modified",
                            timestamp=datetime.now(),
                            details={
                                "old_hash": doc.file_hash,
                                "new_hash": current_hash,
                                "size_change": pdf_path.stat().st_size - doc.file_size,
                            },
                        )
                    )
                else:
                    doc.status = "active"
                    results["active"].append(doc)

            doc.last_verified = datetime.now()

        self._save_index()

        logger.info(
            f"Verified PDFs - Active: {len(results['active'])}, "
            f"Modified: {len(results['modified'])}, Missing: {len(results['missing'])}"
        )

        return results

    def find_pdfs(self, pattern: str = "**/*.pd") -> List[Path]:
        """Find all PDF files in repository.

        Args:
            pattern: Glob pattern for PDF files

        Returns:
            List of PDF file paths
        """
        pdf_files = []

        for pdf_path in self.repo_path.glob(pattern):
            if pdf_path.is_file() and not any(
                part.startswith(".") for part in pdf_path.parts
            ):
                pdf_files.append(pdf_path)

        return pdf_files

    def bulk_track(
        self, pattern: str = "**/*.pd", tags: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Track multiple PDFs at once.

        Args:
            pattern: Glob pattern for PDF files
            tags: Tags to apply to all PDFs

        Returns:
            Summary of tracking results
        """
        pdf_files = self.find_pdfs(pattern)

        results = {
            "tracked": 0,
            "already_tracked": 0,
            "failed": 0,
            "total": len(pdf_files),
        }

        for pdf_path in pdf_files:
            success, doc, message = self.track_pdf(pdf_path, tags)

            if success:
                if "already tracked" in message:
                    results["already_tracked"] += 1
                else:
                    results["tracked"] += 1
            else:
                results["failed"] += 1
                logger.warning(f"Failed to track {pdf_path}: {message}")

        return results

    def get_pdf_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information for a tracked PDF.

        Args:
            document_id: Document ID

        Returns:
            Summary information or None
        """
        doc = self.pdf_index.get(document_id)
        if not doc:
            return None

        summary = {
            "document_id": doc.document_id,
            "file_path": doc.file_path,
            "status": doc.status,
            "size": doc.file_size,
            "pages": doc.metadata.get("pages", 0),
            "title": doc.metadata.get("title"),
            "author": doc.metadata.get("author"),
            "added_date": doc.added_date.isoformat(),
            "last_verified": doc.last_verified.isoformat(),
            "tags": doc.tags,
        }

        # Add structure info if available
        if "structure" in doc.tracking_info:
            structure = doc.tracking_info["structure"]
            summary["structure"] = {
                "pages": structure.get("total_pages", 0),
                "words": structure.get("total_words", 0),
                "sections": structure.get("sections", 0),
                "has_signatures": structure.get("has_signatures", False),
            }

        # Add content summary if available
        if "content_summary" in doc.tracking_info:
            content = doc.tracking_info["content_summary"]
            summary["content"] = {
                "parties": content.get("parties", []),
                "key_dates": content.get("key_dates", []),
                "definitions": len(content.get("definitions", [])),
            }

        return summary

    def search_pdfs(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> List[PDFDocument]:
        """Search tracked PDFs.

        Args:
            query: Text to search in metadata/path
            tags: Filter by tags
            status: Filter by status

        Returns:
            List of matching documents
        """
        results = []

        for doc in self.pdf_index.values():
            # Filter by status
            if status and doc.status != status:
                continue

            # Filter by tags
            if tags and not any(tag in doc.tags for tag in tags):
                continue

            # Search query
            if query:
                query_lower = query.lower()
                searchable = [
                    doc.file_path.lower(),
                    doc.metadata.get("title", "").lower(),
                    doc.metadata.get("author", "").lower(),
                    doc.metadata.get("subject", "").lower(),
                ]

                if not any(query_lower in s for s in searchable):
                    continue

            results.append(doc)

        return results

    def get_events(
        self,
        document_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[PDFChangeEvent]:
        """Get PDF tracking events.

        Args:
            document_id: Filter by document
            event_type: Filter by event type
            limit: Maximum events to return

        Returns:
            List of events
        """
        events = self.events

        # Apply filters
        if document_id:
            events = [e for e in events if e.document_id == document_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    def _update_tracked_pdf(
        self, doc: PDFDocument, pdf_path: Path
    ) -> Tuple[bool, PDFDocument, str]:
        """Update tracking for modified PDF."""
        # Re-extract tracking info
        tracking_info = self.extractor.extract_for_tracking(pdf_path)

        if not tracking_info["trackable"]:
            doc.status = "modified"
            return (
                False,
                doc,
                f"Cannot update tracking: {tracking_info.get('reason', 'Unknown error')}",
            )

        # Update document
        doc.file_hash = self._calculate_file_hash(pdf_path)
        doc.file_size = pdf_path.stat().st_size
        doc.metadata = tracking_info.get("metadata", {})
        doc.tracking_info = tracking_info
        doc.last_verified = datetime.now()
        doc.status = "active"

        self._save_index()

        return True, doc, "PDF tracking updated"

    def _find_by_path(self, file_path: str) -> Optional[PDFDocument]:
        """Find document by file path."""
        for doc in self.pdf_index.values():
            if doc.file_path == file_path:
                return doc
        return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def _generate_document_id(self, file_path: str) -> str:
        """Generate unique document ID."""
        # Use path hash for consistency
        return hashlib.md5(file_path.encode()).hexdigest()[:12]

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        from uuid import uuid4

        return str(uuid4())[:8]

    def _record_event(self, event: PDFChangeEvent):
        """Record a PDF tracking event."""
        self.events.append(event)
        self._save_events()

    def _load_index(self):
        """Load PDF index from disk."""
        if self.pdf_index_file.exists():
            try:
                with open(self.pdf_index_file, "r") as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.items():
                        self.pdf_index[doc_id] = PDFDocument.from_dict(doc_data)
            except Exception as e:
                logger.error(f"Failed to load PDF index: {e}")

        if self.pdf_events_file.exists():
            try:
                with open(self.pdf_events_file, "r") as f:
                    data = json.load(f)
                    for event_data in data:
                        event_data["timestamp"] = datetime.fromisoformat(
                            event_data["timestamp"]
                        )
                        self.events.append(PDFChangeEvent(**event_data))
            except Exception as e:
                logger.error(f"Failed to load PDF events: {e}")

    def _save_index(self):
        """Save PDF index to disk."""
        try:
            index_data = {
                doc_id: doc.to_dict() for doc_id, doc in self.pdf_index.items()
            }

            with open(self.pdf_index_file, "w") as f:
                json.dump(index_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save PDF index: {e}")

    def _save_events(self):
        """Save events to disk."""
        try:
            # Keep only last 1000 events
            if len(self.events) > 1000:
                self.events = self.events[-1000:]

            events_data = [event.to_dict() for event in self.events]

            with open(self.pdf_events_file, "w") as f:
                json.dump(events_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save PDF events: {e}")
