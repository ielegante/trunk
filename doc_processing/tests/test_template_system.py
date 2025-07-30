"""Comprehensive tests for template system including workflow, security, and redaction."""

import json
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from doc_processing.templates.manager import Template, TemplateManager
from doc_processing.templates.redaction import (
    DocumentSanitizer,
    RedactionEngine,
    RedactionRule,
    RedactionType,
    SensitivityLevel,
)
from doc_processing.templates.security import (
    AccessRule,
    PermissionType,
    SecureTemplateValidator,
    SecurityContext,
    SecurityLevel,
    SecurityManager,
)
from doc_processing.templates.workflow import (
    ReviewType,
    TemplateWorkflowManager,
    WorkflowAction,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)


class TestTemplateManager:
    """Tests for template management system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_manager = TemplateManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_template_creation(self):
        """Test template creation and registration."""
        template = Template(
            name="test_template",
            path=self.temp_dir / "test.md",
            category="contracts",
            variables=["client_name", "contract_date"],
            metadata={"description": "Test template"},
        )

        # Write template content
        template.path.write_text(
            "# Contract for {{client_name}}\nDate: {{contract_date}}"
        )

        self.template_manager.register_template(template)

        # Verify template is registered
        retrieved = self.template_manager.get_template("test_template")
        assert retrieved is not None
        assert retrieved.name == "test_template"
        assert retrieved.category == "contracts"
        assert "client_name" in retrieved.variables

    def test_template_instantiation(self):
        """Test template variable substitution."""
        template_content = "# Contract for {{client_name}}\nDate: {{contract_date}}\nAmount: {{amount}}"
        template_path = self.temp_dir / "contract.md"
        template_path.write_text(template_content)

        template = Template(
            name="contract_template",
            path=template_path,
            category="contracts",
            variables=["client_name", "contract_date", "amount"],
            metadata={},
        )

        self.template_manager.register_template(template)

        # Instantiate template
        variables = {
            "client_name": "ABC Corp",
            "contract_date": "2024-01-15",
            "amount": "$50,000",
        }

        result = self.template_manager.instantiate_template(
            "contract_template", variables
        )

        assert "ABC Corp" in result
        assert "2024-01-15" in result
        assert "$50,000" in result
        assert "{{" not in result  # No unreplaced variables

    def test_template_validation(self):
        """Test template variable validation."""
        template = Template(
            name="test_template",
            path=self.temp_dir / "test.md",
            category="test",
            variables=["var1", "var2", "var3"],
            metadata={},
        )

        self.template_manager.register_template(template)

        # Test with missing variables
        variables = {"var1": "value1", "var4": "extra_value"}

        validation = self.template_manager.validate_template_variables(
            "test_template", variables
        )

        assert "var2" in validation["missing"]
        assert "var3" in validation["missing"]
        assert "var4" in validation["extra"]

    def test_template_deprecation(self):
        """Test template deprecation and activation."""
        template = Template(
            name="test_template",
            path=self.temp_dir / "test.md",
            category="test",
            variables=[],
            metadata={},
        )

        self.template_manager.register_template(template)

        # Verify template is active
        templates = self.template_manager.list_templates()
        assert len(templates) == 1
        assert templates[0].is_active

        # Deprecate template
        success = self.template_manager.deprecate_template("test_template")
        assert success

        # Verify template is not in active list
        active_templates = self.template_manager.list_templates(include_inactive=False)
        assert len(active_templates) == 0

        # Verify template is in inactive list
        all_templates = self.template_manager.list_templates(include_inactive=True)
        assert len(all_templates) == 1
        assert not all_templates[0].is_active

        # Reactivate template
        success = self.template_manager.activate_template("test_template")
        assert success

        # Verify template is active again
        active_templates = self.template_manager.list_templates()
        assert len(active_templates) == 1
        assert active_templates[0].is_active


class TestSecurityManager:
    """Tests for security management system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()

    def test_security_context_creation(self):
        """Test security context creation and validation."""
        context = self.security_manager.create_security_context(
            user_id="test_user",
            organization="test_org",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["lawyer", "template_user"],
            permissions=[PermissionType.READ, PermissionType.WRITE],
            ip_address="127.0.0.1",
        )

        assert context.user_id == "test_user"
        assert context.organization == "test_org"
        assert context.security_clearance == SecurityLevel.CONFIDENTIAL
        assert context.is_valid()
        assert context.has_permission(PermissionType.READ)
        assert context.has_permission(PermissionType.WRITE)
        assert not context.has_permission(PermissionType.ADMIN)
        assert context.can_access_security_level(SecurityLevel.INTERNAL)
        assert context.can_access_security_level(SecurityLevel.CONFIDENTIAL)
        assert not context.can_access_security_level(SecurityLevel.RESTRICTED)

    def test_access_control_rules(self):
        """Test access control rule evaluation."""
        # Create security context
        context = self.security_manager.create_security_context(
            user_id="lawyer1",
            organization="law_firm",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["lawyer"],
            permissions=[PermissionType.READ, PermissionType.WRITE],
        )

        # Test access to confidential template
        has_access = self.security_manager.check_access(
            context, "templates/confidential/contract.md", PermissionType.READ
        )
        assert has_access

        # Test access to restricted template (should fail)
        has_access = self.security_manager.check_access(
            context, "templates/restricted/classified.md", PermissionType.READ
        )
        assert not has_access

    def test_session_token_validation(self):
        """Test session token generation and validation."""
        context = self.security_manager.create_security_context(
            user_id="test_user",
            organization="test_org",
            security_clearance=SecurityLevel.INTERNAL,
            roles=["user"],
            permissions=[PermissionType.READ],
        )

        # Validate generated token
        is_valid = self.security_manager.validate_session_token(
            context.session_token, "test_user"
        )
        assert is_valid

        # Test with wrong user ID
        is_valid = self.security_manager.validate_session_token(
            context.session_token, "wrong_user"
        )
        assert not is_valid

        # Test with invalid token
        is_valid = self.security_manager.validate_session_token(
            "invalid_token", "test_user"
        )
        assert not is_valid

    def test_audit_logging(self):
        """Test audit logging functionality."""
        initial_count = len(self.security_manager.audit_log)

        context = self.security_manager.create_security_context(
            user_id="test_user",
            organization="test_org",
            security_clearance=SecurityLevel.INTERNAL,
            roles=["user"],
            permissions=[PermissionType.READ],
        )

        # Check access (should be logged)
        self.security_manager.check_access(
            context, "templates/public/test.md", PermissionType.READ
        )

        # Verify audit events were created
        assert len(self.security_manager.audit_log) > initial_count

        # Get recent events
        events = self.security_manager.get_audit_log(user_id="test_user", limit=5)
        assert len(events) >= 2  # Authentication + access check

        auth_events = [e for e in events if e.operation == "authentication"]
        access_events = [e for e in events if e.operation == "access_check"]

        assert len(auth_events) >= 1
        assert len(access_events) >= 1


