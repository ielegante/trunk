"""Tests for template management and redaction systems."""

import re
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from doc_processing.templates import RedactionEngine, TemplateManager
from doc_processing.templates.manager import Template
from doc_processing.templates.redaction import (
    RedactionRule,
    RedactionType,
    SensitivityLevel,
)


class TestTemplate:
    """Test Template dataclass."""

    def test_template_creation(self):
        """Test creating a Template."""
        template = Template(
            name="contract_template",
            path=Path("templates/contract.md"),
            category="contracts",
            variables=["client_name", "amount", "date"],
            metadata={"author": "Legal Team"},
            version="2.0",
        )
        assert template.name == "contract_template"
        assert template.category == "contracts"
        assert "client_name" in template.variables
        assert template.version == "2.0"


class TestTemplateManager:
    """Test TemplateManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path("/tmp/test_templates")
        self.manager = TemplateManager(self.temp_dir)

    def test_manager_initialization(self):
        """Test manager initialization."""
        assert self.manager.templates_directory == self.temp_dir
        assert self.manager.templates == {}
        assert self.manager.template_index_file == self.temp_dir / "template_index.json"

    def test_register_template(self):
        """Test registering a new template."""
        template = Template(
            name="test_template",
            path=Path("test.md"),
            category="test",
            variables=["var1"],
            metadata={},
        )

        with patch.object(self.manager, "_save_template_index"):
            self.manager.register_template(template)

        assert "test_template" in self.manager.templates
        assert self.manager.get_template("test_template") == template

    def test_get_template_not_found(self):
        """Test getting a template that doesn't exist."""
        result = self.manager.get_template("nonexistent")
        assert result is None

    def test_list_templates_empty(self):
        """Test listing templates when none exist."""
        templates = self.manager.list_templates()
        assert templates == []

    def test_list_templates_with_category_filter(self):
        """Test listing templates with category filter."""
        template1 = Template(
            name="contract1",
            path=Path("c1.md"),
            category="contracts",
            variables=[],
            metadata={},
        )
        template2 = Template(
            name="letter1",
            path=Path("l1.md"),
            category="letters",
            variables=[],
            metadata={},
        )

        with patch.object(self.manager, "_save_template_index"):
            self.manager.register_template(template1)
            self.manager.register_template(template2)

        contract_templates = self.manager.list_templates(category="contracts")
        assert len(contract_templates) == 1
        assert contract_templates[0].name == "contract1"

    def test_instantiate_template_not_found(self):
        """Test instantiating a template that doesn't exist."""
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            self.manager.instantiate_template("nonexistent", {})

    @patch("builtins.open", new_callable=mock_open, read_data="Hello {{name}}!")
    def test_instantiate_template_success(self, mock_file):
        """Test successful template instantiation."""
        template = Template(
            name="greeting",
            path=Path("greeting.md"),
            category="test",
            variables=["name"],
            metadata={},
        )

        with patch.object(self.manager, "_save_template_index"):
            self.manager.register_template(template)

        result = self.manager.instantiate_template("greeting", {"name": "John"})
        assert result == "Hello John!"

    def test_validate_template_variables_not_found(self):
        """Test validating variables for non-existent template."""
        with pytest.raises(ValueError, match="Template 'nonexistent' not found"):
            self.manager.validate_template_variables("nonexistent", {})

    def test_validate_template_variables_success(self):
        """Test successful variable validation."""
        template = Template(
            name="test",
            path=Path("test.md"),
            category="test",
            variables=["name", "date"],
            metadata={},
        )

        with patch.object(self.manager, "_save_template_index"):
            self.manager.register_template(template)

        # Test with missing and extra variables
        result = self.manager.validate_template_variables(
            "test", {"name": "John", "extra_var": "value"}
        )

        assert "date" in result["missing"]
        assert "extra_var" in result["extra"]
        assert len(result["missing"]) == 1
        assert len(result["extra"]) == 1


class TestRedactionRule:
    """Test RedactionRule dataclass."""

    def test_redaction_rule_creation(self):
        """Test creating a RedactionRule."""
        pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        rule = RedactionRule(
            rule_id="ssn",
            name="Social Security Number",
            description="Social Security Numbers",
            pattern=r"\b\d{3}-\d{2}-\d{4}\b",
            redaction_type=RedactionType.REPLACE,
            sensitivity_level=SensitivityLevel.CRITICAL,
            replacement_text="[REDACTED-SSN]",
            categories=["personal_info"],
            is_active=False,
        )
        assert rule.name == "Social Security Number"
        assert rule.rule_id == "ssn"
        assert rule.is_active is False


