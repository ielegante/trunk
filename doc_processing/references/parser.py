"""Reference parsing engine for cross-document references.

This module provides comprehensive parsing of various reference types including
document references, section references, clause references, and custom URIs.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class ReferenceType(Enum):
    """Types of references that can be parsed."""

    INTERNAL_DOCUMENT = "internal_document"  # References within the repository
    EXTERNAL_DOCUMENT = "external_document"  # References to external sources
    SECTION = "section"  # Section/heading references
    CLAUSE = "clause"  # Clause references (numbered)
    PARAGRAPH = "paragraph"  # Paragraph references
    FOOTNOTE = "footnote"  # Footnote references
    CITATION = "citation"  # Legal citations
    URI = "uri"  # Custom URI references (firm://)
    ATTACHMENT = "attachment"  # Attachment references
    DEFINITION = "definition"  # Defined term references
    EXHIBIT = "exhibit"  # Exhibit references
    SCHEDULE = "schedule"  # Schedule/appendix references


@dataclass
class ReferenceLocation:
    """Location information for a reference."""

    start_position: int
    end_position: int
    line_number: int
    column_number: int
    context: str  # Surrounding text for context


@dataclass
class Reference:
    """Represents a parsed reference."""

    reference_id: str
    reference_type: ReferenceType
    source_document: str
    target_document: Optional[str]
    target_section: Optional[str]
    target_element: Optional[str]
    raw_text: str
    normalized_text: str
    location: ReferenceLocation
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert reference to dictionary representation."""
        return {
            "reference_id": self.reference_id,
            "reference_type": self.reference_type.value,
            "source_document": self.source_document,
            "target_document": self.target_document,
            "target_section": self.target_section,
            "target_element": self.target_element,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "location": {
                "start_position": self.location.start_position,
                "end_position": self.location.end_position,
                "line_number": self.location.line_number,
                "column_number": self.location.column_number,
                "context": self.location.context,
            },
            "metadata": self.metadata,
            "confidence": self.confidence,
        }


