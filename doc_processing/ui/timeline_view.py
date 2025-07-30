"""Timeline view for document history and change tracking."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..converters.change_tracker import ChangeEvent, DocumentSnapshot
from ..converters.diff_visualizer import DocumentDiffVisualizer
from ..converters.google_docs import ConversionResult

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """Represents a single event in the document timeline."""

    event_id: str
    timestamp: datetime
    event_type: str  # 'change', 'comment', 'suggestion', 'conflict', 'merge'
    title: str
    description: str
    author: Optional[str] = None
    document_id: Optional[str] = None
    change_details: Optional[Dict[str, Any]] = None
    affected_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class TimelineFilter:
    """Filter configuration for timeline view."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    event_types: Optional[List[str]] = None
    authors: Optional[List[str]] = None
    document_ids: Optional[List[str]] = None
    content_filter: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.start_date:
            data["start_date"] = self.start_date.isoformat()
        if self.end_date:
            data["end_date"] = self.end_date.isoformat()
        return data


@dataclass
class TimelineGroup:
    """Represents a grouped set of timeline events."""

    group_id: str
    group_type: str  # 'day', 'author', 'document', 'event_type'
    group_title: str
    events: List[TimelineEvent]
    event_count: int
    date_range: Tuple[datetime, datetime]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        data["date_range"] = (
            self.date_range[0].isoformat(),
            self.date_range[1].isoformat(),
        )
        return data


