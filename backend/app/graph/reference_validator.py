"""Reference validation system for ensuring reference integrity."""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.graph.reference_tracker import (
    DocumentNode,
    ReferenceEdge,
    ReferenceStatus,
    ReferenceType,
    ReferenceValidation,
    reference_tracker,
)

logger = logging.getLogger(__name__)


class ValidationRule(Enum):
    """Types of validation rules."""

    DOCUMENT_EXISTS = "document_exists"
    CONTENT_MATCH = "content_match"
    VERSION_COMPATIBILITY = "version_compatibility"
    CIRCULAR_REFERENCE = "circular_reference"
    REFERENCE_DEPTH = "reference_depth"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    REFERENCE_FORMAT = "reference_format"
    PERMISSION_CHECK = "permission_check"


@dataclass
class ValidationContext:
    """Context for validation operations."""

    repository_id: str
    user_id: str
    validation_time: datetime
    strict_mode: bool = False
    max_depth: int = 5
    check_permissions: bool = True


@dataclass
class BatchValidationResult:
    """Results of batch validation."""

    total_references: int
    valid_references: int
    broken_references: int
    outdated_references: int
    validation_time: datetime
    issues_by_document: Dict[str, List[str]]
    recommendations: List[str]


class ReferenceValidator:
    """Validates document references and maintains reference integrity."""

    def __init__(self):
        self.tracker = reference_tracker
        self.validation_cache = {}
        self.cache_ttl = timedelta(minutes=30)

        # Reference patterns for different document types
        self.reference_patterns = {
            "legal_citation": re.compile(
                r"\b\d+\s+[A-Z]\.\d+\s+\d+\b"
            ),  # e.g., "123 F.3d 456"
            "section_reference": re.compile(r"§\s*\d+(\.\d+)*"),  # e.g., "§ 12.3.4"
            "exhibit_reference": re.compile(r"Exhibit\s+[A-Z\d]+", re.IGNORECASE),
            "clause_reference": re.compile(r"Clause\s+\d+(\.\d+)*", re.IGNORECASE),
            "document_reference": re.compile(r"Document\s+ID:\s*[\w-]+"),
            "cross_reference": re.compile(
                r"See\s+(also\s+)?[\w\s]+,\s*(supra|infra)", re.IGNORECASE
            ),
        }

    def validate_reference(
        self, reference_id: str, context: ValidationContext
    ) -> ReferenceValidation:
        """Validate a single reference with comprehensive checks."""

        # Check cache first
        cache_key = f"{reference_id}:{context.repository_id}"
        if cache_key in self.validation_cache:
            cached_result, cache_time = self.validation_cache[cache_key]
            if datetime.utcnow() - cache_time < self.cache_ttl:
                return cached_result

        # Perform validation
        validation = self.tracker.validate_reference(reference_id)

        # Additional validation checks
        if context.strict_mode:
            additional_issues = self._perform_strict_validation(reference_id, context)
            validation.issues.extend(additional_issues)
            validation.is_valid = len(validation.issues) == 0

        # Update cache
        self.validation_cache[cache_key] = (validation, datetime.utcnow())

        return validation

    def validate_document_references(
        self, document_id: str, context: ValidationContext
    ) -> Dict[str, Any]:
        """Validate all references in a document."""

        # Get all references for the document
        references = self.tracker.find_references_by_document(
            document_id, direction="both"
        )

        validation_results = {
            "document_id": document_id,
            "validation_time": datetime.utcnow(),
            "total_references": len(references),
            "valid_references": 0,
            "broken_references": 0,
            "outdated_references": 0,
            "issues": [],
            "reference_validations": [],
        }

        for ref in references:
            ref_validation = self.validate_reference(ref["reference_id"], context)

            validation_results["reference_validations"].append(
                {
                    "reference_id": ref["reference_id"],
                    "type": ref["reference_type"],
                    "direction": ref["direction"],
                    "is_valid": ref_validation.is_valid,
                    "status": ref_validation.status.value,
                    "issues": ref_validation.issues,
                }
            )

            if ref_validation.is_valid:
                validation_results["valid_references"] += 1
            elif ref_validation.status == ReferenceStatus.BROKEN:
                validation_results["broken_references"] += 1
            elif ref_validation.status == ReferenceStatus.OUTDATED:
                validation_results["outdated_references"] += 1

            validation_results["issues"].extend(ref_validation.issues)

        # Check for circular references
        circular_refs = self._check_circular_references(document_id, context)
        if circular_refs:
            validation_results["issues"].append(
                f"Circular references detected: {len(circular_refs)} chains"
            )

        return validation_results

    def validate_repository(
        self, repository_id: str, context: ValidationContext
    ) -> BatchValidationResult:
        """Validate all references in a repository."""

        # Get all documents in repository
        query = """
        MATCH (d:Document {repository_id: $repository_id})
        RETURN d.id as document_id
        """

        documents = self.tracker.connection.execute_query(
            query, {"repository_id": repository_id}
        )

        total_refs = 0
        valid_refs = 0
        broken_refs = 0
        outdated_refs = 0
        issues_by_doc = {}

        for doc in documents:
            doc_id = doc["document_id"]
            doc_validation = self.validate_document_references(doc_id, context)

            total_refs += doc_validation["total_references"]
            valid_refs += doc_validation["valid_references"]
            broken_refs += doc_validation["broken_references"]
            outdated_refs += doc_validation["outdated_references"]

            if doc_validation["issues"]:
                issues_by_doc[doc_id] = doc_validation["issues"]

        # Generate recommendations
        recommendations = self._generate_recommendations(
            total_refs, valid_refs, broken_refs, outdated_refs, issues_by_doc
        )

        return BatchValidationResult(
            total_references=total_refs,
            valid_references=valid_refs,
            broken_references=broken_refs,
            outdated_references=outdated_refs,
            validation_time=datetime.utcnow(),
            issues_by_document=issues_by_doc,
            recommendations=recommendations,
        )

    def extract_references(
        self, document_content: str, document_type: str = "general"
    ) -> List[Dict[str, Any]]:
        """Extract potential references from document content."""

        extracted_refs = []

        # Apply relevant patterns based on document type
        patterns_to_use = self.reference_patterns.items()
        if document_type == "legal_contract":
            patterns_to_use = [
                (k, v)
                for k, v in patterns_to_use
                if k in ["legal_citation", "section_reference", "exhibit_reference"]
            ]

        for pattern_name, pattern in patterns_to_use:
            matches = pattern.finditer(document_content)

            for match in matches:
                extracted_refs.append(
                    {
                        "type": pattern_name,
                        "text": match.group(0),
                        "start_pos": match.start(),
                        "end_pos": match.end(),
                        "context": self._extract_context(
                            document_content, match.start(), match.end()
                        ),
                    }
                )

        # Deduplicate and sort by position
        unique_refs = []
        seen = set()
        for ref in sorted(extracted_refs, key=lambda x: x["start_pos"]):
            ref_key = (ref["text"], ref["type"])
            if ref_key not in seen:
                seen.add(ref_key)
                unique_refs.append(ref)

        return unique_refs

    def resolve_reference(
        self, reference_text: str, source_doc_id: str, reference_type: str
    ) -> Optional[str]:
        """Attempt to resolve a reference text to a document ID."""

        # Try different resolution strategies based on reference type
        if reference_type == "document_reference":
            # Extract document ID from text
            match = re.search(r"Document\s+ID:\s*([\w-]+)", reference_text)
            if match:
                potential_id = match.group(1)
                # Verify document exists
                query = "MATCH (d:Document {id: $id}) RETURN d.id"
                result = self.tracker.connection.execute_query(
                    query, {"id": potential_id}
                )
                if result:
                    return potential_id

        elif reference_type == "exhibit_reference":
            # Look for exhibits in the same repository
            query = """
            MATCH (source:Document {id: $source_id})
            MATCH (target:Document)
            WHERE target.repository_id = source.repository_id
            AND target.title =~ $pattern
            RETURN target.id as target_id
            LIMIT 1
            """

            pattern = f".*{reference_text}.*"
            result = self.tracker.connection.execute_query(
                query, {"source_id": source_doc_id, "pattern": pattern}
            )

            if result:
                return result[0]["target_id"]

        return None

    def create_reference_from_extraction(
        self,
        source_doc_id: str,
        extracted_ref: Dict[str, Any],
        target_doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a reference from extracted text."""

        # Attempt to resolve target if not provided
        if not target_doc_id:
            target_doc_id = self.resolve_reference(
                extracted_ref["text"], source_doc_id, extracted_ref["type"]
            )

        if not target_doc_id:
            return {
                "success": False,
                "error": f"Could not resolve reference: {extracted_ref['text']}",
            }

        # Map extraction type to reference type
        type_mapping = {
            "legal_citation": ReferenceType.CITATION,
            "section_reference": ReferenceType.CROSS_REFERENCE,
            "exhibit_reference": ReferenceType.EXHIBIT,
            "clause_reference": ReferenceType.CROSS_REFERENCE,
            "document_reference": ReferenceType.RELATED,
            "cross_reference": ReferenceType.CROSS_REFERENCE,
        }

        ref_type = type_mapping.get(extracted_ref["type"], ReferenceType.RELATED)

        # Create reference
        reference = ReferenceEdge(
            id=f'ref_{hashlib.md5(f"{source_doc_id}:{target_doc_id}:{extracted_ref["start_pos"]}".encode()).hexdigest()[:12]}',
            source_doc_id=source_doc_id,
            target_doc_id=target_doc_id,
            reference_type=ref_type,
            status=ReferenceStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            location={
                "start_pos": extracted_ref["start_pos"],
                "end_pos": extracted_ref["end_pos"],
                "text": extracted_ref["text"],
            },
            context=extracted_ref["context"],
            metadata={"extraction_type": extracted_ref["type"], "auto_extracted": True},
        )

        return self.tracker.create_reference(reference)

    def _perform_strict_validation(
        self, reference_id: str, context: ValidationContext
    ) -> List[str]:
        """Perform additional strict validation checks."""

        additional_issues = []

        # Get reference details
        query = """
        MATCH (source:Document)-[r:REFERENCES {id: $reference_id}]->(target:Document)
        RETURN r, source, target
        """

        result = self.tracker.connection.execute_query(
            query, {"reference_id": reference_id}
        )

        if not result:
            return ["Reference not found for strict validation"]

        record = result[0]
        ref = record["r"]
        source = record["source"]
        target = record["target"]

        # Check temporal consistency
        if source["created_at"] > target["created_at"]:
            ref_type = ref["reference_type"]
            if ref_type in ["supersedes", "amendment"]:
                pass  # This is expected
            else:
                additional_issues.append(
                    "Source document created after target document"
                )

        # Check version compatibility
        if "version" in source and "version" in target:
            if not self._check_version_compatibility(
                source["version"], target["version"], ref["reference_type"]
            ):
                additional_issues.append(
                    f"Version incompatibility: {source['version']} -> {target['version']}"
                )

        # Check reference depth
        depth = self._check_reference_depth(source["id"], context.max_depth)
        if depth > context.max_depth:
            additional_issues.append(
                f"Reference chain too deep: {depth} levels (max: {context.max_depth})"
            )

        return additional_issues

    def _check_circular_references(
        self, document_id: str, context: ValidationContext
    ) -> List[List[str]]:
        """Check for circular reference chains."""

        circular_chains = self.tracker.find_circular_references(context.repository_id)

        # Filter chains that include the document
        relevant_chains = [chain for chain in circular_chains if document_id in chain]

        return relevant_chains

    def _check_version_compatibility(
        self, source_version: str, target_version: str, ref_type: str
    ) -> bool:
        """Check if versions are compatible for the reference type."""

        # Parse semantic versions
        def parse_version(v):
            try:
                parts = v.split(".")
                return tuple(int(p) for p in parts)
            except Exception:
                return (0, 0, 0)

        source_v = parse_version(source_version)
        target_v = parse_version(target_version)

        # Rules based on reference type
        if ref_type == "supersedes":
            return source_v > target_v
        elif ref_type == "amendment":
            return source_v >= target_v
        else:
            # For other types, just ensure major version compatibility
            return source_v[0] == target_v[0]

    def _check_reference_depth(self, document_id: str, max_depth: int) -> int:
        """Check the maximum reference depth from a document."""

        query = """
        MATCH path = (start:Document {id: $document_id})-[:REFERENCES*]->(end:Document)
        WHERE NOT (end)-[:REFERENCES]->()
        RETURN max(length(path)) as max_depth
        """

        result = self.tracker.connection.execute_query(
            query, {"document_id": document_id}
        )

        if result and result[0]["max_depth"]:
            return result[0]["max_depth"]

        return 0

    def _extract_context(
        self, content: str, start: int, end: int, context_size: int = 50
    ) -> str:
        """Extract context around a reference."""

        context_start = max(0, start - context_size)
        context_end = min(len(content), end + context_size)

        context = content[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(content):
            context = context + "..."

        return context

    def _generate_recommendations(
        self, total: int, valid: int, broken: int, outdated: int, issues_by_doc: Dict
    ) -> List[str]:
        """Generate recommendations based on validation results."""

        recommendations = []

        if broken > 0:
            recommendations.append(
                f"Fix {broken} broken references by updating target documents or removing invalid references"
            )

        if outdated > total * 0.2:  # More than 20% outdated
            recommendations.append(
                "Consider reviewing and updating references as many are outdated"
            )

        if len(issues_by_doc) > 5:
            recommendations.append(
                f"Focus on documents with most issues: {list(issues_by_doc.keys())[:3]}"
            )

        if valid == total:
            recommendations.append("All references are valid - good reference hygiene!")

        return recommendations


# Global validator instance
reference_validator = ReferenceValidator()
