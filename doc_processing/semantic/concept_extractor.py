"""Legal concept extraction and entity recognition system.

This module provides advanced NLP-based extraction of legal concepts,
entities, and semantic relationships from legal documents.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ConceptType(Enum):
    """Types of legal concepts that can be extracted."""

    # Contract law concepts
    CONTRACT = "contract"
    AGREEMENT = "agreement"
    OBLIGATION = "obligation"
    CONSIDERATION = "consideration"
    BREACH = "breach"
    PERFORMANCE = "performance"

    # Corporate law concepts
    CORPORATION = "corporation"
    SHAREHOLDER = "shareholder"
    DIRECTOR = "director"
    FIDUCIARY_DUTY = "fiduciary_duty"
    MERGER = "merger"
    ACQUISITION = "acquisition"

    # Litigation concepts
    LAWSUIT = "lawsuit"
    PLAINTIFF = "plaintif"
    DEFENDANT = "defendant"
    CLAIM = "claim"
    DAMAGES = "damages"
    SETTLEMENT = "settlement"
    JURISDICTION = "jurisdiction"

    # Intellectual property concepts
    PATENT = "patent"
    TRADEMARK = "trademark"
    COPYRIGHT = "copyright"
    TRADE_SECRET = "trade_secret"
    INFRINGEMENT = "infringement"

    # Employment law concepts
    EMPLOYMENT = "employment"
    EMPLOYEE = "employee"
    EMPLOYER = "employer"
    TERMINATION = "termination"
    DISCRIMINATION = "discrimination"

    # Real estate concepts
    PROPERTY = "property"
    LEASE = "lease"
    MORTGAGE = "mortgage"
    TITLE = "title"
    EASEMENT = "easement"

    # Regulatory concepts
    COMPLIANCE = "compliance"
    REGULATION = "regulation"
    LICENSE = "license"
    PERMIT = "permit"

    # Financial concepts
    LOAN = "loan"
    SECURITY = "security"
    INVESTMENT = "investment"
    LIABILITY = "liability"
    INDEMNITY = "indemnity"

    # General legal concepts
    LIABILITY = "liability"
    REMEDY = "remedy"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"
    DUE_PROCESS = "due_process"
    PRECEDENT = "precedent"


@dataclass
class ConceptMatch:
    """Represents a match of a legal concept in text."""

    text: str
    start_position: int
    end_position: int
    confidence: float
    context: str = ""


@dataclass
class LegalConcept:
    """Represents an extracted legal concept with metadata."""

    concept_type: ConceptType
    primary_term: str
    keywords: List[str]
    confidence: float

    # Text locations where concept appears
    matches: List[ConceptMatch] = field(default_factory=list)

    # Semantic relationships
    related_concepts: List[str] = field(default_factory=list)
    legal_framework: Optional[str] = None
    jurisdiction_specific: bool = False

    # Concept metadata
    definition: Optional[str] = None
    legal_significance: Optional[str] = None
    common_contexts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert concept to dictionary representation."""
        return {
            "concept_type": self.concept_type.value,
            "primary_term": self.primary_term,
            "keywords": self.keywords,
            "confidence": self.confidence,
            "matches": [
                {
                    "text": match.text,
                    "start_position": match.start_position,
                    "end_position": match.end_position,
                    "confidence": match.confidence,
                    "context": match.context,
                }
                for match in self.matches
            ],
            "related_concepts": self.related_concepts,
            "legal_framework": self.legal_framework,
            "jurisdiction_specific": self.jurisdiction_specific,
            "definition": self.definition,
            "legal_significance": self.legal_significance,
            "common_contexts": self.common_contexts,
        }


