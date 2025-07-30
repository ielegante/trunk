"""Tests for template management system."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from doc_processing.templates import (
    RedactionResult,
    RedactionRule,
    RedactionSystem,
    SanitizationPipeline,
    SanitizationReport,
    SensitiveContent,
    TemplateField,
    TemplateManager,
    TemplateMetadata,
    TemplateRelationship,
    TemplateVersion,
)


class TestTemplateManager(unittest.TestCase):
    """Test TemplateManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.template_manager = TemplateManager(self.temp_dir)

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_create_template(self):
        """Test creating a new template."""
        # Define template fields
        fields = [
            TemplateField(
                field_id="party_name",
                name="Party Name",
                field_type="text",
                description="Name of the contracting party",
                required=True,
                placeholder="{{party_name}}",
            ),
            TemplateField(
                field_id="effective_date",
                name="Effective Date",
                field_type="date",
                description="Contract effective date",
                required=True,
                placeholder="{{effective_date}}",
            ),
        ]

        # Create template
        metadata = self.template_manager.create_template(
            name="NDA Template",
            content="# Non-Disclosure Agreement\n\nThis agreement is between {{party_name}}...",
            category="contracts",
            description="Standard NDA template",
            author="Test User",
            tags=["nda", "confidentiality"],
            fields=fields,
        )

        self.assertEqual(metadata.name, "NDA Template")
        self.assertEqual(metadata.category, "contracts")
        self.assertEqual(metadata.version, "1.0.0")
        self.assertEqual(len(metadata.fields), 2)

        # Verify template file exists
        template_dir = self.template_manager._get_template_dir(metadata.template_id)
        template_file = template_dir / "template.md"
        self.assertTrue(template_file.exists())

        # Verify in index
        self.assertIn(metadata.template_id, self.template_manager.templates_index)

    def test_fork_template(self):
        """Test forking a template to create a document."""
        # Create template first
        metadata = self.template_manager.create_template(
            name="Contract Template",
            content="# Contract\n\nParty: {{party_name}}\nDate: {{date}}",
            category="contracts",
            description="Basic contract",
            author="Test User",
        )

        # Fork template
        doc_path = Path(self.temp_dir) / "documents" / "client_contract.md"
        modifications = {"party_name": "Acme Corp", "date": "2025-01-15"}

        doc_id, relationship = self.template_manager.fork_template(
            template_id=metadata.template_id,
            document_name="Acme Corp Contract",
            document_path=doc_path,
            author="Test User",
            modifications=modifications,
        )

        self.assertIsNotNone(doc_id)
        self.assertEqual(relationship.parent_template_id, metadata.template_id)
        self.assertEqual(relationship.relationship_type, "forked")

        # Verify document created with modifications
        self.assertTrue(doc_path.exists())
        content = doc_path.read_text()
        self.assertIn("Acme Corp", content)
        self.assertIn("2025-01-15", content)

        # Verify relationship saved
        relationships = self.template_manager.get_template_relationships(
            metadata.template_id
        )
        self.assertEqual(len(relationships), 1)

    def test_update_template(self):
        """Test updating an existing template."""
        # Create template
        metadata = self.template_manager.create_template(
            name="Update Test",
            content="Original content",
            category="test",
            description="Test template",
            author="Test User",
        )

        # Update template
        version = self.template_manager.update_template(
            template_id=metadata.template_id,
            content="Updated content with new section",
            author="Test User",
            message="Added new section",
            version_increment="minor",
        )

        self.assertEqual(version.version_number, "1.1.0")
        self.assertEqual(version.message, "Added new section")

        # Verify content updated
        content, updated_metadata = self.template_manager.get_template(
            metadata.template_id
        )
        self.assertEqual(content, "Updated content with new section")
        self.assertEqual(updated_metadata.version, "1.1.0")

        # Verify backup created
        template_dir = self.template_manager._get_template_dir(metadata.template_id)
        backup_file = template_dir / "template_v1.0.0.md"
        self.assertTrue(backup_file.exists())

        # Verify version history
        versions = self.template_manager.get_template_versions(metadata.template_id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version_number, "1.1.0")

    def test_list_templates(self):
        """Test listing templates with filtering."""
        # Create multiple templates
        self.template_manager.create_template(
            name="NDA",
            content="NDA content",
            category="contracts",
            description="NDA",
            author="Test",
            tags=["confidentiality", "legal"],
        )

        self.template_manager.create_template(
            name="Employment Agreement",
            content="Employment content",
            category="agreements",
            description="Employment",
            author="Test",
            tags=["employment", "legal"],
        )

        self.template_manager.create_template(
            name="Service Contract",
            content="Service content",
            category="contracts",
            description="Service",
            author="Test",
            tags=["service", "legal"],
        )

        # List all templates
        all_templates = self.template_manager.list_templates()
        self.assertEqual(len(all_templates), 3)

        # Filter by category
        contracts = self.template_manager.list_templates(category="contracts")
        self.assertEqual(len(contracts), 2)

        # Filter by tags
        legal_templates = self.template_manager.list_templates(tags=["legal"])
        self.assertEqual(len(legal_templates), 3)

        employment_templates = self.template_manager.list_templates(tags=["employment"])
        self.assertEqual(len(employment_templates), 1)

    def test_search_templates(self):
        """Test searching templates."""
        # Create templates
        self.template_manager.create_template(
            name="Non-Disclosure Agreement",
            content="Content",
            category="contracts",
            description="Standard NDA for confidential information",
            author="Test",
            tags=["nda", "confidential"],
        )

        self.template_manager.create_template(
            name="Service Agreement",
            content="Content",
            category="contracts",
            description="Agreement for professional services",
            author="Test",
            tags=["service", "professional"],
        )

        # Search by name
        results = self.template_manager.search_templates("disclosure")
        self.assertEqual(len(results), 1)
        self.assertIn("Non-Disclosure", results[0].name)

        # Search by description
        results = self.template_manager.search_templates("professional")
        self.assertEqual(len(results), 1)
        self.assertIn("Service", results[0].name)

        # Search by tag
        results = self.template_manager.search_templates("confidential")
        self.assertEqual(len(results), 1)

    def test_version_increment(self):
        """Test version incrementing logic."""
        manager = self.template_manager

        # Test patch increment
        self.assertEqual(manager._increment_version("1.2.3", "patch"), "1.2.4")

        # Test minor increment
        self.assertEqual(manager._increment_version("1.2.3", "minor"), "1.3.0")

        # Test major increment
        self.assertEqual(manager._increment_version("1.2.3", "major"), "2.0.0")

        # Test with shorter version
        self.assertEqual(manager._increment_version("1.0", "minor"), "1.1.0")
        self.assertEqual(manager._increment_version("1", "major"), "2.0.0")


