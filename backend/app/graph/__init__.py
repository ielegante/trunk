"""Graph database module for cross-document reference tracking."""

from .change_propagation import (
    ChangePropagationEngine,
    ChangeType,
    DocumentChange,
    ImpactLevel,
    PropagationPlan,
    PropagationResult,
    PropagationStrategy,
    change_propagation_engine,
)
from .neo4j_config import Neo4jConfig, Neo4jConnection, neo4j_connection
from .reference_tracker import (
    DocumentNode,
    ReferenceEdge,
    ReferenceStatus,
    ReferenceTracker,
    ReferenceType,
    ReferenceValidation,
    reference_tracker,
)
from .reference_validator import (
    BatchValidationResult,
    ReferenceValidator,
    ValidationContext,
    ValidationRule,
    reference_validator,
)

__all__ = [
    # Neo4j
    "Neo4jConfig",
    "Neo4jConnection",
    "neo4j_connection",
    # Reference Tracker
    "ReferenceTracker",
    "reference_tracker",
    "ReferenceType",
    "ReferenceStatus",
    "DocumentNode",
    "ReferenceEdge",
    "ReferenceValidation",
    # Reference Validator
    "ReferenceValidator",
    "reference_validator",
    "ValidationRule",
    "ValidationContext",
    "BatchValidationResult",
    # Change Propagation
    "ChangePropagationEngine",
    "change_propagation_engine",
    "ChangeType",
    "PropagationStrategy",
    "ImpactLevel",
    "DocumentChange",
    "PropagationPlan",
    "PropagationResult",
]
