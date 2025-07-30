"""Clause cross-referencing system for legal documents.

This module provides functionality to identify, track, and manage cross-references
between clauses, sections, and definitions across legal documents.
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .legal_citations import Citation
from .parser import Reference, ReferenceType

logger = logging.getLogger(__name__)


class ClauseType(Enum):
    """Types of document clauses."""

    DEFINITION = "definition"
    RECITAL = "recital"
    CONDITION = "condition"
    COVENANT = "covenant"
    REPRESENTATION = "representation"
    WARRANTY = "warranty"
    INDEMNITY = "indemnity"
    LIMITATION = "limitation"
    TERMINATION = "termination"
    MISCELLANEOUS = "miscellaneous"
    SCHEDULE = "schedule"
    EXHIBIT = "exhibit"


class ReferenceScope(Enum):
    """Scope of clause references."""

    INTERNAL = "internal"  # Within same document
    EXTERNAL = "external"  # To other documents
    DEFINITION = "definition"  # To defined terms
    CITATION = "citation"  # To legal authorities
    ATTACHMENT = "attachment"  # To exhibits/schedules


@dataclass
class ClauseIdentifier:
    """Unique identifier for a document clause."""

    document_id: str
    section_number: str
    clause_number: Optional[str] = None
    sub_clause: Optional[str] = None

    def to_string(self) -> str:
        """Convert to string representation."""
        parts = [self.document_id, self.section_number]
        if self.clause_number:
            parts.append(self.clause_number)
        if self.sub_clause:
            parts.append(self.sub_clause)
        return "::".join(parts)

    @classmethod
    def from_string(cls, identifier: str) -> "ClauseIdentifier":
        """Create from string representation."""
        parts = identifier.split("::")
        return cls(
            document_id=parts[0],
            section_number=parts[1],
            clause_number=parts[2] if len(parts) > 2 else None,
            sub_clause=parts[3] if len(parts) > 3 else None,
        )


@dataclass
class Clause:
    """Represents a document clause."""

    identifier: ClauseIdentifier
    clause_type: ClauseType
    title: str
    content: str
    position: Tuple[int, int]  # Start and end position in document
    level: int  # Nesting level (1 = top level section)

    # References
    outgoing_refs: List[Reference] = field(default_factory=list)
    incoming_refs: List[ClauseIdentifier] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    defined_terms: Set[str] = field(default_factory=set)
    referenced_terms: Set[str] = field(default_factory=set)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "identifier": self.identifier.to_string(),
            "clause_type": self.clause_type.value,
            "title": self.title,
            "content": (
                self.content[:200] + "..." if len(self.content) > 200 else self.content
            ),
            "position": {"start": self.position[0], "end": self.position[1]},
            "level": self.level,
            "outgoing_refs_count": len(self.outgoing_refs),
            "incoming_refs_count": len(self.incoming_refs),
            "citations_count": len(self.citations),
            "defined_terms": list(self.defined_terms),
            "referenced_terms": list(self.referenced_terms),
            "metadata": self.metadata,
        }


@dataclass
class ClauseReference:
    """Represents a reference between clauses."""

    source_clause: ClauseIdentifier
    target_clause: ClauseIdentifier
    reference_type: ReferenceType
    reference_scope: ReferenceScope
    reference_text: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_clause": self.source_clause.to_string(),
            "target_clause": self.target_clause.to_string(),
            "reference_type": self.reference_type.value,
            "reference_scope": self.reference_scope.value,
            "reference_text": self.reference_text,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class CrossReferenceMap:
    """Map of cross-references between documents."""

    documents: Dict[str, str]  # document_id -> document_path
    clauses: Dict[str, Clause]  # clause_id -> Clause
    references: List[ClauseReference]
    definitions: Dict[str, List[ClauseIdentifier]]  # term -> defining clauses

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "documents": self.documents,
            "total_clauses": len(self.clauses),
            "total_references": len(self.references),
            "total_definitions": len(self.definitions),
            "clauses": {k: v.to_dict() for k, v in self.clauses.items()},
            "references": [ref.to_dict() for ref in self.references],
            "definitions": {
                term: [c.to_string() for c in clauses]
                for term, clauses in self.definitions.items()
            },
        }


class CrossReferencer:
    """Manages cross-references between document clauses."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cross-referencer.

        Args:
            config: Configuration options
        """
        self.config = config or {}

        # Configuration
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.track_definitions = self.config.get("track_definitions", True)
        self.track_citations = self.config.get("track_citations", True)
        self.max_reference_distance = self.config.get("max_reference_distance", 1000)

        # Initialize patterns
        self._initialize_patterns()

    def _initialize_patterns(self):
        """Initialize patterns for clause detection."""
        # Section/clause numbering patterns
        self.section_patterns = {
            "numeric": re.compile(r"^(\d+(?:\.\d+)*)\s*\.?\s*(.*)$", re.MULTILINE),
            "alpha_numeric": re.compile(
                r"^([A-Z]|\d+)\.(\d+(?:\.\d+)*)\s*\.?\s*(.*)$", re.MULTILINE
            ),
            "article": re.compile(
                r"^(?:Article|ARTICLE)\s+([IVX]+|\d+)\s*[:.]?\s*(.*)$",
                re.MULTILINE | re.IGNORECASE,
            ),
            "section_marker": re.compile(
                r"^(?:Section|SECTION|§)\s*(\d+(?:\.\d+)*)\s*[:.]?\s*(.*)$",
                re.MULTILINE | re.IGNORECASE,
            ),
        }

        # Clause type indicators
        self.clause_type_patterns = {
            ClauseType.DEFINITION: re.compile(
                r"(?:definitions?|defined\s+terms?|meaning\s+of\s+terms?)",
                re.IGNORECASE,
            ),
            ClauseType.RECITAL: re.compile(
                r"(?:whereas|recitals?|background|preamble)", re.IGNORECASE
            ),
            ClauseType.CONDITION: re.compile(
                r"(?:conditions?\s+(?:precedent|subsequent)|subject\s+to)",
                re.IGNORECASE,
            ),
            ClauseType.COVENANT: re.compile(
                r"(?:covenants?|agrees?\s+to|undertakes?\s+to)", re.IGNORECASE
            ),
            ClauseType.REPRESENTATION: re.compile(
                r"(?:represents?\s+(?:and\s+warrants?)?|representations?)",
                re.IGNORECASE,
            ),
            ClauseType.WARRANTY: re.compile(
                r"(?:warrants?|warranties|guarantees?)", re.IGNORECASE
            ),
            ClauseType.INDEMNITY: re.compile(
                r"(?:indemnif(?:y|ies|ication)|hold\s+harmless)", re.IGNORECASE
            ),
            ClauseType.LIMITATION: re.compile(
                r"(?:limitation\s+of\s+liability|exclusion|cap\s+on)", re.IGNORECASE
            ),
            ClauseType.TERMINATION: re.compile(
                r"(?:termination|expir(?:y|ation)|end\s+date)", re.IGNORECASE
            ),
            ClauseType.MISCELLANEOUS: re.compile(
                r"(?:miscellaneous|general\s+provisions?|boilerplate)", re.IGNORECASE
            ),
        }

        # Cross-reference patterns
        self.xref_patterns = {
            "subject_to": re.compile(
                r"subject\s+to\s+(?:the\s+(?:terms|provisions)\s+of\s+)?"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
            "as_provided_in": re.compile(
                r"as\s+(?:provided|set\s+forth|described)\s+in\s+"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
            "in_accordance_with": re.compile(
                r"in\s+accordance\s+with\s+"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
            "pursuant_to": re.compile(
                r"pursuant\s+to\s+"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
            "referenced_in": re.compile(
                r"(?:referenced|mentioned|described)\s+in\s+"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
            "see_section": re.compile(
                r"(?:see|refer\s+to)\s+"
                r"(?:Section|Clause|Article|Paragraph)\s+(\d+(?:\.\d+)*)",
                re.IGNORECASE,
            ),
        }

    def build_cross_reference_map(
        self,
        documents: Dict[str, str],
        parsed_references: Dict[str, List[Reference]],
        parsed_citations: Optional[Dict[str, List[Citation]]] = None,
    ) -> CrossReferenceMap:
        """Build comprehensive cross-reference map from documents.

        Args:
            documents: Mapping of document_id to document content
            parsed_references: Pre-parsed references by document
            parsed_citations: Optional pre-parsed citations by document

        Returns:
            Cross-reference map
        """
        xref_map = CrossReferenceMap(
            documents={doc_id: doc_id for doc_id in documents.keys()},
            clauses={},
            references=[],
            definitions={},
        )

        # Parse clauses from each document
        for doc_id, content in documents.items():
            clauses = self._extract_clauses(doc_id, content)

            # Add references to clauses
            if doc_id in parsed_references:
                self._assign_references_to_clauses(clauses, parsed_references[doc_id])

            # Add citations to clauses
            if parsed_citations and doc_id in parsed_citations:
                self._assign_citations_to_clauses(clauses, parsed_citations[doc_id])

            # Store clauses
            for clause in clauses:
                clause_id = clause.identifier.to_string()
                xref_map.clauses[clause_id] = clause

                # Track definitions
                if self.track_definitions:
                    for term in clause.defined_terms:
                        if term not in xref_map.definitions:
                            xref_map.definitions[term] = []
                        xref_map.definitions[term].append(clause.identifier)

        # Build cross-references between clauses
        clause_refs = self._build_clause_references(
            xref_map.clauses, xref_map.definitions
        )
        xref_map.references = clause_refs

        # Update incoming references
        for ref in clause_refs:
            target_id = ref.target_clause.to_string()
            if target_id in xref_map.clauses:
                xref_map.clauses[target_id].incoming_refs.append(ref.source_clause)

        logger.info(
            f"Built cross-reference map: {len(xref_map.clauses)} clauses, "
            f"{len(xref_map.references)} references"
        )

        return xref_map

    def _extract_clauses(self, document_id: str, content: str) -> List[Clause]:
        """Extract clauses from document content."""
        clauses = []
        lines = content.split("\n")

        current_section = None
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            # Check for section markers
            section_match = None
            section_type = None

            for pattern_type, pattern in self.section_patterns.items():
                match = pattern.match(line.strip())
                if match:
                    section_match = match
                    section_type = pattern_type
                    break

            if section_match:
                # Save previous section if exists
                if current_section:
                    clause = self._create_clause(
                        document_id,
                        current_section,
                        "\n".join(current_content),
                        current_start,
                        i - 1,
                    )
                    if clause:
                        clauses.append(clause)

                # Start new section
                current_section = section_match
                current_content = [line]
                current_start = i
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            clause = self._create_clause(
                document_id,
                current_section,
                "\n".join(current_content),
                current_start,
                len(lines) - 1,
            )
            if clause:
                clauses.append(clause)

        return clauses

    def _create_clause(
        self,
        document_id: str,
        section_match: re.Match,
        content: str,
        start_line: int,
        end_line: int,
    ) -> Optional[Clause]:
        """Create clause from section match and content."""
        # Extract section number and title
        if section_match.lastindex >= 2:
            section_num = section_match.group(1)
            title = section_match.group(2).strip() if section_match.group(2) else ""
        else:
            section_num = section_match.group(1)
            title = ""

        # Determine clause type
        clause_type = self._determine_clause_type(title, content)

        # Extract sub-clauses if present
        clause_num = None
        sub_clause = None
        if "." in section_num:
            parts = section_num.split(".")
            if len(parts) > 2:
                section_num = ".".join(parts[:2])
                clause_num = parts[2]
                if len(parts) > 3:
                    sub_clause = ".".join(parts[3:])

        # Create clause identifier
        identifier = ClauseIdentifier(
            document_id=document_id,
            section_number=section_num,
            clause_number=clause_num,
            sub_clause=sub_clause,
        )

        # Calculate nesting level
        level = section_num.count(".") + 1

        # Extract defined terms if definition clause
        defined_terms = set()
        referenced_terms = set()

        if clause_type == ClauseType.DEFINITION:
            defined_terms = self._extract_defined_terms(content)

        # Extract referenced terms
        referenced_terms = self._extract_referenced_terms(content)

        return Clause(
            identifier=identifier,
            clause_type=clause_type,
            title=title,
            content=content,
            position=(start_line, end_line),
            level=level,
            defined_terms=defined_terms,
            referenced_terms=referenced_terms,
        )

    def _determine_clause_type(self, title: str, content: str) -> ClauseType:
        """Determine the type of clause based on title and content."""
        combined_text = (
            f"{title} {content[:500]}"  # Check title and beginning of content
        )

        for clause_type, pattern in self.clause_type_patterns.items():
            if pattern.search(combined_text):
                return clause_type

        # Check for schedule/exhibit
        if re.search(
            r"(?:schedule|exhibit|appendix|attachment)", combined_text, re.IGNORECASE
        ):
            return (
                ClauseType.SCHEDULE
                if "schedule" in combined_text.lower()
                else ClauseType.EXHIBIT
            )

        return ClauseType.MISCELLANEOUS

    def _extract_defined_terms(self, content: str) -> Set[str]:
        """Extract defined terms from definition clause."""
        defined_terms = set()

        # Pattern for quoted defined terms
        term_pattern = re.compile(
            r'"([A-Z][A-Za-z0-9\s]+?)"'
            r"(?:\s+(?:means|shall\s+mean|has\s+the\s+meaning|is\s+defined\s+as))",
            re.MULTILINE,
        )

        for match in term_pattern.finditer(content):
            term = match.group(1).strip()
            defined_terms.add(term)

        # Pattern for defined terms in bold or with special formatting
        # "**Term**" means...
        bold_pattern = re.compile(
            r"\*\*([A-Z][A-Za-z0-9\s]+?)\*\*"
            r"(?:\s+(?:means|shall\s+mean|has\s+the\s+meaning))",
            re.MULTILINE,
        )

        for match in bold_pattern.finditer(content):
            term = match.group(1).strip()
            defined_terms.add(term)

        return defined_terms

    def _extract_referenced_terms(self, content: str) -> Set[str]:
        """Extract referenced defined terms from content."""
        referenced_terms = set()

        # Pattern for quoted terms (likely references to defined terms)
        term_pattern = re.compile(r'"([A-Z][A-Za-z0-9\s]+?)"', re.MULTILINE)

        for match in term_pattern.finditer(content):
            term = match.group(1).strip()
            # Exclude common phrases that aren't likely defined terms
            if len(term.split()) <= 4 and not any(
                word in term.lower()
                for word in ["the", "and", "or", "o", "to", "in", "for"]
            ):
                referenced_terms.add(term)

        return referenced_terms

    def _assign_references_to_clauses(
        self, clauses: List[Clause], references: List[Reference]
    ):
        """Assign references to their containing clauses."""
        # Sort clauses by position for efficient lookup
        sorted_clauses = sorted(clauses, key=lambda c: c.position[0])

        for ref in references:
            # Find containing clause using binary search
            containing_clause = None

            for clause in sorted_clauses:
                # Approximate position based on line numbers
                ref_line = ref.location.line_number
                if clause.position[0] <= ref_line <= clause.position[1]:
                    containing_clause = clause
                    break

            if containing_clause:
                containing_clause.outgoing_refs.append(ref)

    def _assign_citations_to_clauses(
        self, clauses: List[Clause], citations: List[Citation]
    ):
        """Assign citations to their containing clauses."""
        # Create position map for clauses
        position_map = []
        for clause in clauses:
            # Approximate character positions from line numbers
            start_pos = clause.position[0] * 100  # Rough estimate
            end_pos = clause.position[1] * 100
            position_map.append((start_pos, end_pos, clause))

        for citation in citations:
            if citation.position:
                cite_pos = citation.position[0]

                # Find containing clause
                for start_pos, end_pos, clause in position_map:
                    if start_pos <= cite_pos <= end_pos:
                        clause.citations.append(citation)
                        break

    def _build_clause_references(
        self, clauses: Dict[str, Clause], definitions: Dict[str, List[ClauseIdentifier]]
    ) -> List[ClauseReference]:
        """Build references between clauses."""
        references = []

        for clause_id, clause in clauses.items():
            # Check outgoing references
            for ref in clause.outgoing_refs:
                if ref.reference_type in [ReferenceType.SECTION, ReferenceType.CLAUSE]:
                    # Try to resolve target clause
                    target_clause = self._resolve_clause_reference(
                        ref, clause.identifier, clauses
                    )

                    if target_clause:
                        clause_ref = ClauseReference(
                            source_clause=clause.identifier,
                            target_clause=target_clause,
                            reference_type=ref.reference_type,
                            reference_scope=self._determine_reference_scope(
                                clause.identifier, target_clause
                            ),
                            reference_text=ref.raw_text,
                            confidence=ref.confidence,
                        )
                        references.append(clause_ref)

            # Check for cross-references in content
            for pattern_name, pattern in self.xref_patterns.items():
                for match in pattern.finditer(clause.content):
                    target_section = match.group(1)

                    # Try to find target clause
                    target_clause = self._find_clause_by_section(
                        target_section, clause.identifier.document_id, clauses
                    )

                    if target_clause:
                        clause_ref = ClauseReference(
                            source_clause=clause.identifier,
                            target_clause=target_clause,
                            reference_type=ReferenceType.SECTION,
                            reference_scope=ReferenceScope.INTERNAL,
                            reference_text=match.group(0),
                            confidence=0.9,
                            metadata={"pattern": pattern_name},
                        )
                        references.append(clause_ref)

            # Check for definition references
            if self.track_definitions:
                for term in clause.referenced_terms:
                    if term in definitions:
                        for defining_clause in definitions[term]:
                            clause_ref = ClauseReference(
                                source_clause=clause.identifier,
                                target_clause=defining_clause,
                                reference_type=ReferenceType.DEFINITION,
                                reference_scope=self._determine_reference_scope(
                                    clause.identifier, defining_clause
                                ),
                                reference_text=f'"{term}"',
                                confidence=0.85,
                                metadata={"term": term},
                            )
                            references.append(clause_ref)

        return references

    def _resolve_clause_reference(
        self,
        ref: Reference,
        source_clause: ClauseIdentifier,
        clauses: Dict[str, Clause],
    ) -> Optional[ClauseIdentifier]:
        """Resolve a reference to a specific clause."""
        # If reference includes document, use that
        if ref.target_document and ref.target_document != source_clause.document_id:
            target_doc = ref.target_document
        else:
            target_doc = source_clause.document_id

        # Build potential target identifiers
        if ref.target_element:
            # Parse section number from target element
            section_match = re.match(r"(\d+(?:\.\d+)*)", ref.target_element)
            if section_match:
                section_num = section_match.group(1)

                # Try exact match first
                target_id = ClauseIdentifier(
                    document_id=target_doc, section_number=section_num
                )

                if target_id.to_string() in clauses:
                    return target_id

                # Try with variations
                parts = section_num.split(".")
                for i in range(len(parts), 0, -1):
                    partial_section = ".".join(parts[:i])
                    target_id = ClauseIdentifier(
                        document_id=target_doc, section_number=partial_section
                    )
                    if target_id.to_string() in clauses:
                        return target_id

        return None

    def _find_clause_by_section(
        self, section_number: str, document_id: str, clauses: Dict[str, Clause]
    ) -> Optional[ClauseIdentifier]:
        """Find clause by section number."""
        # Try exact match
        target_id = ClauseIdentifier(
            document_id=document_id, section_number=section_number
        )

        if target_id.to_string() in clauses:
            return target_id

        # Try parent sections
        if "." in section_number:
            parts = section_number.split(".")
            for i in range(len(parts) - 1, 0, -1):
                parent_section = ".".join(parts[:i])
                target_id = ClauseIdentifier(
                    document_id=document_id, section_number=parent_section
                )
                if target_id.to_string() in clauses:
                    return target_id

        return None

    def _determine_reference_scope(
        self, source: ClauseIdentifier, target: ClauseIdentifier
    ) -> ReferenceScope:
        """Determine the scope of a reference."""
        if source.document_id == target.document_id:
            return ReferenceScope.INTERNAL
        else:
            return ReferenceScope.EXTERNAL

    def find_orphaned_clauses(
        self, xref_map: CrossReferenceMap
    ) -> List[ClauseIdentifier]:
        """Find clauses with no incoming or outgoing references.

        Args:
            xref_map: Cross-reference map

        Returns:
            List of orphaned clause identifiers
        """
        orphaned = []

        for clause_id, clause in xref_map.clauses.items():
            # Skip definition clauses (they may not have explicit references)
            if clause.clause_type == ClauseType.DEFINITION:
                continue

            # Skip top-level sections
            if clause.level == 1:
                continue

            # Check if clause has references
            has_outgoing = len(clause.outgoing_refs) > 0
            has_incoming = len(clause.incoming_refs) > 0

            if not has_outgoing and not has_incoming:
                orphaned.append(clause.identifier)

        return orphaned

    def find_circular_references(
        self, xref_map: CrossReferenceMap
    ) -> List[List[ClauseIdentifier]]:
        """Find circular reference chains.

        Args:
            xref_map: Cross-reference map

        Returns:
            List of circular reference chains
        """
        # Build adjacency list
        graph = defaultdict(list)
        for ref in xref_map.references:
            source = ref.source_clause.to_string()
            target = ref.target_clause.to_string()
            graph[source].append(target)

        # Find cycles using DFS
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycle_identifiers = [
                        ClauseIdentifier.from_string(node_id) for node_id in cycle
                    ]
                    cycles.append(cycle_identifiers)

            path.pop()
            rec_stack.remove(node)

        # Check all nodes
        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    def analyze_reference_patterns(self, xref_map: CrossReferenceMap) -> Dict[str, Any]:
        """Analyze patterns in cross-references.

        Args:
            xref_map: Cross-reference map

        Returns:
            Analysis results
        """
        analysis = {
            "total_clauses": len(xref_map.clauses),
            "total_references": len(xref_map.references),
            "reference_density": len(xref_map.references)
            / max(len(xref_map.clauses), 1),
            "by_type": defaultdict(int),
            "by_scope": defaultdict(int),
            "most_referenced": [],
            "most_referencing": [],
            "definition_usage": {},
            "clause_connectivity": {},
        }

        # Count by type and scope
        for ref in xref_map.references:
            analysis["by_type"][ref.reference_type.value] += 1
            analysis["by_scope"][ref.reference_scope.value] += 1

        # Find most referenced and referencing clauses
        reference_counts = defaultdict(int)
        referencing_counts = defaultdict(int)

        for ref in xref_map.references:
            reference_counts[ref.target_clause.to_string()] += 1
            referencing_counts[ref.source_clause.to_string()] += 1

        # Top 10 most referenced
        most_referenced = sorted(
            reference_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        analysis["most_referenced"] = [
            {
                "clause": clause_id,
                "count": count,
                "title": (
                    xref_map.clauses[clause_id].title
                    if clause_id in xref_map.clauses
                    else "Unknown"
                ),
            }
            for clause_id, count in most_referenced
        ]

        # Top 10 most referencing
        most_referencing = sorted(
            referencing_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        analysis["most_referencing"] = [
            {
                "clause": clause_id,
                "count": count,
                "title": (
                    xref_map.clauses[clause_id].title
                    if clause_id in xref_map.clauses
                    else "Unknown"
                ),
            }
            for clause_id, count in most_referencing
        ]

        # Analyze definition usage
        for term, defining_clauses in xref_map.definitions.items():
            usage_count = sum(
                1
                for ref in xref_map.references
                if ref.reference_type == ReferenceType.DEFINITION
                and ref.metadata.get("term") == term
            )

            analysis["definition_usage"][term] = {
                "defined_in": [c.to_string() for c in defining_clauses],
                "usage_count": usage_count,
            }

        # Calculate clause connectivity (incoming + outgoing refs)
        for clause_id, clause in xref_map.clauses.items():
            connectivity = len(clause.outgoing_refs) + len(clause.incoming_refs)
            analysis["clause_connectivity"][clause_id] = connectivity

        return dict(analysis)