class ReferenceParser:
    """Comprehensive reference parsing engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize reference parser.

        Args:
            config: Configuration options for parsing
        """
        self.config = config or {}

        # Configuration options
        self.case_sensitive = self.config.get("case_sensitive", False)
        self.include_context_chars = self.config.get("include_context_chars", 50)
        self.min_confidence_threshold = self.config.get("min_confidence_threshold", 0.7)

        # Initialize reference patterns
        self._initialize_patterns()

        # Reference ID counter
        self._reference_counter = 0

    def _initialize_patterns(self):
        """Initialize regex patterns for reference detection."""
        # Document reference patterns
        self.document_patterns = {
            "see_reference": re.compile(
                r"\b(?:see|See|SEE)\s+(?:also\s+)?(?:generally\s+)?"
                r"([A-Z][A-Za-z0-9\s\-&.,]+?)(?:\s+at\s+([0-9\-–—]+))?"
                r"(?=[,;.\s]|$)",
                re.MULTILINE,
            ),
            "as_defined_in": re.compile(
                r"\bas\s+(?:defined|set\s+forth)\s+in\s+"
                r"(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?)(?:\s+at\s+([0-9\-–—]+))?"
                r"(?=[,;.\s]|$)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "pursuant_to": re.compile(
                r"\bpursuant\s+to\s+(?:the\s+)?"
                r"([A-Z][A-Za-z0-9\s\-&.,]+?)(?:\s+at\s+([0-9\-–—]+))?"
                r"(?=[,;.\s]|$)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "exhibit_reference": re.compile(
                r"\b(?:Exhibit|EXHIBIT)\s+([A-Z0-9\-]+)"
                r"(?:\s+(?:to|of)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?))?",
                re.MULTILINE,
            ),
            "schedule_reference": re.compile(
                r"\b(?:Schedule|SCHEDULE|Appendix|APPENDIX)\s+([A-Z0-9\-]+)"
                r"(?:\s+(?:to|of)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?))?",
                re.MULTILINE,
            ),
        }

        # Section and clause patterns
        self.structure_patterns = {
            "section": re.compile(
                r"\b(?:Section|SECTION|§)\s*([0-9]+(?:\.[0-9]+)*)"
                r"(?:\s*\(([a-zA-Z0-9]+)\))?"
                r"(?:\s+of\s+(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?))?",
                re.MULTILINE,
            ),
            "clause": re.compile(
                r"\b(?:Clause|CLAUSE)\s*([0-9]+(?:\.[0-9]+)*)"
                r"(?:\s*\(([a-zA-Z0-9]+)\))?"
                r"(?:\s+of\s+(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?))?",
                re.MULTILINE,
            ),
            "paragraph": re.compile(
                r"\b(?:Paragraph|PARAGRAPH|¶)\s*([0-9]+(?:\.[0-9]+)*)"
                r"(?:\s*\(([a-zA-Z0-9]+)\))?",
                re.MULTILINE,
            ),
            "article": re.compile(
                r"\b(?:Article|ARTICLE)\s+([IVX]+|[0-9]+)"
                r"(?:\s+of\s+(?:the\s+)?([A-Z][A-Za-z0-9\s\-&.,]+?))?",
                re.MULTILINE,
            ),
        }

        # URI patterns
        self.uri_patterns = {
            "firm_uri": re.compile(
                r"\bfirm://([a-zA-Z0-9\-_/]+)(?:\?([^>\s]+))?", re.MULTILINE
            ),
            "legal_uri": re.compile(
                r"\blegal://([a-zA-Z0-9\-_/]+)(?:\?([^>\s]+))?", re.MULTILINE
            ),
            "doc_uri": re.compile(
                r"\bdoc://([a-zA-Z0-9\-_/]+)(?:\?([^>\s]+))?", re.MULTILINE
            ),
        }

        # Definition and term patterns
        self.definition_patterns = {
            "defined_term": re.compile(
                r'"([A-Z][A-Za-z0-9\s]+?)"'
                r"(?:\s+(?:means|shall\s+mean|has\s+the\s+meaning))",
                re.MULTILINE,
            ),
            "term_reference": re.compile(
                r'\b(?:the\s+)?(?:term\s+)?"([A-Z][A-Za-z0-9\s]+?)"', re.MULTILINE
            ),
            "capitalized_term": re.compile(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", re.MULTILINE
            ),
        }

        # Footnote patterns
        self.footnote_patterns = {
            "footnote_marker": re.compile(
                r"(?:\[\^([0-9]+)\]|<sup>([0-9]+)</sup>|\^([0-9]+))", re.MULTILINE
            ),
            "footnote_reference": re.compile(
                r"\b(?:footnote|Footnote|FOOTNOTE)\s+([0-9]+)", re.MULTILINE
            ),
        }

    def parse_document(
        self,
        content: str,
        document_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Reference]:
        """Parse all references in a document.

        Args:
            content: Document content to parse
            document_path: Path or identifier of the source document
            metadata: Optional metadata about the document

        Returns:
            List of parsed references
        """
        references = []

        # Parse different types of references
        references.extend(self._parse_document_references(content, document_path))
        references.extend(self._parse_structure_references(content, document_path))
        references.extend(self._parse_uri_references(content, document_path))
        references.extend(self._parse_definition_references(content, document_path))
        references.extend(self._parse_footnote_references(content, document_path))

        # Filter by confidence threshold
        references = [
            ref for ref in references if ref.confidence >= self.min_confidence_threshold
        ]

        # Sort by position
        references.sort(key=lambda r: r.location.start_position)

        logger.info(f"Parsed {len(references)} references from {document_path}")

        return references

    def _parse_document_references(
        self, content: str, document_path: str
    ) -> List[Reference]:
        """Parse document-level references."""
        references = []

        for pattern_name, pattern in self.document_patterns.items():
            for match in pattern.finditer(content):
                location = self._get_reference_location(content, match)

                # Extract components based on pattern type
                if pattern_name == "see_reference":
                    target_doc = match.group(1).strip()
                    target_section = match.group(2) if match.lastindex >= 2 else None
                    ref_type = ReferenceType.EXTERNAL_DOCUMENT

                elif pattern_name in ["as_defined_in", "pursuant_to"]:
                    target_doc = match.group(1).strip()
                    target_section = match.group(2) if match.lastindex >= 2 else None
                    ref_type = ReferenceType.INTERNAL_DOCUMENT

                elif pattern_name == "exhibit_reference":
                    exhibit_id = match.group(1)
                    parent_doc = match.group(2) if match.lastindex >= 2 else None
                    target_doc = f"Exhibit {exhibit_id}"
                    if parent_doc:
                        target_doc += f" to {parent_doc}"
                    ref_type = ReferenceType.EXHIBIT

                elif pattern_name == "schedule_reference":
                    schedule_id = match.group(1)
                    parent_doc = match.group(2) if match.lastindex >= 2 else None
                    target_doc = f"Schedule {schedule_id}"
                    if parent_doc:
                        target_doc += f" to {parent_doc}"
                    ref_type = ReferenceType.SCHEDULE

                else:
                    continue

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ref_type,
                    source_document=document_path,
                    target_document=target_doc,
                    target_section=target_section,
                    target_element=None,
                    raw_text=match.group(0),
                    normalized_text=self._normalize_reference_text(match.group(0)),
                    location=location,
                    metadata={"pattern": pattern_name},
                    confidence=0.9,
                )

                references.append(reference)

        return references

    def _parse_structure_references(
        self, content: str, document_path: str
    ) -> List[Reference]:
        """Parse structural references (sections, clauses, etc.)."""
        references = []

        for pattern_name, pattern in self.structure_patterns.items():
            for match in pattern.finditer(content):
                location = self._get_reference_location(content, match)

                # Extract components
                element_number = match.group(1)
                sub_element = match.group(2) if match.lastindex >= 2 else None
                parent_doc = match.group(3) if match.lastindex >= 3 else None

                # Determine reference type
                if pattern_name == "section":
                    ref_type = ReferenceType.SECTION
                elif pattern_name == "clause":
                    ref_type = ReferenceType.CLAUSE
                elif pattern_name == "paragraph":
                    ref_type = ReferenceType.PARAGRAPH
                elif pattern_name == "article":
                    ref_type = ReferenceType.SECTION
                else:
                    continue

                # Build target element
                target_element = element_number
                if sub_element:
                    target_element += f"({sub_element})"

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ref_type,
                    source_document=document_path,
                    target_document=parent_doc
                    or document_path,  # Default to same document
                    target_section=pattern_name.title(),
                    target_element=target_element,
                    raw_text=match.group(0),
                    normalized_text=self._normalize_reference_text(match.group(0)),
                    location=location,
                    metadata={"pattern": pattern_name, "element_type": pattern_name},
                    confidence=0.95,
                )

                references.append(reference)

        return references

    def _parse_uri_references(
        self, content: str, document_path: str
    ) -> List[Reference]:
        """Parse URI-based references."""
        references = []

        for pattern_name, pattern in self.uri_patterns.items():
            for match in pattern.finditer(content):
                location = self._get_reference_location(content, match)

                # Parse URI components
                uri_path = match.group(1)
                query_string = match.group(2) if match.lastindex >= 2 else None

                # Parse query parameters
                query_params = {}
                if query_string:
                    query_params = parse_qs(query_string)

                # Extract document and section from URI path
                path_parts = uri_path.split("/")
                target_doc = path_parts[0] if path_parts else None
                target_section = (
                    "/".join(path_parts[1:]) if len(path_parts) > 1 else None
                )

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ReferenceType.URI,
                    source_document=document_path,
                    target_document=target_doc,
                    target_section=target_section,
                    target_element=None,
                    raw_text=match.group(0),
                    normalized_text=match.group(0),  # Keep URI as-is
                    location=location,
                    metadata={
                        "pattern": pattern_name,
                        "uri_scheme": pattern_name.replace("_uri", ""),
                        "uri_path": uri_path,
                        "query_params": query_params,
                    },
                    confidence=1.0,  # URIs are unambiguous
                )

                references.append(reference)

        return references

    def _parse_definition_references(
        self, content: str, document_path: str
    ) -> List[Reference]:
        """Parse definition and defined term references."""
        references = []
        defined_terms = set()

        # First, find all defined terms
        for match in self.definition_patterns["defined_term"].finditer(content):
            term = match.group(1).strip()
            defined_terms.add(term.lower())

            location = self._get_reference_location(content, match)

            reference = Reference(
                reference_id=self._generate_reference_id(),
                reference_type=ReferenceType.DEFINITION,
                source_document=document_path,
                target_document=document_path,
                target_section="Definitions",
                target_element=term,
                raw_text=match.group(0),
                normalized_text=term,
                location=location,
                metadata={
                    "pattern": "defined_term",
                    "is_definition": True,
                    "term": term,
                },
                confidence=1.0,
            )

            references.append(reference)

        # Then, find references to defined terms
        for match in self.definition_patterns["term_reference"].finditer(content):
            term = match.group(1).strip()

            # Check if this is a reference to a defined term
            if term.lower() in defined_terms:
                location = self._get_reference_location(content, match)

                # Skip if this is part of the definition itself
                if any(
                    ref.location.start_position
                    <= location.start_position
                    <= ref.location.end_position
                    for ref in references
                    if ref.metadata.get("is_definition")
                ):
                    continue

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ReferenceType.DEFINITION,
                    source_document=document_path,
                    target_document=document_path,
                    target_section="Definitions",
                    target_element=term,
                    raw_text=match.group(0),
                    normalized_text=term,
                    location=location,
                    metadata={
                        "pattern": "term_reference",
                        "is_reference": True,
                        "term": term,
                    },
                    confidence=0.9,
                )

                references.append(reference)

        # Also check capitalized terms
        for match in self.definition_patterns["capitalized_term"].finditer(content):
            term = match.group(1).strip()

            if term.lower() in defined_terms:
                location = self._get_reference_location(content, match)

                # Avoid duplicates
                if any(
                    ref.location.start_position == location.start_position
                    for ref in references
                ):
                    continue

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ReferenceType.DEFINITION,
                    source_document=document_path,
                    target_document=document_path,
                    target_section="Definitions",
                    target_element=term,
                    raw_text=match.group(0),
                    normalized_text=term,
                    location=location,
                    metadata={
                        "pattern": "capitalized_term",
                        "is_reference": True,
                        "term": term,
                    },
                    confidence=0.7,  # Lower confidence for capitalized terms
                )

                references.append(reference)

        return references

    def _parse_footnote_references(
        self, content: str, document_path: str
    ) -> List[Reference]:
        """Parse footnote references."""
        references = []

        for pattern_name, pattern in self.footnote_patterns.items():
            for match in pattern.finditer(content):
                location = self._get_reference_location(content, match)

                # Extract footnote number
                footnote_num = None
                for group in match.groups():
                    if group:
                        footnote_num = group
                        break

                if not footnote_num:
                    continue

                reference = Reference(
                    reference_id=self._generate_reference_id(),
                    reference_type=ReferenceType.FOOTNOTE,
                    source_document=document_path,
                    target_document=document_path,
                    target_section="Footnotes",
                    target_element=footnote_num,
                    raw_text=match.group(0),
                    normalized_text=f"Footnote {footnote_num}",
                    location=location,
                    metadata={"pattern": pattern_name, "footnote_number": footnote_num},
                    confidence=1.0,
                )

                references.append(reference)

        return references

    def _get_reference_location(
        self, content: str, match: re.Match
    ) -> ReferenceLocation:
        """Get location information for a reference match."""
        start_pos = match.start()
        end_pos = match.end()

        # Calculate line and column numbers
        lines_before = content[:start_pos].split("\n")
        line_number = len(lines_before)
        column_number = len(lines_before[-1]) + 1 if lines_before else 1

        # Extract context
        context_start = max(0, start_pos - self.include_context_chars)
        context_end = min(len(content), end_pos + self.include_context_chars)
        context = content[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(content):
            context = context + "..."

        return ReferenceLocation(
            start_position=start_pos,
            end_position=end_pos,
            line_number=line_number,
            column_number=column_number,
            context=context,
        )

    def _normalize_reference_text(self, text: str) -> str:
        """Normalize reference text for consistency."""
        # Remove extra whitespace
        text = " ".join(text.split())

        # Normalize dashes
        text = text.replace("–", "-").replace("—", "-")

        # Remove trailing punctuation
        text = text.rstrip(".,;:")

        # Standardize case if not case sensitive
        if not self.case_sensitive:
            # Preserve acronyms and proper nouns
            words = text.split()
            normalized_words = []
            for word in words:
                if word.isupper() and len(word) > 1:
                    # Keep acronyms uppercase
                    normalized_words.append(word)
                elif word[0].isupper():
                    # Keep proper nouns capitalized
                    normalized_words.append(word)
                else:
                    # Lowercase other words
                    normalized_words.append(word.lower())
            text = " ".join(normalized_words)

        return text

    def _generate_reference_id(self) -> str:
        """Generate unique reference ID."""
        self._reference_counter += 1
        return f"ref_{self._reference_counter:06d}"

    def extract_reference_graph(self, references: List[Reference]) -> Dict[str, Any]:
        """Extract a reference graph from parsed references.

        Args:
            references: List of parsed references

        Returns:
            Graph representation of references
        """
        graph = {
            "nodes": {},
            "edges": [],
            "statistics": {
                "total_references": len(references),
                "by_type": {},
                "by_document": {},
            },
        }

        # Build nodes (documents)
        documents = set()
        for ref in references:
            documents.add(ref.source_document)
            if ref.target_document:
                documents.add(ref.target_document)

        for doc in documents:
            graph["nodes"][doc] = {
                "id": doc,
                "type": "document",
                "outgoing_references": 0,
                "incoming_references": 0,
            }

        # Build edges (references)
        for ref in references:
            if ref.target_document and ref.target_document != ref.source_document:
                edge = {
                    "source": ref.source_document,
                    "target": ref.target_document,
                    "reference_type": ref.reference_type.value,
                    "reference_id": ref.reference_id,
                    "metadata": ref.metadata,
                }
                graph["edges"].append(edge)

                # Update node statistics
                graph["nodes"][ref.source_document]["outgoing_references"] += 1
                graph["nodes"][ref.target_document]["incoming_references"] += 1

            # Update statistics
            ref_type = ref.reference_type.value
            graph["statistics"]["by_type"][ref_type] = (
                graph["statistics"]["by_type"].get(ref_type, 0) + 1
            )

            source_doc = ref.source_document
            graph["statistics"]["by_document"][source_doc] = (
                graph["statistics"]["by_document"].get(source_doc, 0) + 1
            )

        return graph

    def find_broken_references(
        self,
        references: List[Reference],
        available_documents: Set[str],
        available_sections: Optional[Dict[str, Set[str]]] = None,
    ) -> List[Reference]:
        """Find references that point to non-existent targets.

        Args:
            references: List of parsed references
            available_documents: Set of available document paths/IDs
            available_sections: Optional mapping of document to available sections

        Returns:
            List of broken references
        """
        broken_references = []

        for ref in references:
            is_broken = False

            # Check document existence
            if ref.target_document and ref.target_document not in available_documents:
                # Check if it's an internal reference to the same document
                if ref.target_document != ref.source_document:
                    is_broken = True

            # Check section existence if provided
            if (
                not is_broken
                and available_sections
                and ref.target_document in available_sections
                and ref.target_section
            ):
                available_secs = available_sections[ref.target_document]
                if ref.target_section not in available_secs:
                    is_broken = True

            if is_broken:
                broken_references.append(ref)

        return broken_references
