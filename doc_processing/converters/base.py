"""Base converter class for document format conversion."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class BaseConverter(ABC):
    """Abstract base class for document converters."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize converter with optional configuration."""
        self.config = config or {}

    @abstractmethod
    def to_markdown(self, source: str) -> str:
        """Convert document to Markdown format."""
        pass

    @abstractmethod
    def from_markdown(self, markdown: str, target_path: Optional[Path] = None) -> str:
        """Convert Markdown to target document format."""
        pass

    @abstractmethod
    def validate_conversion(self, original: str, converted: str) -> bool:
        """Validate round-trip conversion accuracy."""
        pass
