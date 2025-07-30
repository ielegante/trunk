"""Cross-document reference management system."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .uri_handler import URIHandler


@dataclass
class DocumentReference:
    """Represents a reference between documents."""

    source_doc: str
    target_doc: str
    reference_type: str
    source_location: str
    target_location: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CrossDocumentReferenceManager:
    """Manages cross-document references and URI resolution."""

    def __init__(self, repository_path: Path):
        """Initialize reference manager for a repository.

        Args:
            repository_path: Path to the legal document repository
        """
        self.repository_path = repository_path
        self.uri_handler = URIHandler(repository_path)
        self.references: Dict[str, List[DocumentReference]] = {}
        self.reverse_references: Dict[str, List[DocumentReference]] = {}

    def add_reference(self, reference: DocumentReference) -> None:
        """Add a cross-document reference.

        Args:
            reference: DocumentReference to add
        """
        # Add to forward references
        if reference.source_doc not in self.references:
            self.references[reference.source_doc] = []
        self.references[reference.source_doc].append(reference)

        # Add to reverse references
        if reference.target_doc not in self.reverse_references:
            self.reverse_references[reference.target_doc] = []
        self.reverse_references[reference.target_doc].append(reference)

    def get_outbound_references(self, document_path: str) -> List[DocumentReference]:
        """Get all references from a document.

        Args:
            document_path: Path to the source document

        Returns:
            List of outbound references
        """
        return self.references.get(document_path, [])

    def get_inbound_references(self, document_path: str) -> List[DocumentReference]:
        """Get all references to a document.

        Args:
            document_path: Path to the target document

        Returns:
            List of inbound references
        """
        return self.reverse_references.get(document_path, [])

    def validate_references(self) -> Dict[str, List[str]]:
        """Validate all cross-document references.

        Returns:
            Dictionary of validation errors by document
        """
        errors = {}

        for doc_path, refs in self.references.items():
            doc_errors = []
            for ref in refs:
                resolution = self.uri_handler.resolve_uri(ref.target_doc)
                if not resolution or not resolution.get("exists", False):
                    doc_errors.append(f"Broken reference to {ref.target_doc}")

            if doc_errors:
                errors[doc_path] = doc_errors

        return errors

    def update_reference_paths(self, old_path: str, new_path: str) -> None:
        """Update references when a document is moved.

        Args:
            old_path: Original document path
            new_path: New document path
        """
        # Update forward references
        if old_path in self.references:
            self.references[new_path] = self.references.pop(old_path)

        # Update reverse references
        if old_path in self.reverse_references:
            self.reverse_references[new_path] = self.reverse_references.pop(old_path)

        # Update target paths in all references
        for refs_list in self.references.values():
            for ref in refs_list:
                if ref.target_doc == old_path:
                    ref.target_doc = new_path
