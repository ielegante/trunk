"""Auto-renumbering system for section references."""

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SectionNumber:
    """Represents a hierarchical section number."""

    parts: List[int]
    prefix: Optional[str] = None  # e.g., "Article", "Section", "§"
    suffix: Optional[str] = None  # e.g., ".", ":"

    def to_string(self, separator: str = ".") -> str:
        """Convert to string representation."""
        number = separator.join(str(p) for p in self.parts)

        if self.prefix:
            number = f"{self.prefix} {number}"
        if self.suffix:
            number = f"{number}{self.suffix}"

        return number

    def increment(self, level: int = -1) -> "SectionNumber":
        """Increment section number at specified level."""
        new_parts = self.parts.copy()

        if level == -1:
            level = len(new_parts) - 1

        if 0 <= level < len(new_parts):
            new_parts[level] += 1
            # Reset deeper levels
            for i in range(level + 1, len(new_parts)):
                new_parts[i] = 1

        return SectionNumber(new_parts, self.prefix, self.suffix)

    def add_sublevel(self) -> "SectionNumber":
        """Add a new sublevel."""
        new_parts = self.parts.copy()
        new_parts.append(1)
        return SectionNumber(new_parts, self.prefix, self.suffix)

    def parent(self) -> Optional["SectionNumber"]:
        """Get parent section number."""
        if len(self.parts) > 1:
            return SectionNumber(self.parts[:-1], self.prefix, self.suffix)
        return None


