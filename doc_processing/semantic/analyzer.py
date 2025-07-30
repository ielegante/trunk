"""Core semantic analysis engine for legal documents.

This module provides the main semantic analysis orchestration, coordinating
legal concept extraction, similarity analysis, and content classification
for comprehensive document understanding.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .classifier import ClassificationResult, DocumentClassifier
from .concept_extractor import LegalConcept, LegalConceptExtractor
from .similarity import DocumentSimilarityEngine, SimilarityResult

logger = logging.getLogger(__name__)


class AnalysisLevel(Enum):
    """Levels of semantic analysis depth."""

    BASIC = "basic"  # Basic classification and concepts
    STANDARD = "standard"  # Standard analysis with similarity
    COMPREHENSIVE = "comprehensive"  # Full analysis with all features
    CUSTOM = "custom"  # Custom analysis configuration


@dataclass
class AnalysisConfiguration:
    """Configuration for semantic analysis."""

    level: AnalysisLevel = AnalysisLevel.STANDARD

    # Feature flags
    extract_concepts: bool = True
    classify_content: bool = True
    compute_similarity: bool = True
    extract_entities: bool = True
    analyze_sentiment: bool = False
    detect_risks: bool = True

    # Performance settings
    max_document_size: int = 10_000_000  # 10MB
    batch_size: int = 10
    enable_caching: bool = True
    cache_ttl: int = 3600  # 1 hour

    # Quality thresholds
    min_confidence: float = 0.7
    similarity_threshold: float = 0.8
    concept_relevance_threshold: float = 0.6

    # Processing options
    preserve_formatting: bool = True
    include_metadata: bool = True
    generate_summary: bool = True


@dataclass
class AnalysisMetrics:
    """Performance and quality metrics for analysis."""

    processing_time: float
    document_size: int
    concepts_extracted: int
    entities_found: int
    classifications_made: int
    similarity_comparisons: int

    # Quality metrics
    average_confidence: float
    concept_coverage: float  # Percentage of document covered by concepts
    classification_confidence: float

    # Performance metrics
    tokens_per_second: float
    memory_usage: Optional[int] = None
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class AnalysisResult:
    """Complete semantic analysis result for a document."""

    document_id: str
    document_path: str
    analysis_timestamp: datetime
    configuration: AnalysisConfiguration

    # Core analysis results
    concepts: List[LegalConcept] = field(default_factory=list)
    classification: Optional[ClassificationResult] = None
    similarity_results: List[SimilarityResult] = field(default_factory=list)

    # Entity extraction results
    legal_entities: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    key_terms: Set[str] = field(default_factory=set)
    defined_terms: Dict[str, str] = field(default_factory=dict)

    # Document insights
    document_summary: Optional[str] = None
    risk_indicators: List[Dict[str, Any]] = field(default_factory=list)
    compliance_flags: List[str] = field(default_factory=list)

    # Analysis quality and performance
    metrics: Optional[AnalysisMetrics] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary representation."""
        return {
            "document_id": self.document_id,
            "document_path": self.document_path,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "configuration": {
                "level": self.configuration.level.value,
                "extract_concepts": self.configuration.extract_concepts,
                "classify_content": self.configuration.classify_content,
                "compute_similarity": self.configuration.compute_similarity,
            },
            "concepts": [concept.to_dict() for concept in self.concepts],
            "classification": (
                self.classification.to_dict() if self.classification else None
            ),
            "similarity_results": [
                result.to_dict() for result in self.similarity_results
            ],
            "legal_entities": self.legal_entities,
            "key_terms": list(self.key_terms),
            "defined_terms": self.defined_terms,
            "document_summary": self.document_summary,
            "risk_indicators": self.risk_indicators,
            "compliance_flags": self.compliance_flags,
            "metrics": (
                {
                    "processing_time": self.metrics.processing_time,
                    "document_size": self.metrics.document_size,
                    "concepts_extracted": self.metrics.concepts_extracted,
                    "entities_found": self.metrics.entities_found,
                    "average_confidence": self.metrics.average_confidence,
                    "concept_coverage": self.metrics.concept_coverage,
                }
                if self.metrics
                else None
            ),
            "warnings": self.warnings,
            "errors": self.errors,
        }