class TestRedactionSystem(unittest.TestCase):
    """Test RedactionSystem class."""

    def setUp(self):
        """Set up test fixtures."""
        self.redaction_system = RedactionSystem()

    def test_scan_content_basic(self):
        """Test basic content scanning."""
        content = """
        John Smith's SSN is 123-45-6789.
        Contact him at john.smith@example.com or (555) 123-4567.
        His credit card number is 4111111111111111.
        """

        sensitive_items = self.redaction_system.scan_content(content)

        # Should find SSN, email, phone, and credit card
        self.assertGreaterEqual(len(sensitive_items), 4)

        # Check types detected
        types_found = {item.content_type for item in sensitive_items}
        self.assertIn("regex", types_found)  # SSN, email, etc. are regex type

        # Verify SSN found
        ssn_items = [
            item for item in sensitive_items if "123-45-6789" in item.original_text
        ]
        self.assertEqual(len(ssn_items), 1)

    def test_redact_content(self):
        """Test content redaction."""
        content = """
        Client Information:
        Name: Jane Doe
        SSN: 987-65-4321
        Email: jane.doe@lawfirm.com
        Phone: (555) 987-6543
        Account: 12345678901234
        """

        redacted_content, result = self.redaction_system.redact_content(content)

        # Check redactions made
        self.assertGreater(result.redactions_count, 0)
        self.assertIn("[SSN REDACTED]", redacted_content)
        self.assertIn("[EMAIL REDACTED]", redacted_content)
        self.assertIn("[PHONE REDACTED]", redacted_content)
        self.assertNotIn("987-65-4321", redacted_content)
        self.assertNotIn("jane.doe@lawfirm.com", redacted_content)

    def test_create_redaction_checklist(self):
        """Test creation of redaction checklist."""
        content = """
        Agreement between Acme Corp and John Smith dated January 15, 2025.
        Payment amount: $50,000
        Location: 123 Main Street, New York, NY 10001
        Matter #: 2025-001
        """

        checklist = self.redaction_system.create_redaction_checklist(content)

        self.assertIn("automated_detections", checklist)
        self.assertIn("manual_review_items", checklist)
        self.assertIn("suggested_actions", checklist)
        self.assertIn("risk_assessment", checklist)

        # Check manual review items
        self.assertGreater(len(checklist["manual_review_items"]), 0)

        # Check risk assessment
        risk = checklist["risk_assessment"]
        self.assertIn("score", risk)
        self.assertIn("level", risk)
        self.assertIn("recommendation", risk)

    def test_sanitize_for_template(self):
        """Test sanitization for template creation."""
        content = """
        This Agreement is entered into on January 15, 2025, between
        Acme Corporation and John Smith for the amount of $100,000.
        Services will be provided at 123 Main Street, Suite 500.
        """

        (
            sanitized_content,
            placeholder_map,
        ) = self.redaction_system.sanitize_for_template(content)

        # Check placeholders created
        self.assertIn("{{PARTY_1}}", sanitized_content)
        self.assertIn("{{DATE_1}}", sanitized_content)
        self.assertIn("{{AMOUNT_1}}", sanitized_content)

        # Check placeholder map
        self.assertIn("January 15, 2025", placeholder_map)
        self.assertIn("$100,000", placeholder_map)

        # Verify original content replaced
        self.assertNotIn("January 15, 2025", sanitized_content)
        self.assertNotIn("Acme Corporation", sanitized_content)
        self.assertNotIn("$100,000", sanitized_content)

    def test_client_name_tracking(self):
        """Test tracking of client names."""
        # Add client names
        self.redaction_system.add_client_name("Acme Corporation")
        self.redaction_system.add_client_name("John Smith")

        content = """
        Acme Corporation agrees to the terms.
        John Smith is the authorized representative.
        Contact Smith for details.
        """

        sensitive_items = self.redaction_system.scan_content(content)

        # Should find client names
        client_items = [
            item for item in sensitive_items if item.content_type == "client_name"
        ]
        self.assertGreater(len(client_items), 0)

        # Should find variations (e.g., "Smith")
        smith_items = [
            item for item in client_items if "smith" in item.original_text.lower()
        ]
        self.assertGreater(len(smith_items), 0)

    def test_custom_rules(self):
        """Test custom redaction rules."""
        # Create custom rule
        custom_rule = RedactionRule(
            rule_id="custom_1",
            name="Case Number",
            description="Legal case numbers",
            pattern=r"\b\d{4}-CV-\d{5}\b",
            replacement="[CASE NUMBER REDACTED]",
            rule_type="regex",
            enabled=True,
        )

        content = "The case number is 2025-CV-12345 in the district court."

        redacted_content, result = self.redaction_system.redact_content(
            content, custom_rules=[custom_rule]
        )

        self.assertIn("[CASE NUMBER REDACTED]", redacted_content)
        self.assertNotIn("2025-CV-12345", redacted_content)


