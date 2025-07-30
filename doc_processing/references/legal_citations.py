"""Legal citation extraction and parsing system.

This module provides comprehensive extraction and parsing of legal citations
including case law, statutes, regulations, and other legal authorities.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CitationType(Enum):
    """Types of legal citations."""

    CASE = "case"  # Case law citations
    STATUTE = "statute"  # Federal and state statutes
    REGULATION = "regulation"  # Federal regulations (CFR)
    CONSTITUTION = "constitution"  # Constitutional citations
    TREATY = "treaty"  # International treaties
    RESTATEMENT = "restatement"  # Restatements of law
    LAW_REVIEW = "law_review"  # Law review articles
    BOOK = "book"  # Legal treatises and books
    RULE = "rule"  # Court rules (FRCP, FRE, etc.)
    ADMINISTRATIVE = "administrative"  # Administrative decisions
    PATENT = "patent"  # Patent citations
    UNPUBLISHED = "unpublished"  # Unpublished opinions


class JurisdictionType(Enum):
    """Legal jurisdiction types."""

    FEDERAL = "federal"
    STATE = "state"
    INTERNATIONAL = "international"
    ADMINISTRATIVE = "administrative"
    UNKNOWN = "unknown"


@dataclass
class Reporter:
    """Legal reporter information."""

    abbreviation: str
    full_name: str
    series: Optional[str]
    jurisdiction: JurisdictionType
    court_level: Optional[str]  # supreme, appellate, district, etc.


@dataclass
class Citation:
    """Represents a parsed legal citation."""

    citation_id: str
    citation_type: CitationType
    raw_text: str
    normalized_text: str

    # Common fields
    title: Optional[str] = None
    year: Optional[int] = None
    jurisdiction: JurisdictionType = JurisdictionType.UNKNOWN

    # Case law specific
    case_name: Optional[str] = None
    reporter: Optional[Reporter] = None
    volume: Optional[str] = None
    page: Optional[str] = None
    pincite: Optional[str] = None  # Specific page reference
    court: Optional[str] = None

    # Statute specific
    title_number: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    code_name: Optional[str] = None

    # Regulation specific
    cfr_title: Optional[str] = None
    cfr_part: Optional[str] = None
    cfr_section: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    position: Optional[Tuple[int, int]] = None  # Start, end position in text

    def to_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary representation."""
        data = {
            "citation_id": self.citation_id,
            "citation_type": self.citation_type.value,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "title": self.title,
            "year": self.year,
            "jurisdiction": self.jurisdiction.value,
            "metadata": self.metadata,
            "confidence": self.confidence,
        }

        # Add type-specific fields
        if self.citation_type == CitationType.CASE:
            data.update(
                {
                    "case_name": self.case_name,
                    "reporter": self.reporter.abbreviation if self.reporter else None,
                    "volume": self.volume,
                    "page": self.page,
                    "pincite": self.pincite,
                    "court": self.court,
                }
            )
        elif self.citation_type == CitationType.STATUTE:
            data.update(
                {
                    "title_number": self.title_number,
                    "section": self.section,
                    "subsection": self.subsection,
                    "code_name": self.code_name,
                }
            )
        elif self.citation_type == CitationType.REGULATION:
            data.update(
                {
                    "cfr_title": self.cfr_title,
                    "cfr_part": self.cfr_part,
                    "cfr_section": self.cfr_section,
                }
            )

        if self.position:
            data["position"] = {"start": self.position[0], "end": self.position[1]}

        return data


