"""URI-based reference system for cross-document linking."""

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlparse, urlunparse

logger = logging.getLogger(__name__)


@dataclass
class DocumentURI:
    """Represents a document URI in the firm:// scheme."""

    scheme: str = "firm"
    repository: Optional[str] = None  # matter ID or "template"
    document: Optional[str] = None  # document name/path
    section: Optional[str] = None  # section identifier
    subsection: Optional[str] = None  # subsection identifier
    paragraph: Optional[str] = None  # paragraph identifier
    query: Dict[str, List[str]] = field(default_factory=dict)  # query parameters
    fragment: Optional[str] = None  # fragment identifier

    def to_string(self) -> str:
        """Convert URI to string representation."""
        path_parts = []

        if self.repository:
            path_parts.append(self.repository)
        if self.document:
            path_parts.append(self.document)
        if self.section:
            path_parts.append(self.section)
        if self.subsection:
            path_parts.append(self.subsection)
        if self.paragraph:
            path_parts.append(self.paragraph)

        path = "/".join(path_parts)

        # Build query string
        query_str = ""
        if self.query:
            query_parts = []
            for key, values in self.query.items():
                for value in values:
                    query_parts.append(f"{key}={value}")
            if query_parts:
                query_str = "?" + "&".join(query_parts)

        # Build fragment
        fragment_str = f"#{self.fragment}" if self.fragment else ""

        return f"{self.scheme}://{path}{query_str}{fragment_str}"

    @classmethod
    def from_string(cls, uri_string: str) -> "DocumentURI":
        """Parse URI string into DocumentURI object."""
        # Handle special case of "this-doc"
        if uri_string.startswith("firm://this-doc"):
            uri_string = uri_string.replace("this-doc", "_this_doc_")

        # Parse URI
        parsed = urlparse(uri_string)

        if parsed.scheme != "firm":
            raise ValueError(f"Invalid URI scheme: {parsed.scheme}")

        # Parse path components
        path_parts = [p for p in parsed.path.split("/") if p]

        # Restore "this-doc"
        path_parts = ["this-doc" if p == "_this_doc_" else p for p in path_parts]

        # Extract components
        repository = path_parts[0] if len(path_parts) > 0 else None
        document = path_parts[1] if len(path_parts) > 1 else None
        section = path_parts[2] if len(path_parts) > 2 else None
        subsection = path_parts[3] if len(path_parts) > 3 else None
        paragraph = path_parts[4] if len(path_parts) > 4 else None

        # Parse query parameters
        query = parse_qs(parsed.query) if parsed.query else {}

        return cls(
            scheme="firm",
            repository=repository,
            document=document,
            section=section,
            subsection=subsection,
            paragraph=paragraph,
            query=query,
            fragment=parsed.fragment,
        )

    def is_template_reference(self) -> bool:
        """Check if this URI references a template."""
        return self.repository == "template"

    def is_internal_reference(self) -> bool:
        """Check if this URI references the current document."""
        return self.repository == "this-doc"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class DocumentAnchor:
    """Represents a stable anchor point in a document."""

    anchor_id: str
    anchor_type: str  # section, subsection, paragraph, named
    document_path: str
    position: int  # Character position in document
    text: str  # Text at anchor point
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class DocumentReference:
    """Represents a reference from one document to another."""

    reference_id: str
    source_document: str
    source_position: int
    target_uri: DocumentURI
    reference_text: str  # The text that contains the reference
    reference_type: str  # explicit, implicit, citation
    created_at: datetime
    last_verified: datetime
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["target_uri"] = self.target_uri.to_dict()
        data["created_at"] = self.created_at.isoformat()
        data["last_verified"] = self.last_verified.isoformat()
        return data


