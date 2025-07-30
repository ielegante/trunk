"""Template management system for legal documents."""

from .redaction_system import (
    RedactionResult,
    RedactionRule,
    RedactionSystem,
    SensitiveContent,
)
from .sanitization_pipeline import FileChange, SanitizationPipeline, SanitizationReport
from .template_manager import (
    TemplateField,
    TemplateManager,
    TemplateMetadata,
    TemplateRelationship,
    TemplateVersion,
)

__all__ = [
    # Template management
    "TemplateManager",
    "TemplateMetadata",
    "TemplateField",
    "TemplateVersion",
    "TemplateRelationship",
    # Redaction system
    "RedactionSystem",
    "RedactionRule",
    "RedactionResult",
    "SensitiveContent",
    # Sanitization pipeline
    "SanitizationPipeline",
    "SanitizationReport",
    "FileChange",
]