class TestRedactionEngine:
    """Tests for document redaction system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redaction_engine = RedactionEngine()

    def test_sensitive_information_detection(self):
        """Test detection of sensitive information."""
        content = """
        John Doe's SSN is 123-45-6789.
        Credit card: 4532-1234-5678-9012
        Email: john.doe@example.com
        Phone: (555) 123-4567
        """

        matches = self.redaction_engine.scan_for_sensitive_information(content)

        # Should find SSN, credit card, email, phone
        assert len(matches) >= 4

        rule_types = [match.rule_id for match in matches]
        assert "ssn" in rule_types
        assert "credit_card" in rule_types
        assert "email_address" in rule_types
        assert "phone_number" in rule_types

    def test_document_redaction(self):
        """Test complete document redaction."""
        content = """
        CONFIDENTIAL CONTRACT

        Client: John Doe
        SSN: 123-45-6789
        Email: john.doe@example.com

        This agreement contains sensitive information.
        """

        redacted_content, report = self.redaction_engine.redact_document(
            content=content,
            document_id="test_doc_001",
            operator_id="redaction_operator",
        )

        # Verify redaction occurred
        assert report.redaction_count > 0
        assert "123-45-6789" not in redacted_content
        assert "john.doe@example.com" not in redacted_content
        assert "[" in redacted_content or "*" in redacted_content  # Redaction markers

        # Verify report details
        assert report.document_id == "test_doc_001"
        assert report.operator_id == "redaction_operator"
        assert len(report.matches) > 0
        assert len(report.rules_applied) > 0

    def test_redaction_by_category(self):
        """Test redaction filtered by rule categories."""
        content = """
        Personal info: SSN 123-45-6789, Email john@example.com
        Financial info: Credit card 4532-1234-5678-9012
        Technical info: IP address 192.168.1.1
        """

        # Redact only PII category
        redacted_content, report = self.redaction_engine.redact_document(
            content=content,
            document_id="test_doc",
            operator_id="operator",
            rule_categories=["pii"],
        )

        # Should redact SSN and email but not IP address
        assert "123-45-6789" not in redacted_content
        assert "john@example.com" not in redacted_content
        assert "192.168.1.1" in redacted_content  # IP should remain

    def test_template_creation_from_redaction(self):
        """Test template creation from redacted document."""
        content = """
        Dear {{client_name}},

        Your account number is 123456789.
        Email: contact@company.com

        Best regards,
        {{sender_name}}
        """

        redacted_content, report = self.redaction_engine.redact_document(
            content=content,
            document_id="template_source",
            operator_id="template_creator",
        )

        # Create template from redaction
        template_def = self.redaction_engine.create_template_from_redacted_document(
            redacted_content=redacted_content,
            redaction_report=report,
            template_name="email_template",
        )

        assert template_def["name"] == "email_template"
        assert "content" in template_def
        assert "variables" in template_def
        assert len(template_def["variables"]) >= 2  # Original + redacted variables
        assert template_def["metadata"]["created_from_redaction"] is True


class TestDocumentSanitizer:
    """Tests for document sanitization system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = DocumentSanitizer()

    def test_script_removal(self):
        """Test removal of dangerous script elements."""
        content = """
        <p>Safe content</p>
        <script>alert('dangerous');</script>
        <p>More safe content</p>
        """

        sanitized, removed = self.sanitizer.sanitize_content(content)

        assert "<script>" not in sanitized
        assert "alert('dangerous');" not in sanitized
        assert "Safe content" in sanitized
        assert "More safe content" in sanitized
        assert len(removed) > 0
        assert any("embedded_scripts" in item for item in removed)

    def test_external_link_removal(self):
        """Test removal of external links when enabled."""
        content = """
        <p>Visit our site at https://example.com</p>
        <p>Email us at mailto:contact@example.com</p>
        <p>Internal content remains</p>
        """

        sanitized, removed = self.sanitizer.sanitize_content(
            content, remove_external_links=True
        )

        assert "https://example.com" not in sanitized
        assert "mailto:contact@example.com" not in sanitized
        assert "Internal content remains" in sanitized
        assert len(removed) > 0