class TestSanitizationPipeline(unittest.TestCase):
    """Test SanitizationPipeline class."""

    def setUp(self):
        """Set up test fixtures."""
        self.redaction_system = RedactionSystem()
        self.pipeline = SanitizationPipeline(self.redaction_system)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_sanitize_document(self):
        """Test sanitizing a single document."""
        # Create test document
        doc_path = Path(self.temp_dir) / "test_doc.md"
        doc_path.write_text(
            """
        # Contract for John Smith

        SSN: 123-45-6789
        Email: john@example.com
        Payment: $50,000
        """
        )

        # Sanitize document
        output_path, result = self.pipeline.sanitize_document(doc_path)

        self.assertTrue(output_path.exists())
        self.assertGreater(result.redactions_count, 0)

        # Check sanitized content
        sanitized_content = output_path.read_text()
        self.assertIn("[SSN REDACTED]", sanitized_content)
        self.assertIn("[EMAIL REDACTED]", sanitized_content)
        self.assertNotIn("123-45-6789", sanitized_content)
        self.assertNotIn("john@example.com", sanitized_content)

    def test_create_sanitization_filter(self):
        """Test creating git filter script."""
        patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        ]

        script = self.pipeline.create_sanitization_filter(patterns)

        self.assertIn("#!/usr/bin/env python3", script)
        self.assertIn("import sys", script)
        self.assertIn("import re", script)
        self.assertIn("patterns =", script)
        self.assertIn("[REDACTED]", script)

    @patch("subprocess.run")
    def test_git_history_sanitization(self, mock_run):
        """Test git history sanitization (mocked)."""
        # Mock git commands
        mock_run.return_value = MagicMock(
            stdout="abc123|Test User|test@example.com|1234567890|Initial commit",
            returncode=0,
        )

        # Create mock repo
        repo_path = Path(self.temp_dir) / "test_repo"
        repo_path.mkdir()

        # Mock the actual file operations
        with patch.object(self.pipeline, "_clone_repository"):
            with patch.object(
                self.pipeline,
                "_get_commit_history",
                return_value=[
                    {
                        "hash": "abc123",
                        "author": "Test User",
                        "email": "test@example.com",
                        "date": "1234567890",
                        "message": "Initial commit",
                    }
                ],
            ):
                with patch.object(
                    self.pipeline, "_get_changed_files", return_value=["test.md"]
                ):
                    with patch.object(self.pipeline, "_sanitize_file", return_value=2):
                        with patch.object(self.pipeline, "_push_branch"):
                            # Run sanitization
                            report = self.pipeline.sanitize_git_history(repo_path)

        self.assertIsInstance(report, SanitizationReport)
        self.assertEqual(report.original_commits, 1)
        self.assertGreaterEqual(report.files_processed, 0)

    def test_should_process_file(self):
        """Test file processing filter."""
        # Should process
        self.assertTrue(self.pipeline._should_process_file("document.md"))
        self.assertTrue(self.pipeline._should_process_file("contract.txt"))
        self.assertTrue(self.pipeline._should_process_file("agreement.docx"))

        # Should not process
        self.assertFalse(self.pipeline._should_process_file("image.png"))
        self.assertFalse(self.pipeline._should_process_file("script.py"))
        self.assertFalse(
            self.pipeline._should_process_file("node_modules/package.json")
        )
        self.assertFalse(self.pipeline._should_process_file(".git/config"))


if __name__ == "__main__":
    unittest.main()
