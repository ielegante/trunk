"""User interface components for document processing."""

from .conflict_interface import (
    ConflictAction,
    ConflictUIState,
    SplitScreenConflictInterface,
)
from .timeline_view import (
    DocumentTimelineView,
    TimelineEvent,
    TimelineFilter,
    TimelineGroup,
)

__all__ = [
    "SplitScreenConflictInterface",
    "ConflictUIState",
    "ConflictAction",
    "DocumentTimelineView",
    "TimelineEvent",
    "TimelineFilter",
    "TimelineGroup",
]