class TestRedactionManager:
    """Test RedactionManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = RedactionEngine()

    def test_manager_initialization(self):
        """Test manager initialization with default rules."""
        assert len(self.manager.rules) >= 4  # At least the default rules
        assert "ssn" in self.manager.rules
        assert "email_address" in self.manager.rules
        assert "phone_number" in self.manager.rules
        assert "credit_card" in self.manager.rules

    def test_add_custom_rule(self):
        """Test adding a custom redaction rule."""
        rule = RedactionRule(
            rule_id="confidential",
            name="Confidential Marker",
            description="Confidential markers",
            pattern=r"\bCONFIDENTIAL\b",
            redaction_type=RedactionType.REPLACE,
            sensitivity_level=SensitivityLevel.HIGH,
            replacement_text="[REDACTED]",
            categories=["custom"],
        )

        self.manager.add_redaction_rule(rule)
        assert "confidential" in self.manager.rules
        assert self.manager.rules["confidential"] == rule

    def test_remove_rule_success(self):
        """Test successfully removing a rule."""
        # First verify the rule exists
        assert "ssn" in self.manager.rules

        # Remove the rule
        self.manager.remove_redaction_rule("ssn")
        assert "ssn" not in self.manager.rules

    def test_remove_rule_not_found(self):
        """Test removing a rule that doesn't exist."""
        # This should not raise an exception
        self.manager.remove_redaction_rule("nonexistent")
        # No assertion needed - just verify it doesn't crash

    def test_redact_text_ssn(self):
        """Test redacting Social Security Numbers."""
        text = "My SSN is 123-45-6789 and my ID is 987-65-4321."
        result, report = self.manager.redact_document(text, "test_doc", "test_operator")
        assert "123-45-6789" not in result
        assert "987-65-4321" not in result
        assert "***-**-****" in result

    def test_redact_text_email(self):
        """Test redacting email addresses."""
        text = "Contact me at john.doe@example.com for details."
        result, report = self.manager.redact_document(text, "test_doc", "test_operator")
        assert "john.doe@example.com" not in result
        assert "[EMAIL_ADDRESS]" in result

    def test_redact_text_phone(self):
        """Test redacting phone numbers."""
        text = "Call me at (555) 123-4567 or 555.987.6543."
        result, report = self.manager.redact_document(text, "test_doc", "test_operator")
        assert "(555) 123-4567" not in result
        assert "555.987.6543" not in result
        assert "[PHONE_NUMBER]" in result

    def test_redact_text_with_categories(self):
        """Test redacting with category filter."""
        text = "Email: test@example.com, SSN: 123-45-6789"
        result, report = self.manager.redact_document(
            text, "test_doc", "test_operator", rule_categories=["contact"]
        )

        # Email should be redacted (contact category)
        assert "test@example.com" not in result
        assert "[EMAIL_ADDRESS]" in result

        # SSN should not be redacted (pii category)
        assert "123-45-6789" in result

    def test_redact_text_with_exclude_rules(self):
        """Test redacting with excluded rules."""
        text = "Email: test@example.com, SSN: 123-45-6789"
        # Remove email rule temporarily
        self.manager.remove_redaction_rule("email_address")
        result, report = self.manager.redact_document(text, "test_doc", "test_operator")

        # Email should not be redacted (excluded)
        assert "test@example.com" in result

        # SSN should be redacted
        assert "123-45-6789" not in result
        assert "***-**-****" in result

    def test_redact_text_disabled_rule(self):
        """Test that disabled rules are not applied."""
        # Disable the SSN rule
        self.manager.rules["ssn"].is_active = False

        text = "My SSN is 123-45-6789."
        result, report = self.manager.redact_document(text, "test_doc", "test_operator")

        # SSN should not be redacted because rule is disabled
        assert "123-45-6789" in result
        assert "***-**-****" not in result

    @patch("builtins.open", new_callable=mock_open, read_data="SSN: 123-45-6789")
    @patch("pathlib.Path.exists", return_value=True)
    def test_redact_file(self, mock_exists, mock_file):
        """Test redacting a file."""
        input_path = Path("input.txt")
        output_path = Path("output.txt")

        result = self.manager.redact_file(input_path, output_path)

        assert result["total_redactions"] >= 1
        assert "ssn" in result["redaction_counts"]
        assert result["input_file"] == str(input_path)
        assert result["output_file"] == str(output_path)

        # Verify write was called with redacted content
        handle = mock_file()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        assert "***-**-****" in written_content