class LegalConceptExtractor:
    """Extracts legal concepts and entities from legal documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize legal concept extractor.

        Args:
            config: Configuration options
        """
        self.config = config or {}

        # Configuration
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.max_context_chars = self.config.get("max_context_chars", 200)
        self.enable_semantic_relations = self.config.get(
            "enable_semantic_relations", True
        )

        # Initialize concept patterns and knowledge base
        self._initialize_concept_patterns()
        self._initialize_legal_knowledge_base()

        logger.info("Initialized LegalConceptExtractor")

    def _initialize_concept_patterns(self):
        """Initialize regex patterns for legal concept detection."""
        self.concept_patterns = {
            # Contract law patterns
            ConceptType.CONTRACT: {
                "keywords": [
                    "contract",
                    "agreement",
                    "compact",
                    "covenant",
                    "undertaking",
                ],
                "patterns": [
                    re.compile(
                        r"\b(?:this\s+)?(?:agreement|contract)\b", re.IGNORECASE
                    ),
                    re.compile(
                        r"\benter\s+into\s+(?:a\s+)?(?:contract|agreement)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bcontractual\s+(?:obligation|duty|relationship)\b",
                        re.IGNORECASE,
                    ),
                ],
                "context_indicators": ["parties", "terms", "conditions", "execution"],
            },
            ConceptType.BREACH: {
                "keywords": ["breach", "violation", "default", "non-performance"],
                "patterns": [
                    re.compile(
                        r"\bbreach\s+of\s+(?:contract|agreement|duty)\b", re.IGNORECASE
                    ),
                    re.compile(r"\bmaterial\s+breach\b", re.IGNORECASE),
                    re.compile(r"\bdefault\s+(?:under|in)\b", re.IGNORECASE),
                    re.compile(
                        r"\bviolation\s+of\s+(?:terms|provisions)\b", re.IGNORECASE
                    ),
                ],
                "context_indicators": ["remedy", "cure", "damages", "termination"],
            },
            ConceptType.CONSIDERATION: {
                "keywords": [
                    "consideration",
                    "exchange",
                    "quid pro quo",
                    "valuable consideration",
                ],
                "patterns": [
                    re.compile(
                        r"\b(?:for\s+)?(?:good\s+and\s+)?valuable\s+consideration\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\bin\s+consideration\s+(?:of|for)\b", re.IGNORECASE),
                    re.compile(r"\bmutual\s+consideration\b", re.IGNORECASE),
                ],
                "context_indicators": ["payment", "exchange", "benefit", "detriment"],
            },
            # Corporate law patterns
            ConceptType.CORPORATION: {
                "keywords": [
                    "corporation",
                    "company",
                    "entity",
                    "business organization",
                ],
                "patterns": [
                    re.compile(
                        r"\b(?:corporation|corp\.?|company|co\.?)\b", re.IGNORECASE
                    ),
                    re.compile(r"\b(?:LLC|Inc\.?|Ltd\.?)\b"),
                    re.compile(
                        r"\bcorporate\s+(?:entity|structure|governance)\b",
                        re.IGNORECASE,
                    ),
                ],
                "context_indicators": [
                    "incorporation",
                    "bylaws",
                    "shareholders",
                    "board",
                ],
            },
            ConceptType.FIDUCIARY_DUTY: {
                "keywords": [
                    "fiduciary duty",
                    "fiduciary",
                    "duty of care",
                    "duty of loyalty",
                ],
                "patterns": [
                    re.compile(
                        r"\bfiduciary\s+(?:duty|obligation|relationship)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bduty\s+of\s+(?:care|loyalty|good\s+faith)\b", re.IGNORECASE
                    ),
                    re.compile(r"\bfiduciary\s+capacity\b", re.IGNORECASE),
                ],
                "context_indicators": ["trustee", "agent", "director", "good faith"],
            },
            # Litigation patterns
            ConceptType.LAWSUIT: {
                "keywords": ["lawsuit", "litigation", "action", "proceeding", "suit"],
                "patterns": [
                    re.compile(
                        r"\b(?:lawsuit|litigation|legal\s+action)\b", re.IGNORECASE
                    ),
                    re.compile(
                        r"\bcivil\s+(?:action|proceeding|suit)\b", re.IGNORECASE
                    ),
                    re.compile(r"\bcommence\s+(?:an\s+)?action\b", re.IGNORECASE),
                ],
                "context_indicators": ["court", "judge", "jury", "trial"],
            },
            ConceptType.DAMAGES: {
                "keywords": ["damages", "compensation", "monetary relie", "award"],
                "patterns": [
                    re.compile(
                        r"\b(?:actual|compensatory|punitive|liquidated)\s+damages\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bmonetary\s+(?:damages|relief|compensation)\b", re.IGNORECASE
                    ),
                    re.compile(
                        r"\bdamages\s+(?:award|claim|calculation)\b", re.IGNORECASE
                    ),
                ],
                "context_indicators": ["injury", "loss", "harm", "compensation"],
            },
            # Intellectual property patterns
            ConceptType.PATENT: {
                "keywords": [
                    "patent",
                    "invention",
                    "patent application",
                    "patent rights",
                ],
                "patterns": [
                    re.compile(
                        r"\bpatent\s+(?:application|rights?|protection)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\b(?:utility|design|plant)\s+patent\b", re.IGNORECASE),
                    re.compile(
                        r"\bpatentable\s+(?:invention|subject\s+matter)\b",
                        re.IGNORECASE,
                    ),
                ],
                "context_indicators": ["USPTO", "invention", "claims", "prior art"],
            },
            ConceptType.TRADEMARK: {
                "keywords": ["trademark", "service mark", "trade name", "brand"],
                "patterns": [
                    re.compile(
                        r"\btrademark\s+(?:rights?|protection|registration)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\bservice\s+mark\b", re.IGNORECASE),
                    re.compile(r"\btrade\s+name\b", re.IGNORECASE),
                ],
                "context_indicators": ["brand", "mark", "registration", "commerce"],
            },
            # Employment law patterns
            ConceptType.EMPLOYMENT: {
                "keywords": ["employment", "job", "work", "employment relationship"],
                "patterns": [
                    re.compile(
                        r"\bemployment\s+(?:relationship|agreement|contract)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\b(?:at-will|term)\s+employment\b", re.IGNORECASE),
                    re.compile(r"\bemployer-employee\s+relationship\b", re.IGNORECASE),
                ],
                "context_indicators": [
                    "workplace",
                    "salary",
                    "benefits",
                    "termination",
                ],
            },
            ConceptType.DISCRIMINATION: {
                "keywords": [
                    "discrimination",
                    "harassment",
                    "equal opportunity",
                    "protected class",
                ],
                "patterns": [
                    re.compile(
                        r"\b(?:employment|workplace)\s+discrimination\b", re.IGNORECASE
                    ),
                    re.compile(
                        r"\b(?:sexual|racial|age|gender)\s+(?:discrimination|harassment)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bprotected\s+(?:class|characteristic)\b", re.IGNORECASE
                    ),
                ],
                "context_indicators": ["EEOC", "Title VII", "harassment", "bias"],
            },
            # Financial concepts
            ConceptType.LIABILITY: {
                "keywords": ["liability", "responsibility", "obligation", "debt"],
                "patterns": [
                    re.compile(
                        r"\b(?:personal|corporate|limited|joint)\s+liability\b",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"\bliability\s+(?:insurance|coverage|protection)\b",
                        re.IGNORECASE,
                    ),
                    re.compile(r"\blimitation\s+of\s+liability\b", re.IGNORECASE),
                ],
                "context_indicators": [
                    "responsibility",
                    "obligation",
                    "fault",
                    "damages",
                ],
            },
            ConceptType.INDEMNITY: {
                "keywords": ["indemnity", "indemnification", "hold harmless"],
                "patterns": [
                    re.compile(r"\bindemnif(?:y|ies|ication)\b", re.IGNORECASE),
                    re.compile(r"\bhold\s+harmless\b", re.IGNORECASE),
                    re.compile(
                        r"\bindemnity\s+(?:agreement|clause|provision)\b", re.IGNORECASE
                    ),
                ],
                "context_indicators": ["protect", "defend", "reimburse", "loss"],
            },
        }

    def _initialize_legal_knowledge_base(self):
        """Initialize legal knowledge base with concept relationships and definitions."""
        self.concept_definitions = {
            ConceptType.CONTRACT: "A legally binding agreement between two or more parties",
            ConceptType.BREACH: "The failure to perform any duty or obligation specified in a contract",
            ConceptType.CONSIDERATION: "Something of value given in exchange for a promise or performance",
            ConceptType.FIDUCIARY_DUTY: "A legal obligation to act in the best interest of another party",
            ConceptType.DAMAGES: "Monetary compensation awarded to remedy a legal wrong",
            ConceptType.LIABILITY: "Legal responsibility for one's actions or omissions",
            ConceptType.INDEMNITY: "Protection against loss or damage; compensation for loss",
        }

        self.concept_relationships = {
            ConceptType.CONTRACT: [
                ConceptType.BREACH,
                ConceptType.CONSIDERATION,
                ConceptType.PERFORMANCE,
            ],
            ConceptType.BREACH: [
                ConceptType.DAMAGES,
                ConceptType.REMEDY,
                ConceptType.CONTRACT,
            ],
            ConceptType.LIABILITY: [
                ConceptType.DAMAGES,
                ConceptType.INDEMNITY,
                ConceptType.INSURANCE,
            ],
            ConceptType.CORPORATION: [
                ConceptType.FIDUCIARY_DUTY,
                ConceptType.SHAREHOLDER,
                ConceptType.DIRECTOR,
            ],
            ConceptType.EMPLOYMENT: [
                ConceptType.DISCRIMINATION,
                ConceptType.TERMINATION,
                ConceptType.WORKPLACE,
            ],
        }

        self.legal_frameworks = {
            ConceptType.CONTRACT: "Contract Law",
            ConceptType.CORPORATION: "Corporate Law",
            ConceptType.PATENT: "Intellectual Property Law",
            ConceptType.EMPLOYMENT: "Employment Law",
            ConceptType.DISCRIMINATION: "Civil Rights Law",
        }

    def extract_concepts(
        self,
        content: str,
        confidence_threshold: Optional[float] = None,
        concept_types: Optional[List[ConceptType]] = None,
    ) -> List[LegalConcept]:
        """Extract legal concepts from document content.

        Args:
            content: Document content to analyze
            confidence_threshold: Minimum confidence for concept extraction
            concept_types: Specific concept types to extract (None for all)

        Returns:
            List of extracted legal concepts
        """
        threshold = confidence_threshold or self.min_confidence
        target_types = concept_types or list(self.concept_patterns.keys())

        extracted_concepts = []

        for concept_type in target_types:
            if concept_type not in self.concept_patterns:
                continue

            concept_info = self.concept_patterns[concept_type]
            matches = self._find_concept_matches(content, concept_type, concept_info)

            if matches:
                # Calculate overall confidence for this concept
                confidence = self._calculate_concept_confidence(
                    matches, concept_info, content
                )

                if confidence >= threshold:
                    concept = LegalConcept(
                        concept_type=concept_type,
                        primary_term=concept_info["keywords"][0],
                        keywords=concept_info["keywords"],
                        confidence=confidence,
                        matches=matches,
                        definition=self.concept_definitions.get(concept_type),
                        legal_framework=self.legal_frameworks.get(concept_type),
                    )

                    # Add semantic relationships if enabled
                    if self.enable_semantic_relations:
                        concept.related_concepts = [
                            rel.value
                            for rel in self.concept_relationships.get(concept_type, [])
                        ]

                    extracted_concepts.append(concept)

        # Sort by confidence
        extracted_concepts.sort(key=lambda c: c.confidence, reverse=True)

        logger.info(f"Extracted {len(extracted_concepts)} legal concepts from document")
        return extracted_concepts

    def _find_concept_matches(
        self, content: str, concept_type: ConceptType, concept_info: Dict[str, Any]
    ) -> List[ConceptMatch]:
        """Find all matches of a specific concept in the content."""
        matches = []

        # Search using regex patterns
        for pattern in concept_info["patterns"]:
            for match in pattern.finditer(content):
                context = self._extract_context(content, match.start(), match.end())

                # Calculate match confidence based on context
                match_confidence = self._calculate_match_confidence(
                    match.group(0), context, concept_info
                )

                concept_match = ConceptMatch(
                    text=match.group(0),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=match_confidence,
                    context=context,
                )
                matches.append(concept_match)

        # Search for keyword variations
        for keyword in concept_info["keywords"]:
            keyword_pattern = re.compile(
                r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE
            )
            for match in keyword_pattern.finditer(content):
                # Avoid duplicates
                if not any(
                    abs(match.start() - existing.start_position) < 10
                    for existing in matches
                ):
                    context = self._extract_context(content, match.start(), match.end())
                    match_confidence = self._calculate_match_confidence(
                        match.group(0), context, concept_info
                    )

                    if match_confidence >= 0.5:  # Threshold for keyword matches
                        concept_match = ConceptMatch(
                            text=match.group(0),
                            start_position=match.start(),
                            end_position=match.end(),
                            confidence=match_confidence,
                            context=context,
                        )
                        matches.append(concept_match)

        return matches

    def _extract_context(self, content: str, start: int, end: int) -> str:
        """Extract context around a match."""
        context_start = max(0, start - self.max_context_chars // 2)
        context_end = min(len(content), end + self.max_context_chars // 2)

        context = content[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(content):
            context = context + "..."

        return context.strip()

    def _calculate_match_confidence(
        self, matched_text: str, context: str, concept_info: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a concept match."""
        base_confidence = 0.7

        # Boost confidence for exact pattern matches
        for pattern in concept_info["patterns"]:
            if pattern.search(matched_text):
                base_confidence += 0.2
                break

        # Boost confidence for context indicators
        context_lower = context.lower()
        context_indicators = concept_info.get("context_indicators", [])
        context_matches = sum(
            1 for indicator in context_indicators if indicator.lower() in context_lower
        )

        if context_indicators:
            context_boost = (context_matches / len(context_indicators)) * 0.3
            base_confidence += context_boost

        # Reduce confidence for very short matches
        if len(matched_text) < 4:
            base_confidence -= 0.1

        # Cap at 1.0
        return min(base_confidence, 1.0)

    def _calculate_concept_confidence(
        self, matches: List[ConceptMatch], concept_info: Dict[str, Any], content: str
    ) -> float:
        """Calculate overall confidence for a concept based on all matches."""
        if not matches:
            return 0.0

        # Base confidence from average match confidence
        avg_match_confidence = sum(match.confidence for match in matches) / len(matches)

        # Boost for multiple matches
        frequency_boost = min(len(matches) * 0.1, 0.3)

        # Boost for matches in different parts of document
        positions = [match.start_position for match in matches]
        doc_length = len(content)
        distribution_score = 0.0

        if doc_length > 0:
            # Check if matches are distributed across document
            normalized_positions = [pos / doc_length for pos in positions]
            if (
                len(set(int(pos * 3) for pos in normalized_positions)) > 1
            ):  # Matches in different thirds
                distribution_score = 0.1

        total_confidence = avg_match_confidence + frequency_boost + distribution_score
        return min(total_confidence, 1.0)

    def extract_legal_entities(
        self, content: str, entity_types: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract specific legal entities from content.

        Args:
            content: Document content to analyze
            entity_types: Specific entity types to extract

        Returns:
            Dictionary mapping entity types to lists of entities
        """
        target_entities = entity_types or [
            "parties",
            "dates",
            "monetary_amounts",
            "jurisdictions",
            "courts",
            "case_numbers",
            "statutes",
            "regulations",
        ]

        entities = {}

        if "parties" in target_entities:
            entities["parties"] = self._extract_party_entities(content)

        if "dates" in target_entities:
            entities["dates"] = self._extract_date_entities(content)

        if "monetary_amounts" in target_entities:
            entities["monetary_amounts"] = self._extract_monetary_entities(content)

        if "jurisdictions" in target_entities:
            entities["jurisdictions"] = self._extract_jurisdiction_entities(content)

        if "courts" in target_entities:
            entities["courts"] = self._extract_court_entities(content)

        if "case_numbers" in target_entities:
            entities["case_numbers"] = self._extract_case_number_entities(content)

        return entities

    def _extract_party_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract party entities (companies, individuals, organizations)."""
        parties = []

        # Company patterns
        company_pattern = re.compile(
            r"\b([A-Z][A-Za-z\s&,\.\']+?)\s+(?:LLC|Inc\.|Corp\.|Corporation|Company|Co\.|Ltd\.|Limited|LP|LLP)\b",
            re.IGNORECASE,
        )

        for match in company_pattern.finditer(content):
            party_name = match.group(1).strip()
            if len(party_name) > 2:  # Filter out very short matches
                parties.append(
                    {
                        "name": party_name + " " + match.group(0).split()[-1],
                        "type": "company",
                        "position": (match.start(), match.end()),
                        "confidence": 0.9,
                    }
                )

        # Individual name patterns (simplified)
        name_pattern = re.compile(
            r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b"
        )

        for match in name_pattern.finditer(content):
            parties.append(
                {
                    "name": match.group(1),
                    "type": "individual",
                    "position": (match.start(), match.end()),
                    "confidence": 0.8,
                }
            )

        return parties

    def _extract_date_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract date entities."""
        dates = []

        # Various date formats
        date_patterns = [
            re.compile(
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
            ),
            re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
            re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
            re.compile(
                r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"
            ),
        ]

        for pattern in date_patterns:
            for match in pattern.finditer(content):
                dates.append(
                    {
                        "date": match.group(0),
                        "position": (match.start(), match.end()),
                        "confidence": 0.95,
                    }
                )

        return dates

    def _extract_monetary_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract monetary amount entities."""
        amounts = []

        # Money patterns
        money_patterns = [
            re.compile(r"\$[\d,]+(?:\.\d{2})?"),
            re.compile(r"\b\d+\s+dollars?\b", re.IGNORECASE),
            re.compile(r"\b(?:USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?\b"),
            re.compile(r"\b(?:million|billion|thousand)\s+dollars?\b", re.IGNORECASE),
        ]

        for pattern in money_patterns:
            for match in pattern.finditer(content):
                amounts.append(
                    {
                        "amount": match.group(0),
                        "position": (match.start(), match.end()),
                        "confidence": 0.9,
                    }
                )

        return amounts

    def _extract_jurisdiction_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract jurisdiction entities."""
        jurisdictions = []

        # US states and territories
        us_states = [
            "Alabama",
            "Alaska",
            "Arizona",
            "Arkansas",
            "California",
            "Colorado",
            "Connecticut",
            "Delaware",
            "Florida",
            "Georgia",
            "Hawaii",
            "Idaho",
            "Illinois",
            "Indiana",
            "Iowa",
            "Kansas",
            "Kentucky",
            "Louisiana",
            "Maine",
            "Maryland",
            "Massachusetts",
            "Michigan",
            "Minnesota",
            "Mississippi",
            "Missouri",
            "Montana",
            "Nebraska",
            "Nevada",
            "New Hampshire",
            "New Jersey",
            "New Mexico",
            "New York",
            "North Carolina",
            "North Dakota",
            "Ohio",
            "Oklahoma",
            "Oregon",
            "Pennsylvania",
            "Rhode Island",
            "South Carolina",
            "South Dakota",
            "Tennessee",
            "Texas",
            "Utah",
            "Vermont",
            "Virginia",
            "Washington",
            "West Virginia",
            "Wisconsin",
            "Wyoming",
            "District of Columbia",
        ]

        # Create pattern for US states
        states_pattern = r"\b(?:" + "|".join(us_states) + r")\b"
        jurisdiction_pattern = re.compile(states_pattern, re.IGNORECASE)

        for match in jurisdiction_pattern.finditer(content):
            jurisdictions.append(
                {
                    "jurisdiction": match.group(0),
                    "type": "state",
                    "position": (match.start(), match.end()),
                    "confidence": 0.95,
                }
            )

        # Federal jurisdiction
        federal_pattern = re.compile(r"\b(?:United States|federal|Federal)\b")
        for match in federal_pattern.finditer(content):
            jurisdictions.append(
                {
                    "jurisdiction": match.group(0),
                    "type": "federal",
                    "position": (match.start(), match.end()),
                    "confidence": 0.9,
                }
            )

        return jurisdictions

    def _extract_court_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract court entities."""
        courts = []

        court_pattern = re.compile(
            r"\b(?:Supreme Court|Court of Appeals|Appellate Court|District Court|"
            r"Circuit Court|Superior Court|Municipal Court|Bankruptcy Court|"
            r"Tax Court|Federal Court|State Court|Family Court|Probate Court)\b",
            re.IGNORECASE,
        )

        for match in court_pattern.finditer(content):
            courts.append(
                {
                    "court": match.group(0),
                    "position": (match.start(), match.end()),
                    "confidence": 0.9,
                }
            )

        return courts

    def _extract_case_number_entities(self, content: str) -> List[Dict[str, Any]]:
        """Extract case number entities."""
        case_numbers = []

        # Various case number formats
        case_patterns = [
            re.compile(
                r"\b(?:Case|Docket|Civil|Criminal)\s+(?:No\.|Number)\s*:?\s*([A-Z0-9\-:]+)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b\d{1,2}:\d{2}-cv-\d{5}\b"),  # Federal civil case format
            re.compile(r"\b\d{1,2}:\d{2}-cr-\d{5}\b"),  # Federal criminal case format
        ]

        for pattern in case_patterns:
            for match in pattern.finditer(content):
                case_numbers.append(
                    {
                        "case_number": match.group(0),
                        "position": (match.start(), match.end()),
                        "confidence": 0.9,
                    }
                )

        return case_numbers

    def analyze_concept_relationships(
        self, concepts: List[LegalConcept]
    ) -> Dict[str, Any]:
        """Analyze relationships between extracted concepts.

        Args:
            concepts: List of extracted concepts

        Returns:
            Analysis of concept relationships
        """
        analysis = {
            "concept_count": len(concepts),
            "concept_types": {},
            "relationships": [],
            "clusters": [],
            "complexity_score": 0.0,
        }

        # Count concept types
        for concept in concepts:
            concept_type = concept.concept_type.value
            analysis["concept_types"][concept_type] = (
                analysis["concept_types"].get(concept_type, 0) + 1
            )

        # Find explicit relationships
        for concept in concepts:
            for related in concept.related_concepts:
                # Check if related concept is also present
                related_concepts = [
                    c for c in concepts if c.concept_type.value == related
                ]
                if related_concepts:
                    analysis["relationships"].append(
                        {
                            "source": concept.concept_type.value,
                            "target": related,
                            "strength": concept.confidence,
                        }
                    )

        # Calculate complexity score
        unique_types = len(analysis["concept_types"])
        total_relationships = len(analysis["relationships"])
        analysis["complexity_score"] = (unique_types * 0.1) + (
            total_relationships * 0.05
        )

        return analysis
