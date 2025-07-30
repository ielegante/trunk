"""Reference tracking system for cross-document relationships."""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.graph.neo4j_config import neo4j_connection
from neo4j import Session, Transaction

logger = logging.getLogger(__name__)


class ReferenceType(Enum):
    """Types of document references."""

    CITATION = "citation"  # Legal citation to another document
    AMENDMENT = "amendment"  # Document amends another
    SUPERSEDES = "supersedes"  # Document supersedes another
    INCORPORATES = "incorporates"  # Document incorporates content from another
    RELATED = "related"  # General relationship
    PARENT = "parent"  # Parent-child hierarchy
    CHILD = "child"  # Child document
    EXHIBIT = "exhibit"  # Document is exhibit to another
    ATTACHMENT = "attachment"  # Document is attachment
    CROSS_REFERENCE = "cross_re"  # Internal cross-reference
    EXTERNAL = "external"  # External document reference


class ReferenceStatus(Enum):
    """Status of a reference."""

    VALID = "valid"
    BROKEN = "broken"
    OUTDATED = "outdated"
    PENDING = "pending"
    RESOLVED = "resolved"


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
    location: Dict[str, Any]  # line number, section, etc.
    context: str  # surrounding text
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


class ReferenceTracker:
    """Tracks and manages cross-document references using Neo4j."""

    def __init__(self):
        self.connection = neo4j_connection
        self._initialize_schema()

    def _initialize_schema(self):
        """Initialize graph schema and indexes."""
        try:
            self.connection.create_indexes()
            logger.info("Reference tracker schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {str(e)}")

    def create_document_node(self, document: DocumentNode) -> Dict[str, Any]:
        """Create a document node in the graph."""
        query = """
        CREATE (d:Document {
            id: $id,
            repository_id: $repository_id,
            file_path: $file_path,
            title: $title,
            version: $version,
            created_at: datetime($created_at),
            updated_at: datetime($updated_at),
            content_hash: $content_hash,
            document_type: $document_type,
            metadata: $metadata
        })
        RETURN d
        """

        try:
            doc_dict = asdict(document)
            doc_dict["created_at"] = document.created_at.isoformat()
            doc_dict["updated_at"] = document.updated_at.isoformat()

            result = self.connection.execute_query(query, doc_dict)

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
        query = """
        MATCH (source:Document {id: $source_doc_id})
        MATCH (target:Document {id: $target_doc_id})
        CREATE (source)-[r:REFERENCES {
            id: $id,
            reference_type: $reference_type,
            status: $status,
            created_at: datetime($created_at),
            updated_at: datetime($updated_at),
            location: $location,
            context: $context,
            metadata: $metadata
        }]->(target)
        RETURN r, source, target
        """

        try:
            ref_dict = {
                "id": reference.id,
                "source_doc_id": reference.source_doc_id,
                "target_doc_id": reference.target_doc_id,
                "reference_type": reference.reference_type.value,
                "status": reference.status.value,
                "created_at": reference.created_at.isoformat(),
                "updated_at": reference.updated_at.isoformat(),
                "location": reference.location,
                "context": reference.context,
                "metadata": reference.metadata,
            }

            result = self.connection.execute_query(query, ref_dict)

            if not result:
                return {
                    "success": False,
                    "error": "Source or target document not found",
                }

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
        if direction == "outgoing":
            query = """
            MATCH (d:Document {id: $document_id})-[r:REFERENCES]->(target:Document)
            RETURN r, target
            """
        elif direction == "incoming":
            query = """
            MATCH (source:Document)-[r:REFERENCES]->(d:Document {id: $document_id})
            RETURN r, source
            """
        else:  # both
            query = """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[r_out:REFERENCES]->(target:Document)
            OPTIONAL MATCH (source:Document)-[r_in:REFERENCES]->(d)
            RETURN
                collect(DISTINCT {ref: r_out, doc: target, direction: 'outgoing'}) as outgoing,
                collect(DISTINCT {ref: r_in, doc: source, direction: 'incoming'}) as incoming
            """

        try:
            results = self.connection.execute_query(query, {"document_id": document_id})

            references = []
            for record in results:
                if direction == "both":
                    # Process both directions
                    for ref_data in record.get("outgoing", []):
                        if ref_data["re"]:
                            references.append(self._format_reference(ref_data))
                    for ref_data in record.get("incoming", []):
                        if ref_data["re"]:
                            references.append(self._format_reference(ref_data))
                else:
                    # Process single direction
                    ref = record.get("r")
                    doc = record.get("target") or record.get("source")
                    if ref and doc:
                        references.append(
                            {
                                "reference_id": ref["id"],
                                "reference_type": ref["reference_type"],
                                "status": ref["status"],
                                "document": {
                                    "id": doc["id"],
                                    "title": doc["title"],
                                    "file_path": doc["file_path"],
                                },
                                "location": ref.get("location"),
                                "context": ref.get("context"),
                                "direction": (
                                    "outgoing"
                                    if direction == "outgoing"
                                    else "incoming"
                                ),
                            }
                        )

            return references

        except Exception as e:
            logger.error(f"Failed to find references: {str(e)}")
            return []

    def validate_reference(self, reference_id: str) -> ReferenceValidation:
        """Validate a reference is still valid."""
        query = """
        MATCH (source:Document)-[r:REFERENCES {id: $reference_id}]->(target:Document)
        RETURN r, source, target
        """

        try:
            results = self.connection.execute_query(
                query, {"reference_id": reference_id}
            )

            if not results:
                return ReferenceValidation(
                    reference_id=reference_id,
                    is_valid=False,
                    status=ReferenceStatus.BROKEN,
                    issues=["Reference not found in graph"],
                    suggestions=["Reference may have been deleted"],
                    validated_at=datetime.utcnow(),
                )

            record = results[0]
            ref = record["r"]
            source = record["source"]
            target = record["target"]

            issues = []
            suggestions = []

            # Check if target document still exists
            if not target:
                issues.append("Target document not found")
                suggestions.append("Update reference to point to new document location")
                status = ReferenceStatus.BROKEN
            else:
                # Check if content has changed
                if source.get("updated_at") > ref.get("created_at"):
                    issues.append("Source document updated since reference created")
                    suggestions.append("Review reference context for accuracy")

                if target.get("updated_at") > ref.get("created_at"):
                    issues.append("Target document updated since reference created")
                    suggestions.append("Verify referenced content still exists")

                status = ReferenceStatus.OUTDATED if issues else ReferenceStatus.VALID

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
        query = """
        MATCH path = (start:Document {id: $document_id})-[:REFERENCES*1..$max_depth]->(end:Document)
        RETURN path
        LIMIT 100
        """

        try:
            results = self.connection.execute_query(
                query, {"document_id": document_id, "max_depth": max_depth}
            )

            chains = []
            for record in results:
                path = record["path"]
                chain = []

                # Extract nodes and relationships from path
                for i, node in enumerate(path.nodes):
                    chain.append(
                        {
                            "document": {
                                "id": node["id"],
                                "title": node["title"],
                                "file_path": node["file_path"],
                            }
                        }
                    )

                    if i < len(path.relationships):
                        rel = path.relationships[i]
                        chain.append(
                            {
                                "reference": {
                                    "id": rel["id"],
                                    "type": rel["reference_type"],
                                    "status": rel["status"],
                                }
                            }
                        )

                chains.append(chain)

            return chains

        except Exception as e:
            logger.error(f"Failed to find reference chains: {str(e)}")
            return []

    def find_circular_references(self, repository_id: str) -> List[List[str]]:
        """Detect circular reference chains in a repository."""
        query = """
        MATCH (d:Document {repository_id: $repository_id})
        MATCH path = (d)-[:REFERENCES*1..10]->(d)
        RETURN path
        LIMIT 50
        """

        try:
            results = self.connection.execute_query(
                query, {"repository_id": repository_id}
            )

            circular_chains = []
            for record in results:
                path = record["path"]
                chain = [node["id"] for node in path.nodes]
                circular_chains.append(chain)

            return circular_chains

        except Exception as e:
            logger.error(f"Failed to find circular references: {str(e)}")
            return []

    def get_reference_graph(self, document_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get reference graph centered on a document."""
        query = """
        MATCH (center:Document {id: $document_id})
        OPTIONAL MATCH path = (center)-[:REFERENCES*0..$depth]-(connected:Document)
        WITH center, collect(DISTINCT connected) as nodes, collect(path) as paths
        UNWIND paths as p
        WITH center, nodes, relationships(p) as rels
        UNWIND rels as rel
        WITH center, nodes, collect(DISTINCT rel) as relationships
        RETURN center, nodes, relationships
        """

        try:
            results = self.connection.execute_query(
                query, {"document_id": document_id, "depth": depth}
            )

            if not results:
                return {"nodes": [], "edges": []}

            record = results[0]

            # Format nodes
            nodes = [self._format_node(record["center"])]
            for node in record["nodes"]:
                if node and node["id"] != document_id:
                    nodes.append(self._format_node(node))

            # Format edges
            edges = []
            for rel in record["relationships"]:
                if rel:
                    edges.append(self._format_edge(rel))

            return {
                "center_document_id": document_id,
                "depth": depth,
                "nodes": nodes,
                "edges": edges,
                "statistics": {"total_nodes": len(nodes), "total_edges": len(edges)},
            }

        except Exception as e:
            logger.error(f"Failed to get reference graph: {str(e)}")
            return {"nodes": [], "edges": []}

    def update_document_node(
        self, document_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update document node properties."""
        set_clause = ", ".join([f"d.{key} = ${key}" for key in updates.keys()])
        query = """
        MATCH (d:Document {{id: $document_id}})
        SET {set_clause}, d.updated_at = datetime()
        RETURN d
        """

        try:
            params = {"document_id": document_id}
            params.update(updates)

            result = self.connection.execute_query(query, params)

            if not result:
                return {"success": False, "error": "Document not found"}

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
        query = """
        MATCH ()-[r:REFERENCES {id: $reference_id}]->()
        DELETE r
        RETURN count(r) as deleted
        """

        try:
            result = self.connection.execute_query(
                query, {"reference_id": reference_id}
            )
            deleted = result[0]["deleted"] if result else 0

            return {
                "success": deleted > 0,
                "deleted_count": deleted,
                "message": f"Deleted {deleted} reference(s)",
            }

        except Exception as e:
            logger.error(f"Failed to delete reference: {str(e)}")
            return {"success": False, "error": str(e)}

    def _update_reference_status(self, reference_id: str, status: ReferenceStatus):
        """Update reference status."""
        query = """
        MATCH ()-[r:REFERENCES {id: $reference_id}]->()
        SET r.status = $status, r.updated_at = datetime()
        """

        try:
            self.connection.execute_query(
                query, {"reference_id": reference_id, "status": status.value}
            )
        except Exception as e:
            logger.error(f"Failed to update reference status: {str(e)}")

    def _format_reference(self, ref_data: Dict) -> Dict[str, Any]:
        """Format reference data for response."""
        ref = ref_data["re"]
        doc = ref_data["doc"]

        return {
            "reference_id": ref["id"],
            "reference_type": ref["reference_type"],
            "status": ref["status"],
            "document": {
                "id": doc["id"],
                "title": doc["title"],
                "file_path": doc["file_path"],
            },
            "location": ref.get("location"),
            "context": ref.get("context"),
            "direction": ref_data.get("direction", "unknown"),
        }

    def _format_node(self, node: Dict) -> Dict[str, Any]:
        """Format node data for graph visualization."""
        return {
            "id": node["id"],
            "label": node["title"],
            "type": "document",
            "properties": {
                "file_path": node["file_path"],
                "document_type": node.get("document_type"),
                "version": node.get("version"),
            },
        }

    def _format_edge(self, rel: Dict) -> Dict[str, Any]:
        """Format edge data for graph visualization."""
        return {
            "id": rel["id"],
            "source": rel.start_node["id"],
            "target": rel.end_node["id"],
            "type": rel["reference_type"],
            "properties": {"status": rel["status"], "context": rel.get("context")},
        }


# Global reference tracker instance
reference_tracker = ReferenceTracker()
