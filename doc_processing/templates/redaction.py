"""Document redaction and sanitization engine for sensitive information."""

import json
import logging
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class RedactionType(Enum):
    """Types of redaction operations."""

    REPLACE = "replace"  # Replace with placeholder text
    MASK = "mask"  # Mask with characters (e.g., ****)
    REMOVE = "remove"  # Remove completely
    ENCRYPT = "encrypt"  # Encrypt and store key separately
    HASH = "hash"  # Replace with hash value


class SensitivityLevel(Enum):
    """Sensitivity levels for different types of information."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RedactionRule:
    """Rule for identifying and redacting sensitive information."""

    rule_id: str
    name: str
    description: str
    pattern: str  # Regular expression pattern
    redaction_type: RedactionType
    sensitivity_level: SensitivityLevel
    replacement_text: Optional[str] = None
    categories: List[str] = None
    is_active: bool = True

    def __post_init__(self):
        if self.categories is None:
            self.categories = []

        # Compile regex pattern for efficiency
        try:
            self.compiled_pattern = re.compile(
                self.pattern, re.IGNORECASE | re.MULTILINE
            )
        except re.error as e:
            logger.error(f"Invalid regex pattern in rule {self.rule_id}: {e}")
            self.compiled_pattern = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["redaction_type"] = self.redaction_type.value
        data["sensitivity_level"] = self.sensitivity_level.value
        del data["compiled_pattern"]  # Remove compiled pattern from serialization
        return data


@dataclass
class RedactionMatch:
    """Represents a match found by a redaction rule."""

    rule_id: str
    start_pos: int
    end_pos: int
    original_text: str
    redacted_text: str
    redaction_type: RedactionType
    sensitivity_level: SensitivityLevel
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["redaction_type"] = self.redaction_type.value
        data["sensitivity_level"] = self.sensitivity_level.value
        return data


@dataclass
class RedactionReport:
    """Report of redaction operations performed on a document."""

    document_id: str
    original_length: int
    redacted_length: int
    redaction_count: int
    matches: List[RedactionMatch]
    rules_applied: List[str]
    sensitivity_levels_found: List[SensitivityLevel]
    redaction_timestamp: datetime
    operator_id: str
    is_reversible: bool = False
    encryption_key_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["matches"] = [match.to_dict() for match in self.matches]
        data["sensitivity_levels_found"] = [
            level.value for level in self.sensitivity_levels_found
        ]
        data["redaction_timestamp"] = self.redaction_timestamp.isoformat()
        return data


class RedactionEngine:
    """Advanced redaction engine for sensitive information in documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize redaction engine.

        Args:
            config: Configuration options for redaction
        """
        self.config = config or {}
        self.rules: Dict[str, RedactionRule] = {}
        self.encryption_keys: Dict[str, str] = {}

        # Configuration options
        self.preserve_formatting = self.config.get("preserve_formatting", True)
        self.create_audit_trail = self.config.get("create_audit_trail", True)
        self.enable_encryption = self.config.get("enable_encryption", True)
        self.hash_algorithm = self.config.get("hash_algorithm", "sha256")

        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Initialize default redaction rules for common sensitive information."""
        default_rules = [
            # Personal Identifiers
            RedactionRule(
                rule_id="ssn",
                name="Social Security Number",
                description="US Social Security Numbers",
                pattern=r"\b\d{3}-?\d{2}-?\d{4}\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.CRITICAL,
                replacement_text="***-**-****",
                categories=["pii", "government_id"],
            ),
            RedactionRule(
                rule_id="credit_card",
                name="Credit Card Number",
                description="Credit card numbers",
                pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.CRITICAL,
                replacement_text="****-****-****-****",
                categories=["financial", "pii"],
            ),
            RedactionRule(
                rule_id="phone_number",
                name="Phone Number",
                description="US phone numbers",
                pattern=r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.MEDIUM,
                replacement_text="[PHONE_NUMBER]",
                categories=["pii", "contact"],
            ),
            RedactionRule(
                rule_id="email_address",
                name="Email Address",
                description="Email addresses",
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.MEDIUM,
                replacement_text="[EMAIL_ADDRESS]",
                categories=["pii", "contact"],
            ),
            # Financial Information
            RedactionRule(
                rule_id="bank_account",
                name="Bank Account Number",
                description="Bank account numbers",
                pattern=r"\b(?:account|acct)[\s#:]*(\d{8,17})\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.CRITICAL,
                replacement_text="[ACCOUNT_****]",
                categories=["financial"],
            ),
            RedactionRule(
                rule_id="routing_number",
                name="Bank Routing Number",
                description="US bank routing numbers",
                pattern=r"\b(?:routing|aba)[\s#:]*(\d{9})\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.HIGH,
                replacement_text="[ROUTING_***]",
                categories=["financial"],
            ),
            # Legal Information
            RedactionRule(
                rule_id="case_number",
                name="Legal Case Number",
                description="Legal case numbers",
                pattern=r"\b(?:case|docket|file)[\s#:]*([A-Z0-9]{2,}-[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})?)\b",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.HIGH,
                replacement_text="[CASE_NUMBER]",
                categories=["legal"],
            ),
            # Medical Information
            RedactionRule(
                rule_id="medical_record",
                name="Medical Record Number",
                description="Medical record numbers",
                pattern=r"\b(?:mrn|medical\s+record|patient\s+id)[\s#:]*([A-Z0-9]{6,})\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.CRITICAL,
                replacement_text="[MRN_****]",
                categories=["medical", "phi"],
            ),
            # Technical Information
            RedactionRule(
                rule_id="ip_address",
                name="IP Address",
                description="IPv4 and IPv6 addresses",
                pattern=r"\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.LOW,
                replacement_text="[IP_ADDRESS]",
                categories=["technical"],
            ),
            RedactionRule(
                rule_id="api_key",
                name="API Key",
                description="API keys and tokens",
                pattern=r"\b(?:api[_-]?key|token|secret)[\s=:]*([A-Za-z0-9+/]{20,}={0,2})\b",
                redaction_type=RedactionType.MASK,
                sensitivity_level=SensitivityLevel.HIGH,
                replacement_text="[API_KEY_****]",
                categories=["technical", "credentials"],
            ),
            # Custom patterns for legal documents
            RedactionRule(
                rule_id="attorney_client_privilege",
                name="Attorney-Client Privileged Communication",
                description="Text marked as attorney-client privileged",
                pattern=r"\[ATTORNEY[-_]CLIENT[-_]PRIVILEGED\](.*?)\[/ATTORNEY[-_]CLIENT[-_]PRIVILEGED\]",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.CRITICAL,
                replacement_text="[ATTORNEY-CLIENT PRIVILEGED COMMUNICATION REDACTED]",
                categories=["legal", "privileged"],
            ),
            RedactionRule(
                rule_id="confidential_info",
                name="Confidential Information",
                description="Text marked as confidential",
                pattern=r"\[CONFIDENTIAL\](.*?)\[/CONFIDENTIAL\]",
                redaction_type=RedactionType.REPLACE,
                sensitivity_level=SensitivityLevel.HIGH,
                replacement_text="[CONFIDENTIAL INFORMATION REDACTED]",
                categories=["legal", "confidential"],
            ),
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    def add_redaction_rule(self, rule: RedactionRule):
        """Add a custom redaction rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added redaction rule: {rule.rule_id}")

    def remove_redaction_rule(self, rule_id: str):
        """Remove a redaction rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed redaction rule: {rule_id}")

    def get_redaction_rules(
        self, category: Optional[str] = None
    ) -> List[RedactionRule]:
        """Get redaction rules, optionally filtered by category."""
        rules = list(self.rules.values())

        if category:
            rules = [rule for rule in rules if category in rule.categories]

        return [rule for rule in rules if rule.is_active]

    def scan_for_sensitive_information(
        self, content: str, rule_categories: Optional[List[str]] = None
    ) -> List[RedactionMatch]:
        """Scan content for sensitive information without redacting.

        Args:
            content: Content to scan
            rule_categories: Optional list of rule categories to apply

        Returns:
            List of matches found
        """
        matches = []

        # Get applicable rules
        if rule_categories:
            applicable_rules = []
            for rule in self.rules.values():
                if rule.is_active and any(
                    cat in rule.categories for cat in rule_categories
                ):
                    applicable_rules.append(rule)
        else:
            applicable_rules = [rule for rule in self.rules.values() if rule.is_active]

        # Scan content with each rule
        for rule in applicable_rules:
            if rule.compiled_pattern:
                for match in rule.compiled_pattern.finditer(content):
                    redacted_text = self._generate_redacted_text(
                        match.group(), rule.redaction_type, rule.replacement_text
                    )

                    redaction_match = RedactionMatch(
                        rule_id=rule.rule_id,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        original_text=match.group(),
                        redacted_text=redacted_text,
                        redaction_type=rule.redaction_type,
                        sensitivity_level=rule.sensitivity_level,
                    )

                    matches.append(redaction_match)

        # Sort matches by position
        matches.sort(key=lambda m: m.start_pos)

        return matches

    def redact_document(
        self,
        content: str,
        document_id: str,
        operator_id: str,
        rule_categories: Optional[List[str]] = None,
        sensitivity_threshold: Optional[SensitivityLevel] = None,
    ) -> Tuple[str, RedactionReport]:
        """Redact sensitive information from document content.

        Args:
            content: Document content to redact
            document_id: Unique identifier for the document
            operator_id: ID of user performing redaction
            rule_categories: Optional list of rule categories to apply
            sensitivity_threshold: Minimum sensitivity level to redact

        Returns:
            Tuple of (redacted_content, redaction_report)
        """
        original_length = len(content)

        # Scan for sensitive information
        matches = self.scan_for_sensitive_information(content, rule_categories)

        # Filter by sensitivity threshold if specified
        if sensitivity_threshold:
            threshold_value = {
                SensitivityLevel.LOW: 0,
                SensitivityLevel.MEDIUM: 1,
                SensitivityLevel.HIGH: 2,
                SensitivityLevel.CRITICAL: 3,
            }

            min_threshold = threshold_value[sensitivity_threshold]
            matches = [
                match
                for match in matches
                if threshold_value[match.sensitivity_level] >= min_threshold
            ]

        # Apply redactions in reverse order to maintain positions
        redacted_content = content
        matches_applied = []

        for match in reversed(matches):
            # Apply redaction
            before = redacted_content[: match.start_pos]
            after = redacted_content[match.end_pos :]
            redacted_content = before + match.redacted_text + after

            matches_applied.insert(0, match)  # Maintain original order

        # Create redaction report
        rules_applied = list(set(match.rule_id for match in matches_applied))
        sensitivity_levels = list(
            set(match.sensitivity_level for match in matches_applied)
        )

        report = RedactionReport(
            document_id=document_id,
            original_length=original_length,
            redacted_length=len(redacted_content),
            redaction_count=len(matches_applied),
            matches=matches_applied,
            rules_applied=rules_applied,
            sensitivity_levels_found=sensitivity_levels,
            redaction_timestamp=datetime.now(),
            operator_id=operator_id,
            is_reversible=any(
                match.redaction_type == RedactionType.ENCRYPT
                for match in matches_applied
            ),
        )

        logger.info(
            f"Redacted document {document_id}: {len(matches_applied)} redactions applied"
        )

        return redacted_content, report

    def _generate_redacted_text(
        self,
        original_text: str,
        redaction_type: RedactionType,
        replacement_text: Optional[str] = None,
    ) -> str:
        """Generate redacted text based on redaction type.

        Args:
            original_text: Original text to redact
            redaction_type: Type of redaction to apply
            replacement_text: Optional replacement text

        Returns:
            Redacted text
        """
        if redaction_type == RedactionType.REPLACE:
            return replacement_text or "[REDACTED]"

        elif redaction_type == RedactionType.MASK:
            if replacement_text:
                return replacement_text
            else:
                # Create mask with same length
                return "*" * len(original_text)

        elif redaction_type == RedactionType.REMOVE:
            return ""

        elif redaction_type == RedactionType.ENCRYPT:
            # Encrypt the text and return a placeholder
            if self.enable_encryption:
                encrypted_text, key_id = self._encrypt_text(original_text)
                return f"[ENCRYPTED:{key_id}]"
            else:
                return "[ENCRYPTED_CONTENT]"

        elif redaction_type == RedactionType.HASH:
            # Create hash of the text
            import hashlib

            hash_value = hashlib.sha256(original_text.encode()).hexdigest()[:8]
            return f"[HASH:{hash_value}]"

        else:
            return "[REDACTED]"

    def _encrypt_text(self, text: str) -> Tuple[str, str]:
        """Encrypt text and return encrypted text with key ID.

        Args:
            text: Text to encrypt

        Returns:
            Tuple of (encrypted_text, key_id)
        """
        try:
            from cryptography.fernet import Fernet

            # Generate encryption key
            key = Fernet.generate_key()
            key_id = secrets.token_hex(8)

            # Store key for potential reversal
            self.encryption_keys[key_id] = key.decode()

            # Encrypt text
            f = Fernet(key)
            encrypted_text = f.encrypt(text.encode()).decode()

            return encrypted_text, key_id

        except ImportError:
            logger.warning(
                "Cryptography library not available, using placeholder encryption"
            )
            key_id = secrets.token_hex(8)
            return f"ENCRYPTED_{secrets.token_hex(16)}", key_id

    def redact_file(
        self,
        input_path: Path,
        output_path: Path,
        operator_id: str = "system",
        rule_categories: Optional[List[str]] = None,
        sensitivity_threshold: Optional[SensitivityLevel] = None,
    ) -> Dict[str, Any]:
        """Redact sensitive information from a file.

        Args:
            input_path: Path to input file
            output_path: Path to output file
            operator_id: ID of user performing redaction
            rule_categories: Optional list of rule categories to apply
            sensitivity_threshold: Minimum sensitivity level to redact

        Returns:
            Dictionary with redaction results
        """
        # Read input file
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Perform redaction
        document_id = str(input_path)
        redacted_content, report = self.redact_document(
            content, document_id, operator_id, rule_categories, sensitivity_threshold
        )

        # Write redacted content to output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(redacted_content)

        # Create result summary
        redaction_counts = {}
        for rule_id in report.rules_applied:
            redaction_counts[rule_id] = sum(
                1 for match in report.matches if match.rule_id == rule_id
            )

        return {
            "input_file": str(input_path),
            "output_file": str(output_path),
            "total_redactions": report.redaction_count,
            "redaction_counts": redaction_counts,
            "rules_applied": report.rules_applied,
            "sensitivity_levels_found": [
                level.value for level in report.sensitivity_levels_found
            ],
            "redaction_report": report,
        }

    def create_template_from_redacted_document(
        self,
        redacted_content: str,
        redaction_report: RedactionReport,
        template_name: str,
    ) -> Dict[str, Any]:
        """Create a template from a redacted document.

        Args:
            redacted_content: Redacted document content
            redaction_report: Redaction report
            template_name: Name for the template

        Returns:
            Template definition with variable placeholders
        """
        template_content = redacted_content
        variables = []
        variable_map = {}

        # Convert redacted text to template variables
        for i, match in enumerate(redaction_report.matches):
            var_name = f"var_{match.rule_id}_{i}"
            variable_placeholder = f"{{{{{var_name}}}}}"

            # Replace redacted text with variable placeholder
            template_content = template_content.replace(
                match.redacted_text, variable_placeholder, 1
            )

            variables.append(
                {
                    "name": var_name,
                    "type": match.rule_id,
                    "sensitivity_level": match.sensitivity_level.value,
                    "description": f"Redacted {match.rule_id}",
                    "example": (
                        match.original_text
                        if match.sensitivity_level != SensitivityLevel.CRITICAL
                        else "[EXAMPLE]"
                    ),
                }
            )

            variable_map[var_name] = {
                "original_position": match.start_pos,
                "rule_id": match.rule_id,
                "redaction_type": match.redaction_type.value,
            }

        return {
            "name": template_name,
            "content": template_content,
            "variables": variables,
            "variable_map": variable_map,
            "metadata": {
                "created_from_redaction": True,
                "source_document": redaction_report.document_id,
                "redaction_timestamp": redaction_report.redaction_timestamp.isoformat(),
                "redaction_count": redaction_report.redaction_count,
                "sensitivity_levels": [
                    level.value for level in redaction_report.sensitivity_levels_found
                ],
            },
        }


class DocumentSanitizer:
    """Sanitizes documents by removing or cleaning potentially harmful content."""

    def __init__(self):
        """Initialize document sanitizer."""
        # Patterns for potentially harmful content
        self.harmful_patterns = {
            "embedded_scripts": re.compile(
                r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", re.IGNORECASE
            ),
            "embedded_objects": re.compile(
                r"<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>", re.IGNORECASE
            ),
            "embedded_iframes": re.compile(
                r"<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>", re.IGNORECASE
            ),
            "javascript_urls": re.compile(r'javascript:[^"\'>\s]+', re.IGNORECASE),
            "vbscript_urls": re.compile(r'vbscript:[^"\'>\s]+', re.IGNORECASE),
            "data_urls": re.compile(r'data:[^"\'>\s;,]+[;,][^"\'>\s]*', re.IGNORECASE),
            "external_links": re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE),
            "email_links": re.compile(r'mailto:[^\s"\'<>]+', re.IGNORECASE),
        }

    def sanitize_content(
        self,
        content: str,
        remove_scripts: bool = True,
        remove_objects: bool = True,
        remove_external_links: bool = False,
        preserve_structure: bool = True,
    ) -> Tuple[str, List[str]]:
        """Sanitize document content by removing harmful elements.

        Args:
            content: Content to sanitize
            remove_scripts: Whether to remove script elements
            remove_objects: Whether to remove embedded objects
            remove_external_links: Whether to remove external links
            preserve_structure: Whether to preserve document structure

        Returns:
            Tuple of (sanitized_content, removed_elements)
        """
        sanitized_content = content
        removed_elements = []

        # Remove scripts
        if remove_scripts:
            for pattern_name in [
                "embedded_scripts",
                "javascript_urls",
                "vbscript_urls",
            ]:
                pattern = self.harmful_patterns[pattern_name]
                matches = pattern.findall(sanitized_content)
                if matches:
                    sanitized_content = pattern.sub(
                        "[REMOVED_FOR_SECURITY]", sanitized_content
                    )
                    removed_elements.extend(
                        [f"{pattern_name}: {match}" for match in matches[:5]]
                    )

        # Remove embedded objects
        if remove_objects:
            for pattern_name in ["embedded_objects", "embedded_iframes"]:
                pattern = self.harmful_patterns[pattern_name]
                matches = pattern.findall(sanitized_content)
                if matches:
                    replacement = (
                        "[EMBEDDED_OBJECT_REMOVED]" if preserve_structure else ""
                    )
                    sanitized_content = pattern.sub(replacement, sanitized_content)
                    removed_elements.extend(
                        [f"{pattern_name}: {match}" for match in matches[:5]]
                    )

        # Remove external links
        if remove_external_links:
            for pattern_name in ["external_links", "email_links", "data_urls"]:
                pattern = self.harmful_patterns[pattern_name]
                matches = pattern.findall(sanitized_content)
                if matches:
                    sanitized_content = pattern.sub(
                        "[EXTERNAL_LINK_REMOVED]", sanitized_content
                    )
                    removed_elements.extend(
                        [f"{pattern_name}: {match}" for match in matches[:5]]
                    )

        return sanitized_content, removed_elements
