"""Reference scanner for document impact analysis."""

import difflib
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .uri_system import DocumentReference, DocumentURI, URISystem

logger = logging.getLogger(__name__)


@dataclass
class ChangeImpact:
    """Represents the impact of a change on references."""

    change_type: str  # content, structure, deletion, renaming
    severity: str  # high, medium, low
    description: str
    affected_references: List[DocumentReference]
    suggested_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["affected_references"] = [r.to_dict() for r in self.affected_references]
        return data


@dataclass
class DocumentChange:
    """Represents a change in a document."""

    document_path: str
    change_type: str  # modified, deleted, renamed
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    old_path: Optional[str] = None  # For renames
    new_path: Optional[str] = None  # For renames
    sections_affected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class ImpactAnalysisReport:
    """Report of impact analysis results."""

    timestamp: datetime
    source_document: str
    changes_detected: List[DocumentChange]
    impacts: List[ChangeImpact]
    affected_documents: Set[str]
    total_references_affected: int
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["changes_detected"] = [c.to_dict() for c in self.changes_detected]
        data["impacts"] = [i.to_dict() for i in self.impacts]
        data["affected_documents"] = list(self.affected_documents)
        return data


class ReferenceScanner:
    """Scans documents for references and analyzes change impact."""

    # Patterns for structural elements
    SECTION_PATTERN = re.compile(r"^#+\s+(.+)$|^(\d+\.)+\s+(.+)$", re.MULTILINE)
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, uri_system: Optional[URISystem] = None):
        """Initialize reference scanner.

        Args:
            uri_system: Optional URISystem instance
        """
        self.uri_system = uri_system or URISystem()
        self.document_cache = {}

    def scan_repository(self, repo_path: Path) -> Dict[str, List[DocumentReference]]:
        """Scan entire repository for references.

        Args:
            repo_path: Path to repository

        Returns:
            Dictionary mapping documents to their references
        """
        all_references = {}

        # Find all markdown files
        for md_file in repo_path.rglob("*.md"):
            if ".git" in str(md_file):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                doc_path = str(md_file.relative_to(repo_path))

                # Scan for references
                refs = self.uri_system.scan_document_for_references(doc_path, content)

                if refs:
                    all_references[doc_path] = refs
                    logger.info(f"Found {len(refs)} references in {doc_path}")

                # Cache document content
                self.document_cache[doc_path] = content

            except Exception as e:
                logger.error(f"Failed to scan {md_file}: {e}")

        return all_references

    def analyze_change_impact(
        self, document_path: str, old_content: str, new_content: str
    ) -> ImpactAnalysisReport:
        """Analyze the impact of changes to a document.

        Args:
            document_path: Path to document
            old_content: Previous content
            new_content: New content

        Returns:
            ImpactAnalysisReport
        """
        logger.info(f"Analyzing change impact for {document_path}")

        # Detect changes
        changes = self._detect_changes(document_path, old_content, new_content)

        # Analyze impacts
        impacts = []
        affected_docs = set()
        total_refs_affected = 0

        for change in changes:
            change_impacts = self._analyze_single_change(change)
            impacts.extend(change_impacts)

            for impact in change_impacts:
                for ref in impact.affected_references:
                    affected_docs.add(ref.source_document)
                    total_refs_affected += 1

        # Generate recommendations
        recommendations = self._generate_recommendations(impacts)

        # Create report
        report = ImpactAnalysisReport(
            timestamp=datetime.now(),
            source_document=document_path,
            changes_detected=changes,
            impacts=impacts,
            affected_documents=affected_docs,
            total_references_affected=total_refs_affected,
            recommendations=recommendations,
        )

        return report

    def find_broken_references(
        self, repo_path: Path
    ) -> Dict[str, List[Tuple[DocumentReference, str]]]:
        """Find all broken references in repository.

        Args:
            repo_path: Path to repository

        Returns:
            Dictionary mapping documents to broken references
        """
        broken_refs = {}

        # Scan repository first
        all_refs = self.scan_repository(repo_path)

        # Validate each document's references
        for doc_path, refs in all_refs.items():
            invalid_refs = self.uri_system.validate_references(doc_path)

            if invalid_refs:
                broken_refs[doc_path] = invalid_refs
                logger.warning(
                    f"Found {len(invalid_refs)} broken references in {doc_path}"
                )

        return broken_refs

    def build_dependency_graph(self, repo_path: Path) -> Dict[str, Any]:
        """Build complete dependency graph for repository.

        Args:
            repo_path: Path to repository

        Returns:
            Dependency graph data
        """
        # Scan repository
        all_refs = self.scan_repository(repo_path)

        # Build graph
        nodes = []
        edges = []

        # Create nodes for all documents
        all_docs = set()
        for doc_path in all_refs.keys():
            all_docs.add(doc_path)

        for refs in all_refs.values():
            for ref in refs:
                target = self._get_target_from_uri(ref.target_uri)
                if target:
                    all_docs.add(target)

        # Create node data
        for doc in all_docs:
            nodes.append(
                {
                    "id": doc,
                    "label": Path(doc).name,
                    "type": "template" if "template" in doc else "document",
                }
            )

        # Create edges
        edge_set = set()  # To avoid duplicates
        for doc_path, refs in all_refs.items():
            for ref in refs:
                target = self._get_target_from_uri(ref.target_uri)
                if target and target != doc_path:
                    edge_key = (doc_path, target)
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append(
                            {
                                "source": doc_path,
                                "target": target,
                                "type": ref.reference_type,
                            }
                        )

        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": {
                "total_documents": len(nodes),
                "total_references": sum(len(refs) for refs in all_refs.values()),
                "total_connections": len(edges),
            },
        }

    def _detect_changes(
        self, document_path: str, old_content: str, new_content: str
    ) -> List[DocumentChange]:
        """Detect changes between document versions."""
        changes = []

        # Check if document was deleted
        if old_content and not new_content:
            changes.append(
                DocumentChange(
                    document_path=document_path,
                    change_type="deleted",
                    old_content=old_content,
                )
            )
            return changes

        # Extract sections from both versions
        old_sections = self._extract_sections(old_content)
        new_sections = self._extract_sections(new_content)

        # Find changed sections
        old_section_set = set(old_sections.keys())
        new_section_set = set(new_sections.keys())

        deleted_sections = old_section_set - new_section_set
        added_sections = new_section_set - old_section_set
        common_sections = old_section_set & new_section_set

        sections_affected = []

        # Check for modifications in common sections
        for section in common_sections:
            if old_sections[section] != new_sections[section]:
                sections_affected.append(section)

        # Add deleted and added sections
        sections_affected.extend(deleted_sections)
        sections_affected.extend(added_sections)

        if sections_affected:
            changes.append(
                DocumentChange(
                    document_path=document_path,
                    change_type="modified",
                    old_content=old_content,
                    new_content=new_content,
                    sections_affected=list(sections_affected),
                )
            )

        return changes

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from document content."""
        sections = {}

        # Split by headings
        lines = content.split("\n")
        current_section = "preamble"
        section_content = []

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(line)

            if heading_match:
                # Save previous section
                if section_content:
                    sections[current_section] = "\n".join(section_content).strip()

                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_section = f"h{level}:{title}"
                section_content = [line]
            else:
                section_content.append(line)

        # Save last section
        if section_content:
            sections[current_section] = "\n".join(section_content).strip()

        return sections

    def _analyze_single_change(self, change: DocumentChange) -> List[ChangeImpact]:
        """Analyze impact of a single change."""
        impacts = []

        if change.change_type == "deleted":
            # Document deletion affects all incoming references
            dependents = self.uri_system.get_document_dependents(change.document_path)

            affected_refs = []
            for refs in dependents.values():
                affected_refs.extend(refs)

            if affected_refs:
                impacts.append(
                    ChangeImpact(
                        change_type="deletion",
                        severity="high",
                        description=f"Document {change.document_path} was deleted",
                        affected_references=affected_refs,
                        suggested_action="Update or remove references to deleted document",
                    )
                )

        elif change.change_type == "modified":
            # Check if structural changes affect references
            if change.sections_affected:
                # Get all references to this document
                dependents = self.uri_system.get_document_dependents(
                    change.document_path
                )

                for source_doc, refs in dependents.items():
                    for ref in refs:
                        # Check if reference points to affected section
                        if self._reference_affected_by_sections(
                            ref, change.sections_affected
                        ):
                            impacts.append(
                                ChangeImpact(
                                    change_type="structure",
                                    severity="medium",
                                    description=f"Section referenced by {source_doc} was modified",
                                    affected_references=[ref],
                                    suggested_action="Verify reference still points to correct content",
                                )
                            )

        return impacts

    def _reference_affected_by_sections(
        self, ref: DocumentReference, affected_sections: List[str]
    ) -> bool:
        """Check if reference is affected by section changes."""
        # Check if reference targets a specific section
        if ref.target_uri.section:
            section_id = ref.target_uri.section

            # Check against affected sections
            for section in affected_sections:
                if section_id in section or section in section_id:
                    return True

        # For non-specific references, assume they might be affected
        return len(affected_sections) > 0

    def _generate_recommendations(self, impacts: List[ChangeImpact]) -> List[str]:
        """Generate recommendations based on impacts."""
        recommendations = []

        # Count by severity
        high_severity = sum(1 for i in impacts if i.severity == "high")
        medium_severity = sum(1 for i in impacts if i.severity == "medium")

        if high_severity > 0:
            recommendations.append(
                f"URGENT: {high_severity} high-severity impacts detected. "
                "Immediate action required to fix broken references."
            )

        if medium_severity > 0:
            recommendations.append(
                f"Review {medium_severity} medium-severity impacts. "
                "Verify that references still point to intended content."
            )

        # Group by change type
        deletions = [i for i in impacts if i.change_type == "deletion"]
        structural = [i for i in impacts if i.change_type == "structure"]

        if deletions:
            recommendations.append(
                f"Update {len(deletions)} references to deleted content. "
                "Consider redirecting to alternative documents."
            )

        if structural:
            recommendations.append(
                f"Verify {len(structural)} references affected by structural changes. "
                "Update section numbers if necessary."
            )

        # Add general recommendations
        if impacts:
            recommendations.append(
                "Run reference validation across all affected documents."
            )
            recommendations.append(
                "Consider adding reference tests to prevent future breakage."
            )

        return recommendations

    def _get_target_from_uri(self, uri: DocumentURI) -> Optional[str]:
        """Extract target document path from URI."""
        if uri.is_internal_reference():
            return None  # Internal references don't point to other documents

        if uri.repository and uri.document:
            return f"{uri.repository}/{uri.document}"

        return None