class URISystem:
    """Manages URI-based references across documents."""

    # Patterns for detecting references
    URI_PATTERN = re.compile(r"firm://[^\s\)>\]]+")
    SECTION_REF_PATTERN = re.compile(r"(?:Section|§)\s*(\d+(?:\.\d+)*)", re.IGNORECASE)
    PLACEHOLDER_PATTERN = re.compile(r"\{\{([^}]+)\}\}")

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize URI system.

        Args:
            storage_path: Path for storing reference data
        """
        self.storage_path = storage_path or Path(".references")
        self.storage_path.mkdir(exist_ok=True)

        # Caches
        self.anchors: Dict[str, List[DocumentAnchor]] = {}
        self.references: Dict[str, List[DocumentReference]] = {}
        self.uri_index: Dict[str, Set[str]] = {}  # target_uri -> source_docs

        # Load existing data
        self._load_data()

    def create_uri(
        self,
        repository: Optional[str] = None,
        document: Optional[str] = None,
        section: Optional[str] = None,
        subsection: Optional[str] = None,
        paragraph: Optional[str] = None,
        **kwargs,
    ) -> DocumentURI:
        """Create a new document URI.

        Args:
            repository: Repository/matter ID or "template" or "this-doc"
            document: Document path within repository
            section: Section identifier
            subsection: Subsection identifier
            paragraph: Paragraph identifier
            **kwargs: Additional query parameters

        Returns:
            DocumentURI object
        """
        uri = DocumentURI(
            repository=repository,
            document=document,
            section=section,
            subsection=subsection,
            paragraph=paragraph,
        )

        # Add query parameters
        for key, value in kwargs.items():
            if isinstance(value, list):
                uri.query[key] = value
            else:
                uri.query[key] = [str(value)]

        return uri

    def parse_uri(self, uri_string: str) -> DocumentURI:
        """Parse a URI string.

        Args:
            uri_string: URI string to parse

        Returns:
            DocumentURI object
        """
        return DocumentURI.from_string(uri_string)

    def create_anchor(
        self,
        document_path: str,
        anchor_type: str,
        position: int,
        text: str,
        anchor_id: Optional[str] = None,
        **metadata,
    ) -> DocumentAnchor:
        """Create a document anchor.

        Args:
            document_path: Path to document
            anchor_type: Type of anchor
            position: Character position
            text: Text at anchor
            anchor_id: Optional custom ID
            **metadata: Additional metadata

        Returns:
            DocumentAnchor object
        """
        if not anchor_id:
            # Generate stable ID based on content
            content = f"{document_path}:{anchor_type}:{position}:{text}"
            anchor_id = hashlib.sha256(content.encode()).hexdigest()[:12]

        anchor = DocumentAnchor(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            document_path=document_path,
            position=position,
            text=text,
            metadata=metadata,
        )

        # Store anchor
        if document_path not in self.anchors:
            self.anchors[document_path] = []
        self.anchors[document_path].append(anchor)

        self._save_anchors(document_path)
        return anchor

    def scan_document_for_references(
        self, document_path: str, content: str
    ) -> List[DocumentReference]:
        """Scan document content for references.

        Args:
            document_path: Path to document
            content: Document content

        Returns:
            List of found references
        """
        references = []

        # Find URI references
        for match in self.URI_PATTERN.finditer(content):
            uri_string = match.group()
            position = match.start()

            try:
                uri = self.parse_uri(uri_string)

                ref = DocumentReference(
                    reference_id=self._generate_reference_id(document_path, position),
                    source_document=document_path,
                    source_position=position,
                    target_uri=uri,
                    reference_text=uri_string,
                    reference_type="explicit",
                    created_at=datetime.now(),
                    last_verified=datetime.now(),
                )

                references.append(ref)

            except ValueError as e:
                logger.warning(f"Invalid URI in {document_path}: {uri_string} - {e}")

        # Find section references
        for match in self.SECTION_REF_PATTERN.finditer(content):
            section_num = match.group(1)
            position = match.start()

            # Create implicit reference to current document section
            uri = self.create_uri(
                repository="this-doc",
                section=f"section-{section_num.replace('.', '-')}",
            )

            ref = DocumentReference(
                reference_id=self._generate_reference_id(document_path, position),
                source_document=document_path,
                source_position=position,
                target_uri=uri,
                reference_text=match.group(),
                reference_type="implicit",
                created_at=datetime.now(),
                last_verified=datetime.now(),
            )

            references.append(ref)

        # Store references
        self.references[document_path] = references
        self._save_references(document_path)

        # Update index
        self._update_uri_index(references)

        return references

    def resolve_reference(
        self, uri: DocumentURI, context_document: Optional[str] = None
    ) -> Optional[DocumentAnchor]:
        """Resolve a URI to a specific anchor.

        Args:
            uri: URI to resolve
            context_document: Current document for relative references

        Returns:
            DocumentAnchor if found, None otherwise
        """
        # Handle internal references
        if uri.is_internal_reference() and context_document:
            document_path = context_document
        elif uri.repository and uri.document:
            document_path = f"{uri.repository}/{uri.document}"
        else:
            return None

        # Get anchors for document
        anchors = self.anchors.get(document_path, [])

        # Find matching anchor
        for anchor in anchors:
            if self._anchor_matches_uri(anchor, uri):
                return anchor

        return None

    def get_document_dependencies(
        self, document_path: str
    ) -> Dict[str, List[DocumentReference]]:
        """Get all documents that this document depends on.

        Args:
            document_path: Path to document

        Returns:
            Dictionary mapping target documents to references
        """
        dependencies = {}

        refs = self.references.get(document_path, [])
        for ref in refs:
            if not ref.target_uri.is_internal_reference():
                target = ref.target_uri.to_string()
                if target not in dependencies:
                    dependencies[target] = []
                dependencies[target].append(ref)

        return dependencies

    def get_document_dependents(
        self, document_path: str
    ) -> Dict[str, List[DocumentReference]]:
        """Get all documents that depend on this document.

        Args:
            document_path: Path to document

        Returns:
            Dictionary mapping source documents to references
        """
        dependents = {}

        # Build possible URIs for this document
        possible_uris = self._build_possible_uris(document_path)

        # Check all references
        for source_doc, refs in self.references.items():
            for ref in refs:
                if ref.target_uri.to_string() in possible_uris:
                    if source_doc not in dependents:
                        dependents[source_doc] = []
                    dependents[source_doc].append(ref)

        return dependents

    def update_references(
        self, document_path: str, old_content: str, new_content: str
    ) -> List[str]:
        """Update references when document content changes.

        Args:
            document_path: Path to document
            old_content: Previous content
            new_content: New content

        Returns:
            List of affected document paths
        """
        # Find what changed
        old_refs = set()
        new_refs = set()

        # Extract old references
        for match in self.URI_PATTERN.finditer(old_content):
            old_refs.add(match.group())

        # Extract new references
        for match in self.URI_PATTERN.finditer(new_content):
            new_refs.add(match.group())

        # Determine changes
        removed_refs = old_refs - new_refs
        added_refs = new_refs - old_refs

        affected_docs = set()

        # Handle removed references
        if removed_refs:
            for uri_string in removed_refs:
                try:
                    uri = self.parse_uri(uri_string)
                    target = self._get_target_document(uri)
                    if target:
                        affected_docs.add(target)
                except Exception:
                    pass

        # Re-scan document
        self.scan_document_for_references(document_path, new_content)

        # Get all dependents
        dependents = self.get_document_dependents(document_path)
        affected_docs.update(dependents.keys())

        return list(affected_docs)

    def validate_references(
        self, document_path: str
    ) -> List[Tuple[DocumentReference, str]]:
        """Validate all references in a document.

        Args:
            document_path: Path to document

        Returns:
            List of (reference, error_message) for invalid references
        """
        invalid_refs = []

        refs = self.references.get(document_path, [])
        for ref in refs:
            # Try to resolve reference
            anchor = self.resolve_reference(ref.target_uri, document_path)

            if not anchor:
                error = f"Cannot resolve reference: {ref.target_uri.to_string()}"
                invalid_refs.append((ref, error))
                ref.is_valid = False
            else:
                ref.is_valid = True

            ref.last_verified = datetime.now()

        # Save updated references
        if refs:
            self._save_references(document_path)

        return invalid_refs

    def apply_renumbering(self, content: str, renumbering_map: Dict[str, str]) -> str:
        """Apply section renumbering to content.

        Args:
            content: Document content
            renumbering_map: Map of placeholder -> actual number

        Returns:
            Content with renumbering applied
        """
        result = content

        # Replace placeholders
        for placeholder, actual in renumbering_map.items():
            pattern = f"{{{{{placeholder}}}}}"
            result = result.replace(pattern, actual)

        return result

    def _generate_reference_id(self, document_path: str, position: int) -> str:
        """Generate unique reference ID."""
        content = f"{document_path}:{position}:{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _anchor_matches_uri(self, anchor: DocumentAnchor, uri: DocumentURI) -> bool:
        """Check if anchor matches URI."""
        # Match by section
        if uri.section:
            section_id = uri.section.replace("-", ".")
            if anchor.anchor_type == "section" and section_id in anchor.text:
                return True

        # Match by anchor ID
        if uri.fragment and anchor.anchor_id == uri.fragment:
            return True

        # Match by metadata
        if uri.query:
            for key, values in uri.query.items():
                if key in anchor.metadata:
                    if str(anchor.metadata[key]) in values:
                        return True

        return False

    def _build_possible_uris(self, document_path: str) -> Set[str]:
        """Build all possible URIs that could reference this document."""
        uris = set()

        parts = document_path.split("/")
        if len(parts) >= 2:
            repo = parts[0]
            doc = "/".join(parts[1:])

            # Basic document reference
            uri = self.create_uri(repository=repo, document=doc)
            uris.add(uri.to_string())

            # With sections
            anchors = self.anchors.get(document_path, [])
            for anchor in anchors:
                if anchor.anchor_type == "section":
                    uri = self.create_uri(
                        repository=repo, document=doc, section=anchor.anchor_id
                    )
                    uris.add(uri.to_string())

        return uris

    def _get_target_document(self, uri: DocumentURI) -> Optional[str]:
        """Get document path from URI."""
        if uri.repository and uri.document:
            return f"{uri.repository}/{uri.document}"
        return None

    def _update_uri_index(self, references: List[DocumentReference]):
        """Update URI index with new references."""
        for ref in references:
            uri_str = ref.target_uri.to_string()
            if uri_str not in self.uri_index:
                self.uri_index[uri_str] = set()
            self.uri_index[uri_str].add(ref.source_document)

    def _load_data(self):
        """Load stored reference data."""
        # Load anchors
        anchors_dir = self.storage_path / "anchors"
        if anchors_dir.exists():
            for anchor_file in anchors_dir.glob("*.json"):
                doc_path = anchor_file.stem.replace("__", "/")
                self._load_anchors(doc_path)

        # Load references
        refs_dir = self.storage_path / "references"
        if refs_dir.exists():
            for ref_file in refs_dir.glob("*.json"):
                doc_path = ref_file.stem.replace("__", "/")
                self._load_references(doc_path)

    def _save_anchors(self, document_path: str):
        """Save anchors for a document."""
        import json

        anchors_dir = self.storage_path / "anchors"
        anchors_dir.mkdir(exist_ok=True)

        file_name = document_path.replace("/", "__") + ".json"
        file_path = anchors_dir / file_name

        anchors_data = [a.to_dict() for a in self.anchors.get(document_path, [])]

        with open(file_path, "w") as f:
            json.dump(anchors_data, f, indent=2)

    def _load_anchors(self, document_path: str):
        """Load anchors for a document."""
        import json

        anchors_dir = self.storage_path / "anchors"
        file_name = document_path.replace("/", "__") + ".json"
        file_path = anchors_dir / file_name

        if file_path.exists():
            with open(file_path, "r") as f:
                anchors_data = json.load(f)

            self.anchors[document_path] = [
                DocumentAnchor(**data) for data in anchors_data
            ]

    def _save_references(self, document_path: str):
        """Save references for a document."""
        import json

        refs_dir = self.storage_path / "references"
        refs_dir.mkdir(exist_ok=True)

        file_name = document_path.replace("/", "__") + ".json"
        file_path = refs_dir / file_name

        refs_data = [r.to_dict() for r in self.references.get(document_path, [])]

        with open(file_path, "w") as f:
            json.dump(refs_data, f, indent=2, default=str)

    def _load_references(self, document_path: str):
        """Load references for a document."""
        import json

        refs_dir = self.storage_path / "references"
        file_name = document_path.replace("/", "__") + ".json"
        file_path = refs_dir / file_name

        if file_path.exists():
            with open(file_path, "r") as f:
                refs_data = json.load(f)

            refs = []
            for data in refs_data:
                # Reconstruct URI
                uri_data = data.pop("target_uri")
                uri = DocumentURI(**uri_data)

                # Parse dates
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["last_verified"] = datetime.fromisoformat(data["last_verified"])

                ref = DocumentReference(target_uri=uri, **data)
                refs.append(ref)

            self.references[document_path] = refs
            self._update_uri_index(refs)