@dataclass
class Section:
    """Represents a document section."""

    section_id: str
    title: str
    number: SectionNumber
    level: int
    content: str
    line_start: int
    line_end: int
    subsections: List["Section"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["number"] = self.number.to_string()
        data["subsections"] = [s.to_dict() for s in self.subsections]
        return data


@dataclass
class RenumberingRule:
    """Rule for renumbering sections."""

    rule_id: str
    name: str
    pattern: str  # Regex pattern to match
    numbering_scheme: str  # "numeric", "alpha", "roman"
    start_at: int = 1
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    applies_to_level: Optional[int] = None  # None means all levels

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class AutoRenumberingSystem:
    """System for automatic section renumbering."""

    # Default patterns
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    PLACEHOLDER_PATTERN = re.compile(r"\{\{([^}]+)\}\}")
    SECTION_REF_PATTERN = re.compile(
        r"(?:Section|§|Article)\s*(\d+(?:\.\d+)*)", re.IGNORECASE
    )

    # Numbering schemes
    SCHEMES = {
        "numeric": lambda n: str(n),
        "alpha_lower": lambda n: chr(ord("a") + n - 1) if n <= 26 else str(n),
        "alpha_upper": lambda n: chr(ord("A") + n - 1) if n <= 26 else str(n),
        "roman_lower": lambda n: AutoRenumberingSystem._to_roman(n).lower(),
        "roman_upper": lambda n: AutoRenumberingSystem._to_roman(n),
    }

    def __init__(self):
        """Initialize auto-renumbering system."""
        self.rules: List[RenumberingRule] = self._default_rules()
        self.section_map: Dict[str, Section] = {}
        self.placeholder_map: Dict[str, str] = {}

    def parse_document_structure(self, content: str) -> List[Section]:
        """Parse document structure into sections.

        Args:
            content: Document content

        Returns:
            List of top-level sections
        """
        lines = content.split("\n")
        sections = []
        section_stack = []
        current_content = []
        line_num = 0

        for i, line in enumerate(lines):
            heading_match = self.HEADING_PATTERN.match(line)

            if heading_match:
                # Save previous section content
                if section_stack:
                    section_stack[-1].content = "\n".join(current_content).strip()
                    section_stack[-1].line_end = line_num - 1

                # Extract heading info
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Create section
                section = Section(
                    section_id=self._generate_section_id(title),
                    title=title,
                    number=SectionNumber([1]),  # Will be renumbered
                    level=level,
                    content="",
                    line_start=i,
                    line_end=i,
                )

                # Find parent section
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()

                if section_stack:
                    # Add as subsection
                    section_stack[-1].subsections.append(section)
                else:
                    # Top-level section
                    sections.append(section)

                section_stack.append(section)
                current_content = []
            else:
                current_content.append(line)

            line_num = i

        # Save last section content
        if section_stack:
            section_stack[-1].content = "\n".join(current_content).strip()
            section_stack[-1].line_end = line_num

        # Renumber sections
        self._renumber_sections(sections)

        # Build section map
        self._build_section_map(sections)

        return sections

    def apply_renumbering(
        self, content: str, custom_rules: Optional[List[RenumberingRule]] = None
    ) -> str:
        """Apply automatic renumbering to document.

        Args:
            content: Document content
            custom_rules: Optional custom renumbering rules

        Returns:
            Content with renumbering applied
        """
        # Parse structure
        sections = self.parse_document_structure(content)

        # Apply custom rules if provided
        if custom_rules:
            self.rules.extend(custom_rules)

        # Build renumbering map
        renumber_map = self._build_renumber_map(sections)

        # Apply to content
        result = content

        # Replace placeholders
        for placeholder, replacement in renumber_map.items():
            pattern = f"{{{{{placeholder}}}}}"
            result = result.replace(pattern, replacement)

        # Update section references
        result = self._update_section_references(result, sections)

        return result

    def extract_placeholders(self, content: str) -> List[str]:
        """Extract all placeholders from content.

        Args:
            content: Document content

        Returns:
            List of placeholder names
        """
        placeholders = []

        for match in self.PLACEHOLDER_PATTERN.finditer(content):
            placeholder = match.group(1)
            if placeholder not in placeholders:
                placeholders.append(placeholder)

        return placeholders

    def generate_renumber_map(self, sections: List[Section]) -> Dict[str, str]:
        """Generate mapping of placeholders to section numbers.

        Args:
            sections: Document sections

        Returns:
            Dictionary mapping placeholder names to section numbers
        """
        renumber_map = {}

        def process_sections(section_list: List[Section], parent_path: str = ""):
            for section in section_list:
                # Generate placeholder name from section title
                placeholder = self._title_to_placeholder(section.title)

                # Store mapping
                renumber_map[placeholder] = section.number.to_string()

                # Also store with parent path for uniqueness
                if parent_path:
                    full_placeholder = f"{parent_path}_{placeholder}"
                    renumber_map[full_placeholder] = section.number.to_string()

                # Process subsections
                if section.subsections:
                    process_sections(section.subsections, placeholder)

        process_sections(sections)
        return renumber_map

    def find_section_by_placeholder(self, placeholder: str) -> Optional[Section]:
        """Find section by placeholder name.

        Args:
            placeholder: Placeholder name

        Returns:
            Section if found, None otherwise
        """
        # Check direct mapping
        if placeholder in self.placeholder_map:
            section_id = self.placeholder_map[placeholder]
            return self.section_map.get(section_id)

        # Try fuzzy matching
        placeholder_lower = placeholder.lower().replace("-", "_")
        for stored_placeholder, section_id in self.placeholder_map.items():
            if stored_placeholder.lower().replace("-", "_") == placeholder_lower:
                return self.section_map.get(section_id)

        return None

    def _default_rules(self) -> List[RenumberingRule]:
        """Get default renumbering rules."""
        return [
            RenumberingRule(
                rule_id="main_sections",
                name="Main Sections",
                pattern=r"^#\s+",
                numbering_scheme="numeric",
                start_at=1,
                suffix=".",
                applies_to_level=1,
            ),
            RenumberingRule(
                rule_id="subsections",
                name="Subsections",
                pattern=r"^##\s+",
                numbering_scheme="numeric",
                start_at=1,
                applies_to_level=2,
            ),
            RenumberingRule(
                rule_id="articles",
                name="Articles",
                pattern=r"^#+\s+Article",
                numbering_scheme="roman_upper",
                prefix="Article",
                start_at=1,
            ),
        ]

    def _renumber_sections(
        self, sections: List[Section], parent_number: Optional[SectionNumber] = None
    ):
        """Recursively renumber sections."""
        for i, section in enumerate(sections):
            # Determine numbering based on rules
            rule = self._find_applicable_rule(section)

            if parent_number:
                # Subsection numbering
                if i == 0:
                    section.number = parent_number.add_sublevel()
                else:
                    section.number = sections[i - 1].number.increment()
            else:
                # Top-level numbering
                if i == 0:
                    section.number = SectionNumber([1])
                else:
                    section.number = sections[i - 1].number.increment()

            # Apply rule formatting
            if rule:
                section.number.prefix = rule.prefix
                section.number.suffix = rule.suffix

            # Renumber subsections
            if section.subsections:
                self._renumber_sections(section.subsections, section.number)

    def _build_section_map(self, sections: List[Section]):
        """Build section ID to section mapping."""

        def add_sections(section_list: List[Section]):
            for section in section_list:
                self.section_map[section.section_id] = section

                # Add placeholder mapping
                placeholder = self._title_to_placeholder(section.title)
                self.placeholder_map[placeholder] = section.section_id

                if section.subsections:
                    add_sections(section.subsections)

        add_sections(sections)

    def _build_renumber_map(self, sections: List[Section]) -> Dict[str, str]:
        """Build complete renumbering map."""
        renumber_map = self.generate_renumber_map(sections)

        # Add variations
        variations = {}
        for placeholder, number in renumber_map.items():
            # Add hyphenated version
            hyphenated = placeholder.replace("_", "-")
            if hyphenated != placeholder:
                variations[hyphenated] = number

            # Add space version
            spaced = placeholder.replace("_", " ")
            if spaced != placeholder:
                variations[spaced] = number

        renumber_map.update(variations)
        return renumber_map

    def _update_section_references(self, content: str, sections: List[Section]) -> str:
        """Update section references in content."""
        result = content

        # Build number to section mapping
        number_map = {}

        def map_sections(section_list: List[Section]):
            for section in section_list:
                number_str = section.number.to_string()
                number_map[number_str] = section

                # Also map without prefix/suffix
                bare_number = ".".join(str(p) for p in section.number.parts)
                number_map[bare_number] = section

                if section.subsections:
                    map_sections(section.subsections)

        map_sections(sections)

        # Update references
        def replace_reference(match):
            old_number = match.group(1)

            # Try to find new section with similar structure
            if old_number in number_map:
                section = number_map[old_number]
                return match.group(0).replace(old_number, section.number.to_string())

            return match.group(0)

        result = self.SECTION_REF_PATTERN.sub(replace_reference, result)

        return result

    def _find_applicable_rule(self, section: Section) -> Optional[RenumberingRule]:
        """Find applicable renumbering rule for section."""
        for rule in self.rules:
            if rule.applies_to_level and rule.applies_to_level != section.level:
                continue

            # Check if pattern matches section title or content
            if re.search(rule.pattern, f"{'#' * section.level} {section.title}"):
                return rule

        return None

    def _generate_section_id(self, title: str) -> str:
        """Generate unique section ID from title."""
        # Clean title
        clean_title = re.sub(r"[^\w\s-]", "", title.lower())
        clean_title = re.sub(r"[-\s]+", "-", clean_title)
        return clean_title.strip("-")

    def _title_to_placeholder(self, title: str) -> str:
        """Convert section title to placeholder name."""
        # Remove special characters and convert to snake_case
        placeholder = re.sub(r"[^\w\s]", "", title)
        placeholder = re.sub(r"\s+", "_", placeholder)
        placeholder = placeholder.lower().strip("_")
        return placeholder

    @staticmethod
    def _to_roman(num: int) -> str:
        """Convert number to Roman numerals."""
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
        roman_num = ""
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman_num += syms[i]
                num -= val[i]
            i += 1
        return roman_num
