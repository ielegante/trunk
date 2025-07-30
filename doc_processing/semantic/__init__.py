"""Semantic analysis and search module for legal documents.

This module provides advanced semantic analysis capabilities including:
- Legal concept extraction and entity recognition
- Document similarity computation and comparison
- Intelligent content classification and categorization
- Semantic search and discovery functionality
"""

from .analyzer import AnalysisResult, SemanticAnalyzer
from .classifier import ClassificationResult, DocumentCategory, DocumentClassifier
from .concept_extractor import ConceptType, LegalConcept, LegalConceptExtractor
from .search_engine import QueryType, SearchResult, SemanticSearchEngine
from .similarity import DocumentSimilarityEngine, SimilarityMethod, SimilarityResult

__all__ = [
    "SemanticAnalyzer",
    "AnalysisResult",
    "LegalConceptExtractor",
    "LegalConcept",
    "ConceptType",
    "DocumentSimilarityEngine",
    "SimilarityResult",
    "SimilarityMethod",
    "DocumentClassifier",
    "ClassificationResult",
    "DocumentCategory",
    "SemanticSearchEngine",
    "SearchResult",
    "QueryType",
]