class SemanticAnalyzer:
    """Main semantic analysis engine for legal documents."""

    def __init__(self, config: Optional[AnalysisConfiguration] = None):
        """Initialize semantic analyzer.

        Args:
            config: Analysis configuration
        """
        self.config = config or AnalysisConfiguration()

        # Initialize component analyzers
        self.concept_extractor = LegalConceptExtractor()
        self.similarity_engine = DocumentSimilarityEngine()
        self.classifier = DocumentClassifier()

        # Analysis cache
        self._cache = {} if self.config.enable_caching else None
        self._analysis_counter = 0

        logger.info(
            f"Initialized SemanticAnalyzer with {self.config.level.value} analysis level"
        )

    def analyze_document(
        self,
        content: str,
        document_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        reference_documents: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """Perform comprehensive semantic analysis on a document.

        Args:
            content: Document content to analyze
            document_path: Path to the document
            metadata: Optional document metadata
            reference_documents: Optional list of reference documents for similarity

        Returns:
            Complete analysis result
        """
        start_time = time.time()
        document_id = self._generate_document_id(document_path)

        # Check cache
        if self._cache and document_id in self._cache:
            cached_result = self._cache[document_id]
            if self._is_cache_valid(cached_result):
                logger.debug(f"Returning cached analysis for {document_id}")
                return cached_result

        # Validate document size
        if len(content) > self.config.max_document_size:
            raise ValueError(
                f"Document size ({len(content)}) exceeds maximum ({self.config.max_document_size})"
            )

        # Initialize result
        result = AnalysisResult(
            document_id=document_id,
            document_path=document_path,
            analysis_timestamp=datetime.now(),
            configuration=self.config,
        )

        try:
            # Extract legal concepts
            if self.config.extract_concepts:
                logger.debug(f"Extracting legal concepts from {document_id}")
                result.concepts = self.concept_extractor.extract_concepts(
                    content,
                    confidence_threshold=self.config.concept_relevance_threshold,
                )

                # Extract key terms and defined terms
                result.key_terms, result.defined_terms = self._extract_key_terms(
                    content
                )

            # Classify document content
            if self.config.classify_content:
                logger.debug(f"Classifying document {document_id}")
                result.classification = self.classifier.classify_document(
                    content, metadata=metadata, concepts=result.concepts
                )

            # Extract legal entities
            if self.config.extract_entities:
                logger.debug(f"Extracting legal entities from {document_id}")
                result.legal_entities = self._extract_legal_entities(content)

            # Compute document similarity
            if self.config.compute_similarity and reference_documents:
                logger.debug(f"Computing similarity for {document_id}")
                result.similarity_results = self._compute_similarities(
                    content, reference_documents
                )

            # Generate document summary
            if self.config.generate_summary:
                result.document_summary = self._generate_summary(
                    content, result.concepts
                )

            # Detect risk indicators
            if self.config.detect_risks:
                result.risk_indicators = self._detect_risk_indicators(
                    content, result.concepts
                )
                result.compliance_flags = self._check_compliance(
                    content, result.concepts
                )

            # Calculate metrics
            processing_time = time.time() - start_time
            result.metrics = self._calculate_metrics(content, result, processing_time)

            # Cache result if enabled
            if self._cache:
                self._cache[document_id] = result

            logger.info(
                f"Completed semantic analysis for {document_id} in {processing_time:.2f}s"
            )

        except Exception as e:
            error_msg = f"Error analyzing document {document_id}: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)

            # Still calculate basic metrics
            processing_time = time.time() - start_time
            result.metrics = AnalysisMetrics(
                processing_time=processing_time,
                document_size=len(content),
                concepts_extracted=0,
                entities_found=0,
                classifications_made=0,
                similarity_comparisons=0,
                average_confidence=0.0,
                concept_coverage=0.0,
                classification_confidence=0.0,
                tokens_per_second=0.0,
            )

        return result

    def analyze_document_batch(
        self,
        documents: List[Tuple[str, str, Optional[Dict[str, Any]]]],
        compute_cross_similarity: bool = True,
    ) -> List[AnalysisResult]:
        """Analyze a batch of documents with optional cross-similarity computation.

        Args:
            documents: List of (content, path, metadata) tuples
            compute_cross_similarity: Whether to compute similarity between documents

        Returns:
            List of analysis results
        """
        logger.info(f"Starting batch analysis of {len(documents)} documents")

        results = []
        document_contents = []

        # Analyze each document individually
        for i, (content, path, metadata) in enumerate(documents):
            logger.debug(f"Analyzing document {i+1}/{len(documents)}: {path}")

            try:
                result = self.analyze_document(content, path, metadata)
                results.append(result)
                document_contents.append(content)

            except Exception as e:
                logger.error(f"Failed to analyze document {path}: {str(e)}")
                # Create error result
                error_result = AnalysisResult(
                    document_id=self._generate_document_id(path),
                    document_path=path,
                    analysis_timestamp=datetime.now(),
                    configuration=self.config,
                    errors=[f"Analysis failed: {str(e)}"],
                )
                results.append(error_result)
                document_contents.append(content)

        # Compute cross-similarities if requested
        if compute_cross_similarity and len(document_contents) > 1:
            logger.debug("Computing cross-document similarities")
            self._add_cross_similarities(results, document_contents)

        logger.info(f"Completed batch analysis of {len(documents)} documents")
        return results

    def _extract_key_terms(self, content: str) -> Tuple[Set[str], Dict[str, str]]:
        """Extract key terms and defined terms from content."""
        import re

        key_terms = set()
        defined_terms = {}

        # Extract quoted terms (likely key terms)
        quoted_pattern = re.compile(r'"([A-Z][A-Za-z\s]+?)"')
        for match in quoted_pattern.finditer(content):
            term = match.group(1).strip()
            if len(term.split()) <= 4:  # Reasonable term length
                key_terms.add(term)

        # Extract defined terms with definitions
        definition_pattern = re.compile(
            r'"([A-Z][A-Za-z\s]+?)"\s+(?:means|shall mean|is defined as|refers to)\s+([^.]+\.)',
            re.IGNORECASE,
        )
        for match in definition_pattern.finditer(content):
            term = match.group(1).strip()
            definition = match.group(2).strip()
            defined_terms[term] = definition
            key_terms.add(term)

        # Extract capitalized terms that appear multiple times
        cap_pattern = re.compile(r"\b[A-Z][A-Za-z]{2,}\b")
        term_counts = {}
        for match in cap_pattern.finditer(content):
            term = match.group(0)
            term_counts[term] = term_counts.get(term, 0) + 1

        # Add frequently used capitalized terms
        for term, count in term_counts.items():
            if count >= 3 and len(term) >= 4:
                key_terms.add(term)

        return key_terms, defined_terms

    def _extract_legal_entities(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract legal entities from content using pattern matching."""
        import re

        entities = {
            "parties": [],
            "dates": [],
            "monetary_amounts": [],
            "jurisdictions": [],
            "courts": [],
            "case_numbers": [],
            "statutes": [],
            "regulations": [],
        }

        # Extract parties (simplified)
        party_patterns = [
            re.compile(
                r"\b([A-Z][A-Za-z\s&,\.]+?)\s+(?:LLC|Inc\.|Corp\.|Company|Co\.|Ltd\.)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bPlaintiff\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s|,|$)", re.IGNORECASE
            ),
            re.compile(
                r"\bDefendant\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s|,|$)", re.IGNORECASE
            ),
        ]

        for pattern in party_patterns:
            for match in pattern.finditer(content):
                party_name = match.group(1).strip()
                entities["parties"].append(
                    {
                        "name": party_name,
                        "position": (match.start(), match.end()),
                        "confidence": 0.8,
                    }
                )

        # Extract dates
        date_pattern = re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|"
            r"\b\d{1,2}/\d{1,2}/\d{4}\b|"
            r"\b\d{4}-\d{2}-\d{2}\b"
        )

        for match in date_pattern.finditer(content):
            entities["dates"].append(
                {
                    "date": match.group(0),
                    "position": (match.start(), match.end()),
                    "confidence": 0.9,
                }
            )

        # Extract monetary amounts
        money_pattern = re.compile(
            r"\$[\d,]+(?:\.\d{2})?|\b\d+\s+dollars?\b", re.IGNORECASE
        )

        for match in money_pattern.finditer(content):
            entities["monetary_amounts"].append(
                {
                    "amount": match.group(0),
                    "position": (match.start(), match.end()),
                    "confidence": 0.85,
                }
            )

        # Extract jurisdictions
        jurisdiction_pattern = re.compile(
            r"\b(?:United States|Delaware|California|New York|Texas|Florida|Illinois|Pennsylvania|Ohio|Georgia|North Carolina|Michigan|New Jersey|Virginia|Washington|Arizona|Massachusetts|Tennessee|Indiana|Missouri|Maryland|Wisconsin|Colorado|Minnesota|South Carolina|Alabama|Louisiana|Kentucky|Oregon|Oklahoma|Connecticut|Utah|Iowa|Nevada|Arkansas|Mississippi|Kansas|New Mexico|Nebraska|West Virginia|Idaho|Hawaii|New Hampshire|Maine|Montana|Rhode Island|South Dakota|North Dakota|Vermont|Wyoming|Alaska)\b"
        )

        for match in jurisdiction_pattern.finditer(content):
            entities["jurisdictions"].append(
                {
                    "jurisdiction": match.group(0),
                    "position": (match.start(), match.end()),
                    "confidence": 0.9,
                }
            )

        # Extract court names
        court_pattern = re.compile(
            r"\b(?:Supreme Court|Court of Appeals|District Court|Circuit Court|Superior Court|Municipal Court|Bankruptcy Court|Tax Court|Federal Court|State Court)\b",
            re.IGNORECASE,
        )

        for match in court_pattern.finditer(content):
            entities["courts"].append(
                {
                    "court": match.group(0),
                    "position": (match.start(), match.end()),
                    "confidence": 0.85,
                }
            )

        return entities

    def _compute_similarities(
        self, content: str, reference_documents: List[str]
    ) -> List[SimilarityResult]:
        """Compute similarity between document and reference documents."""
        similarities = []

        for ref_doc in reference_documents:
            try:
                similarity = self.similarity_engine.compute_similarity(
                    content, ref_doc, method="semantic"
                )
                if similarity.score >= self.config.similarity_threshold:
                    similarities.append(similarity)
            except Exception as e:
                logger.warning(
                    f"Failed to compute similarity with reference document: {str(e)}"
                )

        return similarities

    def _generate_summary(self, content: str, concepts: List[LegalConcept]) -> str:
        """Generate a brief summary of the document."""
        # Simple extractive summarization
        sentences = content.split(". ")

        # Score sentences based on concept presence
        sentence_scores = {}
        concept_terms = set()
        for concept in concepts[:10]:  # Top 10 concepts
            concept_terms.update(concept.keywords)

        for i, sentence in enumerate(sentences[:20]):  # First 20 sentences
            score = 0
            sentence_lower = sentence.lower()
            for term in concept_terms:
                if term.lower() in sentence_lower:
                    score += 1
            sentence_scores[i] = score

        # Select top scoring sentences
        top_sentences = sorted(
            sentence_scores.items(), key=lambda x: x[1], reverse=True
        )[:3]
        top_sentences.sort(key=lambda x: x[0])  # Restore original order

        summary_sentences = [
            sentences[i] for i, _ in top_sentences if i < len(sentences)
        ]
        return (
            ". ".join(summary_sentences) + "."
            if summary_sentences
            else "No summary available."
        )

    def _detect_risk_indicators(
        self, content: str, concepts: List[LegalConcept]
    ) -> List[Dict[str, Any]]:
        """Detect potential risk indicators in the document."""
        import re

        risk_indicators = []

        # Define risk patterns
        risk_patterns = {
            "indemnification": {
                "pattern": re.compile(r"\bindemnif(?:y|ies|ication)\b", re.IGNORECASE),
                "severity": "high",
                "description": "Indemnification clause detected",
            },
            "limitation_of_liability": {
                "pattern": re.compile(
                    r"\blimitation\s+of\s+liability\b", re.IGNORECASE
                ),
                "severity": "medium",
                "description": "Limitation of liability clause detected",
            },
            "liquidated_damages": {
                "pattern": re.compile(r"\bliquidated\s+damages\b", re.IGNORECASE),
                "severity": "high",
                "description": "Liquidated damages clause detected",
            },
            "personal_guarantee": {
                "pattern": re.compile(r"\bpersonal\s+guarantee\b", re.IGNORECASE),
                "severity": "high",
                "description": "Personal guarantee requirement detected",
            },
            "termination_for_convenience": {
                "pattern": re.compile(
                    r"\btermination\s+for\s+convenience\b", re.IGNORECASE
                ),
                "severity": "medium",
                "description": "Termination for convenience clause detected",
            },
        }

        # Check for risk patterns
        for risk_type, risk_info in risk_patterns.items():
            matches = list(risk_info["pattern"].finditer(content))
            for match in matches:
                risk_indicators.append(
                    {
                        "type": risk_type,
                        "severity": risk_info["severity"],
                        "description": risk_info["description"],
                        "position": (match.start(), match.end()),
                        "text": match.group(0),
                        "confidence": 0.9,
                    }
                )

        # Check concept-based risks
        high_risk_concepts = ["liability", "indemnity", "penalty", "breach", "default"]
        for concept in concepts:
            if any(keyword in high_risk_concepts for keyword in concept.keywords):
                risk_indicators.append(
                    {
                        "type": "concept_risk",
                        "severity": "medium",
                        "description": f"High-risk legal concept detected: {concept.concept_type.value}",
                        "concept": concept.concept_type.value,
                        "confidence": concept.confidence,
                    }
                )

        return risk_indicators

    def _check_compliance(
        self, content: str, concepts: List[LegalConcept]
    ) -> List[str]:
        """Check for compliance-related flags."""
        compliance_flags = []

        # Check for GDPR-related terms
        gdpr_terms = [
            "personal data",
            "data protection",
            "privacy policy",
            "consent",
            "data subject",
        ]
        if any(term in content.lower() for term in gdpr_terms):
            compliance_flags.append("GDPR_RELEVANT")

        # Check for financial regulations
        finreg_terms = [
            "securities",
            "investment",
            "financial instrument",
            "sec filing",
        ]
        if any(term in content.lower() for term in finreg_terms):
            compliance_flags.append("FINANCIAL_REGULATION")

        # Check for employment law
        employment_terms = [
            "employment",
            "employee",
            "workplace",
            "discrimination",
            "harassment",
        ]
        if any(term in content.lower() for term in employment_terms):
            compliance_flags.append("EMPLOYMENT_LAW")

        # Check for intellectual property
        ip_terms = [
            "patent",
            "trademark",
            "copyright",
            "trade secret",
            "intellectual property",
        ]
        if any(term in content.lower() for term in ip_terms):
            compliance_flags.append("INTELLECTUAL_PROPERTY")

        return compliance_flags

    def _add_cross_similarities(
        self, results: List[AnalysisResult], contents: List[str]
    ):
        """Add cross-document similarities to analysis results."""
        for i, result_i in enumerate(results):
            for j, result_j in enumerate(results):
                if i != j:
                    try:
                        similarity = self.similarity_engine.compute_similarity(
                            contents[i], contents[j], method="semantic"
                        )
                        similarity.target_document = result_j.document_id
                        result_i.similarity_results.append(similarity)
                    except Exception as e:
                        logger.warning(f"Failed to compute cross-similarity: {str(e)}")

    def _calculate_metrics(
        self, content: str, result: AnalysisResult, processing_time: float
    ) -> AnalysisMetrics:
        """Calculate analysis metrics."""
        # Estimate token count (rough approximation)
        token_count = len(content.split())

        # Calculate average confidence
        confidences = []
        if result.concepts:
            confidences.extend([c.confidence for c in result.concepts])
        if result.classification:
            confidences.append(result.classification.confidence)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Calculate concept coverage (percentage of document covered by concepts)
        concept_coverage = 0.0
        if result.concepts:
            covered_chars = sum(
                len(" ".join(concept.keywords)) for concept in result.concepts
            )
            concept_coverage = (
                min(covered_chars / len(content), 1.0) if content else 0.0
            )

        return AnalysisMetrics(
            processing_time=processing_time,
            document_size=len(content),
            concepts_extracted=len(result.concepts),
            entities_found=sum(
                len(entities) for entities in result.legal_entities.values()
            ),
            classifications_made=1 if result.classification else 0,
            similarity_comparisons=len(result.similarity_results),
            average_confidence=avg_confidence,
            concept_coverage=concept_coverage,
            classification_confidence=(
                result.classification.confidence if result.classification else 0.0
            ),
            tokens_per_second=(
                token_count / processing_time if processing_time > 0 else 0.0
            ),
        )

    def _generate_document_id(self, document_path: str) -> str:
        """Generate unique document ID."""
        self._analysis_counter += 1
        return f"doc_{self._analysis_counter:06d}_{Path(document_path).stem}"

    def _is_cache_valid(self, cached_result: AnalysisResult) -> bool:
        """Check if cached result is still valid."""
        if not self.config.enable_caching:
            return False

        cache_age = (datetime.now() - cached_result.analysis_timestamp).seconds
        return cache_age < self.config.cache_ttl

    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get overall analysis statistics."""
        cache_stats = {}
        if self._cache:
            cache_stats = {"cache_size": len(self._cache), "cache_enabled": True}
        else:
            cache_stats = {"cache_enabled": False}

        return {
            "total_analyses": self._analysis_counter,
            "configuration": {
                "level": self.config.level.value,
                "max_document_size": self.config.max_document_size,
                "batch_size": self.config.batch_size,
                "min_confidence": self.config.min_confidence,
            },
            **cache_stats,
        }
