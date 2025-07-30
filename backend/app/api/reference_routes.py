"""API routes for cross-document reference management."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.api.auth_routes import get_current_user_id
from app.graph.change_propagation import (
    ChangeType,
    DocumentChange,
    change_propagation_engine,
)
from app.graph.reference_tracker import (
    DocumentNode,
    ReferenceEdge,
    ReferenceStatus,
    ReferenceType,
    reference_tracker,
)
from app.graph.reference_validator import (
    ValidationContext,
    reference_validator,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/references", tags=["cross-document references"])


class CreateDocumentRequest(BaseModel):
    """Request to create a document node."""

    repository_id: str
    file_path: str
    title: str
    version: str = "1.0.0"
    content_hash: str
    document_type: str = "general"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CreateReferenceRequest(BaseModel):
    """Request to create a reference."""

    source_document_id: str
    target_document_id: str
    reference_type: str
    location: Dict[str, Any] = Field(default_factory=dict)
    context: str = ""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExtractReferencesRequest(BaseModel):
    """Request to extract references from content."""

    document_id: str
    content: str
    document_type: str = "general"
    auto_create: bool = False


class DocumentChangeRequest(BaseModel):
    """Request to notify about document change."""

    document_id: str
    change_type: str
    description: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ValidateReferencesRequest(BaseModel):
    """Request to validate references."""

    document_id: Optional[str] = None
    repository_id: Optional[str] = None
    strict_mode: bool = False
    max_depth: int = 5


@router.post("/documents")
async def create_document_node(
    request: CreateDocumentRequest, user_id: str = Depends(get_current_user_id)
):
    """Create a document node in the reference graph."""

    try:
        document = DocumentNode(
            id=f"doc_{request.repository_id}_{request.file_path.replace('/', '_')}",
            repository_id=request.repository_id,
            file_path=request.file_path,
            title=request.title,
            version=request.version,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            content_hash=request.content_hash,
            document_type=request.document_type,
            metadata=request.metadata,
        )

        result = reference_tracker.create_document_node(document)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error"))

        return result

    except Exception as e:
        logger.error(f"Failed to create document node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_reference(
    request: CreateReferenceRequest, user_id: str = Depends(get_current_user_id)
):
    """Create a reference between documents."""

    try:
        # Validate reference type
        try:
            ref_type = ReferenceType(request.reference_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reference type: {request.reference_type}",
            )

        reference = ReferenceEdge(
            id=f"ref_{datetime.utcnow().timestamp()}",
            source_doc_id=request.source_document_id,
            target_doc_id=request.target_document_id,
            reference_type=ref_type,
            status=ReferenceStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            location=request.location,
            context=request.context,
            metadata=request.metadata,
        )

        result = reference_tracker.create_reference(reference)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error"))

        # Validate the new reference
        validation_context = ValidationContext(
            repository_id="",  # Will be fetched from document
            user_id=user_id,
            validation_time=datetime.utcnow(),
        )

        validation = reference_validator.validate_reference(
            result["reference_id"], validation_context
        )

        return {
            **result,
            "validation": {
                "is_valid": validation.is_valid,
                "status": validation.status.value,
                "issues": validation.issues,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create reference: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{document_id}")
async def get_document_references(
    document_id: str,
    direction: str = Query("both", regex="^(incoming|outgoing|both)$"),
    user_id: str = Depends(get_current_user_id),
):
    """Get all references for a document."""

    try:
        references = reference_tracker.find_references_by_document(
            document_id, direction
        )

        return {
            "document_id": document_id,
            "direction": direction,
            "total_references": len(references),
            "references": references,
        }

    except Exception as e:
        logger.error(f"Failed to get document references: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains/{document_id}")
async def get_reference_chains(
    document_id: str,
    max_depth: int = Query(3, ge=1, le=10),
    user_id: str = Depends(get_current_user_id),
):
    """Get reference chains starting from a document."""

    try:
        chains = reference_tracker.find_reference_chains(document_id, max_depth)

        return {
            "document_id": document_id,
            "max_depth": max_depth,
            "total_chains": len(chains),
            "chains": chains,
        }

    except Exception as e:
        logger.error(f"Failed to get reference chains: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/{document_id}")
async def get_reference_graph(
    document_id: str,
    depth: int = Query(2, ge=1, le=5),
    user_id: str = Depends(get_current_user_id),
):
    """Get reference graph centered on a document."""

    try:
        graph = reference_tracker.get_reference_graph(document_id, depth)
        return graph

    except Exception as e:
        logger.error(f"Failed to get reference graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_references(
    request: ExtractReferencesRequest, user_id: str = Depends(get_current_user_id)
):
    """Extract references from document content."""

    try:
        extracted_refs = reference_validator.extract_references(
            request.content, request.document_type
        )

        created_refs = []
        if request.auto_create:
            for ref in extracted_refs:
                result = reference_validator.create_reference_from_extraction(
                    request.document_id, ref
                )
                if result["success"]:
                    created_refs.append(result)

        return {
            "document_id": request.document_id,
            "total_extracted": len(extracted_refs),
            "extracted_references": extracted_refs,
            "auto_created": len(created_refs),
            "created_references": created_refs,
        }

    except Exception as e:
        logger.error(f"Failed to extract references: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_references(
    request: ValidateReferencesRequest, user_id: str = Depends(get_current_user_id)
):
    """Validate document references."""

    try:
        context = ValidationContext(
            repository_id=request.repository_id or "",
            user_id=user_id,
            validation_time=datetime.utcnow(),
            strict_mode=request.strict_mode,
            max_depth=request.max_depth,
        )

        if request.document_id:
            # Validate single document
            result = reference_validator.validate_document_references(
                request.document_id, context
            )
            return result

        elif request.repository_id:
            # Validate entire repository
            result = reference_validator.validate_repository(
                request.repository_id, context
            )
            return {
                "repository_id": request.repository_id,
                "validation_time": result.validation_time,
                "total_references": result.total_references,
                "valid_references": result.valid_references,
                "broken_references": result.broken_references,
                "outdated_references": result.outdated_references,
                "issues_by_document": result.issues_by_document,
                "recommendations": result.recommendations,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Either document_id or repository_id must be provided",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate references: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/changes/notify")
async def notify_document_change(
    request: DocumentChangeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """Notify system of a document change for propagation."""

    try:
        # Validate change type
        try:
            change_type = ChangeType(request.change_type)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid change type: {request.change_type}"
            )

        change = DocumentChange(
            document_id=request.document_id,
            change_type=change_type,
            change_timestamp=datetime.utcnow(),
            user_id=user_id,
            description=request.description,
            old_value=request.old_value,
            new_value=request.new_value,
            metadata=request.metadata,
        )

        # Analyze impact
        impact_analysis = change_propagation_engine.analyze_change_impact(change)

        # Create propagation plan
        plan = change_propagation_engine.create_propagation_plan(
            change, impact_analysis
        )

        # Execute propagation in background
        background_tasks.add_task(
            change_propagation_engine.execute_propagation_plan, plan
        )

        return {
            "change_acknowledged": True,
            "impact_analysis": impact_analysis,
            "propagation_plan": {
                "strategy": plan.propagation_strategy.value,
                "affected_documents": len(plan.affected_documents),
                "estimated_duration": plan.estimated_duration,
                "validation_required": plan.validation_required,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process document change: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circular/{repository_id}")
async def detect_circular_references(
    repository_id: str, user_id: str = Depends(get_current_user_id)
):
    """Detect circular references in a repository."""

    try:
        circular_refs = reference_tracker.find_circular_references(repository_id)

        return {
            "repository_id": repository_id,
            "circular_references_found": len(circular_refs) > 0,
            "circular_chains": circular_refs,
        }

    except Exception as e:
        logger.error(f"Failed to detect circular references: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{reference_id}")
async def update_reference(
    reference_id: str,
    status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id),
):
    """Update a reference."""

    try:
        updates = {}

        if status:
            try:
                ReferenceStatus(status)  # Validate
                updates["status"] = status
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if metadata:
            updates["metadata"] = metadata

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Update in Neo4j
        query = """
        MATCH ()-[r:REFERENCES {id: $reference_id}]->()
        SET r += $updates, r.updated_at = datetime()
        RETURN r
        """

        result = reference_tracker.connection.execute_query(
            query, {"reference_id": reference_id, "updates": updates}
        )

        if not result:
            raise HTTPException(status_code=404, detail="Reference not found")

        return {"success": True, "reference_id": reference_id, "updates": updates}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update reference: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{reference_id}")
async def delete_reference(
    reference_id: str, user_id: str = Depends(get_current_user_id)
):
    """Delete a reference."""

    try:
        result = reference_tracker.delete_reference(reference_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail="Reference not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete reference: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/{repository_id}")
async def get_reference_statistics(
    repository_id: str, user_id: str = Depends(get_current_user_id)
):
    """Get reference statistics for a repository."""

    try:
        # Get general statistics
        stats = reference_tracker.connection.get_statistics()

        # Get repository-specific statistics
        query = """
        MATCH (d:Document {repository_id: $repo_id})
        OPTIONAL MATCH (d)-[r:REFERENCES]->()
        WITH count(DISTINCT d) as doc_count, count(r) as ref_count
        RETURN doc_count, ref_count
        """

        result = reference_tracker.connection.execute_query(
            query, {"repo_id": repository_id}
        )

        if result:
            repo_stats = result[0]
            stats.update(
                {
                    "repository_document_count": repo_stats["doc_count"],
                    "repository_reference_count": repo_stats["ref_count"],
                }
            )

        return {"repository_id": repository_id, "statistics": stats}

    except Exception as e:
        logger.error(f"Failed to get reference statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