class LegalCitationExtractor:
    """Extracts and parses legal citations from text."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize citation extractor.

        Args:
            config: Configuration options
        """
        self.config = config or {}

        # Configuration
        self.include_unpublished = self.config.get("include_unpublished", True)
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.extract_pincites = self.config.get("extract_pincites", True)

        # Initialize reporters and patterns
        self._initialize_reporters()
        self._initialize_patterns()

        # Citation ID counter
        self._citation_counter = 0

    def _initialize_reporters(self):
        """Initialize legal reporter database."""
        self.reporters = {
            # U.S. Supreme Court
            "U.S.": Reporter(
                "U.S.",
                "United States Reports",
                None,
                JurisdictionType.FEDERAL,
                "supreme",
            ),
            "S. Ct.": Reporter(
                "S. Ct.",
                "Supreme Court Reporter",
                None,
                JurisdictionType.FEDERAL,
                "supreme",
            ),
            "S.Ct.": Reporter(
                "S.Ct.",
                "Supreme Court Reporter",
                None,
                JurisdictionType.FEDERAL,
                "supreme",
            ),
            "L. Ed.": Reporter(
                "L. Ed.", "Lawyers' Edition", None, JurisdictionType.FEDERAL, "supreme"
            ),
            "L.Ed.": Reporter(
                "L.Ed.", "Lawyers' Edition", None, JurisdictionType.FEDERAL, "supreme"
            ),
            "L. Ed. 2d": Reporter(
                "L. Ed. 2d",
                "Lawyers' Edition",
                "2d",
                JurisdictionType.FEDERAL,
                "supreme",
            ),
            "L.Ed.2d": Reporter(
                "L.Ed.2d", "Lawyers' Edition", "2d", JurisdictionType.FEDERAL, "supreme"
            ),
            # Federal Reporters
            "F.": Reporter(
                "F.", "Federal Reporter", "1st", JurisdictionType.FEDERAL, "appellate"
            ),
            "F.2d": Reporter(
                "F.2d", "Federal Reporter", "2d", JurisdictionType.FEDERAL, "appellate"
            ),
            "F.3d": Reporter(
                "F.3d", "Federal Reporter", "3d", JurisdictionType.FEDERAL, "appellate"
            ),
            "F.4th": Reporter(
                "F.4th",
                "Federal Reporter",
                "4th",
                JurisdictionType.FEDERAL,
                "appellate",
            ),
            "F. Supp.": Reporter(
                "F. Supp.",
                "Federal Supplement",
                "1st",
                JurisdictionType.FEDERAL,
                "district",
            ),
            "F.Supp.": Reporter(
                "F.Supp.",
                "Federal Supplement",
                "1st",
                JurisdictionType.FEDERAL,
                "district",
            ),
            "F. Supp. 2d": Reporter(
                "F. Supp. 2d",
                "Federal Supplement",
                "2d",
                JurisdictionType.FEDERAL,
                "district",
            ),
            "F.Supp.2d": Reporter(
                "F.Supp.2d",
                "Federal Supplement",
                "2d",
                JurisdictionType.FEDERAL,
                "district",
            ),
            "F. Supp. 3d": Reporter(
                "F. Supp. 3d",
                "Federal Supplement",
                "3d",
                JurisdictionType.FEDERAL,
                "district",
            ),
            "F.Supp.3d": Reporter(
                "F.Supp.3d",
                "Federal Supplement",
                "3d",
                JurisdictionType.FEDERAL,
                "district",
            ),
            # Federal Specialized
            "Fed. Cl.": Reporter(
                "Fed. Cl.",
                "Federal Claims Reporter",
                None,
                JurisdictionType.FEDERAL,
                "specialized",
            ),
            "Fed.Cl.": Reporter(
                "Fed.Cl.",
                "Federal Claims Reporter",
                None,
                JurisdictionType.FEDERAL,
                "specialized",
            ),
            "B.R.": Reporter(
                "B.R.",
                "Bankruptcy Reporter",
                None,
                JurisdictionType.FEDERAL,
                "bankruptcy",
            ),
            "T.C.": Reporter(
                "T.C.", "Tax Court Reports", None, JurisdictionType.FEDERAL, "tax"
            ),
            # Regional Reporters
            "A.": Reporter(
                "A.", "Atlantic Reporter", "1st", JurisdictionType.STATE, "appellate"
            ),
            "A.2d": Reporter(
                "A.2d", "Atlantic Reporter", "2d", JurisdictionType.STATE, "appellate"
            ),
            "A.3d": Reporter(
                "A.3d", "Atlantic Reporter", "3d", JurisdictionType.STATE, "appellate"
            ),
            "P.": Reporter(
                "P.", "Pacific Reporter", "1st", JurisdictionType.STATE, "appellate"
            ),
            "P.2d": Reporter(
                "P.2d", "Pacific Reporter", "2d", JurisdictionType.STATE, "appellate"
            ),
            "P.3d": Reporter(
                "P.3d", "Pacific Reporter", "3d", JurisdictionType.STATE, "appellate"
            ),
            "N.E.": Reporter(
                "N.E.",
                "North Eastern Reporter",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "N.E.2d": Reporter(
                "N.E.2d",
                "North Eastern Reporter",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "N.E.3d": Reporter(
                "N.E.3d",
                "North Eastern Reporter",
                "3d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "N.W.": Reporter(
                "N.W.",
                "North Western Reporter",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "N.W.2d": Reporter(
                "N.W.2d",
                "North Western Reporter",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "S.E.": Reporter(
                "S.E.",
                "South Eastern Reporter",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "S.E.2d": Reporter(
                "S.E.2d",
                "South Eastern Reporter",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "S.W.": Reporter(
                "S.W.",
                "South Western Reporter",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "S.W.2d": Reporter(
                "S.W.2d",
                "South Western Reporter",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "S.W.3d": Reporter(
                "S.W.3d",
                "South Western Reporter",
                "3d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "So.": Reporter(
                "So.", "Southern Reporter", "1st", JurisdictionType.STATE, "appellate"
            ),
            "So. 2d": Reporter(
                "So. 2d", "Southern Reporter", "2d", JurisdictionType.STATE, "appellate"
            ),
            "So.2d": Reporter(
                "So.2d", "Southern Reporter", "2d", JurisdictionType.STATE, "appellate"
            ),
            "So. 3d": Reporter(
                "So. 3d", "Southern Reporter", "3d", JurisdictionType.STATE, "appellate"
            ),
            "So.3d": Reporter(
                "So.3d", "Southern Reporter", "3d", JurisdictionType.STATE, "appellate"
            ),
            # State-specific (examples)
            "Cal.": Reporter(
                "Cal.", "California Reports", "1st", JurisdictionType.STATE, "supreme"
            ),
            "Cal.2d": Reporter(
                "Cal.2d", "California Reports", "2d", JurisdictionType.STATE, "supreme"
            ),
            "Cal.3d": Reporter(
                "Cal.3d", "California Reports", "3d", JurisdictionType.STATE, "supreme"
            ),
            "Cal.4th": Reporter(
                "Cal.4th",
                "California Reports",
                "4th",
                JurisdictionType.STATE,
                "supreme",
            ),
            "Cal.5th": Reporter(
                "Cal.5th",
                "California Reports",
                "5th",
                JurisdictionType.STATE,
                "supreme",
            ),
            "Cal. App.": Reporter(
                "Cal. App.",
                "California Appellate Reports",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal.App.": Reporter(
                "Cal.App.",
                "California Appellate Reports",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal. App. 2d": Reporter(
                "Cal. App. 2d",
                "California Appellate Reports",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal.App.2d": Reporter(
                "Cal.App.2d",
                "California Appellate Reports",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal. App. 3d": Reporter(
                "Cal. App. 3d",
                "California Appellate Reports",
                "3d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal.App.3d": Reporter(
                "Cal.App.3d",
                "California Appellate Reports",
                "3d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal. App. 4th": Reporter(
                "Cal. App. 4th",
                "California Appellate Reports",
                "4th",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal.App.4th": Reporter(
                "Cal.App.4th",
                "California Appellate Reports",
                "4th",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal. App. 5th": Reporter(
                "Cal. App. 5th",
                "California Appellate Reports",
                "5th",
                JurisdictionType.STATE,
                "appellate",
            ),
            "Cal.App.5th": Reporter(
                "Cal.App.5th",
                "California Appellate Reports",
                "5th",
                JurisdictionType.STATE,
                "appellate",
            ),
            "N.Y.": Reporter(
                "N.Y.", "New York Reports", "1st", JurisdictionType.STATE, "supreme"
            ),
            "N.Y.2d": Reporter(
                "N.Y.2d", "New York Reports", "2d", JurisdictionType.STATE, "supreme"
            ),
            "N.Y.3d": Reporter(
                "N.Y.3d", "New York Reports", "3d", JurisdictionType.STATE, "supreme"
            ),
            "A.D.": Reporter(
                "A.D.",
                "Appellate Division Reports",
                "1st",
                JurisdictionType.STATE,
                "appellate",
            ),
            "A.D.2d": Reporter(
                "A.D.2d",
                "Appellate Division Reports",
                "2d",
                JurisdictionType.STATE,
                "appellate",
            ),
            "A.D.3d": Reporter(
                "A.D.3d",
                "Appellate Division Reports",
                "3d",
                JurisdictionType.STATE,
                "appellate",
            ),
        }

        # Create regex pattern for reporters
        reporter_names = sorted(
            self.reporters.keys(), key=len, reverse=True
        )  # Longer names first
        self.reporter_pattern = "|".join(re.escape(name) for name in reporter_names)

    def _initialize_patterns(self):
        """Initialize regex patterns for citation extraction."""
        # Case citation pattern
        # Format: Party v. Party, Volume Reporter Page (Court Year)
        self.case_pattern = re.compile(
            r"\b([A-Z][A-Za-z\'\-&,.\s]+?)\s+v\.\s+([A-Z][A-Za-z\'\-&,.\s]+?),?\s+"
            r"(\d+)\s+(" + self.reporter_pattern + r")\s+(\d+)"
            r"(?:,\s+(\d+(?:\-\d+)?))?"  # Optional pincite
            r"(?:\s+\(([^)]+)\))?",  # Optional parenthetical (court and year)
            re.MULTILINE,
        )

        # Federal statute pattern
        # Format: Title U.S.C. § Section
        self.federal_statute_pattern = re.compile(
            r"\b(\d+)\s+U\.S\.C\.(?:\s+§+)?\s+(\d+[a-zA-Z0-9\-]*)"
            r"(?:\(([a-zA-Z0-9\)\(]+)\))?",  # Optional subsection
            re.MULTILINE,
        )

        # State statute patterns (examples)
        self.state_statute_patterns = {
            "california": re.compile(
                r"\bCal(?:\.|ifornia)\s+([A-Za-z.]+)\s+Code\s+§+\s*(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "new_york": re.compile(
                r"\bN\.Y\.\s+([A-Za-z.]+)\s+Law\s+§+\s*(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "delaware": re.compile(
                r"\b(\d+)\s+Del(?:\.|aware)\s+C\.\s+§+\s*(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
        }

        # Federal regulation pattern
        # Format: Title C.F.R. § Part.Section
        self.cfr_pattern = re.compile(
            r"\b(\d+)\s+C\.F\.R\.(?:\s+§+)?\s+(\d+)\.(\d+[a-zA-Z0-9\-]*)", re.MULTILINE
        )

        # Constitutional citation pattern
        self.constitutional_pattern = re.compile(
            r"\bU\.S\.\s+Const\.\s+"
            r"(?:art\.\s+([IVX]+|\d+)(?:,\s+§\s*(\d+))?|"  # Article
            r"amend\.\s+([IVX]+|\d+))",  # Amendment
            re.IGNORECASE | re.MULTILINE,
        )

        # Federal Rules patterns
        self.federal_rules_patterns = {
            "frcp": re.compile(
                r"\b(?:Fed\.\s*R\.\s*Civ\.\s*P\.|FRCP)\s+(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "fre": re.compile(
                r"\b(?:Fed\.\s*R\.\s*Evid\.|FRE)\s+(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "frcrp": re.compile(
                r"\b(?:Fed\.\s*R\.\s*Crim\.\s*P\.|FRCrP)\s+(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
            "frap": re.compile(
                r"\b(?:Fed\.\s*R\.\s*App\.\s*P\.|FRAP)\s+(\d+[a-zA-Z0-9\-\.]*)",
                re.IGNORECASE | re.MULTILINE,
            ),
        }

        # Restatement pattern
        self.restatement_pattern = re.compile(
            r"\bRestatement\s+\(([A-Za-z0-9]+)\)\s+of\s+([A-Za-z\s]+)"
            r"(?:\s+§\s*(\d+[a-zA-Z0-9\-\.]*))?",
            re.IGNORECASE | re.MULTILINE,
        )

        # Law review pattern
        self.law_review_pattern = re.compile(
            r"\b([A-Za-z\s&.]+?),\s+"  # Author
            r'([A-Za-z0-9\s,:\'"\-]+?),\s+'  # Title
            r"(\d+)\s+([A-Za-z.\s]+L\.\s*Rev\.)\s+(\d+)"  # Volume Journal Page
            r"(?:\s+\((\d{4})\))?",  # Optional year
            re.MULTILINE,
        )

        # Unpublished opinion pattern
        self.unpublished_pattern = re.compile(
            r"\b([A-Z][A-Za-z\'\-&,.\s]+?)\s+v\.\s+([A-Z][A-Za-z\'\-&,.\s]+?),?\s+"
            r"(?:No\.|Docket No\.|Case No\.)\s+([A-Z0-9\-:]+)"
            r"(?:\s+\(([^)]+)\))?",  # Optional court and date
            re.MULTILINE,
        )

    def extract_citations(self, text: str) -> List[Citation]:
        """Extract all legal citations from text.

        Args:
            text: Text to extract citations from

        Returns:
            List of extracted citations
        """
        citations = []

        # Extract different types of citations
        citations.extend(self._extract_case_citations(text))
        citations.extend(self._extract_statute_citations(text))
        citations.extend(self._extract_regulation_citations(text))
        citations.extend(self._extract_constitutional_citations(text))
        citations.extend(self._extract_rule_citations(text))
        citations.extend(self._extract_restatement_citations(text))

        if self.include_unpublished:
            citations.extend(self._extract_unpublished_citations(text))

        # Filter by confidence
        citations = [c for c in citations if c.confidence >= self.min_confidence]

        # Sort by position
        citations.sort(key=lambda c: c.position[0] if c.position else 0)

        logger.info(f"Extracted {len(citations)} legal citations")

        return citations

    def _extract_case_citations(self, text: str) -> List[Citation]:
        """Extract case law citations."""
        citations = []

        for match in self.case_pattern.finditer(text):
            party1 = match.group(1).strip()
            party2 = match.group(2).strip()
            volume = match.group(3)
            reporter_abbr = match.group(4)
            page = match.group(5)
            pincite = match.group(6) if match.lastindex >= 6 else None
            parenthetical = match.group(7) if match.lastindex >= 7 else None

            # Parse parenthetical for court and year
            court = None
            year = None
            if parenthetical:
                year_match = re.search(r"(\d{4})", parenthetical)
                if year_match:
                    year = int(year_match.group(1))
                court_text = parenthetical.replace(
                    str(year) if year else "", ""
                ).strip()
                if court_text:
                    court = court_text.strip(",")

            # Get reporter info
            reporter = self.reporters.get(reporter_abbr)

            # Build case name
            case_name = f"{party1} v. {party2}"

            # Build normalized citation
            normalized = f"{case_name}, {volume} {reporter_abbr} {page}"
            if pincite and self.extract_pincites:
                normalized += f", {pincite}"
            if parenthetical:
                normalized += f" ({parenthetical})"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.CASE,
                raw_text=match.group(0),
                normalized_text=normalized,
                case_name=case_name,
                reporter=reporter,
                volume=volume,
                page=page,
                pincite=pincite if self.extract_pincites else None,
                court=court,
                year=year,
                jurisdiction=(
                    reporter.jurisdiction if reporter else JurisdictionType.UNKNOWN
                ),
                position=(match.start(), match.end()),
                confidence=0.95,
            )

            citations.append(citation)

        return citations

    def _extract_statute_citations(self, text: str) -> List[Citation]:
        """Extract statutory citations."""
        citations = []

        # Federal statutes
        for match in self.federal_statute_pattern.finditer(text):
            title = match.group(1)
            section = match.group(2)
            subsection = match.group(3) if match.lastindex >= 3 else None

            normalized = f"{title} U.S.C. § {section}"
            if subsection:
                normalized += f"({subsection})"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.STATUTE,
                raw_text=match.group(0),
                normalized_text=normalized,
                title_number=title,
                section=section,
                subsection=subsection,
                code_name="U.S.C.",
                jurisdiction=JurisdictionType.FEDERAL,
                position=(match.start(), match.end()),
                confidence=0.95,
            )

            citations.append(citation)

        # State statutes
        for state, pattern in self.state_statute_patterns.items():
            for match in pattern.finditer(text):
                if state == "delaware":
                    title = match.group(1)
                    section = match.group(2)
                    code_type = "Del. C."
                else:
                    code_type = match.group(1)
                    section = match.group(2)
                    title = None

                state_name = state.replace("_", " ").title()
                normalized = f"{state_name} {code_type} § {section}"
                if title:
                    normalized = f"{title} {normalized}"

                citation = Citation(
                    citation_id=self._generate_citation_id(),
                    citation_type=CitationType.STATUTE,
                    raw_text=match.group(0),
                    normalized_text=normalized,
                    title_number=title,
                    section=section,
                    code_name=f"{state_name} {code_type}",
                    jurisdiction=JurisdictionType.STATE,
                    position=(match.start(), match.end()),
                    metadata={"state": state},
                    confidence=0.9,
                )

                citations.append(citation)

        return citations

    def _extract_regulation_citations(self, text: str) -> List[Citation]:
        """Extract federal regulation citations."""
        citations = []

        for match in self.cfr_pattern.finditer(text):
            cfr_title = match.group(1)
            cfr_part = match.group(2)
            cfr_section = match.group(3)

            normalized = f"{cfr_title} C.F.R. § {cfr_part}.{cfr_section}"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.REGULATION,
                raw_text=match.group(0),
                normalized_text=normalized,
                cfr_title=cfr_title,
                cfr_part=cfr_part,
                cfr_section=cfr_section,
                jurisdiction=JurisdictionType.FEDERAL,
                position=(match.start(), match.end()),
                confidence=0.95,
            )

            citations.append(citation)

        return citations

    def _extract_constitutional_citations(self, text: str) -> List[Citation]:
        """Extract constitutional citations."""
        citations = []

        for match in self.constitutional_pattern.finditer(text):
            if match.group(1):  # Article
                article = match.group(1)
                section = match.group(2) if match.lastindex >= 2 else None
                normalized = f"U.S. Const. art. {article}"
                if section:
                    normalized += f", § {section}"
                title = f"Article {article}"
            else:  # Amendment
                amendment = match.group(3)
                normalized = f"U.S. Const. amend. {amendment}"
                title = f"Amendment {amendment}"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.CONSTITUTION,
                raw_text=match.group(0),
                normalized_text=normalized,
                title=title,
                jurisdiction=JurisdictionType.FEDERAL,
                position=(match.start(), match.end()),
                confidence=0.95,
            )

            citations.append(citation)

        return citations

    def _extract_rule_citations(self, text: str) -> List[Citation]:
        """Extract federal rule citations."""
        citations = []

        rule_names = {
            "frcp": "Fed. R. Civ. P.",
            "fre": "Fed. R. Evid.",
            "frcrp": "Fed. R. Crim. P.",
            "frap": "Fed. R. App. P.",
        }

        for rule_type, pattern in self.federal_rules_patterns.items():
            for match in pattern.finditer(text):
                rule_number = match.group(1)
                rule_name = rule_names[rule_type]
                normalized = f"{rule_name} {rule_number}"

                citation = Citation(
                    citation_id=self._generate_citation_id(),
                    citation_type=CitationType.RULE,
                    raw_text=match.group(0),
                    normalized_text=normalized,
                    title=rule_name,
                    section=rule_number,
                    jurisdiction=JurisdictionType.FEDERAL,
                    position=(match.start(), match.end()),
                    metadata={"rule_type": rule_type},
                    confidence=0.95,
                )

                citations.append(citation)

        return citations

    def _extract_restatement_citations(self, text: str) -> List[Citation]:
        """Extract Restatement citations."""
        citations = []

        for match in self.restatement_pattern.finditer(text):
            edition = match.group(1)
            subject = match.group(2).strip()
            section = match.group(3) if match.lastindex >= 3 else None

            title = f"Restatement ({edition}) of {subject}"
            normalized = title
            if section:
                normalized += f" § {section}"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.RESTATEMENT,
                raw_text=match.group(0),
                normalized_text=normalized,
                title=title,
                section=section,
                position=(match.start(), match.end()),
                metadata={"edition": edition, "subject": subject},
                confidence=0.9,
            )

            citations.append(citation)

        return citations

    def _extract_unpublished_citations(self, text: str) -> List[Citation]:
        """Extract unpublished opinion citations."""
        citations = []

        for match in self.unpublished_pattern.finditer(text):
            party1 = match.group(1).strip()
            party2 = match.group(2).strip()
            docket_number = match.group(3)
            parenthetical = match.group(4) if match.lastindex >= 4 else None

            case_name = f"{party1} v. {party2}"
            normalized = f"{case_name}, No. {docket_number}"

            # Parse parenthetical for court and date
            court = None
            year = None
            if parenthetical:
                year_match = re.search(r"(\d{4})", parenthetical)
                if year_match:
                    year = int(year_match.group(1))
                court_text = parenthetical.replace(
                    str(year) if year else "", ""
                ).strip()
                if court_text:
                    court = court_text.strip(",")
                normalized += f" ({parenthetical})"

            citation = Citation(
                citation_id=self._generate_citation_id(),
                citation_type=CitationType.UNPUBLISHED,
                raw_text=match.group(0),
                normalized_text=normalized,
                case_name=case_name,
                court=court,
                year=year,
                position=(match.start(), match.end()),
                metadata={"docket_number": docket_number},
                confidence=0.85,
            )

            citations.append(citation)

        return citations

    def _generate_citation_id(self) -> str:
        """Generate unique citation ID."""
        self._citation_counter += 1
        return f"cite_{self._citation_counter:06d}"

    def group_citations_by_type(
        self, citations: List[Citation]
    ) -> Dict[CitationType, List[Citation]]:
        """Group citations by their type.

        Args:
            citations: List of citations to group

        Returns:
            Dictionary mapping citation types to lists of citations
        """
        grouped = {}
        for citation in citations:
            if citation.citation_type not in grouped:
                grouped[citation.citation_type] = []
            grouped[citation.citation_type].append(citation)

        return grouped

    def find_citation_updates(
        self, citations: List[Citation], current_year: Optional[int] = None
    ) -> List[Tuple[Citation, str]]:
        """Find potentially outdated citations that may need updates.

        Args:
            citations: List of citations to check
            current_year: Current year for comparison

        Returns:
            List of tuples (citation, reason) for citations that may need updates
        """
        if current_year is None:
            current_year = datetime.now().year

        outdated = []

        for citation in citations:
            reasons = []

            # Check age of cases
            if citation.year and citation.citation_type == CitationType.CASE:
                age = current_year - citation.year
                if age > 20:
                    reasons.append(
                        f"Case is {age} years old - check for subsequent history"
                    )

            # Check for superseded statutes
            if citation.citation_type == CitationType.STATUTE:
                # This would need a database of statutory amendments
                # For now, flag very old references
                if citation.metadata.get("last_amended"):
                    last_amended = citation.metadata["last_amended"]
                    if current_year - last_amended > 5:
                        reasons.append("Statute may have been amended")

            # Check for outdated regulations
            if citation.citation_type == CitationType.REGULATION:
                # CFR is updated annually
                reasons.append("Verify current CFR version")

            # Check for old restatements
            if citation.citation_type == CitationType.RESTATEMENT:
                edition = citation.metadata.get("edition", "").lower()
                if "second" in edition or "2d" in edition:
                    reasons.append("Check if Third Restatement is available")
                elif "first" in edition or "1st" in edition:
                    reasons.append("Likely superseded by newer Restatement")

            if reasons:
                outdated.append((citation, "; ".join(reasons)))

        return outdated

    def format_citation_list(
        self, citations: List[Citation], style: str = "bluebook"
    ) -> List[str]:
        """Format citations according to legal citation style.

        Args:
            citations: List of citations to format
            style: Citation style to use (currently only bluebook)

        Returns:
            List of formatted citation strings
        """
        formatted = []

        for citation in citations:
            if style == "bluebook":
                formatted_text = self._format_bluebook(citation)
            else:
                formatted_text = citation.normalized_text

            formatted.append(formatted_text)

        return formatted

    def _format_bluebook(self, citation: Citation) -> str:
        """Format citation according to Bluebook style."""
        # This is a simplified Bluebook formatting
        # Full Bluebook compliance would require extensive rules

        if citation.citation_type == CitationType.CASE:
            # Basic case citation format
            text = citation.case_name
            if citation.volume and citation.reporter and citation.page:
                text += f", {citation.volume} {citation.reporter.abbreviation} {citation.page}"
                if citation.pincite:
                    text += f", {citation.pincite}"
            if citation.court and citation.year:
                text += f" ({citation.court} {citation.year})"
            elif citation.year:
                text += f" ({citation.year})"

        elif citation.citation_type == CitationType.STATUTE:
            # Statute format
            text = citation.normalized_text

        elif citation.citation_type == CitationType.REGULATION:
            # Regulation format
            text = citation.normalized_text
            if citation.year:
                text += f" ({citation.year})"

        else:
            # Default to normalized text
            text = citation.normalized_text

        return text