class TestTemplateWorkflowManager:
    """Tests for template workflow management system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_manager = TemplateManager(self.temp_dir)
        self.security_manager = SecurityManager()
        self.redaction_engine = RedactionEngine()

        self.workflow_manager = TemplateWorkflowManager(
            template_manager=self.template_manager,
            security_manager=self.security_manager,
            redaction_engine=self.redaction_engine,
        )

        # Create test security context
        self.context = self.security_manager.create_security_context(
            user_id="template_creator",
            organization="law_firm",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["lawyer", "template_creator"],
            permissions=[
                PermissionType.READ,
                PermissionType.WRITE,
                PermissionType.EXECUTE,
            ],
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_workflow_creation(self):
        """Test creation of template workflow."""
        template_content = """
        # Legal Agreement Template

        Client: {{client_name}}
        Date: {{agreement_date}}

        This agreement contains standard legal language.
        """

        workflow = self.workflow_manager.create_template_workflow(
            template_name="legal_agreement",
            template_content=template_content,
            template_metadata={
                "category": "agreements",
                "variables": ["client_name", "agreement_date"],
            },
            context=self.context,
        )

        assert workflow.template_name == "legal_agreement"
        assert workflow.created_by == "template_creator"
        assert workflow.status in [WorkflowStatus.DRAFT, WorkflowStatus.PENDING_REVIEW]
        assert len(workflow.pending_steps) > 0
        assert workflow.workflow_id.startswith("wf_")

    def test_workflow_submission(self):
        """Test workflow submission for review."""
        # Create workflow
        workflow = self.workflow_manager.create_template_workflow(
            template_name="test_template",
            template_content="# Test Template\n{{content}}",
            template_metadata={"category": "test"},
            context=self.context,
        )

        # Submit for review
        success = self.workflow_manager.submit_for_review(
            workflow_id=workflow.workflow_id, context=self.context
        )

        assert success

        # Check workflow status
        updated_workflow = self.workflow_manager._get_workflow(workflow.workflow_id)
        assert updated_workflow.status == WorkflowStatus.PENDING_REVIEW
        assert len(updated_workflow.assigned_reviewers) > 0

    def test_workflow_review_process(self):
        """Test workflow review and approval process."""
        # Create and submit workflow
        workflow = self.workflow_manager.create_template_workflow(
            template_name="review_test",
            template_content="# Clean Template\n{{variable}}",
            template_metadata={"category": "test"},
            context=self.context,
        )

        self.workflow_manager.submit_for_review(
            workflow_id=workflow.workflow_id, context=self.context
        )

        # Create reviewer context
        reviewer_context = self.security_manager.create_security_context(
            user_id="security_admin",
            organization="law_firm",
            security_clearance=SecurityLevel.RESTRICTED,
            roles=["security_reviewer"],
            permissions=[
                PermissionType.READ,
                PermissionType.EXECUTE,
                PermissionType.ADMIN,
            ],
        )

        # Get first pending step
        updated_workflow = self.workflow_manager._get_workflow(workflow.workflow_id)
        first_step = (
            updated_workflow.pending_steps[0]
            if updated_workflow.pending_steps
            else None
        )

        if first_step:
            # Assign reviewer
            updated_workflow.assigned_reviewers[first_step] = "security_admin"

            # Review template
            success = self.workflow_manager.review_template(
                workflow_id=workflow.workflow_id,
                step_id=first_step,
                decision="approved",
                context=reviewer_context,
                comment="Template looks good",
            )

            assert success

            # Check workflow progression
            final_workflow = self.workflow_manager._get_workflow(workflow.workflow_id)
            assert first_step in final_workflow.completed_steps

    def test_template_deployment(self):
        """Test template deployment after approval."""
        # Create approved workflow (mock)
        workflow = self.workflow_manager.create_template_workflow(
            template_name="deployment_test",
            template_content="# Deployment Test\n{{content}}",
            template_metadata={"category": "test"},
            context=self.context,
        )

        # Manually set to approved status for testing
        workflow.status = WorkflowStatus.APPROVED
        workflow.metadata["sanitized_content"] = "# Deployment Test\n{{content}}"

        # Create admin context
        admin_context = self.security_manager.create_security_context(
            user_id="admin",
            organization="law_firm",
            security_clearance=SecurityLevel.RESTRICTED,
            roles=["admin"],
            permissions=[PermissionType.ADMIN],
        )

        # Deploy template
        deployment_path = self.workflow_manager.deploy_template(
            workflow_id=workflow.workflow_id,
            context=admin_context,
            deployment_target="test",
        )

        assert deployment_path
        assert Path(deployment_path).exists()

        # Verify template was registered
        deployed_template = self.template_manager.get_template("deployment_test")
        assert deployed_template is not None
        assert deployed_template.name == "deployment_test"

    def test_workflow_redaction(self):
        """Test template content redaction in workflow."""
        sensitive_content = """
        # Template with Sensitive Data

        Example SSN: 123-45-6789
        Example email: test@example.com

        Template content: {{variable}}
        """

        workflow = self.workflow_manager.create_template_workflow(
            template_name="sensitive_template",
            template_content=sensitive_content,
            template_metadata={"category": "test"},
            context=self.context,
        )

        # Apply redaction
        redacted_content, report = self.workflow_manager.redact_template_content(
            workflow_id=workflow.workflow_id, context=self.context
        )

        assert "123-45-6789" not in redacted_content
        assert "test@example.com" not in redacted_content
        assert report.redaction_count > 0
        assert "{{variable}}" in redacted_content  # Template variables should remain

    def test_pending_reviews_query(self):
        """Test querying pending reviews for user."""
        # Create workflow and assign reviewer
        workflow = self.workflow_manager.create_template_workflow(
            template_name="pending_review_test",
            template_content="# Test\n{{content}}",
            template_metadata={"category": "test"},
            context=self.context,
        )

        self.workflow_manager.submit_for_review(
            workflow_id=workflow.workflow_id,
            context=self.context,
            reviewer_assignments={"security_review": "reviewer1"},
        )

        # Create reviewer context
        reviewer_context = self.security_manager.create_security_context(
            user_id="reviewer1",
            organization="law_firm",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["reviewer"],
            permissions=[PermissionType.READ, PermissionType.EXECUTE],
        )

        # Get pending reviews
        pending = self.workflow_manager.get_pending_reviews(reviewer_context)

        assert len(pending) > 0
        assert any(w["workflow_id"] == workflow.workflow_id for w in pending)
        assert any(w["template_name"] == "pending_review_test" for w in pending)

    def test_workflow_status_tracking(self):
        """Test comprehensive workflow status tracking."""
        workflow = self.workflow_manager.create_template_workflow(
            template_name="status_test",
            template_content="# Status Test\n{{content}}",
            template_metadata={"category": "test"},
            context=self.context,
        )

        # Get workflow status
        status = self.workflow_manager.get_workflow_status(workflow.workflow_id)

        assert "workflow" in status
        assert "progress" in status
        assert "events" in status
        assert "reviewers" in status
        assert "timeline" in status

        assert status["workflow"]["template_name"] == "status_test"
        assert status["progress"]["percentage"] >= 0
        assert len(status["events"]) >= 1  # Creation event


class TestTemplateSystemIntegration:
    """Integration tests for complete template system."""

    def setup_method(self):
        """Set up integrated test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_manager = TemplateManager(self.temp_dir)
        self.security_manager = SecurityManager()
        self.redaction_engine = RedactionEngine()

        self.workflow_manager = TemplateWorkflowManager(
            template_manager=self.template_manager,
            security_manager=self.security_manager,
            redaction_engine=self.redaction_engine,
        )

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_end_to_end_template_lifecycle(self):
        """Test complete template lifecycle from creation to deployment."""
        # Create user context
        creator_context = self.security_manager.create_security_context(
            user_id="template_creator",
            organization="law_firm",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["lawyer", "template_creator"],
            permissions=[
                PermissionType.READ,
                PermissionType.WRITE,
                PermissionType.EXECUTE,
            ],
        )

        # Create template with sensitive content
        template_content = """
        # Client Agreement Template

        [CONFIDENTIAL]
        This agreement is between {{client_name}} and the law firm.

        Client Contact: {{client_email}}
        Agreement Date: {{agreement_date}}

        Terms and conditions apply.
        [/CONFIDENTIAL]
        """

        # 1. Create workflow
        workflow = self.workflow_manager.create_template_workflow(
            template_name="client_agreement",
            template_content=template_content,
            template_metadata={
                "category": "agreements",
                "variables": ["client_name", "client_email", "agreement_date"],
                "description": "Standard client agreement template",
            },
            context=creator_context,
        )

        assert workflow.status in [WorkflowStatus.DRAFT, WorkflowStatus.PENDING_REVIEW]

        # 2. Apply redaction
        (
            redacted_content,
            redaction_report,
        ) = self.workflow_manager.redact_template_content(
            workflow_id=workflow.workflow_id,
            redaction_rules=["legal"],
            context=creator_context,
        )

        assert "[CONFIDENTIAL]" not in redacted_content
        assert redaction_report.redaction_count > 0

        # 3. Submit for review
        success = self.workflow_manager.submit_for_review(
            workflow_id=workflow.workflow_id, context=creator_context
        )
        assert success

        # 4. Create admin context for approval
        admin_context = self.security_manager.create_security_context(
            user_id="admin",
            organization="law_firm",
            security_clearance=SecurityLevel.RESTRICTED,
            roles=["admin", "template_admin"],
            permissions=[PermissionType.ADMIN],
        )

        # 5. Approve workflow (simplified - skip individual review steps)
        updated_workflow = self.workflow_manager._get_workflow(workflow.workflow_id)
        updated_workflow.status = WorkflowStatus.APPROVED
        updated_workflow.completed_steps = updated_workflow.pending_steps.copy()
        updated_workflow.pending_steps = []

        # 6. Deploy template
        deployment_path = self.workflow_manager.deploy_template(
            workflow_id=workflow.workflow_id,
            context=admin_context,
            deployment_target="production",
        )

        assert deployment_path
        assert Path(deployment_path).exists()

        # 7. Verify template is available
        deployed_template = self.template_manager.get_template("client_agreement")
        assert deployed_template is not None
        assert deployed_template.category == "agreements"
        assert deployed_template.is_active

        # 8. Test template instantiation
        instance_content = self.template_manager.instantiate_template(
            "client_agreement",
            {
                "client_name": "ABC Corporation",
                "client_email": "contact@abc.com",
                "agreement_date": "2024-01-15",
            },
        )

        assert "ABC Corporation" in instance_content
        assert "contact@abc.com" in instance_content
        assert "2024-01-15" in instance_content

        # 9. Verify workflow events are logged
        status = self.workflow_manager.get_workflow_status(workflow.workflow_id)
        assert len(status["events"]) > 0
        assert any(e["action"] == "create" for e in status["events"])
        assert any(e["action"] == "redact" for e in status["events"])
        assert any(e["action"] == "deploy" for e in status["events"])

    def test_security_compliance_workflow(self):
        """Test security compliance throughout workflow."""
        # Create low-privilege user
        user_context = self.security_manager.create_security_context(
            user_id="regular_user",
            organization="law_firm",
            security_clearance=SecurityLevel.INTERNAL,
            roles=["employee"],
            permissions=[PermissionType.READ],
        )

        # Attempt to create workflow (should fail)
        with pytest.raises(PermissionError):
            self.workflow_manager.create_template_workflow(
                template_name="unauthorized_template",
                template_content="# Test",
                template_metadata={"category": "test"},
                context=user_context,
            )

        # Create privileged user
        privileged_context = self.security_manager.create_security_context(
            user_id="privileged_user",
            organization="law_firm",
            security_clearance=SecurityLevel.CONFIDENTIAL,
            roles=["lawyer"],
            permissions=[
                PermissionType.READ,
                PermissionType.WRITE,
                PermissionType.EXECUTE,
            ],
        )

        # Create workflow with privileged user
        workflow = self.workflow_manager.create_template_workflow(
            template_name="privileged_template",
            template_content="# Privileged Template\n{{content}}",
            template_metadata={"category": "confidential"},
            context=privileged_context,
        )

        # Verify audit trail
        audit_events = self.security_manager.get_audit_log(
            user_id="privileged_user", operation="workflow_create"
        )
        assert len(audit_events) > 0

        # Verify security metrics
        metrics = self.security_manager.get_security_metrics()
        assert metrics["total_audit_events"] > 0
        assert "security_events" in metrics