class DocumentTimelineView:
    """Creates timeline visualizations for document history."""

    def __init__(self, diff_visualizer: Optional[DocumentDiffVisualizer] = None):
        """Initialize timeline view.

        Args:
            diff_visualizer: Optional DocumentDiffVisualizer instance
        """
        self.diff_visualizer = diff_visualizer or DocumentDiffVisualizer()
        self.timeline_events: List[TimelineEvent] = []
        self.event_cache: Dict[str, TimelineEvent] = {}

        # Configuration
        self.max_events_per_page = 50
        self.default_time_range = timedelta(days=30)
        self.group_by_default = "day"

    def add_change_event(
        self,
        change_event: ChangeEvent,
        document_snapshot: Optional[DocumentSnapshot] = None,
    ) -> TimelineEvent:
        """Add a change event to the timeline.

        Args:
            change_event: ChangeEvent to add
            document_snapshot: Optional document snapshot for context

        Returns:
            TimelineEvent created from the change
        """
        event_id = f"change_{change_event.document_id}_{int(change_event.timestamp.timestamp())}"

        # Determine event title and description
        title = f"Document {change_event.change_type.title()} Change"
        description = self._format_change_description(change_event)

        # Extract affected content
        affected_content = None
        if change_event.change_details:
            affected_content = change_event.change_details.get("content_preview", "")

        timeline_event = TimelineEvent(
            event_id=event_id,
            timestamp=change_event.timestamp,
            event_type="change",
            title=title,
            description=description,
            author=change_event.author,
            document_id=change_event.document_id,
            change_details=change_event.change_details,
            affected_content=affected_content,
            metadata={
                "change_type": change_event.change_type,
                "document_snapshot": (
                    document_snapshot.to_dict() if document_snapshot else None
                ),
            },
        )

        self.timeline_events.append(timeline_event)
        self.event_cache[event_id] = timeline_event

        logger.debug(f"Added change event {event_id} to timeline")
        return timeline_event

    def add_comment_event(
        self,
        comment_id: str,
        document_id: str,
        author: str,
        content: str,
        timestamp: datetime,
        anchor_text: Optional[str] = None,
    ) -> TimelineEvent:
        """Add a comment event to the timeline.

        Args:
            comment_id: Comment identifier
            document_id: Document identifier
            author: Comment author
            content: Comment content
            timestamp: Comment timestamp
            anchor_text: Optional text the comment is anchored to

        Returns:
            TimelineEvent created from the comment
        """
        event_id = f"comment_{comment_id}_{int(timestamp.timestamp())}"

        title = f"Comment Added by {author}"
        description = (
            f"Comment: {content[:100]}..."
            if len(content) > 100
            else f"Comment: {content}"
        )

        timeline_event = TimelineEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type="comment",
            title=title,
            description=description,
            author=author,
            document_id=document_id,
            affected_content=anchor_text,
            metadata={
                "comment_id": comment_id,
                "full_content": content,
                "anchor_text": anchor_text,
            },
        )

        self.timeline_events.append(timeline_event)
        self.event_cache[event_id] = timeline_event

        logger.debug(f"Added comment event {event_id} to timeline")
        return timeline_event

    def add_suggestion_event(
        self,
        suggestion_id: str,
        document_id: str,
        author: str,
        suggestion_type: str,
        content: str,
        timestamp: datetime,
        suggested_text: Optional[str] = None,
    ) -> TimelineEvent:
        """Add a suggestion event to the timeline.

        Args:
            suggestion_id: Suggestion identifier
            document_id: Document identifier
            author: Suggestion author
            suggestion_type: Type of suggestion (INSERT, DELETE, REPLACE)
            content: Suggestion content
            timestamp: Suggestion timestamp
            suggested_text: Optional text being suggested

        Returns:
            TimelineEvent created from the suggestion
        """
        event_id = f"suggestion_{suggestion_id}_{int(timestamp.timestamp())}"

        title = f"Suggestion ({suggestion_type}) by {author}"
        description = (
            f"Suggested: {content[:100]}..."
            if len(content) > 100
            else f"Suggested: {content}"
        )

        timeline_event = TimelineEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type="suggestion",
            title=title,
            description=description,
            author=author,
            document_id=document_id,
            affected_content=suggested_text,
            metadata={
                "suggestion_id": suggestion_id,
                "suggestion_type": suggestion_type,
                "full_content": content,
                "suggested_text": suggested_text,
            },
        )

        self.timeline_events.append(timeline_event)
        self.event_cache[event_id] = timeline_event

        logger.debug(f"Added suggestion event {event_id} to timeline")
        return timeline_event

    def add_conflict_event(
        self,
        conflict_id: str,
        document_id: str,
        conflict_type: str,
        timestamp: datetime,
        resolver: Optional[str] = None,
        resolution_status: str = "pending",
    ) -> TimelineEvent:
        """Add a conflict event to the timeline.

        Args:
            conflict_id: Conflict identifier
            document_id: Document identifier
            conflict_type: Type of conflict
            timestamp: Conflict timestamp
            resolver: Optional resolver identifier
            resolution_status: Status of conflict resolution

        Returns:
            TimelineEvent created from the conflict
        """
        event_id = f"conflict_{conflict_id}_{int(timestamp.timestamp())}"

        title = f"Conflict Detected ({conflict_type.title()})"
        description = f"Conflict resolution status: {resolution_status.title()}"
        if resolver:
            description += f" | Resolved by: {resolver}"

        timeline_event = TimelineEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type="conflict",
            title=title,
            description=description,
            author=resolver,
            document_id=document_id,
            metadata={
                "conflict_id": conflict_id,
                "conflict_type": conflict_type,
                "resolution_status": resolution_status,
                "resolver": resolver,
            },
        )

        self.timeline_events.append(timeline_event)
        self.event_cache[event_id] = timeline_event

        logger.debug(f"Added conflict event {event_id} to timeline")
        return timeline_event

    def add_merge_event(
        self,
        merge_id: str,
        document_id: str,
        merger: str,
        timestamp: datetime,
        source_branches: List[str],
        target_branch: str,
        conflicts_resolved: int = 0,
    ) -> TimelineEvent:
        """Add a merge event to the timeline.

        Args:
            merge_id: Merge identifier
            document_id: Document identifier
            merger: Person who performed the merge
            timestamp: Merge timestamp
            source_branches: Source branches being merged
            target_branch: Target branch for merge
            conflicts_resolved: Number of conflicts resolved

        Returns:
            TimelineEvent created from the merge
        """
        event_id = f"merge_{merge_id}_{int(timestamp.timestamp())}"

        title = f"Merge Completed by {merger}"
        description = f"Merged {', '.join(source_branches)} into {target_branch}"
        if conflicts_resolved > 0:
            description += f" | {conflicts_resolved} conflicts resolved"

        timeline_event = TimelineEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type="merge",
            title=title,
            description=description,
            author=merger,
            document_id=document_id,
            metadata={
                "merge_id": merge_id,
                "source_branches": source_branches,
                "target_branch": target_branch,
                "conflicts_resolved": conflicts_resolved,
            },
        )

        self.timeline_events.append(timeline_event)
        self.event_cache[event_id] = timeline_event

        logger.debug(f"Added merge event {event_id} to timeline")
        return timeline_event

    def filter_timeline(self, filter_config: TimelineFilter) -> List[TimelineEvent]:
        """Filter timeline events based on configuration.

        Args:
            filter_config: Filter configuration

        Returns:
            List of filtered timeline events
        """
        filtered_events = self.timeline_events

        # Filter by date range
        if filter_config.start_date:
            filtered_events = [
                e for e in filtered_events if e.timestamp >= filter_config.start_date
            ]
        if filter_config.end_date:
            filtered_events = [
                e for e in filtered_events if e.timestamp <= filter_config.end_date
            ]

        # Filter by event types
        if filter_config.event_types:
            filtered_events = [
                e for e in filtered_events if e.event_type in filter_config.event_types
            ]

        # Filter by authors
        if filter_config.authors:
            filtered_events = [
                e for e in filtered_events if e.author in filter_config.authors
            ]

        # Filter by document IDs
        if filter_config.document_ids:
            filtered_events = [
                e
                for e in filtered_events
                if e.document_id in filter_config.document_ids
            ]

        # Filter by content
        if filter_config.content_filter:
            content_filter = filter_config.content_filter.lower()
            filtered_events = [
                e
                for e in filtered_events
                if (
                    content_filter in e.title.lower()
                    or content_filter in e.description.lower()
                    or (
                        e.affected_content
                        and content_filter in e.affected_content.lower()
                    )
                )
            ]

        return sorted(filtered_events, key=lambda e: e.timestamp, reverse=True)

    def group_timeline_events(
        self, events: List[TimelineEvent], group_by: str = "day"
    ) -> List[TimelineGroup]:
        """Group timeline events by specified criteria.

        Args:
            events: List of timeline events to group
            group_by: Grouping criteria ('day', 'author', 'document', 'event_type')

        Returns:
            List of TimelineGroup objects
        """
        groups: Dict[str, List[TimelineEvent]] = {}

        for event in events:
            if group_by == "day":
                group_key = event.timestamp.date().isoformat()
            elif group_by == "author":
                group_key = event.author or "Unknown"
            elif group_by == "document":
                group_key = event.document_id or "Unknown"
            elif group_by == "event_type":
                group_key = event.event_type
            else:
                group_key = "All Events"

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(event)

        # Create TimelineGroup objects
        timeline_groups = []
        for group_key, group_events in groups.items():
            group_events.sort(key=lambda e: e.timestamp, reverse=True)

            # Calculate date range
            timestamps = [e.timestamp for e in group_events]
            min_date = min(timestamps)
            max_date = max(timestamps)

            # Generate group title
            if group_by == "day":
                group_title = min_date.strftime("%B %d, %Y")
            elif group_by == "author":
                group_title = f"Events by {group_key}"
            elif group_by == "document":
                group_title = f"Document: {group_key}"
            elif group_by == "event_type":
                group_title = f"{group_key.title()} Events"
            else:
                group_title = group_key

            timeline_group = TimelineGroup(
                group_id=f"group_{group_by}_{group_key}",
                group_type=group_by,
                group_title=group_title,
                events=group_events,
                event_count=len(group_events),
                date_range=(min_date, max_date),
            )

            timeline_groups.append(timeline_group)

        # Sort groups by most recent event
        timeline_groups.sort(key=lambda g: g.date_range[1], reverse=True)

        return timeline_groups

    def create_timeline_visualization(
        self,
        filter_config: Optional[TimelineFilter] = None,
        group_by: str = "day",
        max_events: Optional[int] = None,
    ) -> str:
        """Create HTML visualization of the timeline.

        Args:
            filter_config: Optional filter configuration
            group_by: Grouping criteria
            max_events: Maximum number of events to display

        Returns:
            HTML string with timeline visualization
        """
        # Filter events
        if filter_config:
            events = self.filter_timeline(filter_config)
        else:
            events = self.timeline_events

        # Limit events if specified
        if max_events:
            events = events[:max_events]

        # Group events
        groups = self.group_timeline_events(events, group_by)

        html_parts = []

        # Add CSS
        html_parts.append(self._get_timeline_css())

        # Start timeline container
        html_parts.append('<div class="timeline-container">')

        # Add header
        html_parts.append(self._create_timeline_header(len(events), filter_config))

        # Add filter controls
        html_parts.append(self._create_filter_controls(filter_config))

        # Add timeline content
        html_parts.append('<div class="timeline-content">')

        for group in groups:
            html_parts.append(self._create_timeline_group(group))

        html_parts.append("</div>")

        # Add footer
        html_parts.append(self._create_timeline_footer())

        # End timeline container
        html_parts.append("</div>")

        # Add JavaScript
        html_parts.append(self._get_timeline_javascript())

        return "".join(html_parts)

    def create_event_detail_view(self, event_id: str) -> str:
        """Create detailed view for a specific event.

        Args:
            event_id: Event identifier

        Returns:
            HTML string with event details
        """
        event = self.event_cache.get(event_id)
        if not event:
            return "<div class='error'>Event not found</div>"

        html_parts = []

        # Add CSS
        html_parts.append(self._get_event_detail_css())

        # Start detail container
        html_parts.append('<div class="event-detail">')

        # Add event header
        html_parts.append(self._create_event_header(event))

        # Add event content
        html_parts.append(self._create_event_content(event))

        # Add event metadata
        html_parts.append(self._create_event_metadata(event))

        # Add related events
        related_events = self._find_related_events(event)
        if related_events:
            html_parts.append(self._create_related_events(related_events))

        # End detail container
        html_parts.append("</div>")

        return "".join(html_parts)

    def export_timeline(
        self,
        output_path: Path,
        format: str = "json",
        filter_config: Optional[TimelineFilter] = None,
    ) -> Dict[str, Any]:
        """Export timeline data to file.

        Args:
            output_path: Output file path
            format: Export format ('json', 'csv', 'html')
            filter_config: Optional filter configuration

        Returns:
            Dictionary with export metadata
        """
        # Filter events
        if filter_config:
            events = self.filter_timeline(filter_config)
        else:
            events = self.timeline_events

        export_data = {
            "timeline_events": [event.to_dict() for event in events],
            "event_count": len(events),
            "export_timestamp": datetime.now().isoformat(),
            "filter_config": filter_config.to_dict() if filter_config else None,
        }

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)
        elif format == "csv":
            import csv

            with open(output_path, "w", newline="") as f:
                if events:
                    writer = csv.DictWriter(f, fieldnames=events[0].to_dict().keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(event.to_dict())
        elif format == "html":
            html_content = self.create_timeline_visualization(filter_config)
            with open(output_path, "w") as f:
                f.write(html_content)

        logger.info(f"Exported timeline to {output_path} in {format} format")
        return export_data

    def _format_change_description(self, change_event: ChangeEvent) -> str:
        """Format change event description."""
        change_type = change_event.change_type
        details = change_event.change_details or {}

        if change_type == "content":
            return (
                f"Content modified: {details.get('change_summary', 'Content changed')}"
            )
        elif change_type == "formatting":
            return f"Formatting changed: {details.get('formatting_changes', 'Formatting updated')}"
        elif change_type == "structure":
            return f"Structure modified: {details.get('structure_changes', 'Document structure changed')}"
        elif change_type == "metadata":
            return f"Metadata updated: {details.get('metadata_changes', 'Document metadata changed')}"
        else:
            return f"Document {change_type} change"

    def _find_related_events(self, event: TimelineEvent) -> List[TimelineEvent]:
        """Find events related to the given event."""
        related = []

        # Find events in the same document
        for e in self.timeline_events:
            if (
                e.event_id != event.event_id
                and e.document_id == event.document_id
                and abs((e.timestamp - event.timestamp).total_seconds()) < 3600
            ):  # Within 1 hour
                related.append(e)

        # Sort by timestamp
        related.sort(key=lambda e: e.timestamp, reverse=True)

        return related[:5]  # Limit to 5 related events

    def _get_timeline_css(self) -> str:
        """Get CSS for timeline visualization."""
        return """
        <style>
        .timeline-container {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }

        .timeline-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }

        .timeline-title {
            font-size: 28px;
            font-weight: 600;
            margin: 0 0 10px 0;
        }

        .timeline-subtitle {
            font-size: 16px;
            opacity: 0.9;
        }

        .filter-controls {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .filter-row {
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
        }

        .filter-row:last-child {
            margin-bottom: 0;
        }

        .filter-label {
            font-weight: 600;
            min-width: 120px;
        }

        .filter-input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-width: 200px;
        }

        .filter-select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-width: 150px;
        }

        .timeline-content {
            position: relative;
        }

        .timeline-content::before {
            content: '';
            position: absolute;
            left: 30px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #dee2e6;
        }

        .timeline-group {
            margin-bottom: 40px;
        }

        .group-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-left: 60px;
        }

        .group-date {
            background: #007bff;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,123,255,0.3);
        }

        .group-stats {
            margin-left: 20px;
            color: #6c757d;
            font-size: 14px;
        }

        .timeline-event {
            position: relative;
            background: white;
            margin-left: 60px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .timeline-event:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }

        .timeline-event::before {
            content: '';
            position: absolute;
            left: -40px;
            top: 20px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #007bff;
            border: 3px solid white;
            box-shadow: 0 0 0 2px #007bff;
        }

        .event-change::before { background: #28a745; box-shadow: 0 0 0 2px #28a745; }
        .event-comment::before { background: #ffc107; box-shadow: 0 0 0 2px #ffc107; }
        .event-suggestion::before { background: #17a2b8; box-shadow: 0 0 0 2px #17a2b8; }
        .event-conflict::before { background: #dc3545; box-shadow: 0 0 0 2px #dc3545; }
        .event-merge::before { background: #6f42c1; box-shadow: 0 0 0 2px #6f42c1; }

        .event-header {
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .event-title {
            font-weight: 600;
            color: #495057;
            margin: 0;
        }

        .event-time {
            font-size: 14px;
            color: #6c757d;
        }

        .event-content {
            padding: 15px 20px;
        }

        .event-description {
            color: #495057;
            line-height: 1.6;
            margin-bottom: 10px;
        }

        .event-author {
            font-size: 14px;
            color: #6c757d;
            margin-bottom: 10px;
        }

        .event-affected-content {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            border-left: 4px solid #007bff;
        }

        .event-actions {
            padding: 10px 20px;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: background-color 0.2s ease;
        }

        .btn-primary {
            background: #007bff;
            color: white;
        }

        .btn-primary:hover {
            background: #0056b3;
        }

        .btn-outline {
            background: transparent;
            color: #007bff;
            border: 1px solid #007bff;
        }

        .btn-outline:hover {
            background: #007bff;
            color: white;
        }

        .timeline-footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 14px;
        }

        .load-more {
            background: #007bff;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }

        .load-more:hover {
            background: #0056b3;
        }

        @media (max-width: 768px) {
            .timeline-container {
                padding: 10px;
            }

            .timeline-content::before {
                left: 20px;
            }

            .timeline-event {
                margin-left: 40px;
            }

            .timeline-event::before {
                left: -30px;
            }

            .group-header {
                padding-left: 40px;
            }

            .filter-row {
                flex-direction: column;
                align-items: flex-start;
            }
        }
        </style>
        """

    def _create_timeline_header(
        self, event_count: int, filter_config: Optional[TimelineFilter]
    ) -> str:
        """Create timeline header."""
        subtitle = f"Showing {event_count} events"
        if filter_config:
            if filter_config.start_date or filter_config.end_date:
                subtitle += " (filtered)"

        return """
        <div class="timeline-header">
            <h1 class="timeline-title">Document Timeline</h1>
            <p class="timeline-subtitle">{subtitle}</p>
        </div>
        """

    def _create_filter_controls(self, filter_config: Optional[TimelineFilter]) -> str:
        """Create filter controls."""
        return """
        <div class="filter-controls">
            <div class="filter-row">
                <label class="filter-label">Date Range:</label>
                <input type="date" class="filter-input" id="start-date" placeholder="Start Date">
                <input type="date" class="filter-input" id="end-date" placeholder="End Date">
            </div>
            <div class="filter-row">
                <label class="filter-label">Event Types:</label>
                <select class="filter-select" id="event-types" multiple>
                    <option value="change">Changes</option>
                    <option value="comment">Comments</option>
                    <option value="suggestion">Suggestions</option>
                    <option value="conflict">Conflicts</option>
                    <option value="merge">Merges</option>
                </select>
            </div>
            <div class="filter-row">
                <label class="filter-label">Author:</label>
                <input type="text" class="filter-input" id="author-filter" placeholder="Filter by author">
            </div>
            <div class="filter-row">
                <label class="filter-label">Content:</label>
                <input type="text" class="filter-input" id="content-filter" placeholder="Search content">
                <button class="btn btn-primary" onclick="applyFilters()">Apply Filters</button>
                <button class="btn btn-outline" onclick="clearFilters()">Clear</button>
            </div>
        </div>
        """

    def _create_timeline_group(self, group: TimelineGroup) -> str:
        """Create timeline group HTML."""
        html_parts = []

        # Group header
        html_parts.append(
            """
        <div class="timeline-group">
            <div class="group-header">
                <div class="group-date">{group.group_title}</div>
                <div class="group-stats">{group.event_count} events</div>
            </div>
        """
        )

        # Group events
        for event in group.events:
            html_parts.append(self._create_timeline_event(event))

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_timeline_event(self, event: TimelineEvent) -> str:
        """Create timeline event HTML."""
        time_str = event.timestamp.strftime("%I:%M %p")

        html_parts = []

        # Start event
        html_parts.append(
            f'<div class="timeline-event event-{event.event_type}" data-event-id="{event.event_id}">'
        )

        # Event header
        html_parts.append(
            """
        <div class="event-header">
            <h3 class="event-title">{event.title}</h3>
            <span class="event-time">{time_str}</span>
        </div>
        """
        )

        # Event content
        html_parts.append('<div class="event-content">')

        # Description
        html_parts.append(f'<p class="event-description">{event.description}</p>')

        # Author
        if event.author:
            html_parts.append(f'<p class="event-author">by {event.author}</p>')

        # Affected content
        if event.affected_content:
            html_parts.append(
                """
            <div class="event-affected-content">
                {self._escape_html(event.affected_content[:200])}
                {'...' if len(event.affected_content) > 200 else ''}
            </div>
            """
            )

        html_parts.append("</div>")

        # Event actions
        html_parts.append(
            """
        <div class="event-actions">
            <button class="btn btn-primary" onclick="viewEventDetail('{event.event_id}')">
                View Details
            </button>
            <button class="btn btn-outline" onclick="showRelatedEvents('{event.event_id}')">
                Related Events
            </button>
        </div>
        """
        )

        # End event
        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_timeline_footer(self) -> str:
        """Create timeline footer."""
        return """
        <div class="timeline-footer">
            <button class="load-more" onclick="loadMoreEvents()">
                Load More Events
            </button>
        </div>
        """

    def _get_timeline_javascript(self) -> str:
        """Get JavaScript for timeline functionality."""
        return """
        <script>
        class TimelineView {
            constructor() {
                this.currentPage = 1;
                this.eventsPerPage = 50;
                this.currentFilter = null;

                this.initializeEventHandlers();
            }

            initializeEventHandlers() {
                // Set up filter input handlers
                document.getElementById('start-date').addEventListener('change', () => this.onFilterChange());
                document.getElementById('end-date').addEventListener('change', () => this.onFilterChange());
                document.getElementById('event-types').addEventListener('change', () => this.onFilterChange());
                document.getElementById('author-filter').addEventListener('input', () => this.onFilterChange());
                document.getElementById('content-filter').addEventListener('input', () => this.onFilterChange());

                // Set up event clicking
                document.querySelectorAll('.timeline-event').forEach(element => {
                    element.addEventListener('click', (e) => {
                        if (!e.target.classList.contains('btn')) {
                            this.selectEvent(element.dataset.eventId);
                        }
                    });
                });
            }

            onFilterChange() {
                // Auto-apply filters with debounce
                clearTimeout(this.filterTimeout);
                this.filterTimeout = setTimeout(() => {
                    this.applyFilters();
                }, 500);
            }

            selectEvent(eventId) {
                // Remove previous selection
                document.querySelectorAll('.timeline-event').forEach(el => {
                    el.classList.remove('selected');
                });

                // Add selection to clicked event
                const eventElement = document.querySelector(`[data-event-id="${eventId}"]`);
                if (eventElement) {
                    eventElement.classList.add('selected');
                }

                console.log('Selected event:', eventId);
            }

            applyFilters() {
                console.log('Applying filters...');
                // Implementation would send filter request to server
            }

            clearFilters() {
                document.getElementById('start-date').value = '';
                document.getElementById('end-date').value = '';
                document.getElementById('event-types').selectedIndex = -1;
                document.getElementById('author-filter').value = '';
                document.getElementById('content-filter').value = '';

                console.log('Filters cleared');
                this.applyFilters();
            }

            loadMoreEvents() {
                this.currentPage++;
                console.log('Loading more events, page:', this.currentPage);
                // Implementation would load additional events
            }
        }

        // Initialize timeline view
        const timelineView = new TimelineView();

        // Global functions for event handlers
        function viewEventDetail(eventId) {
            console.log('Viewing event detail:', eventId);
            // Implementation would open event detail view
        }

        function showRelatedEvents(eventId) {
            console.log('Showing related events for:', eventId);
            // Implementation would show related events
        }

        function applyFilters() {
            timelineView.applyFilters();
        }

        function clearFilters() {
            timelineView.clearFilters();
        }

        function loadMoreEvents() {
            timelineView.loadMoreEvents();
        }

        // Add CSS for selected event
        const style = document.createElement('style');
        style.textContent = `
            .timeline-event.selected {
                transform: translateX(10px);
                box-shadow: 0 4px 16px rgba(0,123,255,0.3);
                border-left: 4px solid #007bff;
            }
        `;
        document.head.appendChild(style);
        </script>
        """

    def _get_event_detail_css(self) -> str:
        """Get CSS for event detail view."""
        return """
        <style>
        .event-detail {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        }

        .event-detail-header {
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
            background: #f8f9fa;
            border-radius: 8px 8px 0 0;
        }

        .event-detail-title {
            font-size: 24px;
            font-weight: 600;
            margin: 0 0 10px 0;
            color: #495057;
        }

        .event-detail-meta {
            color: #6c757d;
            font-size: 14px;
        }

        .event-detail-content {
            padding: 20px;
        }

        .content-section {
            margin-bottom: 20px;
        }

        .content-section h4 {
            margin: 0 0 10px 0;
            font-size: 16px;
            font-weight: 600;
            color: #495057;
        }

        .content-section-content {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #007bff;
        }

        .event-metadata {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
        }

        .metadata-item {
            display: flex;
            margin-bottom: 10px;
        }

        .metadata-item:last-child {
            margin-bottom: 0;
        }

        .metadata-label {
            font-weight: 600;
            min-width: 120px;
            color: #495057;
        }

        .metadata-value {
            color: #6c757d;
        }

        .related-events {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
        }

        .related-events h4 {
            margin-bottom: 15px;
        }

        .related-event {
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }

        .related-event:hover {
            background-color: #f8f9fa;
        }

        .related-event-title {
            font-weight: 600;
            color: #495057;
        }

        .related-event-time {
            font-size: 14px;
            color: #6c757d;
        }
        </style>
        """

    def _create_event_header(self, event: TimelineEvent) -> str:
        """Create event detail header."""
        return """
        <div class="event-detail-header">
            <h1 class="event-detail-title">{event.title}</h1>
            <div class="event-detail-meta">
                {event.timestamp.strftime("%B %d, %Y at %I:%M %p")}
                {f" • by {event.author}" if event.author else ""}
                {f" • {event.document_id}" if event.document_id else ""}
            </div>
        </div>
        """

    def _create_event_content(self, event: TimelineEvent) -> str:
        """Create event detail content."""
        html_parts = []

        html_parts.append('<div class="event-detail-content">')

        # Description
        html_parts.append(
            """
        <div class="content-section">
            <h4>Description</h4>
            <div class="content-section-content">
                {event.description}
            </div>
        </div>
        """
        )

        # Affected content
        if event.affected_content:
            html_parts.append(
                """
            <div class="content-section">
                <h4>Affected Content</h4>
                <div class="content-section-content">
                    <code>{self._escape_html(event.affected_content)}</code>
                </div>
            </div>
            """
            )

        # Change details
        if event.change_details:
            html_parts.append(
                """
            <div class="content-section">
                <h4>Change Details</h4>
                <div class="content-section-content">
                    <pre>{json.dumps(event.change_details, indent=2)}</pre>
                </div>
            </div>
            """
            )

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_event_metadata(self, event: TimelineEvent) -> str:
        """Create event metadata section."""
        html_parts = []

        html_parts.append('<div class="event-metadata">')
        html_parts.append("<h4>Event Metadata</h4>")

        # Basic metadata
        html_parts.append(
            """
        <div class="metadata-item">
            <div class="metadata-label">Event ID:</div>
            <div class="metadata-value">{event.event_id}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Event Type:</div>
            <div class="metadata-value">{event.event_type.title()}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Timestamp:</div>
            <div class="metadata-value">{event.timestamp.isoformat()}</div>
        </div>
        """
        )

        # Additional metadata
        if event.metadata:
            for key, value in event.metadata.items():
                if key != "document_snapshot":  # Skip large objects
                    html_parts.append(
                        """
                    <div class="metadata-item">
                        <div class="metadata-label">{key.title()}:</div>
                        <div class="metadata-value">{str(value)}</div>
                    </div>
                    """
                    )

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_related_events(self, related_events: List[TimelineEvent]) -> str:
        """Create related events section."""
        html_parts = []

        html_parts.append('<div class="related-events">')
        html_parts.append("<h4>Related Events</h4>")

        for event in related_events:
            html_parts.append(
                """
            <div class="related-event" onclick="viewEventDetail('{event.event_id}')">
                <div class="related-event-title">{event.title}</div>
                <div class="related-event-time">{event.timestamp.strftime("%I:%M %p")}</div>
            </div>
            """
            )

        html_parts.append("</div>")

        return "".join(html_parts)

    def _escape_html(self, text: str) -> str:
        """Escape HTML characters in text."""
        import html

        return html.escape(str(text))
