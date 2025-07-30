"""Redaction system for removing sensitive content from templates."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RedactionRule:
    """Defines a rule for redacting content."""

    rule_id: str
    name: str
    description: str
    pattern: str  # Regex pattern
    replacement: str
    rule_type: str  # "regex", "keyword", "entity"
    enabled: bool = True
    case_sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class RedactionResult:
    """Result of a redaction operation."""

    original_length: int
    redacted_length: int
    redactions_count: int
    redacted_items: List[Dict[str, Any]]  # What was redacted
    warnings: List[str]
    confidence_score: float  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class SensitiveContent:
    """Represents detected sensitive content."""

    content_type: str  # "ssn", "email", "phone", etc.
    original_text: str
    start_position: int
    end_position: int
    confidence: float
    context: str  # Surrounding text for context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class RedactionSystem:
    """System for detecting and removing sensitive content."""

    # Built-in patterns for common sensitive data
    BUILT_IN_PATTERNS = {
        "ssn": {
            "pattern": r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b",
            "description": "Social Security Number",
            "replacement": "[SSN REDACTED]",
        },
        "ein": {
            "pattern": r"\b\d{2}-\d{7}\b",
            "description": "Employer Identification Number",
            "replacement": "[EIN REDACTED]",
        },
        "email": {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "description": "Email address",
            "replacement": "[EMAIL REDACTED]",
        },
        "phone": {
            "pattern": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
            "description": "Phone number",
            "replacement": "[PHONE REDACTED]",
        },
        "credit_card": {
            "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b",
            "description": "Credit card number",
            "replacement": "[CREDIT CARD REDACTED]",
        },
        "bank_account": {
            "pattern": r"\b[0-9]{8,17}\b",
            "description": "Bank account number",
            "replacement": "[ACCOUNT NUMBER REDACTED]",
        },
        "ip_address": {
            "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            "description": "IP address",
            "replacement": "[IP ADDRESS REDACTED]",
        },
        "date_of_birth": {
            "pattern": r"\b(?:DOB|Date of Birth|Birth Date):?\s*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
            "description": "Date of birth",
            "replacement": "[DOB REDACTED]",
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize redaction system.

        Args:
            config_path: Optional path to custom redaction rules
        """
        self.rules = self._load_built_in_rules()
        self.custom_rules = []

        if config_path:
            self.custom_rules = self._load_custom_rules(config_path)

        # Entity recognition patterns
        self.entity_patterns = self._build_entity_patterns()

        # Client name tracking
        self.known_client_names = set()
        self.known_matter_numbers = set()

    def scan_content(self, content: str) -> List[SensitiveContent]:
        """Scan content for sensitive information.

        Args:
            content: Content to scan

        Returns:
            List of detected sensitive content
        """
        sensitive_items = []

        # Apply all redaction rules
        for rule in self.rules + self.custom_rules:
            if not rule.enabled:
                continue

            pattern = re.compile(
                rule.pattern, re.IGNORECASE if not rule.case_sensitive else 0
            )

            for match in pattern.finditer(content):
                # Get context around match
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

                sensitive_items.append(
                    SensitiveContent(
                        content_type=rule.rule_type,
                        original_text=match.group(),
                        start_position=match.start(),
                        end_position=match.end(),
                        confidence=0.9 if rule.rule_type == "regex" else 0.7,
                        context=context,
                    )
                )

        # Scan for entity names
        entity_items = self._scan_for_entities(content)
        sensitive_items.extend(entity_items)

        # Sort by position
        sensitive_items.sort(key=lambda x: x.start_position)

        return sensitive_items

    def redact_content(
        self,
        content: str,
        aggressive: bool = False,
        custom_rules: Optional[List[RedactionRule]] = None,
    ) -> Tuple[str, RedactionResult]:
        """Redact sensitive content from text.

        Args:
            content: Content to redact
            aggressive: If True, use more aggressive redaction
            custom_rules: Additional rules to apply

        Returns:
            Tuple of (redacted_content, result)
        """
        original_length = len(content)
        redacted_content = content
        redacted_items = []
        warnings = []

        # Combine all rules
        all_rules = self.rules + self.custom_rules
        if custom_rules:
            all_rules.extend(custom_rules)

        # Apply redaction rules
        for rule in all_rules:
            if not rule.enabled:
                continue

            pattern = re.compile(
                rule.pattern, re.IGNORECASE if not rule.case_sensitive else 0
            )
            matches = list(pattern.finditer(redacted_content))

            if matches:
                # Replace matches in reverse order to maintain positions
                for match in reversed(matches):
                    original_text = match.group()
                    redacted_items.append(
                        {
                            "type": rule.rule_type,
                            "rule": rule.name,
                            "original_length": len(original_text),
                            "position": match.start(),
                        }
                    )

                    redacted_content = (
                        redacted_content[: match.start()]
                        + rule.replacement
                        + redacted_content[match.end() :]
                    )

        # Entity redaction
        if aggressive:
            redacted_content, entity_redactions = self._redact_entities(
                redacted_content
            )
            redacted_items.extend(entity_redactions)

        # Check for potential missed sensitive content
        remaining_sensitive = self._check_remaining_sensitive(redacted_content)
        if remaining_sensitive:
            warnings.extend(remaining_sensitive)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(redacted_items, warnings)

        result = RedactionResult(
            original_length=original_length,
            redacted_length=len(redacted_content),
            redactions_count=len(redacted_items),
            redacted_items=redacted_items,
            warnings=warnings,
            confidence_score=confidence_score,
        )

        return redacted_content, result

    def create_redaction_checklist(self, content: str) -> Dict[str, Any]:
        """Create a checklist for manual redaction review.

        Args:
            content: Content to analyze

        Returns:
            Checklist dictionary
        """
        checklist = {
            "automated_detections": [],
            "manual_review_items": [],
            "suggested_actions": [],
            "risk_assessment": {},
        }

        # Get automated detections
        sensitive_items = self.scan_content(content)

        for item in sensitive_items:
            checklist["automated_detections"].append(
                {
                    "type": item.content_type,
                    "text": (
                        item.original_text[:20] + "..."
                        if len(item.original_text) > 20
                        else item.original_text
                    ),
                    "position": f"Characters {item.start_position}-{item.end_position}",
                    "confidence": item.confidence,
                }
            )

        # Add manual review items
        checklist["manual_review_items"] = [
            {
                "item": "Client names and aliases",
                "action": 'Replace with generic terms like "Client" or "[Party A]"',
                "required": True,
            },
            {
                "item": "Matter numbers and case references",
                "action": "Replace with generic identifiers",
                "required": True,
            },
            {
                "item": "Specific dates related to client matters",
                "action": 'Consider replacing with relative dates or "[DATE]"',
                "required": False,
            },
            {
                "item": "Financial amounts and terms",
                "action": 'Replace with placeholders like "[AMOUNT]" or ranges',
                "required": True,
            },
            {
                "item": "Geographic locations",
                "action": 'Replace specific addresses with "[ADDRESS]" or city/state only',
                "required": True,
            },
            {
                "item": "Third-party names",
                "action": 'Replace with role descriptions like "[VENDOR]" or "[COUNTERPARTY]"',
                "required": True,
            },
        ]

        # Suggest actions based on content
        if re.search(r"\$[\d,]+", content):
            checklist["suggested_actions"].append(
                "Replace specific dollar amounts with ranges or placeholders"
            )

        if re.search(r"\b\d{4}\b", content):
            checklist["suggested_actions"].append(
                "Review four-digit numbers that might be years or codes"
            )

        if re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", content):
            checklist["suggested_actions"].append(
                "Review proper names for client/party identification"
            )

        # Risk assessment
        risk_score = len(sensitive_items) * 10
        risk_score += len(re.findall(r"[A-Z][a-z]+ [A-Z][a-z]+", content)) * 2

        checklist["risk_assessment"] = {
            "score": min(risk_score, 100),
            "level": (
                "High" if risk_score > 50 else "Medium" if risk_score > 20 else "Low"
            ),
            "recommendation": (
                "Thorough manual review required"
                if risk_score > 50
                else "Standard review recommended"
            ),
        }

        return checklist

    def sanitize_for_template(self, content: str) -> Tuple[str, Dict[str, str]]:
        """Sanitize content for use as a template.

        Args:
            content: Content to sanitize

        Returns:
            Tuple of (sanitized_content, placeholder_map)
        """
        sanitized_content = content
        placeholder_map = {}
        placeholder_counter = {
            "party": 1,
            "date": 1,
            "amount": 1,
            "location": 1,
            "term": 1,
        }

        # Replace party names
        party_pattern = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
        for match in party_pattern.finditer(content):
            name = match.group()
            if name not in placeholder_map:
                placeholder = f"{{{{PARTY_{placeholder_counter['party']}}}}}"
                placeholder_map[name] = placeholder
                placeholder_counter["party"] += 1

            sanitized_content = sanitized_content.replace(name, placeholder_map[name])

        # Replace dates
        date_patterns = [
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
            r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        ]

        for pattern in date_patterns:
            for match in re.finditer(pattern, sanitized_content, re.IGNORECASE):
                date = match.group()
                if date not in placeholder_map:
                    placeholder = f"{{{{DATE_{placeholder_counter['date']}}}}}"
                    placeholder_map[date] = placeholder
                    placeholder_counter["date"] += 1

                sanitized_content = sanitized_content.replace(
                    date, placeholder_map[date]
                )

        # Replace amounts
        amount_pattern = re.compile(r"\$[\d,]+(?:\.\d{2})?")
        for match in amount_pattern.finditer(sanitized_content):
            amount = match.group()
            if amount not in placeholder_map:
                placeholder = f"{{{{AMOUNT_{placeholder_counter['amount']}}}}}"
                placeholder_map[amount] = placeholder
                placeholder_counter["amount"] += 1

            sanitized_content = sanitized_content.replace(
                amount, placeholder_map[amount]
            )

        return sanitized_content, placeholder_map

    def add_client_name(self, name: str):
        """Add a client name to track for redaction.

        Args:
            name: Client name to track
        """
        self.known_client_names.add(name.lower())

        # Also add variations
        parts = name.split()
        if len(parts) >= 2:
            # Add last name only
            self.known_client_names.add(parts[-1].lower())
            # Add first name last name
            self.known_client_names.add(f"{parts[0]} {parts[-1]}".lower())

    def add_matter_number(self, matter_number: str):
        """Add a matter number to track for redaction.

        Args:
            matter_number: Matter number to track
        """
        self.known_matter_numbers.add(matter_number)

    def _load_built_in_rules(self) -> List[RedactionRule]:
        """Load built-in redaction rules.

        Returns:
            List of built-in rules
        """
        rules = []

        for rule_id, rule_data in self.BUILT_IN_PATTERNS.items():
            rules.append(
                RedactionRule(
                    rule_id=rule_id,
                    name=rule_id.replace("_", " ").title(),
                    description=rule_data["description"],
                    pattern=rule_data["pattern"],
                    replacement=rule_data["replacement"],
                    rule_type="regex",
                    enabled=True,
                    case_sensitive=False,
                )
            )

        return rules

    def _load_custom_rules(self, config_path: Path) -> List[RedactionRule]:
        """Load custom redaction rules from config file.

        Args:
            config_path: Path to config file

        Returns:
            List of custom rules
        """
        if not config_path.exists():
            logger.warning(f"Custom rules file not found: {config_path}")
            return []

        try:
            with open(config_path, "r") as f:
                rules_data = json.load(f)

            rules = []
            for rule_data in rules_data:
                rules.append(RedactionRule(**rule_data))

            return rules

        except Exception as e:
            logger.error(f"Failed to load custom rules: {e}")
            return []

    def _build_entity_patterns(self) -> Dict[str, Pattern]:
        """Build patterns for entity recognition.

        Returns:
            Dictionary of entity patterns
        """
        patterns = {
            "person_name": re.compile(r"\b[A-Z][a-z]+ (?:[A-Z]\. )?[A-Z][a-z]+\b"),
            "company_name": re.compile(
                r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Inc|LLC|Corp|Corporation|Company|LLP|LP|Ltd)\b"
            ),
            "address": re.compile(
                r"\b\d+\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b",
                re.IGNORECASE,
            ),
        }

        return patterns

    def _scan_for_entities(self, content: str) -> List[SensitiveContent]:
        """Scan for entity names in content.

        Args:
            content: Content to scan

        Returns:
            List of detected entities
        """
        entities = []

        # Check for known client names
        content_lower = content.lower()
        for client_name in self.known_client_names:
            index = content_lower.find(client_name)
            while index != -1:
                entities.append(
                    SensitiveContent(
                        content_type="client_name",
                        original_text=content[index : index + len(client_name)],
                        start_position=index,
                        end_position=index + len(client_name),
                        confidence=1.0,
                        context=content[
                            max(0, index - 50) : min(
                                len(content), index + len(client_name) + 50
                            )
                        ],
                    )
                )
                index = content_lower.find(client_name, index + 1)

        # Check for matter numbers
        for matter_number in self.known_matter_numbers:
            index = content.find(matter_number)
            while index != -1:
                entities.append(
                    SensitiveContent(
                        content_type="matter_number",
                        original_text=matter_number,
                        start_position=index,
                        end_position=index + len(matter_number),
                        confidence=1.0,
                        context=content[
                            max(0, index - 50) : min(
                                len(content), index + len(matter_number) + 50
                            )
                        ],
                    )
                )
                index = content.find(matter_number, index + 1)

        return entities

    def _redact_entities(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Redact entity names from content.

        Args:
            content: Content to redact

        Returns:
            Tuple of (redacted_content, redaction_list)
        """
        redacted_content = content
        redactions = []

        # Apply entity patterns
        for entity_type, pattern in self.entity_patterns.items():
            matches = list(pattern.finditer(redacted_content))

            for match in reversed(matches):
                original_text = match.group()
                replacement = f"[{entity_type.upper().replace('_', ' ')} REDACTED]"

                redactions.append(
                    {
                        "type": "entity",
                        "rule": entity_type,
                        "original_length": len(original_text),
                        "position": match.start(),
                    }
                )

                redacted_content = (
                    redacted_content[: match.start()]
                    + replacement
                    + redacted_content[match.end() :]
                )

        return redacted_content, redactions

    def _check_remaining_sensitive(self, content: str) -> List[str]:
        """Check for potentially missed sensitive content.

        Args:
            content: Redacted content to check

        Returns:
            List of warnings
        """
        warnings = []

        # Check for remaining numbers that might be sensitive
        if re.search(r"\b\d{6,}\b", content):
            warnings.append(
                "Document contains long number sequences that may need review"
            )

        # Check for email-like patterns
        if re.search(r"@[a-zA-Z]+\.[a-zA-Z]+", content):
            warnings.append("Document may contain partial email addresses")

        # Check for potential names
        name_pattern = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")
        names_found = name_pattern.findall(content)
        if len(names_found) > 3:
            warnings.append(
                f"Document contains {len(names_found)} potential names that may need review"
            )

        return warnings

    def _calculate_confidence(
        self, redactions: List[Dict[str, Any]], warnings: List[str]
    ) -> float:
        """Calculate confidence score for redaction.

        Args:
            redactions: List of redactions made
            warnings: List of warnings

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not redactions and not warnings:
            return 1.0

        base_score = 0.9

        # Reduce score based on warnings
        base_score -= len(warnings) * 0.1

        # Increase score based on successful redactions
        base_score += min(len(redactions) * 0.02, 0.1)

        return max(0.0, min(1.0, base_score))
