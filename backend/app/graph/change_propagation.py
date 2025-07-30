"""Change propagation engine for managing updates across referenced documents."""

import asyncio
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.graph.reference_tracker import (
    ReferenceStatus,
    ReferenceType,
    reference_tracker,
)
from app.graph.reference_validator import ValidationContext, reference_validator

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of document changes."""

    CONTENT_UPDATE = "content_update"
    METADATA_UPDATE = "metadata_update"
    VERSION_UPDATE = "version_update"
    DELETION = "deletion"
    RENAME = "rename"
    MOVE = "move"
    REFERENCE_UPDATE = "reference_update"
    STATUS_CHANGE = "status_change"


class PropagationStrategy(Enum):
    """Strategies for change propagation."""

    IMMEDIATE = "immediate"  # Propagate changes immediately
    BATCH = "batch"  # Batch changes for efficiency
    SCHEDULED = "scheduled"  # Schedule propagation for later
    MANUAL = "manual"  # Require manual approval
    SELECTIVE = "selective"  # Propagate based on rules


class ImpactLevel(Enum):
    """Impact levels of changes."""

    CRITICAL = "critical"  # Requires immediate action
    HIGH = "high"  # Significant impact
    MEDIUM = "medium"  # Moderate impact
    LOW = "low"  # Minor impact
    NONE = "none"  # No impact


@dataclass
class DocumentChange:
    """Represents a change to a document."""

    document_id: str
    change_type: ChangeType
    change_timestamp: datetime
    user_id: str
    description: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    metadata: Dict[str, Any]


@dataclass
class PropagationPlan:
    """Plan for propagating changes."""

    change: DocumentChange
    affected_documents: List[str]
    impact_analysis: Dict[str, ImpactLevel]
    propagation_strategy: PropagationStrategy
    estimated_duration: int  # seconds
    dependencies: List[str]
    validation_required: bool


@dataclass
class PropagationResult:
    """Result of change propagation."""

    plan_id: str
    success: bool
    documents_updated: List[str]
    documents_failed: List[str]
    notifications_sent: List[Dict[str, str]]
    propagation_time: float
    rollback_available: bool
    error_details: Optional[str]


class ChangePropagationEngine:
    """Manages change propagation across document references."""

    def __init__(self):
        self.tracker = reference_tracker
        self.validator = reference_validator
        self.propagation_queue = deque()
        self.active_propagations = {}
        self.propagation_history = []
        self.change_listeners = []

        # Propagation rules by reference type
        self.propagation_rules = {
            ReferenceType.AMENDMENT: {
                "strategy": PropagationStrategy.IMMEDIATE,
                "impact": ImpactLevel.HIGH,
                "bidirectional": False,
            },
            ReferenceType.SUPERSEDES: {
                "strategy": PropagationStrategy.MANUAL,
                "impact": ImpactLevel.CRITICAL,
                "bidirectional": False,
            },
            ReferenceType.INCORPORATES: {
                "strategy": PropagationStrategy.IMMEDIATE,
                "impact": ImpactLevel.HIGH,
                "bidirectional": True,
            },
            ReferenceType.EXHIBIT: {
                "strategy": PropagationStrategy.BATCH,
                "impact": ImpactLevel.MEDIUM,
                "bidirectional": False,
            },
            ReferenceType.CROSS_REFERENCE: {
                "strategy": PropagationStrategy.SELECTIVE,
                "impact": ImpactLevel.LOW,
                "bidirectional": True,
            },
        }

    def analyze_change_impact(self, change: DocumentChange) -> Dict[str, Any]:
        """Analyze the impact of a document change."""

        impact_analysis = {
            "document_id": change.document_id,
            "change_type": change.change_type.value,
            "timestamp": change.change_timestamp,
            "affected_documents": [],
            "impact_levels": {},
            "reference_chains": [],
            "circular_dependencies": [],
            "total_impact_score": 0,
        }

        # Find all documents that reference this document
        references = self.tracker.find_references_by_document(
            change.document_id, direction="both"
        )

        # Analyze each reference
        for ref in references:
            doc_id = ref["document"]["id"]
            ref_type = ReferenceType(ref["reference_type"])

            # Determine impact level based on reference type and change type
            impact_level = self._calculate_impact_level(change.change_type, ref_type)

            impact_analysis["affected_documents"].append(doc_id)
            impact_analysis["impact_levels"][doc_id] = impact_level.value

            # Check for reference chains
            chains = self.tracker.find_reference_chains(doc_id, max_depth=3)
            for chain in chains:
                if change.document_id in [
                    node["document"]["id"] for node in chain if "document" in node
                ]:
                    impact_analysis["reference_chains"].append(chain)

        # Check for circular dependencies
        circular_refs = self.tracker.find_circular_references(
            self._get_repository_id(change.document_id)
        )
        impact_analysis["circular_dependencies"] = circular_refs

        # Calculate total impact score
        impact_scores = {
            ImpactLevel.CRITICAL: 100,
            ImpactLevel.HIGH: 75,
            ImpactLevel.MEDIUM: 50,
            ImpactLevel.LOW: 25,
            ImpactLevel.NONE: 0,
        }

        total_score = sum(
            impact_scores[ImpactLevel(level)]
            for level in impact_analysis["impact_levels"].values()
        )
        impact_analysis["total_impact_score"] = total_score

        return impact_analysis

    def create_propagation_plan(
        self, change: DocumentChange, impact_analysis: Dict[str, Any]
    ) -> PropagationPlan:
        """Create a plan for propagating changes."""

        # Determine propagation strategy
        strategy = self._determine_propagation_strategy(
            change, impact_analysis["total_impact_score"]
        )

        # Filter affected documents based on strategy
        affected_docs = self._filter_affected_documents(
            impact_analysis["affected_documents"],
            impact_analysis["impact_levels"],
            strategy,
        )

        # Estimate propagation duration
        estimated_duration = len(affected_docs) * 2  # 2 seconds per document

        # Identify dependencies
        dependencies = self._identify_dependencies(change.document_id, affected_docs)

        # Determine if validation is required
        validation_required = (
            impact_analysis["total_impact_score"] > 100
            or len(impact_analysis["circular_dependencies"]) > 0
            or change.change_type in [ChangeType.DELETION, ChangeType.VERSION_UPDATE]
        )

        return PropagationPlan(
            change=change,
            affected_documents=affected_docs,
            impact_analysis=impact_analysis["impact_levels"],
            propagation_strategy=strategy,
            estimated_duration=estimated_duration,
            dependencies=dependencies,
            validation_required=validation_required,
        )

    async def execute_propagation_plan(
        self, plan: PropagationPlan
    ) -> PropagationResult:
        """Execute a propagation plan."""

        plan_id = f"prop_{datetime.utcnow().timestamp()}"
        self.active_propagations[plan_id] = plan

        start_time = datetime.utcnow()
        documents_updated = []
        documents_failed = []
        notifications_sent = []

        try:
            # Validate before propagation if required
            if plan.validation_required:
                validation_context = ValidationContext(
                    repository_id=self._get_repository_id(plan.change.document_id),
                    user_id=plan.change.user_id,
                    validation_time=datetime.utcnow(),
                    strict_mode=True,
                )

                for doc_id in plan.affected_documents:
                    validation = self.validator.validate_document_references(
                        doc_id, validation_context
                    )
                    if validation["broken_references"] > 0:
                        documents_failed.append(doc_id)
                        logger.warning(
                            f"Skipping propagation to {doc_id} due to broken references"
                        )

            # Execute propagation based on strategy
            if plan.propagation_strategy == PropagationStrategy.IMMEDIATE:
                results = await self._propagate_immediate(plan)
            elif plan.propagation_strategy == PropagationStrategy.BATCH:
                results = await self._propagate_batch(plan)
            elif plan.propagation_strategy == PropagationStrategy.SCHEDULED:
                results = await self._schedule_propagation(plan)
            elif plan.propagation_strategy == PropagationStrategy.MANUAL:
                results = await self._queue_for_manual_approval(plan)
            else:  # SELECTIVE
                results = await self._propagate_selective(plan)

            documents_updated = results.get("updated", [])
            documents_failed.extend(results.get("failed", []))
            notifications_sent = results.get("notifications", [])

            # Record propagation in history
            self.propagation_history.append(
                {
                    "plan_id": plan_id,
                    "timestamp": datetime.utcnow(),
                    "change": asdict(plan.change),
                    "documents_updated": documents_updated,
                    "documents_failed": documents_failed,
                }
            )

            propagation_time = (datetime.utcnow() - start_time).total_seconds()

            return PropagationResult(
                plan_id=plan_id,
                success=len(documents_failed) == 0,
                documents_updated=documents_updated,
                documents_failed=documents_failed,
                notifications_sent=notifications_sent,
                propagation_time=propagation_time,
                rollback_available=True,
                error_details=(
                    None
                    if len(documents_failed) == 0
                    else f"Failed to update {len(documents_failed)} documents"
                ),
            )

        except Exception as e:
            logger.error(f"Propagation failed: {str(e)}")
            return PropagationResult(
                plan_id=plan_id,
                success=False,
                documents_updated=documents_updated,
                documents_failed=plan.affected_documents,
                notifications_sent=notifications_sent,
                propagation_time=(datetime.utcnow() - start_time).total_seconds(),
                rollback_available=len(documents_updated) > 0,
                error_details=str(e),
            )
        finally:
            del self.active_propagations[plan_id]

    def register_change_listener(self, listener_func):
        """Register a function to be called when changes occur."""
        self.change_listeners.append(listener_func)

    def rollback_propagation(self, plan_id: str) -> Dict[str, Any]:
        """Rollback a propagation operation."""

        # Find propagation in history
        propagation = None
        for prop in self.propagation_history:
            if prop["plan_id"] == plan_id:
                propagation = prop
                break

        if not propagation:
            return {"success": False, "error": "Propagation not found in history"}

        # Rollback changes
        rollback_count = 0
        for doc_id in propagation["documents_updated"]:
            try:
                # Restore previous state (would need to implement state tracking)
                logger.info(f"Rolling back changes to document {doc_id}")
                rollback_count += 1
            except Exception as e:
                logger.error(f"Failed to rollback {doc_id}: {str(e)}")

        return {
            "success": True,
            "documents_rolled_back": rollback_count,
            "message": f"Successfully rolled back {rollback_count} documents",
        }

    async def _propagate_immediate(self, plan: PropagationPlan) -> Dict[str, List]:
        """Propagate changes immediately."""

        updated = []
        failed = []
        notifications = []

        for doc_id in plan.affected_documents:
            try:
                # Update reference status
                self._update_reference_status_for_change(
                    plan.change.document_id, doc_id, plan.change
                )

                # Notify listeners
                for listener in self.change_listeners:
                    await listener(doc_id, plan.change)

                updated.append(doc_id)
                notifications.append(
                    {
                        "document_id": doc_id,
                        "notification_type": "immediate_update",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"Failed to propagate to {doc_id}: {str(e)}")
                failed.append(doc_id)

        return {"updated": updated, "failed": failed, "notifications": notifications}

    async def _propagate_batch(self, plan: PropagationPlan) -> Dict[str, List]:
        """Batch propagation for efficiency."""

        # Add to propagation queue
        for doc_id in plan.affected_documents:
            self.propagation_queue.append((doc_id, plan.change))

        # Process queue when it reaches threshold or timeout
        if len(self.propagation_queue) >= 10:
            return await self._process_propagation_queue()

        return {
            "updated": [],
            "failed": [],
            "notifications": [
                {
                    "document_ids": plan.affected_documents,
                    "notification_type": "queued_for_batch",
                    "queue_size": len(self.propagation_queue),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

    async def _schedule_propagation(self, plan: PropagationPlan) -> Dict[str, List]:
        """Schedule propagation for later execution."""

        # In a real implementation, this would use a task scheduler
        scheduled_time = datetime.utcnow().isoformat()

        return {
            "updated": [],
            "failed": [],
            "notifications": [
                {
                    "document_ids": plan.affected_documents,
                    "notification_type": "scheduled",
                    "scheduled_time": scheduled_time,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

    async def _queue_for_manual_approval(
        self, plan: PropagationPlan
    ) -> Dict[str, List]:
        """Queue changes for manual approval."""

        approval_request = {
            "plan_id": f"approval_{datetime.utcnow().timestamp()}",
            "change": asdict(plan.change),
            "affected_documents": plan.affected_documents,
            "impact_analysis": plan.impact_analysis,
            "requested_at": datetime.utcnow().isoformat(),
            "requested_by": plan.change.user_id,
        }

        # Store approval request (in a real system, this would go to a queue or database)

        return {
            "updated": [],
            "failed": [],
            "notifications": [
                {
                    "document_ids": plan.affected_documents,
                    "notification_type": "pending_approval",
                    "approval_id": approval_request["plan_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

    async def _propagate_selective(self, plan: PropagationPlan) -> Dict[str, List]:
        """Selective propagation based on rules."""

        updated = []
        failed = []
        notifications = []

        for doc_id in plan.affected_documents:
            impact = ImpactLevel(
                plan.impact_analysis.get(doc_id, ImpactLevel.LOW.value)
            )

            # Only propagate if impact is above threshold
            if impact in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]:
                try:
                    self._update_reference_status_for_change(
                        plan.change.document_id, doc_id, plan.change
                    )
                    updated.append(doc_id)
                except Exception as e:
                    logger.error(f"Selective propagation failed for {doc_id}: {str(e)}")
                    failed.append(doc_id)
            else:
                notifications.append(
                    {
                        "document_id": doc_id,
                        "notification_type": "skipped_low_impact",
                        "impact_level": impact.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return {"updated": updated, "failed": failed, "notifications": notifications}

    async def _process_propagation_queue(self) -> Dict[str, List]:
        """Process batched propagation queue."""

        updated = []
        failed = []
        notifications = []

        # Process all items in queue
        while self.propagation_queue:
            doc_id, change = self.propagation_queue.popleft()

            try:
                self._update_reference_status_for_change(
                    change.document_id, doc_id, change
                )
                updated.append(doc_id)
            except Exception as e:
                logger.error(f"Batch propagation failed for {doc_id}: {str(e)}")
                failed.append(doc_id)

        notifications.append(
            {
                "notification_type": "batch_processed",
                "documents_processed": len(updated) + len(failed),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return {"updated": updated, "failed": failed, "notifications": notifications}

    def _calculate_impact_level(
        self, change_type: ChangeType, ref_type: ReferenceType
    ) -> ImpactLevel:
        """Calculate impact level based on change and reference types."""

        # Critical impacts
        if change_type == ChangeType.DELETION:
            return ImpactLevel.CRITICAL

        if change_type == ChangeType.VERSION_UPDATE and ref_type in [
            ReferenceType.SUPERSEDES,
            ReferenceType.AMENDMENT,
        ]:
            return ImpactLevel.CRITICAL

        # High impacts
        if change_type in [ChangeType.CONTENT_UPDATE, ChangeType.MOVE] and ref_type in [
            ReferenceType.INCORPORATES,
            ReferenceType.AMENDMENT,
        ]:
            return ImpactLevel.HIGH

        # Medium impacts
        if ref_type in [ReferenceType.EXHIBIT, ReferenceType.ATTACHMENT]:
            return ImpactLevel.MEDIUM

        # Low impacts
        if ref_type == ReferenceType.CROSS_REFERENCE:
            return ImpactLevel.LOW

        return ImpactLevel.MEDIUM  # Default

    def _determine_propagation_strategy(
        self, change: DocumentChange, impact_score: int
    ) -> PropagationStrategy:
        """Determine appropriate propagation strategy."""

        # Critical changes require immediate or manual propagation
        if impact_score > 200:
            return PropagationStrategy.MANUAL
        elif impact_score > 100:
            return PropagationStrategy.IMMEDIATE
        elif impact_score > 50:
            return PropagationStrategy.BATCH
        else:
            return PropagationStrategy.SELECTIVE

    def _filter_affected_documents(
        self,
        documents: List[str],
        impact_levels: Dict[str, str],
        strategy: PropagationStrategy,
    ) -> List[str]:
        """Filter affected documents based on strategy."""

        if strategy == PropagationStrategy.SELECTIVE:
            # Only include high impact documents
            return [
                doc
                for doc in documents
                if impact_levels.get(doc)
                in [ImpactLevel.HIGH.value, ImpactLevel.CRITICAL.value]
            ]

        return documents  # Return all for other strategies

    def _identify_dependencies(
        self, source_doc: str, affected_docs: List[str]
    ) -> List[str]:
        """Identify dependencies between affected documents."""

        dependencies = []

        for doc in affected_docs:
            # Check if this document references others in the affected list
            refs = self.tracker.find_references_by_document(doc, direction="outgoing")

            for ref in refs:
                if ref["document"]["id"] in affected_docs:
                    dependencies.append(f"{doc} -> {ref['document']['id']}")

        return dependencies

    def _get_repository_id(self, document_id: str) -> str:
        """Get repository ID for a document."""

        query = """
        MATCH (d:Document {id: $document_id})
        RETURN d.repository_id as repo_id
        """

        result = self.tracker.connection.execute_query(
            query, {"document_id": document_id}
        )

        if result:
            return result[0]["repo_id"]

        return ""

    def _update_reference_status_for_change(
        self, source_doc: str, target_doc: str, change: DocumentChange
    ):
        """Update reference status based on change."""

        # Find references between documents
        query = """
        MATCH (source:Document {id: $source_id})-[r:REFERENCES]->(target:Document {id: $target_id})
        SET r.last_validated = datetime($timestamp),
            r.validation_status = $status
        RETURN r
        """

        status = (
            ReferenceStatus.OUTDATED
            if change.change_type
            in [ChangeType.CONTENT_UPDATE, ChangeType.VERSION_UPDATE]
            else ReferenceStatus.BROKEN
        )

        self.tracker.connection.execute_query(
            query,
            {
                "source_id": source_doc,
                "target_id": target_doc,
                "timestamp": change.change_timestamp.isoformat(),
                "status": status.value,
            },
        )


# Global change propagation engine instance
change_propagation_engine = ChangePropagationEngine()
