"""Reference integrity validation system.

This module provides comprehensive validation of cross-document references,
legal citations, and clause dependencies to ensure document integrity
and accuracy.
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .cross_referencer import ClauseIdentifier, ClauseReference, CrossReferenceMap
from .legal_citations import Citation, CitationType
from .parser import Reference, ReferenceType

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationCategory(Enum):
    """Categories of validation issues."""

    BROKEN_REFERENCE = "broken_reference"
    CIRCULAR_REFERENCE = "circular_reference"
    ORPHANED_CLAUSE = "orphaned_clause"
    INCONSISTENT_NUMBERING = "inconsistent_numbering"
    MISSING_DEFINITION = "missing_definition"
    UNUSED_DEFINITION = "unused_definition"
    OUTDATED_CITATION = "outdated_citation"
    INVALID_CITATION = "invalid_citation"
    DUPLICATE_REFERENCE = "duplicate_reference"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    INCONSISTENT_FORMATTING = "inconsistent_formatting"
    MISSING_CROSS_REFERENCE = "missing_cross_reference"


@dataclass
class ValidationIssue:
    """Represents a validation issue."""

    issue_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    description: str

    # Location information
    source_document: Optional[str] = None
    source_clause: Optional[ClauseIdentifier] = None
    source_position: Optional[Tuple[int, int]] = None

    # Target information (for references)
    target_document: Optional[str] = None
    target_clause: Optional[ClauseIdentifier] = None

    # Related objects
    reference: Optional[Reference] = None
    citation: Optional[Citation] = None
    clause_reference: Optional[ClauseReference] = None

    # Suggested fixes
    suggested_fixes: List[str] = field(default_factory=list)
    auto_fixable: bool = False

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = {
            "issue_id": self.issue_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "description": self.description,
            "source_document": self.source_document,
            "target_document": self.target_document,
            "suggested_fixes": self.suggested_fixes,
            "auto_fixable": self.auto_fixable,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.source_clause:
            data["source_clause"] = self.source_clause.to_string()
        if self.target_clause:
            data["target_clause"] = self.target_clause.to_string()
        if self.source_position:
            data["source_position"] = {
                "start": self.source_position[0],
                "end": self.source_position[1],
            }

        return data


@dataclass
class ValidationResult:
    """Results of validation process."""

    document_id: str
    validation_timestamp: datetime
    total_issues: int
    issues_by_severity: Dict[ValidationSeverity, int]
    issues_by_category: Dict[ValidationCategory, int]
    issues: List[ValidationIssue]

    # Summary statistics
    total_references: int = 0
    valid_references: int = 0
    total_citations: int = 0
    valid_citations: int = 0
    total_clauses: int = 0

    # Validation metadata
    validation_rules_applied: List[str] = field(default_factory=list)
    validation_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "document_id": self.document_id,
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "total_issues": self.total_issues,
            "issues_by_severity": {
                sev.value: count for sev, count in self.issues_by_severity.items()
            },
            "issues_by_category": {
                cat.value: count for cat, count in self.issues_by_category.items()
            },
            "total_references": self.total_references,
            "valid_references": self.valid_references,
            "total_citations": self.total_citations,
            "valid_citations": self.valid_citations,
            "total_clauses": self.total_clauses,
            "validation_rules_applied": self.validation_rules_applied,
            "validation_duration": self.validation_duration,
            "issues": [
                issue.to_dict() for issue in self.issues[:100]
            ],  # Limit for serialization
        }


class ReferenceValidator:
    """Validates reference integrity across legal documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize reference validator.

        Args:
            config: Configuration options
        """
        self.config = config or {}

        # Configuration
        self.strict_mode = self.config.get("strict_mode", False)
        self.check_outdated_citations = self.config.get(
            "check_outdated_citations", True
        )
        self.min_citation_year = self.config.get("min_citation_year", 1950)
        self.max_citation_age_years = self.config.get("max_citation_age_years", 50)
        self.check_circular_references = self.config.get(
            "check_circular_references", True
        )
        self.check_orphaned_clauses = self.config.get("check_orphaned_clauses", True)

        # Issue counter
        self._issue_counter = 0

        # Validation rules
        self._initialize_validation_rules()

    def _initialize_validation_rules(self):
        """Initialize validation rules."""
        self.validation_rules = {
            "broken_references": self._validate_broken_references,
            "circular_references": self._validate_circular_references,
            "orphaned_clauses": self._validate_orphaned_clauses,
            "missing_definitions": self._validate_missing_definitions,
            "unused_definitions": self._validate_unused_definitions,
            "citation_validity": self._validate_citation_validity,
            "numbering_consistency": self._validate_numbering_consistency,
            "duplicate_references": self._validate_duplicate_references,
            "ambiguous_references": self._validate_ambiguous_references,
            "formatting_consistency": self._validate_formatting_consistency,
        }

    def validate_cross_references(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> ValidationResult:
        """Validate cross-references in the reference map.

        Args:
            xref_map: Cross-reference map to validate
            document_contents: Optional document contents for additional validation

        Returns:
            Validation results
        """
        start_time = datetime.now()
        issues = []
        rules_applied = []

        # Apply validation rules
        for rule_name, rule_func in self.validation_rules.items():
            try:
                rule_issues = rule_func(xref_map, document_contents)
                issues.extend(rule_issues)
                rules_applied.append(rule_name)
            except Exception as e:
                logger.error(f"Error applying validation rule {rule_name}: {e}")
                # Create issue for validation failure
                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.BROKEN_REFERENCE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Validation rule {rule_name} failed",
                    description=f"Error applying validation rule: {e}",
                    metadata={"rule_name": rule_name, "error": str(e)},
                )
                issues.append(issue)

        # Calculate statistics
        issues_by_severity = defaultdict(int)
        issues_by_category = defaultdict(int)

        for issue in issues:
            issues_by_severity[issue.severity] += 1
            issues_by_category[issue.category] += 1

        # Calculate reference statistics
        total_references = len(xref_map.references)
        broken_refs = sum(
            1
            for issue in issues
            if issue.category == ValidationCategory.BROKEN_REFERENCE
        )
        valid_references = total_references - broken_refs

        # Calculate citation statistics
        total_citations = sum(
            len(clause.citations) for clause in xref_map.clauses.values()
        )
        invalid_citations = sum(
            1
            for issue in issues
            if issue.category
            in [
                ValidationCategory.INVALID_CITATION,
                ValidationCategory.OUTDATED_CITATION,
            ]
        )
        valid_citations = total_citations - invalid_citations

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result = ValidationResult(
            document_id="cross_reference_map",
            validation_timestamp=end_time,
            total_issues=len(issues),
            issues_by_severity=dict(issues_by_severity),
            issues_by_category=dict(issues_by_category),
            issues=issues,
            total_references=total_references,
            valid_references=valid_references,
            total_citations=total_citations,
            valid_citations=valid_citations,
            total_clauses=len(xref_map.clauses),
            validation_rules_applied=rules_applied,
            validation_duration=duration,
        )

        logger.info(
            f"Validation completed: {len(issues)} issues found in {duration:.2f}s"
        )

        return result

    def validate_document_references(
        self,
        document_id: str,
        references: List[Reference],
        citations: List[Citation],
        available_documents: Set[str],
        available_sections: Optional[Dict[str, Set[str]]] = None,
    ) -> ValidationResult:
        """Validate references within a single document.

        Args:
            document_id: ID of document being validated
            references: List of references in the document
            citations: List of citations in the document
            available_documents: Set of available document identifiers
            available_sections: Optional mapping of documents to available sections

        Returns:
            Validation results
        """
        start_time = datetime.now()
        issues = []

        # Validate references
        for ref in references:
            ref_issues = self._validate_single_reference(
                ref, document_id, available_documents, available_sections
            )
            issues.extend(ref_issues)

        # Validate citations
        for citation in citations:
            cite_issues = self._validate_single_citation(citation, document_id)
            issues.extend(cite_issues)

        # Calculate statistics
        issues_by_severity = defaultdict(int)
        issues_by_category = defaultdict(int)

        for issue in issues:
            issues_by_severity[issue.severity] += 1
            issues_by_category[issue.category] += 1

        broken_refs = sum(
            1
            for issue in issues
            if issue.category == ValidationCategory.BROKEN_REFERENCE
        )
        valid_references = len(references) - broken_refs

        invalid_citations = sum(
            1
            for issue in issues
            if issue.category
            in [
                ValidationCategory.INVALID_CITATION,
                ValidationCategory.OUTDATED_CITATION,
            ]
        )
        valid_citations = len(citations) - invalid_citations

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result = ValidationResult(
            document_id=document_id,
            validation_timestamp=end_time,
            total_issues=len(issues),
            issues_by_severity=dict(issues_by_severity),
            issues_by_category=dict(issues_by_category),
            issues=issues,
            total_references=len(references),
            valid_references=valid_references,
            total_citations=len(citations),
            valid_citations=valid_citations,
            validation_rules_applied=["reference_validity", "citation_validity"],
            validation_duration=duration,
        )

        return result

    def _validate_broken_references(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Validate that all references point to existing targets."""
        issues = []

        for ref in xref_map.references:
            target_exists = ref.target_clause.to_string() in xref_map.clauses

            if not target_exists:
                # Check if target document exists
                if ref.target_clause.document_id not in xref_map.documents:
                    severity = ValidationSeverity.ERROR
                    message = f"Reference to non-existent document: {ref.target_clause.document_id}"
                    fixes = [
                        f"Create document {ref.target_clause.document_id}",
                        "Update reference to correct document",
                    ]
                else:
                    severity = ValidationSeverity.WARNING
                    message = f"Reference to non-existent clause: {ref.target_clause.to_string()}"
                    fixes = [
                        f"Create clause {ref.target_clause.section_number}",
                        "Update reference to existing clause",
                    ]

                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.BROKEN_REFERENCE,
                    severity=severity,
                    message=message,
                    description=f"The reference '{ref.reference_text}' points to a clause that does not exist.",
                    source_document=ref.source_clause.document_id,
                    source_clause=ref.source_clause,
                    target_document=ref.target_clause.document_id,
                    target_clause=ref.target_clause,
                    clause_reference=ref,
                    suggested_fixes=fixes,
                    metadata={"reference_type": ref.reference_type.value},
                )
                issues.append(issue)

        return issues

    def _validate_circular_references(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Detect circular reference chains."""
        if not self.check_circular_references:
            return []

        issues = []

        # Build adjacency graph
        graph = defaultdict(list)
        for ref in xref_map.references:
            source = ref.source_clause.to_string()
            target = ref.target_clause.to_string()
            graph[source].append((target, ref))

        # Find cycles using DFS
        visited = set()
        rec_stack = set()

        def find_cycles(node: str, path: List[Tuple[str, ClauseReference]]) -> None:
            visited.add(node)
            rec_stack.add(node)

            for neighbor, ref in graph[node]:
                if neighbor in [p[0] for p in path]:  # Found cycle
                    cycle_start = next(
                        i for i, (n, _) in enumerate(path) if n == neighbor
                    )
                    cycle_path = path[cycle_start:] + [(neighbor, ref)]

                    # Create issue for circular reference
                    cycle_clauses = [
                        ClauseIdentifier.from_string(n) for n, _ in cycle_path
                    ]
                    cycle_refs = [
                        r for _, r in cycle_path[:-1]
                    ]  # Exclude duplicate end

                    issue = ValidationIssue(
                        issue_id=self._generate_issue_id(),
                        category=ValidationCategory.CIRCULAR_REFERENCE,
                        severity=ValidationSeverity.WARNING,
                        message=f"Circular reference detected involving {len(cycle_clauses)} clauses",
                        description=f"Circular reference chain: {' -> '.join(c.to_string() for c in cycle_clauses)}",
                        source_document=cycle_clauses[0].document_id,
                        source_clause=cycle_clauses[0],
                        suggested_fixes=[
                            "Review reference chain and remove unnecessary references",
                            "Consider restructuring clauses to eliminate circular dependency",
                        ],
                        metadata={
                            "cycle_length": len(cycle_clauses),
                            "cycle_clauses": [c.to_string() for c in cycle_clauses],
                        },
                    )
                    issues.append(issue)

                elif neighbor not in visited:
                    find_cycles(neighbor, path + [(neighbor, ref)])

            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                find_cycles(node, [(node, None)])

        return issues

    def _validate_orphaned_clauses(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Find clauses with no incoming or outgoing references."""
        if not self.check_orphaned_clauses:
            return []

        issues = []

        # Count references for each clause
        reference_counts = defaultdict(lambda: {"incoming": 0, "outgoing": 0})

        for ref in xref_map.references:
            source_id = ref.source_clause.to_string()
            target_id = ref.target_clause.to_string()
            reference_counts[source_id]["outgoing"] += 1
            reference_counts[target_id]["incoming"] += 1

        for clause_id, clause in xref_map.clauses.items():
            counts = reference_counts[clause_id]

            # Skip definition clauses and top-level sections
            if clause.clause_type.value == "definition" or clause.level == 1:
                continue

            # Check if clause is orphaned
            if counts["incoming"] == 0 and counts["outgoing"] == 0:
                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.ORPHANED_CLAUSE,
                    severity=ValidationSeverity.INFO,
                    message=f"Orphaned clause: {clause.title}",
                    description=f"Clause {clause.identifier.to_string()} has no incoming or outgoing references.",
                    source_document=clause.identifier.document_id,
                    source_clause=clause.identifier,
                    suggested_fixes=[
                        "Add references to this clause from other relevant clauses",
                        "Add references from this clause to related provisions",
                        "Consider if this clause is necessary",
                    ],
                    metadata={
                        "clause_type": clause.clause_type.value,
                        "clause_level": clause.level,
                    },
                )
                issues.append(issue)

        return issues

    def _validate_missing_definitions(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Find referenced terms that are not defined."""
        issues = []

        # Collect all referenced terms
        referenced_terms = set()
        for clause in xref_map.clauses.values():
            referenced_terms.update(clause.referenced_terms)

        # Check for missing definitions
        for term in referenced_terms:
            if term not in xref_map.definitions:
                # Find clauses that reference this undefined term
                referencing_clauses = [
                    clause
                    for clause in xref_map.clauses.values()
                    if term in clause.referenced_terms
                ]

                for clause in referencing_clauses:
                    issue = ValidationIssue(
                        issue_id=self._generate_issue_id(),
                        category=ValidationCategory.MISSING_DEFINITION,
                        severity=ValidationSeverity.WARNING,
                        message=f"Undefined term referenced: '{term}'",
                        description=f"The term '{term}' is referenced but not defined in any definitions clause.",
                        source_document=clause.identifier.document_id,
                        source_clause=clause.identifier,
                        suggested_fixes=[
                            f"Add definition for '{term}' in definitions clause",
                            f"Remove quotes from '{term}' if not a defined term",
                            f"Check if '{term}' is defined under a different name",
                        ],
                        metadata={"undefined_term": term},
                    )
                    issues.append(issue)

        return issues

    def _validate_unused_definitions(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Find defined terms that are never referenced."""
        issues = []

        # Collect all referenced terms
        referenced_terms = set()
        for clause in xref_map.clauses.values():
            referenced_terms.update(clause.referenced_terms)

        # Check for unused definitions
        for term, defining_clauses in xref_map.definitions.items():
            if term not in referenced_terms:
                for defining_clause in defining_clauses:
                    clause = xref_map.clauses.get(defining_clause.to_string())
                    if clause:
                        issue = ValidationIssue(
                            issue_id=self._generate_issue_id(),
                            category=ValidationCategory.UNUSED_DEFINITION,
                            severity=ValidationSeverity.INFO,
                            message=f"Unused definition: '{term}'",
                            description=f"The term '{term}' is defined but never referenced in the document.",
                            source_document=defining_clause.document_id,
                            source_clause=defining_clause,
                            suggested_fixes=[
                                f"Add references to '{term}' where appropriate",
                                f"Remove definition of '{term}' if not needed",
                                f"Check if '{term}' is referenced under a different format",
                            ],
                            metadata={"unused_term": term},
                        )
                        issues.append(issue)

        return issues

    def _validate_citation_validity(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Validate legal citations for correctness and currency."""
        if not self.check_outdated_citations:
            return []

        issues = []
        current_year = datetime.now().year

        for clause in xref_map.clauses.values():
            for citation in clause.citations:
                citation_issues = self._validate_single_citation(
                    citation, clause.identifier.document_id
                )
                issues.extend(citation_issues)

        return issues

    def _validate_numbering_consistency(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Check for consistent clause numbering within documents."""
        issues = []

        # Group clauses by document
        by_document = defaultdict(list)
        for clause in xref_map.clauses.values():
            by_document[clause.identifier.document_id].append(clause)

        for doc_id, clauses in by_document.items():
            # Sort by section number for analysis
            sorted_clauses = sorted(
                clauses,
                key=lambda c: [int(x) for x in c.identifier.section_number.split(".")],
            )

            # Check for gaps in numbering
            for i, clause in enumerate(sorted_clauses[:-1]):
                current_parts = [
                    int(x) for x in clause.identifier.section_number.split(".")
                ]
                next_parts = [
                    int(x)
                    for x in sorted_clauses[i + 1].identifier.section_number.split(".")
                ]

                # Check for skipped numbers at same level
                if len(current_parts) == len(next_parts):
                    if len(current_parts) == 1:
                        # Top level sections
                        if next_parts[0] - current_parts[0] > 1:
                            issue = ValidationIssue(
                                issue_id=self._generate_issue_id(),
                                category=ValidationCategory.INCONSISTENT_NUMBERING,
                                severity=ValidationSeverity.INFO,
                                message=f"Gap in section numbering: {current_parts[0]} to {next_parts[0]}",
                                description=f"Section numbers skip from {clause.identifier.section_number} to {sorted_clauses[i + 1].identifier.section_number}",
                                source_document=doc_id,
                                source_clause=clause.identifier,
                                suggested_fixes=[
                                    "Add missing sections",
                                    "Renumber sections to eliminate gaps",
                                ],
                                metadata={
                                    "missing_sections": list(
                                        range(current_parts[0] + 1, next_parts[0])
                                    )
                                },
                            )
                            issues.append(issue)

        return issues

    def _validate_duplicate_references(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Find duplicate references between the same source and target."""
        issues = []

        # Group references by source and target
        ref_groups = defaultdict(list)
        for ref in xref_map.references:
            key = (ref.source_clause.to_string(), ref.target_clause.to_string())
            ref_groups[key].append(ref)

        # Find duplicates
        for (source, target), refs in ref_groups.items():
            if len(refs) > 1:
                source_clause = ClauseIdentifier.from_string(source)
                target_clause = ClauseIdentifier.from_string(target)

                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.DUPLICATE_REFERENCE,
                    severity=ValidationSeverity.INFO,
                    message=f"Duplicate references from {source} to {target}",
                    description=f"Found {len(refs)} references from the same source to the same target clause.",
                    source_document=source_clause.document_id,
                    source_clause=source_clause,
                    target_clause=target_clause,
                    suggested_fixes=[
                        "Remove redundant references",
                        "Combine references into a single clear reference",
                    ],
                    metadata={
                        "duplicate_count": len(refs),
                        "reference_texts": [ref.reference_text for ref in refs],
                    },
                )
                issues.append(issue)

        return issues

    def _validate_ambiguous_references(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Find references that could refer to multiple targets."""
        issues = []

        # Group clauses by section number (ignoring document)
        section_groups = defaultdict(list)
        for clause in xref_map.clauses.values():
            section_groups[clause.identifier.section_number].append(clause)

        # Find potentially ambiguous references
        for ref in xref_map.references:
            if ref.reference_scope.value == "external":
                continue  # External references are expected to be specific

            # Check if target section exists in multiple documents
            target_section = ref.target_clause.section_number
            matching_clauses = section_groups.get(target_section, [])

            if len(matching_clauses) > 1:
                # Check if reference specifies document
                if (
                    not ref.target_clause.document_id
                    or ref.target_clause.document_id == ref.source_clause.document_id
                ):
                    other_docs = [
                        c.identifier.document_id
                        for c in matching_clauses
                        if c.identifier.document_id != ref.source_clause.document_id
                    ]

                    if other_docs:
                        issue = ValidationIssue(
                            issue_id=self._generate_issue_id(),
                            category=ValidationCategory.AMBIGUOUS_REFERENCE,
                            severity=ValidationSeverity.WARNING,
                            message=f"Ambiguous reference to Section {target_section}",
                            description=f"Section {target_section} exists in multiple documents: {', '.join(other_docs)}",
                            source_document=ref.source_clause.document_id,
                            source_clause=ref.source_clause,
                            clause_reference=ref,
                            suggested_fixes=[
                                "Specify document name in reference",
                                "Use full cross-reference format",
                            ],
                            metadata={
                                "ambiguous_documents": other_docs,
                                "section_number": target_section,
                            },
                        )
                        issues.append(issue)

        return issues

    def _validate_formatting_consistency(
        self,
        xref_map: CrossReferenceMap,
        document_contents: Optional[Dict[str, str]] = None,
    ) -> List[ValidationIssue]:
        """Check for consistent reference formatting."""
        issues = []

        # Analyze reference patterns
        patterns = defaultdict(list)
        for ref in xref_map.references:
            # Normalize and categorize reference text
            normalized = re.sub(r"\d+(?:\.\d+)*", "N", ref.reference_text)
            patterns[normalized].append(ref)

        # Find inconsistent patterns for same reference type
        for pattern, refs in patterns.items():
            if len(refs) > 1:
                # Check if all references are the same type
                ref_types = set(ref.reference_type for ref in refs)
                if len(ref_types) == 1:
                    # Group by exact text
                    text_groups = defaultdict(list)
                    for ref in refs:
                        text_groups[ref.reference_text].append(ref)

                    if len(text_groups) > 1:
                        # Found formatting inconsistency
                        most_common = max(text_groups.items(), key=lambda x: len(x[1]))

                        for text, text_refs in text_groups.items():
                            if text != most_common[0]:
                                for ref in text_refs:
                                    issue = ValidationIssue(
                                        issue_id=self._generate_issue_id(),
                                        category=ValidationCategory.INCONSISTENT_FORMATTING,
                                        severity=ValidationSeverity.INFO,
                                        message=f"Inconsistent reference formatting: '{text}'",
                                        description=f"Reference format '{text}' differs from common format '{most_common[0]}'",
                                        source_document=ref.source_clause.document_id,
                                        source_clause=ref.source_clause,
                                        clause_reference=ref,
                                        suggested_fixes=[
                                            f"Change to format: '{most_common[0]}'",
                                            "Standardize reference formatting across document",
                                        ],
                                        metadata={
                                            "inconsistent_format": text,
                                            "suggested_format": most_common[0],
                                        },
                                    )
                                    issues.append(issue)

        return issues

    def _validate_single_reference(
        self,
        reference: Reference,
        document_id: str,
        available_documents: Set[str],
        available_sections: Optional[Dict[str, Set[str]]] = None,
    ) -> List[ValidationIssue]:
        """Validate a single reference."""
        issues = []

        # Check if target document exists
        if (
            reference.target_document
            and reference.target_document not in available_documents
        ):
            issue = ValidationIssue(
                issue_id=self._generate_issue_id(),
                category=ValidationCategory.BROKEN_REFERENCE,
                severity=ValidationSeverity.ERROR,
                message=f"Reference to non-existent document: {reference.target_document}",
                description=f"The reference '{reference.raw_text}' points to document '{reference.target_document}' which does not exist.",
                source_document=document_id,
                source_position=(
                    reference.location.start_position if reference.location else None
                ),
                target_document=reference.target_document,
                reference=reference,
                suggested_fixes=[
                    f"Create document '{reference.target_document}'",
                    "Update reference to correct document name",
                    "Remove invalid reference",
                ],
            )
            issues.append(issue)

        # Check if target section exists (if section info available)
        elif (
            available_sections
            and reference.target_document in available_sections
            and reference.target_section
            and reference.target_section
            not in available_sections[reference.target_document]
        ):
            issue = ValidationIssue(
                issue_id=self._generate_issue_id(),
                category=ValidationCategory.BROKEN_REFERENCE,
                severity=ValidationSeverity.WARNING,
                message=f"Reference to non-existent section: {reference.target_section}",
                description=f"The reference '{reference.raw_text}' points to section '{reference.target_section}' which does not exist in document '{reference.target_document}'.",
                source_document=document_id,
                source_position=(
                    (reference.location.start_position, reference.location.end_position)
                    if reference.location
                    else None
                ),
                target_document=reference.target_document,
                reference=reference,
                suggested_fixes=[
                    f"Create section '{reference.target_section}'",
                    "Update reference to correct section",
                    "Remove invalid reference",
                ],
            )
            issues.append(issue)

        return issues

    def _validate_single_citation(
        self, citation: Citation, document_id: str
    ) -> List[ValidationIssue]:
        """Validate a single legal citation."""
        issues = []
        current_year = datetime.now().year

        # Check citation age
        if citation.year and self.check_outdated_citations:
            age = current_year - citation.year

            if citation.year < self.min_citation_year:
                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.OUTDATED_CITATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"Very old citation: {citation.year}",
                    description=f"Citation '{citation.normalized_text}' is from {citation.year}, which may be outdated.",
                    source_document=document_id,
                    source_position=citation.position,
                    citation=citation,
                    suggested_fixes=[
                        "Check if citation has been superseded",
                        "Find more recent authority",
                        "Verify citation is still good law",
                    ],
                    metadata={"citation_age": age},
                )
                issues.append(issue)

            elif age > self.max_citation_age_years:
                issue = ValidationIssue(
                    issue_id=self._generate_issue_id(),
                    category=ValidationCategory.OUTDATED_CITATION,
                    severity=ValidationSeverity.INFO,
                    message=f"Old citation: {age} years old",
                    description=f"Citation '{citation.normalized_text}' is {age} years old. Consider checking for more recent authority.",
                    source_document=document_id,
                    source_position=citation.position,
                    citation=citation,
                    suggested_fixes=[
                        "Check for subsequent history",
                        "Look for more recent cases on same issue",
                        "Verify citation is still good law",
                    ],
                    metadata={"citation_age": age},
                )
                issues.append(issue)

        # Check citation format
        if citation.confidence < 0.8:
            issue = ValidationIssue(
                issue_id=self._generate_issue_id(),
                category=ValidationCategory.INVALID_CITATION,
                severity=ValidationSeverity.WARNING,
                message="Potentially malformed citation",
                description=f"Citation '{citation.raw_text}' may not be properly formatted (confidence: {citation.confidence:.2f}).",
                source_document=document_id,
                source_position=citation.position,
                citation=citation,
                suggested_fixes=[
                    "Check citation format against Bluebook rules",
                    "Verify all citation elements are correct",
                    "Consider manual review of citation",
                ],
                metadata={"confidence": citation.confidence},
            )
            issues.append(issue)

        return issues

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self._issue_counter += 1
        return f"issue_{self._issue_counter:06d}"

    def generate_validation_report(
        self,
        validation_results: Union[ValidationResult, List[ValidationResult]],
        output_format: str = "json",
    ) -> str:
        """Generate validation report in specified format.

        Args:
            validation_results: Validation results to report
            output_format: Output format (json, markdown, html)

        Returns:
            Formatted report string
        """
        if isinstance(validation_results, ValidationResult):
            results = [validation_results]
        else:
            results = validation_results

        if output_format == "json":
            return self._generate_json_report(results)
        elif output_format == "markdown":
            return self._generate_markdown_report(results)
        elif output_format == "html":
            return self._generate_html_report(results)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _generate_json_report(self, results: List[ValidationResult]) -> str:
        """Generate JSON validation report."""
        report_data = {
            "validation_summary": {
                "total_documents": len(results),
                "total_issues": sum(r.total_issues for r in results),
                "validation_timestamp": datetime.now().isoformat(),
            },
            "results": [result.to_dict() for result in results],
        }

        return json.dumps(report_data, indent=2)

    def _generate_markdown_report(self, results: List[ValidationResult]) -> str:
        """Generate Markdown validation report."""
        total_issues = sum(r.total_issues for r in results)

        report = """# Reference Validation Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Documents Validated:** {len(results)}
**Total Issues Found:** {total_issues}

## Summary

"""

        for result in results:
            report += """### {result.document_id}

- **Total Issues:** {result.total_issues}
- **References:** {result.valid_references}/{result.total_references} valid
- **Citations:** {result.valid_citations}/{result.total_citations} valid
- **Validation Duration:** {result.validation_duration:.2f}s

**Issues by Severity:**
"""
            for severity, count in result.issues_by_severity.items():
                report += f"- {severity.title()}: {count}\n"

            report += "\n**Issues by Category:**\n"
            for category, count in result.issues_by_category.items():
                report += f"- {category.replace('_', ' ').title()}: {count}\n"

            report += "\n"

        # Add detailed issues
        for result in results:
            if result.issues:
                report += """## Detailed Issues - {result.document_id}

"""
                for issue in result.issues[:20]:  # Limit to top 20 issues
                    report += """### {issue.severity.value.upper()}: {issue.message}

**Category:** {issue.category.value.replace('_', ' ').title()}
**Description:** {issue.description}

"""
                    if issue.suggested_fixes:
                        report += "**Suggested Fixes:**\n"
                        for fix in issue.suggested_fixes:
                            report += f"- {fix}\n"
                        report += "\n"

        return report

    def _generate_html_report(self, results: List[ValidationResult]) -> str:
        """Generate HTML validation report."""
        total_issues = sum(r.total_issues for r in results)

        html = """<!DOCTYPE html>
<html>
<head>
    <title>Reference Validation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        .error {{ color: #d32f2f; }}
        .warning {{ color: #f57c00; }}
        .info {{ color: #1976d2; }}
        .critical {{ color: #b71c1c; font-weight: bold; }}
        .issue {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ccc; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Reference Validation Report</h1>

    <div class="summary">
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Documents Validated:</strong> {len(results)}</p>
        <p><strong>Total Issues Found:</strong> {total_issues}</p>
    </div>
"""

        # Summary table
        html += """
    <h2>Summary by Document</h2>
    <table>
        <tr>
            <th>Document</th>
            <th>Total Issues</th>
            <th>References</th>
            <th>Citations</th>
            <th>Duration</th>
        </tr>
"""

        for result in results:
            html += """
        <tr>
            <td>{result.document_id}</td>
            <td>{result.total_issues}</td>
            <td>{result.valid_references}/{result.total_references}</td>
            <td>{result.valid_citations}/{result.total_citations}</td>
            <td>{result.validation_duration:.2f}s</td>
        </tr>
"""

        html += """
    </table>
"""

        # Detailed issues
        for result in results:
            if result.issues:
                html += """
    <h2>Issues - {result.document_id}</h2>
"""
                for issue in result.issues[:20]:  # Limit to top 20
                    severity_class = issue.severity.value
                    html += """
    <div class="issue">
        <h3 class="{severity_class}">{issue.severity.value.upper()}: {issue.message}</h3>
        <p><strong>Category:</strong> {issue.category.value.replace('_', ' ').title()}</p>
        <p><strong>Description:</strong> {issue.description}</p>
"""
                    if issue.suggested_fixes:
                        html += "<p><strong>Suggested Fixes:</strong></p><ul>"
                        for fix in issue.suggested_fixes:
                            html += f"<li>{fix}</li>"
                        html += "</ul>"

                    html += "</div>"

        html += """
</body>
</html>
"""

        return html
