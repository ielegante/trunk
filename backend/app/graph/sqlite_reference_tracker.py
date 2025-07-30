"""SQLite-based reference tracking system for cross-document relationships."""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.database import database_manager
from app.models import Document, Reference, ReferenceStatus, ReferenceType
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased, joinedload

logger = logging.getLogger(__name__)


@dataclass
class DocumentNode:
    """Represents a document in the graph."""

    id: str
    repository_id: str
    file_path: str
    title: str
    version: str
    created_at: datetime
    updated_at: datetime
    content_hash: str
    document_type: str
    metadata: Dict[str, Any]


@dataclass
class ReferenceEdge:
    """Represents a reference relationship between documents."""

    id: str
    source_doc_id: str
    target_doc_id: str
    reference_type: ReferenceType
    status: ReferenceStatus
    created_at: datetime
    updated_at: datetime
    location: Dict[str, Any]
    context: str
    metadata: Dict[str, Any]


@dataclass
class ReferenceValidation:
    """Results of reference validation."""

    reference_id: str
    is_valid: bool
    status: ReferenceStatus
    issues: List[str]
    suggestions: List[str]
    validated_at: datetime


class SQLiteReferenceTracker:
    """Tracks and manages cross-document references using SQLite."""

    def __init__(self):
        self.db = database_manager

    def create_document_node(self, document: DocumentNode) -> Dict[str, Any]:
        """Create a document node in the database."""
        try:
            with self.db.get_session() as session:
                # Check if document already exists
                existing = session.query(Document).filter_by(id=document.id).first()
                if existing:
                    return {
                        "success": False,
                        "error": "Document already exists",
                        "document_id": document.id,
                    }

                # Create new document
                db_document = Document(
                    id=document.id,
                    repository_id=document.repository_id,
                    file_path=document.file_path,
                    title=document.title,
                    version=document.version,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                    content_hash=document.content_hash,
                    document_type=document.document_type,
                    metadata=document.metadata,
                )

                session.add(db_document)
                session.commit()

                return {
                    "success": True,
                    "document_id": document.id,
                    "message": "Document node created successfully",
                }

        except Exception as e:
            logger.error(f"Failed to create document node: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_reference(self, reference: ReferenceEdge) -> Dict[str, Any]:
        """Create a reference relationship between documents."""
        try:
            with self.db.get_session() as session:
                # Verify both documents exist
                source_doc = (
                    session.query(Document)
                    .filter_by(id=reference.source_doc_id)
                    .first()
                )
                target_doc = (
                    session.query(Document)
                    .filter_by(id=reference.target_doc_id)
                    .first()
                )

                if not source_doc or not target_doc:
                    return {
                        "success": False,
                        "error": "Source or target document not found",
                    }

                # Check if reference already exists
                existing_ref = (
                    session.query(Reference).filter_by(id=reference.id).first()
                )

                if existing_ref:
                    return {
                        "success": False,
                        "error": "Reference already exists",
                        "reference_id": reference.id,
                    }

                # Create new reference
                db_reference = Reference(
                    id=reference.id,
                    source_doc_id=reference.source_doc_id,
                    target_doc_id=reference.target_doc_id,
                    reference_type=reference.reference_type.value,
                    status=reference.status.value,
                    created_at=reference.created_at,
                    updated_at=reference.updated_at,
                    location=reference.location,
                    context=reference.context,
                    metadata=reference.metadata,
                )

                session.add(db_reference)
                session.commit()

                return {
                    "success": True,
                    "reference_id": reference.id,
                    "message": "Reference created successfully",
                }

        except Exception as e:
            logger.error(f"Failed to create reference: {str(e)}")
            return {"success": False, "error": str(e)}

    def find_references_by_document(
        self, document_id: str, direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """Find all references for a document."""
        try:
            with self.db.get_session() as session:
                references = []

                if direction in ["outgoing", "both"]:
                    # Find outgoing references
                    outgoing_query = (
                        session.query(Reference, Document)
                        .join(Document, Reference.target_doc_id == Document.id)
                        .filter(Reference.source_doc_id == document_id)
                    )

                    for ref, target_doc in outgoing_query.all():
                        references.append(
                            {
                                "reference_id": ref.id,
                                "reference_type": ref.reference_type,
                                "status": ref.status,
                                "document": {
                                    "id": target_doc.id,
                                    "title": target_doc.title,
                                    "file_path": target_doc.file_path,
                                },
                                "location": ref.location,
                                "context": ref.context,
                                "direction": "outgoing",
                            }
                        )

                if direction in ["incoming", "both"]:
                    # Find incoming references
                    incoming_query = (
                        session.query(Reference, Document)
                        .join(Document, Reference.source_doc_id == Document.id)
                        .filter(Reference.target_doc_id == document_id)
                    )

                    for ref, source_doc in incoming_query.all():
                        references.append(
                            {
                                "reference_id": ref.id,
                                "reference_type": ref.reference_type,
                                "status": ref.status,
                                "document": {
                                    "id": source_doc.id,
                                    "title": source_doc.title,
                                    "file_path": source_doc.file_path,
                                },
                                "location": ref.location,
                                "context": ref.context,
                                "direction": "incoming",
                            }
                        )

                return references

        except Exception as e:
            logger.error(f"Failed to find references: {str(e)}")
            return []

    def validate_reference(self, reference_id: str) -> ReferenceValidation:
        """Validate a reference is still valid."""
        try:
            with self.db.get_session() as session:
                # Get reference with related documents
                ref_query = (
                    session.query(Reference)
                    .options(
                        joinedload(Reference.source_document),
                        joinedload(Reference.target_document),
                    )
                    .filter_by(id=reference_id)
                    .first()
                )

                if not ref_query:
                    return ReferenceValidation(
                        reference_id=reference_id,
                        is_valid=False,
                        status=ReferenceStatus.BROKEN,
                        issues=["Reference not found in database"],
                        suggestions=["Reference may have been deleted"],
                        validated_at=datetime.utcnow(),
                    )

                issues = []
                suggestions = []

                # Check if target document still exists
                if not ref_query.target_document:
                    issues.append("Target document not found")
                    suggestions.append(
                        "Update reference to point to new document location"
                    )
                    status = ReferenceStatus.BROKEN
                else:
                    # Check if content has changed
                    if ref_query.source_document.updated_at > ref_query.created_at:
                        issues.append("Source document updated since reference created")
                        suggestions.append("Review reference context for accuracy")

                    if ref_query.target_document.updated_at > ref_query.created_at:
                        issues.append("Target document updated since reference created")
                        suggestions.append("Verify referenced content still exists")

                    status = (
                        ReferenceStatus.OUTDATED if issues else ReferenceStatus.VALID
                    )

                # Update reference status
                self._update_reference_status(reference_id, status)

                return ReferenceValidation(
                    reference_id=reference_id,
                    is_valid=len(issues) == 0,
                    status=status,
                    issues=issues,
                    suggestions=suggestions,
                    validated_at=datetime.utcnow(),
                )

        except Exception as e:
            logger.error(f"Failed to validate reference: {str(e)}")
            return ReferenceValidation(
                reference_id=reference_id,
                is_valid=False,
                status=ReferenceStatus.BROKEN,
                issues=[f"Validation error: {str(e)}"],
                suggestions=["Check system logs for details"],
                validated_at=datetime.utcnow(),
            )

    def find_reference_chains(
        self, document_id: str, max_depth: int = 3
    ) -> List[List[Dict]]:
        """Find chains of references starting from a document."""
        try:
            with self.db.get_session() as session:
                chains = []

                # Use recursive CTE to find reference chains
                # This is a simplified implementation - full recursive traversal
                # would require more complex SQL or multiple queries

                def find_chains_recursive(
                    current_doc_id: str, current_chain: List[Dict], depth: int
                ):
                    if depth >= max_depth:
                        return

                    # Find outgoing references from current document
                    outgoing_refs = (
                        session.query(Reference, Document)
                        .join(Document, Reference.target_doc_id == Document.id)
                        .filter(Reference.source_doc_id == current_doc_id)
                        .all()
                    )

                    for ref, target_doc in outgoing_refs:
                        new_chain = current_chain + [
                            {
                                "reference": {
                                    "id": ref.id,
                                    "type": ref.reference_type,
                                    "status": ref.status,
                                }
                            },
                            {
                                "document": {
                                    "id": target_doc.id,
                                    "title": target_doc.title,
                                    "file_path": target_doc.file_path,
                                }
                            },
                        ]

                        if len(new_chain) > 2:  # Has at least one reference
                            chains.append(new_chain)

                        # Recursively find more chains
                        find_chains_recursive(target_doc.id, new_chain, depth + 1)

                # Start the search
                start_doc = session.query(Document).filter_by(id=document_id).first()
                if start_doc:
                    initial_chain = [
                        {
                            "document": {
                                "id": start_doc.id,
                                "title": start_doc.title,
                                "file_path": start_doc.file_path,
                            }
                        }
                    ]

                    find_chains_recursive(document_id, initial_chain, 0)

                return chains[:100]  # Limit to first 100 chains

        except Exception as e:
            logger.error(f"Failed to find reference chains: {str(e)}")
            return []

    def find_circular_references(self, repository_id: str) -> List[List[str]]:
        """Detect circular reference chains in a repository."""
        try:
            with self.db.get_session() as session:
                # Find all documents in the repository
                docs = (
                    session.query(Document).filter_by(repository_id=repository_id).all()
                )
                doc_ids = {doc.id for doc in docs}

                circular_chains = []

                for doc in docs:
                    visited = set()
                    current_path = []

                    def find_circular_path(current_doc_id: str, path: List[str]):
                        if current_doc_id in visited:
                            # Found a cycle
                            cycle_start = path.index(current_doc_id)
                            cycle = path[cycle_start:] + [current_doc_id]
                            if len(cycle) > 2:  # Meaningful cycle
                                circular_chains.append(cycle)
                            return

                        visited.add(current_doc_id)
                        path.append(current_doc_id)

                        # Find outgoing references
                        refs = (
                            session.query(Reference)
                            .filter(
                                Reference.source_doc_id == current_doc_id,
                                Reference.target_doc_id.in_(doc_ids),
                            )
                            .all()
                        )

                        for ref in refs:
                            find_circular_path(ref.target_doc_id, path[:])

                        visited.remove(current_doc_id)
                        path.pop()

                    find_circular_path(doc.id, [])

                return circular_chains[:50]  # Limit to first 50 cycles

        except Exception as e:
            logger.error(f"Failed to find circular references: {str(e)}")
            return []

    def get_reference_graph(self, document_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get reference graph centered on a document."""
        try:
            with self.db.get_session() as session:
                nodes = []
                edges = []
                processed_docs = set()

                def add_document_and_references(doc_id: str, current_depth: int):
                    if current_depth > depth or doc_id in processed_docs:
                        return

                    processed_docs.add(doc_id)

                    # Get document
                    doc = session.query(Document).filter_by(id=doc_id).first()
                    if not doc:
                        return

                    # Add node
                    nodes.append(
                        {
                            "id": doc.id,
                            "label": doc.title,
                            "type": "document",
                            "properties": {
                                "file_path": doc.file_path,
                                "document_type": doc.document_type,
                                "version": doc.version,
                            },
                        }
                    )

                    # Get outgoing references
                    outgoing_refs = (
                        session.query(Reference, Document)
                        .join(Document, Reference.target_doc_id == Document.id)
                        .filter(Reference.source_doc_id == doc_id)
                        .all()
                    )

                    for ref, target_doc in outgoing_refs:
                        edges.append(
                            {
                                "id": ref.id,
                                "source": doc_id,
                                "target": target_doc.id,
                                "type": ref.reference_type,
                                "properties": {
                                    "status": ref.status,
                                    "context": ref.context,
                                },
                            }
                        )

                        # Recursively add connected documents
                        add_document_and_references(target_doc.id, current_depth + 1)

                    # Get incoming references
                    incoming_refs = (
                        session.query(Reference, Document)
                        .join(Document, Reference.source_doc_id == Document.id)
                        .filter(Reference.target_doc_id == doc_id)
                        .all()
                    )

                    for ref, source_doc in incoming_refs:
                        if ref.id not in [edge["id"] for edge in edges]:
                            edges.append(
                                {
                                    "id": ref.id,
                                    "source": source_doc.id,
                                    "target": doc_id,
                                    "type": ref.reference_type,
                                    "properties": {
                                        "status": ref.status,
                                        "context": ref.context,
                                    },
                                }
                            )

                        # Recursively add connected documents
                        add_document_and_references(source_doc.id, current_depth + 1)

                # Start the graph building
                add_document_and_references(document_id, 0)

                return {
                    "center_document_id": document_id,
                    "depth": depth,
                    "nodes": nodes,
                    "edges": edges,
                    "statistics": {
                        "total_nodes": len(nodes),
                        "total_edges": len(edges),
                    },
                }

        except Exception as e:
            logger.error(f"Failed to get reference graph: {str(e)}")
            return {"nodes": [], "edges": []}

    def update_document_node(
        self, document_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update document node properties."""
        try:
            with self.db.get_session() as session:
                doc = session.query(Document).filter_by(id=document_id).first()
                if not doc:
                    return {"success": False, "error": "Document not found"}

                # Update allowed fields
                allowed_fields = {
                    "title",
                    "version",
                    "content_hash",
                    "document_type",
                    "metadata",
                    "file_path",
                }

                for key, value in updates.items():
                    if key in allowed_fields and hasattr(doc, key):
                        setattr(doc, key, value)

                doc.updated_at = datetime.utcnow()
                session.commit()

                return {
                    "success": True,
                    "document_id": document_id,
                    "message": "Document updated successfully",
                }

        except Exception as e:
            logger.error(f"Failed to update document: {str(e)}")
            return {"success": False, "error": str(e)}

    def delete_reference(self, reference_id: str) -> Dict[str, Any]:
        """Delete a reference relationship."""
        try:
            with self.db.get_session() as session:
                ref = session.query(Reference).filter_by(id=reference_id).first()
                if not ref:
                    return {
                        "success": False,
                        "deleted_count": 0,
                        "message": "Reference not found",
                    }

                session.delete(ref)
                session.commit()

                return {
                    "success": True,
                    "deleted_count": 1,
                    "message": "Reference deleted successfully",
                }

        except Exception as e:
            logger.error(f"Failed to delete reference: {str(e)}")
            return {"success": False, "error": str(e)}

    def _update_reference_status(self, reference_id: str, status: ReferenceStatus):
        """Update reference status."""
        try:
            with self.db.get_session() as session:
                ref = session.query(Reference).filter_by(id=reference_id).first()
                if ref:
                    ref.status = status.value
                    ref.updated_at = datetime.utcnow()
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update reference status: {str(e)}")

    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics."""
        try:
            with self.db.get_session() as session:
                stats = {}

                # Count documents
                stats["document_count"] = session.query(Document).count()

                # Count references by type
                reference_types = [
                    "citation",
                    "amendment",
                    "supersedes",
                    "incorporates",
                    "related",
                    "parent",
                    "child",
                    "exhibit",
                    "attachment",
                    "cross_re",
                    "external",
                ]

                for ref_type in reference_types:
                    count = (
                        session.query(Reference)
                        .filter_by(reference_type=ref_type)
                        .count()
                    )
                    stats[f"{ref_type}_count"] = count

                # Count references by status
                for status in ["valid", "broken", "outdated", "pending", "resolved"]:
                    count = session.query(Reference).filter_by(status=status).count()
                    stats[f"{status}_status_count"] = count

                # Total references
                stats["total_references"] = session.query(Reference).count()

                return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {}


# Global reference tracker instance
sqlite_reference_tracker = SQLiteReferenceTracker()
