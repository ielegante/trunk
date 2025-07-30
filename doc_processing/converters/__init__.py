"""Document format converters for Google Docs, Word, and Markdown."""

from .accuracy_tester import AccuracyTester, AccuracyTestResult, TestSuite
from .base import BaseConverter
from .change_tracker import (
    ChangeEvent,
    DocumentSnapshot,
    RealTimeChangeTracker,
    TrackingConfig,
)
from .conflict_resolver import ConflictRegion, ConflictResolution, ConflictResolver
from .diff_visualizer import (
    DiffBlock,
    DiffLine,
    DiffVisualization,
    DocumentDiffVisualizer,
)
from .google_docs import (
    Comment,
    ConversionResult,
    DocumentElement,
    GoogleDocsConverter,
    Suggestion,
)
from .word import WordConverter
from .word_docx import (
    TrackChange,
    WordComment,
    WordConversionResult,
    WordDocxConverter,
    WordMetadata,
    WordParagraph,
    WordStyle,
    WordTable,
)

__all__ = [
    # Base converter
    "BaseConverter",
    # Google Docs conversion
    "GoogleDocsConverter",
    "ConversionResult",
    "DocumentElement",
    "Comment",
    "Suggestion",
    # Word converters
    "WordConverter",
    "WordDocxConverter",
    "WordConversionResult",
    "WordParagraph",
    "WordTable",
    "WordStyle",
    "WordComment",
    "TrackChange",
    "WordMetadata",
    # Change tracking
    "RealTimeChangeTracker",
    "ChangeEvent",
    "TrackingConfig",
    "DocumentSnapshot",
    # Diff visualization
    "DocumentDiffVisualizer",
    "DiffVisualization",
    "DiffLine",
    "DiffBlock",
    # Accuracy testing
    "AccuracyTester",
    "AccuracyTestResult",
    "TestSuite",
    # Conflict resolution
    "ConflictResolver",
    "ConflictRegion",
    "ConflictResolution",
]
