"""Tests for cross-document reference management."""

from pathlib import Path

from doc_processing.references import CrossDocumentReferenceManager, URIHandler
from doc_processing.references.manager import DocumentReference


class TestDocumentReference:
    """Test DocumentReference dataclass."""

    def test_document_reference_creation(self):
        """Test creating a DocumentReference."""
        ref = DocumentReference(
            source_doc="contract.md",
            target_doc="terms.md",
            reference_type="clause_reference",
            source_location="line:15",
            target_location="section:2.1",
            metadata={"context": "payment terms"},
        )
        assert ref.source_doc == "contract.md"
        assert ref.target_doc == "terms.md"
        assert ref.reference_type == "clause_reference"
        assert ref.metadata["context"] == "payment terms"


class TestCrossDocumentReferenceManager:
    """Test CrossDocumentReferenceManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_repo = Path("/tmp/test_repo")
        self.manager = CrossDocumentReferenceManager(self.temp_repo)

    def test_manager_initialization(self):
        """Test manager initialization."""
        assert self.manager.repository_path == self.temp_repo
        assert isinstance(self.manager.uri_handler, URIHandler)
        assert self.manager.references == {}
        assert self.manager.reverse_references == {}

    def test_add_reference(self):
        """Test adding a cross-document reference."""
        ref = DocumentReference(
            source_doc="contract.md",
            target_doc="terms.md",
            reference_type="clause_reference",
            source_location="line:15",
        )

        self.manager.add_reference(ref)

        # Check forward reference
        outbound_refs = self.manager.get_outbound_references("contract.md")
        assert len(outbound_refs) == 1
        assert outbound_refs[0] == ref

        # Check reverse reference
        inbound_refs = self.manager.get_inbound_references("terms.md")
        assert len(inbound_refs) == 1
        assert inbound_refs[0] == ref

    def test_get_outbound_references_empty(self):
        """Test getting outbound references for document with none."""
        refs = self.manager.get_outbound_references("nonexistent.md")
        assert refs == []

    def test_get_inbound_references_empty(self):
        """Test getting inbound references for document with none."""
        refs = self.manager.get_inbound_references("nonexistent.md")
        assert refs == []

    def test_multiple_references_same_source(self):
        """Test multiple references from the same source document."""
        ref1 = DocumentReference(
            source_doc="contract.md",
            target_doc="terms.md",
            reference_type="clause_reference",
            source_location="line:15",
        )
        ref2 = DocumentReference(
            source_doc="contract.md",
            target_doc="definitions.md",
            reference_type="definition_reference",
            source_location="line:25",
        )

        self.manager.add_reference(ref1)
        self.manager.add_reference(ref2)

        outbound_refs = self.manager.get_outbound_references("contract.md")
        assert len(outbound_refs) == 2
        assert ref1 in outbound_refs
        assert ref2 in outbound_refs

    def test_update_reference_paths(self):
        """Test updating reference paths when document is moved."""
        ref = DocumentReference(
            source_doc="old_contract.md",
            target_doc="terms.md",
            reference_type="clause_reference",
            source_location="line:15",
        )

        self.manager.add_reference(ref)
        self.manager.update_reference_paths("old_contract.md", "new_contract.md")

        # Old path should be empty
        old_refs = self.manager.get_outbound_references("old_contract.md")
        assert old_refs == []

        # New path should have the reference
        new_refs = self.manager.get_outbound_references("new_contract.md")
        assert len(new_refs) == 1

    def test_validate_references(self):
        """Test reference validation."""
        ref = DocumentReference(
            source_doc="contract.md",
            target_doc="nonexistent.md",
            reference_type="clause_reference",
            source_location="line:15",
        )

        self.manager.add_reference(ref)
        errors = self.manager.validate_references()

        assert "contract.md" in errors
        assert "Broken reference to nonexistent.md" in errors["contract.md"]


class TestURIHandler:
    """Test URIHandler functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_repo = Path("/tmp/test_repo")
        self.handler = URIHandler(self.temp_repo)

    def test_handler_initialization(self):
        """Test URI handler initialization."""
        assert self.handler.repository_path == self.temp_repo
        assert "trunk" in self.handler.uri_schemes
        assert "file" in self.handler.uri_schemes
        assert "http" in self.handler.uri_schemes
        assert "https" in self.handler.uri_schemes

    def test_extract_scheme_trunk(self):
        """Test extracting trunk scheme."""
        scheme = self.handler._extract_scheme("trunk://documents/contract.md")
        assert scheme == "trunk"

    def test_extract_scheme_file(self):
        """Test extracting file scheme."""
        scheme = self.handler._extract_scheme("file:///path/to/file.txt")
        assert scheme == "file"

    def test_extract_scheme_relative_path(self):
        """Test extracting scheme from relative path."""
        scheme = self.handler._extract_scheme("documents/contract.md")
        assert scheme == "file"

    def test_extract_scheme_http(self):
        """Test extracting HTTP scheme."""
        scheme = self.handler._extract_scheme("http://example.com/doc.html")
        assert scheme == "http"

    def test_extract_scheme_https(self):
        """Test extracting HTTPS scheme."""
        scheme = self.handler._extract_scheme("https://example.com/doc.html")
        assert scheme == "https"

    def test_extract_scheme_invalid(self):
        """Test extracting invalid scheme."""
        scheme = self.handler._extract_scheme("invalid_uri")
        assert scheme == "file"  # Treated as relative path

    def test_resolve_trunk_uri(self):
        """Test resolving trunk URI."""
        result = self.handler._resolve_trunk_uri("trunk://documents/contract.md")
        assert result["type"] == "trunk_document"
        assert result["relative_path"] == "documents/contract.md"
        assert "path" in result
        assert "exists" in result

    def test_resolve_file_uri(self):
        """Test resolving file URI."""
        result = self.handler._resolve_file_uri("file:///path/to/file.txt")
        assert result["type"] == "file"
        assert result["path"] == "/path/to/file.txt"
        assert "exists" in result

    def test_resolve_relative_file_path(self):
        """Test resolving relative file path."""
        result = self.handler._resolve_file_uri("documents/contract.md")
        assert result["type"] == "file"
        assert result["is_relative"] is True

    def test_resolve_http_uri(self):
        """Test resolving HTTP URI."""
        result = self.handler._resolve_http_uri("http://example.com/doc.html")
        assert result["type"] == "http"
        assert result["url"] == "http://example.com/doc.html"
        assert "accessible" in result

    def test_resolve_https_uri(self):
        """Test resolving HTTPS URI."""
        result = self.handler._resolve_https_uri("https://example.com/doc.html")
        assert result["type"] == "https"
        assert result["url"] == "https://example.com/doc.html"
        assert "accessible" in result

    def test_create_trunk_uri(self):
        """Test creating trunk URI from document path."""
        uri = self.handler.create_trunk_uri("documents/contract.md")
        assert uri == "trunk://documents/contract.md"

    def test_create_trunk_uri_with_leading_slash(self):
        """Test creating trunk URI with leading slash."""
        uri = self.handler.create_trunk_uri("/documents/contract.md")
        assert uri == "trunk://documents/contract.md"

    def test_resolve_uri_trunk(self):
        """Test resolving trunk URI through main interface."""
        result = self.handler.resolve_uri("trunk://documents/contract.md")
        assert result is not None
        assert result["type"] == "trunk_document"

    def test_resolve_uri_invalid_scheme(self):
        """Test resolving URI with invalid scheme."""
        result = self.handler.resolve_uri("invalid://test")
        assert result is None
