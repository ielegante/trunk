"""Template workflow management system for legal document processing.

This module provides comprehensive workflow management for template creation,
approval, deployment, and lifecycle management with security controls and
audit trails.
"""

import json
import logging
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .manager import Template, TemplateManager
from .redaction import DocumentSanitizer, RedactionEngine, RedactionReport
from .security import PermissionType, SecurityContext, SecurityLevel, SecurityManager

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Template workflow status states."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class WorkflowAction(Enum):
    """Actions that can be performed in template workflow."""

    CREATE = "create"
    SUBMIT_FOR_REVIEW = "submit_for_review"
    ASSIGN_REVIEWER = "assign_reviewer"
    APPROVE = "approve"
    REJECT = "reject"
    DEPLOY = "deploy"
    DEPRECATE = "deprecate"
    ARCHIVE = "archive"
    UPDATE = "update"
    REDACT = "redact"
    SANITIZE = "sanitize"


class ReviewType(Enum):
    """Types of template reviews."""

    LEGAL_REVIEW = "legal_review"
    SECURITY_REVIEW = "security_review"
    COMPLIANCE_REVIEW = "compliance_review"
    TECHNICAL_REVIEW = "technical_review"
    FINAL_APPROVAL = "final_approval"


@dataclass
class WorkflowStep:
    """Individual step in template workflow."""

    step_id: str
    step_name: str
    step_type: ReviewType
    required_role: str
    required_permissions: List[PermissionType]
    is_parallel: bool = False
    timeout_hours: Optional[int] = None
    auto_approve_conditions: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowInstance:
    """Active workflow instance for a template."""

    workflow_id: str
    template_name: str
    template_version: str
    status: WorkflowStatus
    current_step: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    assigned_reviewers: Dict[str, str]  # step_id -> user_id
    completed_steps: List[str]
    pending_steps: List[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


@dataclass
class WorkflowEvent:
    """Event in template workflow process."""

    event_id: str
    workflow_id: str
    action: WorkflowAction
    actor_id: str
    timestamp: datetime
    step_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["action"] = self.action.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class ApprovalDecision:
    """Approval decision for workflow step."""

    decision_id: str
    workflow_id: str
    step_id: str
    reviewer_id: str
    decision: str  # "approved", "rejected", "needs_changes"
    timestamp: datetime
    comment: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class TemplateWorkflowManager:
    """Manages template workflows with security and compliance controls."""

    def __init__(
        self,
        template_manager: TemplateManager,
        security_manager: SecurityManager,
        redaction_engine: RedactionEngine,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize workflow manager.

        Args:
            template_manager: Template management system
            security_manager: Security control system
            redaction_engine: Document redaction system
            config: Configuration options
        """
        self.template_manager = template_manager
        self.security_manager = security_manager
        self.redaction_engine = redaction_engine
        self.sanitizer = DocumentSanitizer()

        self.config = config or {}

        # Workflow storage
        self.workflows: Dict[str, WorkflowInstance] = {}
        self.workflow_events: List[WorkflowEvent] = []
        self.approval_decisions: List[ApprovalDecision] = {}

        # Configuration
        self.auto_approval_enabled = self.config.get("auto_approval_enabled", False)
        self.parallel_reviews_enabled = self.config.get(
            "parallel_reviews_enabled", True
        )
        self.default_review_timeout_hours = self.config.get(
            "default_review_timeout_hours", 72
        )

        # Initialize default workflow steps
        self._initialize_default_workflow()

    def _initialize_default_workflow(self):
        """Initialize default template workflow steps."""
        self.default_workflow_steps = [
            WorkflowStep(
                step_id="security_review",
                step_name="Security Review",
                step_type=ReviewType.SECURITY_REVIEW,
                required_role="security_reviewer",
                required_permissions=[PermissionType.READ, PermissionType.EXECUTE],
                timeout_hours=24,
                auto_approve_conditions={
                    "no_sensitive_data": True,
                    "no_dangerous_constructs": True,
                },
            ),
            WorkflowStep(
                step_id="legal_review",
                step_name="Legal Review",
                step_type=ReviewType.LEGAL_REVIEW,
                required_role="legal_reviewer",
                required_permissions=[PermissionType.READ, PermissionType.EXECUTE],
                is_parallel=True,
                timeout_hours=48,
            ),
            WorkflowStep(
                step_id="compliance_review",
                step_name="Compliance Review",
                step_type=ReviewType.COMPLIANCE_REVIEW,
                required_role="compliance_officer",
                required_permissions=[PermissionType.READ, PermissionType.EXECUTE],
                is_parallel=True,
                timeout_hours=48,
            ),
            WorkflowStep(
                step_id="final_approval",
                step_name="Final Approval",
                step_type=ReviewType.FINAL_APPROVAL,
                required_role="template_admin",
                required_permissions=[PermissionType.ADMIN],
                timeout_hours=24,
            ),
        ]

    def create_template_workflow(
        self,
        template_name: str,
        template_content: str,
        template_metadata: Dict[str, Any],
        context: SecurityContext,
        workflow_steps: Optional[List[WorkflowStep]] = None,
    ) -> WorkflowInstance:
        """Create new template workflow instance.

        Args:
            template_name: Name of the template
            template_content: Template content
            template_metadata: Template metadata
            context: Security context
            workflow_steps: Custom workflow steps (optional)

        Returns:
            Created workflow instance
        """
        # Validate security context
        if not self.security_manager.check_access(
            context, f"templates/{template_name}", PermissionType.WRITE
        ):
            raise PermissionError(
                f"User {context.user_id} does not have permission to create templates"
            )

        # Generate workflow ID
        workflow_id = f"wf_{secrets.token_hex(8)}"

        # Use default workflow steps if none provided
        steps = workflow_steps or self.default_workflow_steps

        # Perform initial security validation
        security_findings = self._validate_template_security(template_content)

        # Perform redaction scan
        redaction_matches = self.redaction_engine.scan_for_sensitive_information(
            template_content
        )

        # Sanitize content
        sanitized_content, removed_elements = self.sanitizer.sanitize_content(
            template_content
        )

        # Determine initial status based on findings
        initial_status = WorkflowStatus.DRAFT
        if (
            security_findings["is_safe"]
            and not redaction_matches
            and not removed_elements
        ):
            initial_status = WorkflowStatus.PENDING_REVIEW

        # Create workflow instance
        workflow = WorkflowInstance(
            workflow_id=workflow_id,
            template_name=template_name,
            template_version="1.0",
            status=initial_status,
            current_step=steps[0].step_id if steps else None,
            created_by=context.user_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            assigned_reviewers={},
            completed_steps=[],
            pending_steps=[step.step_id for step in steps],
            metadata={
                "original_content": template_content,
                "sanitized_content": sanitized_content,
                "template_metadata": template_metadata,
                "security_findings": security_findings,
                "redaction_matches": [match.to_dict() for match in redaction_matches],
                "removed_elements": removed_elements,
                "workflow_steps": [asdict(step) for step in steps],
            },
        )

        self.workflows[workflow_id] = workflow

        # Log workflow creation
        self._log_workflow_event(
            workflow_id=workflow_id,
            action=WorkflowAction.CREATE,
            actor_id=context.user_id,
            details={
                "template_name": template_name,
                "security_score": security_findings.get("severity", "unknown"),
                "sensitive_data_found": len(redaction_matches) > 0,
                "elements_removed": len(removed_elements),
            },
        )

        logger.info(
            f"Created workflow {workflow_id} for template {template_name} by {context.user_id}"
        )

        return workflow

    def submit_for_review(
        self,
        workflow_id: str,
        context: SecurityContext,
        reviewer_assignments: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Submit template for review process.

        Args:
            workflow_id: Workflow identifier
            context: Security context
            reviewer_assignments: Optional reviewer assignments {step_id: user_id}

        Returns:
            True if successfully submitted
        """
        workflow = self._get_workflow(workflow_id)

        # Validate permissions
        if workflow.created_by != context.user_id and not context.has_permission(
            PermissionType.ADMIN
        ):
            raise PermissionError(
                "Only template creator or admin can submit for review"
            )

        # Validate current status
        if workflow.status not in [WorkflowStatus.DRAFT, WorkflowStatus.REJECTED]:
            raise ValueError(
                f"Cannot submit workflow in status {workflow.status.value}"
            )

        # Update status
        workflow.status = WorkflowStatus.PENDING_REVIEW
        workflow.updated_at = datetime.now()

        # Assign reviewers
        if reviewer_assignments:
            workflow.assigned_reviewers.update(reviewer_assignments)

        # Auto-assign reviewers for unassigned steps
        self._auto_assign_reviewers(workflow, context)

        # Log event
        self._log_workflow_event(
            workflow_id=workflow_id,
            action=WorkflowAction.SUBMIT_FOR_REVIEW,
            actor_id=context.user_id,
            details={"assigned_reviewers": workflow.assigned_reviewers},
        )

        # Check for auto-approval
        if self.auto_approval_enabled:
            self._check_auto_approval(workflow)

        logger.info(f"Submitted workflow {workflow_id} for review")

        return True

    def review_template(
        self,
        workflow_id: str,
        step_id: str,
        decision: str,
        context: SecurityContext,
        comment: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Review template in workflow step.

        Args:
            workflow_id: Workflow identifier
            step_id: Workflow step identifier
            decision: Review decision ("approved", "rejected", "needs_changes")
            context: Security context
            comment: Optional review comment
            conditions: Optional approval conditions

        Returns:
            True if review completed successfully
        """
        workflow = self._get_workflow(workflow_id)

        # Validate reviewer assignment
        if workflow.assigned_reviewers.get(step_id) != context.user_id:
            if not context.has_permission(PermissionType.ADMIN):
                raise PermissionError("User is not assigned to review this step")

        # Validate workflow status
        if workflow.status not in [
            WorkflowStatus.PENDING_REVIEW,
            WorkflowStatus.IN_REVIEW,
        ]:
            raise ValueError(
                f"Cannot review workflow in status {workflow.status.value}"
            )

        # Find workflow step
        step = self._get_workflow_step(workflow, step_id)
        if not step:
            raise ValueError(f"Workflow step {step_id} not found")

        # Validate reviewer permissions
        if not context.has_permission(PermissionType.EXECUTE):
            raise PermissionError("Insufficient permissions for review")

        # Record approval decision
        decision_id = f"dec_{secrets.token_hex(8)}"
        approval_decision = ApprovalDecision(
            decision_id=decision_id,
            workflow_id=workflow_id,
            step_id=step_id,
            reviewer_id=context.user_id,
            decision=decision,
            timestamp=datetime.now(),
            comment=comment,
            conditions=conditions,
        )

        self.approval_decisions[decision_id] = approval_decision

        # Update workflow based on decision
        if decision == "approved":
            if step_id in workflow.pending_steps:
                workflow.pending_steps.remove(step_id)
            workflow.completed_steps.append(step_id)

            # Check if all steps completed
            if not workflow.pending_steps:
                workflow.status = WorkflowStatus.APPROVED
                workflow.current_step = None
            else:
                workflow.status = WorkflowStatus.IN_REVIEW
                workflow.current_step = workflow.pending_steps[0]

        elif decision == "rejected":
            workflow.status = WorkflowStatus.REJECTED
            workflow.current_step = None

        elif decision == "needs_changes":
            workflow.status = WorkflowStatus.DRAFT
            workflow.current_step = (
                workflow.pending_steps[0] if workflow.pending_steps else None
            )

        workflow.updated_at = datetime.now()

        # Log review event
        action = (
            WorkflowAction.APPROVE if decision == "approved" else WorkflowAction.REJECT
        )
        self._log_workflow_event(
            workflow_id=workflow_id,
            action=action,
            actor_id=context.user_id,
            step_id=step_id,
            details={
                "decision": decision,
                "comment": comment,
                "conditions": conditions,
            },
            comment=comment,
        )

        logger.info(
            f"Review completed for workflow {workflow_id}, step {step_id}: {decision}"
        )

        return True

    def deploy_template(
        self,
        workflow_id: str,
        context: SecurityContext,
        deployment_target: str = "production",
    ) -> str:
        """Deploy approved template to specified environment.

        Args:
            workflow_id: Workflow identifier
            context: Security context
            deployment_target: Target environment

        Returns:
            Template path in deployment environment
        """
        workflow = self._get_workflow(workflow_id)

        # Validate permissions
        if not context.has_permission(PermissionType.ADMIN):
            raise PermissionError("Only admins can deploy templates")

        # Validate workflow status
        if workflow.status != WorkflowStatus.APPROVED:
            raise ValueError(
                f"Cannot deploy workflow in status {workflow.status.value}"
            )

        # Get sanitized template content
        template_content = workflow.metadata.get("sanitized_content")
        if not template_content:
            raise ValueError("No sanitized content available for deployment")

        # Create template
        template_path = (
            self.template_manager.templates_directory
            / deployment_target
            / f"{workflow.template_name}.md"
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)

        # Write template content
        template_path.write_text(template_content, encoding="utf-8")

        # Register template
        template = Template(
            name=workflow.template_name,
            path=template_path,
            category=workflow.metadata.get("template_metadata", {}).get(
                "category", "general"
            ),
            variables=workflow.metadata.get("template_metadata", {}).get(
                "variables", []
            ),
            metadata={
                **workflow.metadata.get("template_metadata", {}),
                "workflow_id": workflow_id,
                "deployment_target": deployment_target,
                "deployed_at": datetime.now().isoformat(),
                "deployed_by": context.user_id,
            },
            version=workflow.template_version,
        )

        self.template_manager.register_template(template)

        # Update workflow status
        workflow.status = WorkflowStatus.DEPLOYED
        workflow.updated_at = datetime.now()
        workflow.metadata["deployment_target"] = deployment_target
        workflow.metadata["deployment_path"] = str(template_path)

        # Log deployment
        self._log_workflow_event(
            workflow_id=workflow_id,
            action=WorkflowAction.DEPLOY,
            actor_id=context.user_id,
            details={
                "deployment_target": deployment_target,
                "template_path": str(template_path),
            },
        )

        logger.info(
            f"Deployed template {workflow.template_name} from workflow {workflow_id}"
        )

        return str(template_path)

    def redact_template_content(
        self,
        workflow_id: str,
        redaction_rules: Optional[List[str]] = None,
        context: Optional[SecurityContext] = None,
    ) -> Tuple[str, RedactionReport]:
        """Apply redaction to template content.

        Args:
            workflow_id: Workflow identifier
            redaction_rules: Optional list of redaction rule categories
            context: Security context

        Returns:
            Tuple of (redacted_content, redaction_report)
        """
        workflow = self._get_workflow(workflow_id)

        if context and not context.has_permission(PermissionType.EXECUTE):
            raise PermissionError("Insufficient permissions for redaction")

        # Get template content
        template_content = workflow.metadata.get(
            "sanitized_content"
        ) or workflow.metadata.get("original_content")
        if not template_content:
            raise ValueError("No template content available for redaction")

        # Apply redaction
        redacted_content, redaction_report = self.redaction_engine.redact_document(
            content=template_content,
            document_id=workflow_id,
            operator_id=context.user_id if context else "system",
            rule_categories=redaction_rules,
        )

        # Update workflow metadata
        workflow.metadata["redacted_content"] = redacted_content
        workflow.metadata["redaction_report"] = redaction_report.to_dict()
        workflow.updated_at = datetime.now()

        # Log redaction
        self._log_workflow_event(
            workflow_id=workflow_id,
            action=WorkflowAction.REDACT,
            actor_id=context.user_id if context else "system",
            details={
                "redaction_count": redaction_report.redaction_count,
                "rule_categories": redaction_rules,
            },
        )

        return redacted_content, redaction_report

    def create_template_from_redaction(
        self, workflow_id: str, template_name: str, context: SecurityContext
    ) -> Dict[str, Any]:
        """Create template from redacted document.

        Args:
            workflow_id: Workflow identifier
            template_name: Name for new template
            context: Security context

        Returns:
            Template definition
        """
        workflow = self._get_workflow(workflow_id)

        if not context.has_permission(PermissionType.WRITE):
            raise PermissionError("Insufficient permissions to create templates")

        # Get redaction report
        redaction_report_data = workflow.metadata.get("redaction_report")
        if not redaction_report_data:
            raise ValueError("No redaction report available")

        # Reconstruct redaction report
        from .redaction import RedactionMatch, RedactionType, SensitivityLevel

        matches = []
        for match_data in redaction_report_data.get("matches", []):
            match = RedactionMatch(
                rule_id=match_data["rule_id"],
                start_pos=match_data["start_pos"],
                end_pos=match_data["end_pos"],
                original_text=match_data["original_text"],
                redacted_text=match_data["redacted_text"],
                redaction_type=RedactionType(match_data["redaction_type"]),
                sensitivity_level=SensitivityLevel(match_data["sensitivity_level"]),
            )
            matches.append(match)

        redaction_report = RedactionReport(
            document_id=redaction_report_data["document_id"],
            original_length=redaction_report_data["original_length"],
            redacted_length=redaction_report_data["redacted_length"],
            redaction_count=redaction_report_data["redaction_count"],
            matches=matches,
            rules_applied=redaction_report_data["rules_applied"],
            sensitivity_levels_found=[
                SensitivityLevel(level)
                for level in redaction_report_data["sensitivity_levels_found"]
            ],
            redaction_timestamp=datetime.fromisoformat(
                redaction_report_data["redaction_timestamp"]
            ),
            operator_id=redaction_report_data["operator_id"],
        )

        # Get redacted content
        redacted_content = workflow.metadata.get("redacted_content")
        if not redacted_content:
            raise ValueError("No redacted content available")

        # Create template definition
        template_definition = (
            self.redaction_engine.create_template_from_redacted_document(
                redacted_content=redacted_content,
                redaction_report=redaction_report,
                template_name=template_name,
            )
        )

        # Update workflow metadata
        workflow.metadata["template_definition"] = template_definition
        workflow.updated_at = datetime.now()

        logger.info(f"Created template definition from redacted workflow {workflow_id}")

        return template_definition

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get comprehensive workflow status information.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow status information
        """
        workflow = self._get_workflow(workflow_id)

        # Get workflow events
        events = [
            event for event in self.workflow_events if event.workflow_id == workflow_id
        ]

        # Get approval decisions
        decisions = [
            decision
            for decision in self.approval_decisions.values()
            if decision.workflow_id == workflow_id
        ]

        # Calculate progress
        total_steps = len(workflow.pending_steps) + len(workflow.completed_steps)
        progress_percentage = (
            (len(workflow.completed_steps) / total_steps * 100)
            if total_steps > 0
            else 0
        )

        return {
            "workflow": workflow.to_dict(),
            "progress": {
                "percentage": progress_percentage,
                "completed_steps": len(workflow.completed_steps),
                "total_steps": total_steps,
                "current_step": workflow.current_step,
            },
            "events": [event.to_dict() for event in events[-10:]],  # Last 10 events
            "decisions": [asdict(decision) for decision in decisions],
            "reviewers": workflow.assigned_reviewers,
            "timeline": self._calculate_workflow_timeline(workflow, events),
        }

    def get_pending_reviews(self, context: SecurityContext) -> List[Dict[str, Any]]:
        """Get workflows pending review by the user.

        Args:
            context: Security context

        Returns:
            List of workflows pending review
        """
        pending_workflows = []

        for workflow in self.workflows.values():
            if workflow.status in [
                WorkflowStatus.PENDING_REVIEW,
                WorkflowStatus.IN_REVIEW,
            ]:
                # Check if user is assigned as reviewer
                for step_id, reviewer_id in workflow.assigned_reviewers.items():
                    if (
                        reviewer_id == context.user_id
                        and step_id in workflow.pending_steps
                    ):
                        pending_workflows.append(
                            {
                                "workflow_id": workflow.workflow_id,
                                "template_name": workflow.template_name,
                                "status": workflow.status.value,
                                "step_id": step_id,
                                "created_at": workflow.created_at.isoformat(),
                                "created_by": workflow.created_by,
                                "priority": self._calculate_workflow_priority(workflow),
                            }
                        )

        # Sort by priority and creation date
        pending_workflows.sort(
            key=lambda w: (w["priority"], w["created_at"]), reverse=True
        )

        return pending_workflows

    def _get_workflow(self, workflow_id: str) -> WorkflowInstance:
        """Get workflow instance by ID."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        return self.workflows[workflow_id]

    def _get_workflow_step(
        self, workflow: WorkflowInstance, step_id: str
    ) -> Optional[WorkflowStep]:
        """Get workflow step definition."""
        steps_data = workflow.metadata.get("workflow_steps", [])
        for step_data in steps_data:
            if step_data["step_id"] == step_id:
                return WorkflowStep(**step_data)
        return None

    def _validate_template_security(self, content: str) -> Dict[str, Any]:
        """Validate template content for security issues."""
        from .security import SecureTemplateValidator

        validator = SecureTemplateValidator()
        return validator.validate_template_content(content)

    def _auto_assign_reviewers(
        self, workflow: WorkflowInstance, context: SecurityContext
    ):
        """Auto-assign reviewers for workflow steps."""
        # This is a simplified implementation
        # In practice, this would integrate with user management system
        default_reviewers = {
            "security_review": "security_admin",
            "legal_review": "legal_admin",
            "compliance_review": "compliance_admin",
            "final_approval": "template_admin",
        }

        for step_id in workflow.pending_steps:
            if step_id not in workflow.assigned_reviewers:
                if step_id in default_reviewers:
                    workflow.assigned_reviewers[step_id] = default_reviewers[step_id]

    def _check_auto_approval(self, workflow: WorkflowInstance):
        """Check if workflow qualifies for auto-approval."""
        security_findings = workflow.metadata.get("security_findings", {})
        redaction_matches = workflow.metadata.get("redaction_matches", [])

        # Auto-approve if no security issues and no sensitive data
        if (
            security_findings.get("is_safe", False)
            and not redaction_matches
            and security_findings.get("severity", "high") == "low"
        ):
            workflow.status = WorkflowStatus.APPROVED
            workflow.completed_steps = workflow.pending_steps.copy()
            workflow.pending_steps = []
            workflow.current_step = None
            workflow.updated_at = datetime.now()

            self._log_workflow_event(
                workflow_id=workflow.workflow_id,
                action=WorkflowAction.APPROVE,
                actor_id="system",
                details={"auto_approved": True},
            )

    def _log_workflow_event(
        self,
        workflow_id: str,
        action: WorkflowAction,
        actor_id: str,
        step_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ):
        """Log workflow event."""
        event = WorkflowEvent(
            event_id=f"evt_{secrets.token_hex(8)}",
            workflow_id=workflow_id,
            action=action,
            actor_id=actor_id,
            timestamp=datetime.now(),
            step_id=step_id,
            details=details,
            comment=comment,
        )

        self.workflow_events.append(event)

        # Also log to security system for audit
        self.security_manager._audit_log(
            operation=f"workflow_{action.value}",
            result="success",
            user_id=actor_id,
            organization="",
            details={"workflow_id": workflow_id, "step_id": step_id, **(details or {})},
        )

    def _calculate_workflow_timeline(
        self, workflow: WorkflowInstance, events: List[WorkflowEvent]
    ) -> Dict[str, Any]:
        """Calculate workflow timeline metrics."""
        if not events:
            return {}

        total_duration = (
            workflow.updated_at - workflow.created_at
        ).total_seconds() / 3600  # hours

        step_durations = {}
        current_step_start = None

        for event in events:
            if event.action == WorkflowAction.SUBMIT_FOR_REVIEW:
                current_step_start = event.timestamp
            elif (
                event.action in [WorkflowAction.APPROVE, WorkflowAction.REJECT]
                and current_step_start
            ):
                if event.step_id:
                    duration = (
                        event.timestamp - current_step_start
                    ).total_seconds() / 3600
                    step_durations[event.step_id] = duration

        return {
            "total_duration_hours": total_duration,
            "step_durations": step_durations,
            "average_step_duration": (
                sum(step_durations.values()) / len(step_durations)
                if step_durations
                else 0
            ),
        }

    def _calculate_workflow_priority(self, workflow: WorkflowInstance) -> int:
        """Calculate workflow priority score."""
        priority = 0

        # Age factor
        age_hours = (datetime.now() - workflow.created_at).total_seconds() / 3600
        if age_hours > 72:  # Older than 3 days
            priority += 3
        elif age_hours > 24:  # Older than 1 day
            priority += 2
        elif age_hours > 8:  # Older than 8 hours
            priority += 1

        # Security factor
        security_findings = workflow.metadata.get("security_findings", {})
        if security_findings.get("severity") == "critical":
            priority += 5
        elif security_findings.get("severity") == "high":
            priority += 3
        elif security_findings.get("severity") == "medium":
            priority += 1

        # Sensitive data factor
        redaction_matches = workflow.metadata.get("redaction_matches", [])
        if redaction_matches:
            priority += 2

        return priority
