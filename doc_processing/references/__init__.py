"""Cross-document reference system."""

from .auto_renumber import (
    AutoRenumberingSystem,
    RenumberingRule,
    Section,
    SectionNumber,
)
from .dependency_visualizer import (
    DependencyAlert,
    DependencyEdge,
    DependencyNode,
    DependencyVisualizer,
)
from .reference_scanner import (
    ChangeImpact,
    DocumentChange,
    ImpactAnalysisReport,
    ReferenceScanner,
)
from .uri_system import DocumentAnchor, DocumentReference, DocumentURI, URISystem

__all__ = [
    # URI system
    "URISystem",
    "DocumentURI",
    "DocumentAnchor",
    "DocumentReference",
    # Reference scanner
    "ReferenceScanner",
    "ChangeImpact",
    "DocumentChange",
    "ImpactAnalysisReport",
    # Auto-renumbering
    "AutoRenumberingSystem",
    "SectionNumber",
    "Section",
    "RenumberingRule",
    # Dependency visualization
    "DependencyVisualizer",
    "DependencyNode",
    "DependencyEdge",
    "DependencyAlert",
]