# Test fixtures
@pytest.fixture
def sample_template_content():
    """Sample template content for testing."""
    return """
    # {{document_type}} Agreement

    Date: {{agreement_date}}
    Parties: {{party1}} and {{party2}}

    This agreement contains the following terms:

    1. {{term1}}
    2. {{term2}}
    3. {{term3}}

    Signatures:
    {{party1_signature}}
    {{party2_signature}}
    """


@pytest.fixture
def sensitive_template_content():
    """Template content with sensitive information for testing."""
    return """
    # Confidential Client Data Template

    [ATTORNEY-CLIENT-PRIVILEGED]
    Client SSN: 123-45-6789
    Client Email: client@example.com
    Case Number: CASE-2024-001
    [/ATTORNEY-CLIENT-PRIVILEGED]

    Template Variables:
    Client Name: {{client_name}}
    Case Type: {{case_type}}
    Filing Date: {{filing_date}}

    <script>alert('malicious');</script>
    """


@pytest.fixture
def mock_security_context():
    """Mock security context for testing."""
    return SecurityContext(
        user_id="test_user",
        organization="test_org",
        security_clearance=SecurityLevel.CONFIDENTIAL,
        roles=["lawyer", "template_user"],
        permissions=[PermissionType.READ, PermissionType.WRITE, PermissionType.EXECUTE],
        session_token="mock_token_123",
        expires_at=datetime.now() + timedelta(hours=8),
    )
