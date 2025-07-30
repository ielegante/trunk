"""User experience enhancements and refinements for document processing."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """User preferences and settings."""

    user_id: str
    theme: str = "light"  # light, dark, auto
    font_size: str = "medium"  # small, medium, large
    show_line_numbers: bool = True
    auto_save_interval: int = 30  # seconds
    conflict_resolution_mode: str = "split"  # split, inline, side-by-side
    show_diff_highlights: bool = True
    enable_keyboard_shortcuts: bool = True
    notification_preferences: Dict[str, bool] = None
    ui_animations: bool = True
    compact_view: bool = False

    def __post_init__(self):
        if self.notification_preferences is None:
            self.notification_preferences = {
                "conflict_detected": True,
                "merge_completed": True,
                "document_changed": False,
                "comment_added": True,
                "suggestion_made": True,
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class UserSession:
    """User session tracking and management."""

    session_id: str
    user_id: str
    start_time: datetime
    last_activity: datetime
    documents_accessed: List[str] = None
    actions_performed: List[Dict[str, Any]] = None
    current_document: Optional[str] = None
    active_conflicts: List[str] = None

    def __post_init__(self):
        if self.documents_accessed is None:
            self.documents_accessed = []
        if self.actions_performed is None:
            self.actions_performed = []
        if self.active_conflicts is None:
            self.active_conflicts = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        data["last_activity"] = self.last_activity.isoformat()
        return data


@dataclass
class NotificationMessage:
    """Notification message for user."""

    message_id: str
    user_id: str
    message_type: str  # info, warning, error, success
    title: str
    content: str
    timestamp: datetime
    read: bool = False
    persistent: bool = False
    action_required: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class UserExperienceManager:
    """Manages user experience enhancements and refinements."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize user experience manager.

        Args:
            storage_path: Path for storing user data
        """
        self.storage_path = storage_path or Path("user_data")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # User data storage
        self.user_preferences: Dict[str, UserPreferences] = {}
        self.user_sessions: Dict[str, UserSession] = {}
        self.notifications: Dict[str, List[NotificationMessage]] = {}

        # Load existing data
        self._load_user_data()

        # UI enhancement settings
        self.ui_themes = {
            "light": self._get_light_theme(),
            "dark": self._get_dark_theme(),
            "auto": self._get_auto_theme(),
        }

        self.keyboard_shortcuts = self._get_keyboard_shortcuts()
        self.accessibility_features = self._get_accessibility_features()

    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get user preferences, creating defaults if not found.

        Args:
            user_id: User identifier

        Returns:
            UserPreferences object
        """
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
            self._save_user_data()

        return self.user_preferences[user_id]

    def update_user_preferences(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> UserPreferences:
        """Update user preferences.

        Args:
            user_id: User identifier
            preferences: Dictionary of preferences to update

        Returns:
            Updated UserPreferences object
        """
        user_prefs = self.get_user_preferences(user_id)

        # Update preferences
        for key, value in preferences.items():
            if hasattr(user_prefs, key):
                setattr(user_prefs, key, value)

        self._save_user_data()

        logger.info(f"Updated preferences for user {user_id}")
        return user_prefs

    def create_user_session(self, user_id: str) -> UserSession:
        """Create a new user session.

        Args:
            user_id: User identifier

        Returns:
            UserSession object
        """
        session_id = f"session_{user_id}_{int(datetime.now().timestamp())}"

        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            start_time=datetime.now(),
            last_activity=datetime.now(),
        )

        self.user_sessions[session_id] = session
        self._save_user_data()

        logger.info(f"Created session {session_id} for user {user_id}")
        return session

    def update_session_activity(self, session_id: str, action: Dict[str, Any]):
        """Update session activity.

        Args:
            session_id: Session identifier
            action: Action performed
        """
        if session_id in self.user_sessions:
            session = self.user_sessions[session_id]
            session.last_activity = datetime.now()
            session.actions_performed.append(
                {**action, "timestamp": datetime.now().isoformat()}
            )

            # Track document access
            if "document_id" in action:
                doc_id = action["document_id"]
                if doc_id not in session.documents_accessed:
                    session.documents_accessed.append(doc_id)
                session.current_document = doc_id

            self._save_user_data()

    def create_notification(
        self,
        user_id: str,
        message_type: str,
        title: str,
        content: str,
        persistent: bool = False,
        action_required: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationMessage:
        """Create a notification for user.

        Args:
            user_id: User identifier
            message_type: Type of message (info, warning, error, success)
            title: Notification title
            content: Notification content
            persistent: Whether notification persists until dismissed
            action_required: Whether user action is required
            metadata: Optional metadata

        Returns:
            NotificationMessage object
        """
        message_id = f"notification_{user_id}_{int(datetime.now().timestamp())}"

        notification = NotificationMessage(
            message_id=message_id,
            user_id=user_id,
            message_type=message_type,
            title=title,
            content=content,
            timestamp=datetime.now(),
            persistent=persistent,
            action_required=action_required,
            metadata=metadata,
        )

        if user_id not in self.notifications:
            self.notifications[user_id] = []

        self.notifications[user_id].append(notification)
        self._save_user_data()

        logger.info(f"Created {message_type} notification for user {user_id}: {title}")
        return notification

    def get_user_notifications(
        self, user_id: str, unread_only: bool = False
    ) -> List[NotificationMessage]:
        """Get user notifications.

        Args:
            user_id: User identifier
            unread_only: Whether to return only unread notifications

        Returns:
            List of NotificationMessage objects
        """
        notifications = self.notifications.get(user_id, [])

        if unread_only:
            notifications = [n for n in notifications if not n.read]

        # Sort by timestamp (newest first)
        notifications.sort(key=lambda n: n.timestamp, reverse=True)

        return notifications

    def mark_notification_read(self, user_id: str, message_id: str):
        """Mark notification as read.

        Args:
            user_id: User identifier
            message_id: Message identifier
        """
        notifications = self.notifications.get(user_id, [])

        for notification in notifications:
            if notification.message_id == message_id:
                notification.read = True
                self._save_user_data()
                break

    def create_personalized_interface(
        self, user_id: str, interface_type: str = "conflict_resolution"
    ) -> str:
        """Create personalized interface based on user preferences.

        Args:
            user_id: User identifier
            interface_type: Type of interface to create

        Returns:
            HTML string with personalized interface
        """
        prefs = self.get_user_preferences(user_id)

        if interface_type == "conflict_resolution":
            return self._create_personalized_conflict_interface(prefs)
        elif interface_type == "timeline":
            return self._create_personalized_timeline_interface(prefs)
        elif interface_type == "merge":
            return self._create_personalized_merge_interface(prefs)
        else:
            return self._create_default_interface(prefs)

    def get_user_dashboard(self, user_id: str) -> str:
        """Create user dashboard with recent activity and notifications.

        Args:
            user_id: User identifier

        Returns:
            HTML string with dashboard
        """
        prefs = self.get_user_preferences(user_id)
        notifications = self.get_user_notifications(user_id, unread_only=True)

        # Get recent sessions
        recent_sessions = [
            session
            for session in self.user_sessions.values()
            if session.user_id == user_id
        ]
        recent_sessions.sort(key=lambda s: s.last_activity, reverse=True)
        recent_sessions = recent_sessions[:5]  # Last 5 sessions

        html_parts = []

        # Add dashboard CSS
        html_parts.append(self._get_dashboard_css(prefs))

        # Start dashboard
        html_parts.append('<div class="user-dashboard">')

        # Dashboard header
        html_parts.append(self._create_dashboard_header(user_id, prefs))

        # Dashboard content
        html_parts.append('<div class="dashboard-content">')

        # Left column
        html_parts.append('<div class="dashboard-left">')

        # Recent activity
        html_parts.append(self._create_recent_activity_widget(recent_sessions))

        # Document access
        html_parts.append(self._create_document_access_widget(user_id))

        html_parts.append("</div>")

        # Right column
        html_parts.append('<div class="dashboard-right">')

        # Notifications
        html_parts.append(self._create_notifications_widget(notifications))

        # Quick actions
        html_parts.append(self._create_quick_actions_widget(prefs))

        html_parts.append("</div>")

        html_parts.append("</div>")
        html_parts.append("</div>")

        # Add dashboard JavaScript
        html_parts.append(self._get_dashboard_javascript())

        return "".join(html_parts)

    def get_accessibility_interface(self, user_id: str) -> str:
        """Create accessibility-enhanced interface.

        Args:
            user_id: User identifier

        Returns:
            HTML string with accessibility features
        """
        prefs = self.get_user_preferences(user_id)

        html_parts = []

        # Add accessibility CSS
        html_parts.append(self._get_accessibility_css(prefs))

        # Accessibility controls
        html_parts.append(
            """
        <div class="accessibility-controls" role="toolbar" aria-label="Accessibility controls">
            <button class="accessibility-btn" onclick="increaseFontSize()" aria-label="Increase font size">
                A+
            </button>
            <button class="accessibility-btn" onclick="decreaseFontSize()" aria-label="Decrease font size">
                A-
            </button>
            <button class="accessibility-btn" onclick="toggleHighContrast()" aria-label="Toggle high contrast">
                ◐
            </button>
            <button class="accessibility-btn" onclick="toggleScreenReader()" aria-label="Toggle screen reader support">
                🔊
            </button>
        </div>
        """
        )

        # Screen reader announcements
        html_parts.append(
            """
        <div id="sr-announcements" class="sr-only" aria-live="polite" aria-atomic="true">
        </div>
        """
        )

        # Keyboard shortcuts help
        html_parts.append(self._create_keyboard_shortcuts_help())

        # Add accessibility JavaScript
        html_parts.append(self._get_accessibility_javascript())

        return "".join(html_parts)

    def _get_light_theme(self) -> Dict[str, str]:
        """Get light theme configuration."""
        return {
            "background": "#fffff",
            "surface": "#f8f9fa",
            "primary": "#007bf",
            "secondary": "#6c757d",
            "text": "#212529",
            "text_secondary": "#6c757d",
            "border": "#dee2e6",
            "success": "#28a745",
            "warning": "#ffc107",
            "error": "#dc3545",
        }

    def _get_dark_theme(self) -> Dict[str, str]:
        """Get dark theme configuration."""
        return {
            "background": "#1a1a1a",
            "surface": "#2d2d2d",
            "primary": "#4dabf7",
            "secondary": "#868e96",
            "text": "#fffff",
            "text_secondary": "#adb5bd",
            "border": "#495057",
            "success": "#51cf66",
            "warning": "#ffd43b",
            "error": "#ff6b6b",
        }

    def _get_auto_theme(self) -> Dict[str, str]:
        """Get auto theme configuration (detects system preference)."""
        return {
            "background": "var(--bg-color)",
            "surface": "var(--surface-color)",
            "primary": "var(--primary-color)",
            "secondary": "var(--secondary-color)",
            "text": "var(--text-color)",
            "text_secondary": "var(--text-secondary-color)",
            "border": "var(--border-color)",
            "success": "var(--success-color)",
            "warning": "var(--warning-color)",
            "error": "var(--error-color)",
        }

    def _get_keyboard_shortcuts(self) -> Dict[str, str]:
        """Get keyboard shortcuts configuration."""
        return {
            "Ctrl+1": "Take ours resolution",
            "Ctrl+2": "Take theirs resolution",
            "Ctrl+3": "Merge both",
            "Ctrl+S": "Save progress",
            "Ctrl+Z": "Undo",
            "Ctrl+Y": "Redo",
            "Ctrl+F": "Find in document",
            "Ctrl+H": "Show/hide help",
            "Ctrl+Left": "Previous conflict",
            "Ctrl+Right": "Next conflict",
            "Escape": "Cancel current action",
            "Tab": "Navigate to next element",
            "Shift+Tab": "Navigate to previous element",
        }

    def _get_accessibility_features(self) -> Dict[str, Any]:
        """Get accessibility features configuration."""
        return {
            "screen_reader_support": True,
            "high_contrast_mode": True,
            "keyboard_navigation": True,
            "focus_indicators": True,
            "aria_labels": True,
            "skip_links": True,
            "font_size_adjustment": True,
            "motion_reduction": True,
        }

    def _create_personalized_conflict_interface(self, prefs: UserPreferences) -> str:
        """Create personalized conflict resolution interface."""
        theme = self.ui_themes[prefs.theme]

        html_parts = []

        # Theme-specific CSS
        html_parts.append(
            """
        <style>
        :root {{
            --bg-color: {theme["background"]};
            --surface-color: {theme["surface"]};
            --primary-color: {theme["primary"]};
            --text-color: {theme["text"]};
            --border-color: {theme["border"]};
        }}

        .personalized-conflict-interface {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-size: {self._get_font_size_value(prefs.font_size)};
            {"animation: none;" if not prefs.ui_animations else ""}
        }}

        .conflict-panel {{
            background-color: var(--surface-color);
            border: 1px solid var(--border-color);
            {"padding: 10px;" if prefs.compact_view else "padding: 20px;"}
        }}

        .line-numbers {{
            {"display: block;" if prefs.show_line_numbers else "display: none;"}
        }}

        .diff-highlight {{
            {"background-color: rgba(255, 255, 0, 0.3);" if prefs.show_diff_highlights else "background-color: transparent;"}
        }}
        </style>
        """
        )

        # Interface content
        html_parts.append('<div class="personalized-conflict-interface">')

        # Add content based on preferences
        if prefs.conflict_resolution_mode == "split":
            html_parts.append(self._create_split_view_content(prefs))
        elif prefs.conflict_resolution_mode == "inline":
            html_parts.append(self._create_inline_view_content(prefs))
        else:
            html_parts.append(self._create_side_by_side_content(prefs))

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_personalized_timeline_interface(self, prefs: UserPreferences) -> str:
        """Create personalized timeline interface."""
        theme = self.ui_themes[prefs.theme]

        # Similar implementation to conflict interface but for timeline
        return """
        <div class="personalized-timeline" style="
            background-color: {theme["background"]};
            color: {theme["text"]};
            font-size: {self._get_font_size_value(prefs.font_size)};
        ">
            <div class="timeline-content">
                Timeline content adapted to user preferences
            </div>
        </div>
        """

    def _create_personalized_merge_interface(self, prefs: UserPreferences) -> str:
        """Create personalized merge interface."""
        theme = self.ui_themes[prefs.theme]

        # Similar implementation for merge interface
        return """
        <div class="personalized-merge" style="
            background-color: {theme["background"]};
            color: {theme["text"]};
            font-size: {self._get_font_size_value(prefs.font_size)};
        ">
            <div class="merge-content">
                Merge interface adapted to user preferences
            </div>
        </div>
        """

    def _create_default_interface(self, prefs: UserPreferences) -> str:
        """Create default personalized interface."""
        theme = self.ui_themes[prefs.theme]

        return """
        <div class="personalized-interface" style="
            background-color: {theme["background"]};
            color: {theme["text"]};
            font-size: {self._get_font_size_value(prefs.font_size)};
        ">
            <div class="interface-content">
                Default interface adapted to user preferences
            </div>
        </div>
        """

    def _get_font_size_value(self, size: str) -> str:
        """Get font size value."""
        sizes = {"small": "14px", "medium": "16px", "large": "18px"}
        return sizes.get(size, "16px")

    def _get_dashboard_css(self, prefs: UserPreferences) -> str:
        """Get dashboard CSS."""
        theme = self.ui_themes[prefs.theme]

        return """
        <style>
        .user-dashboard {{
            background-color: {theme["background"]};
            color: {theme["text"]};
            font-size: {self._get_font_size_value(prefs.font_size)};
            min-height: 100vh;
            padding: 20px;
        }}

        .dashboard-header {{
            background: linear-gradient(135deg, {theme["primary"]} 0%, {theme["secondary"]} 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}

        .dashboard-content {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }}

        .dashboard-widget {{
            background-color: {theme["surface"]};
            border: 1px solid {theme["border"]};
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}

        .widget-header {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: {theme["text"]};
        }}

        .notification {{
            background-color: {theme["surface"]};
            border-left: 4px solid {theme["primary"]};
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }}

        .notification.warning {{
            border-left-color: {theme["warning"]};
        }}

        .notification.error {{
            border-left-color: {theme["error"]};
        }}

        .notification.success {{
            border-left-color: {theme["success"]};
        }}

        .btn {{
            background-color: {theme["primary"]};
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
            transition: background-color 0.2s ease;
        }}

        .btn:hover {{
            background-color: {theme["secondary"]};
        }}

        @media (max-width: 768px) {{
            .dashboard-content {{
                grid-template-columns: 1fr;
            }}
        }}
        </style>
        """

    def _create_dashboard_header(self, user_id: str, prefs: UserPreferences) -> str:
        """Create dashboard header."""
        return """
        <div class="dashboard-header">
            <h1>Welcome back, {user_id}</h1>
            <p>Your personalized document processing dashboard</p>
        </div>
        """

    def _create_recent_activity_widget(self, sessions: List[UserSession]) -> str:
        """Create recent activity widget."""
        html_parts = []

        html_parts.append('<div class="dashboard-widget">')
        html_parts.append('<div class="widget-header">Recent Activity</div>')

        if sessions:
            html_parts.append('<div class="activity-list">')
            for session in sessions:
                html_parts.append(
                    """
                <div class="activity-item">
                    <div class="activity-time">{session.last_activity.strftime("%m/%d %I:%M %p")}</div>
                    <div class="activity-description">
                        Session with {len(session.documents_accessed)} documents
                    </div>
                </div>
                """
                )
            html_parts.append("</div>")
        else:
            html_parts.append('<div class="empty-state">No recent activity</div>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_document_access_widget(self, user_id: str) -> str:
        """Create document access widget."""
        # Get recently accessed documents
        recent_docs = set()
        for session in self.user_sessions.values():
            if session.user_id == user_id:
                recent_docs.update(session.documents_accessed)

        html_parts = []

        html_parts.append('<div class="dashboard-widget">')
        html_parts.append('<div class="widget-header">Recent Documents</div>')

        if recent_docs:
            html_parts.append('<div class="document-list">')
            for doc_id in list(recent_docs)[:5]:  # Show last 5
                html_parts.append(
                    """
                <div class="document-item">
                    <div class="document-name">{doc_id}</div>
                    <div class="document-actions">
                        <button class="btn btn-small" onclick="openDocument('{doc_id}')">Open</button>
                    </div>
                </div>
                """
                )
            html_parts.append("</div>")
        else:
            html_parts.append('<div class="empty-state">No recent documents</div>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_notifications_widget(
        self, notifications: List[NotificationMessage]
    ) -> str:
        """Create notifications widget."""
        html_parts = []

        html_parts.append('<div class="dashboard-widget">')
        html_parts.append('<div class="widget-header">Notifications</div>')

        if notifications:
            html_parts.append('<div class="notifications-list">')
            for notification in notifications[:5]:  # Show first 5
                html_parts.append(
                    """
                <div class="notification {notification.message_type}">
                    <div class="notification-title">{notification.title}</div>
                    <div class="notification-content">{notification.content}</div>
                    <div class="notification-time">{notification.timestamp.strftime("%I:%M %p")}</div>
                </div>
                """
                )
            html_parts.append("</div>")
        else:
            html_parts.append('<div class="empty-state">No new notifications</div>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_quick_actions_widget(self, prefs: UserPreferences) -> str:
        """Create quick actions widget."""
        return """
        <div class="dashboard-widget">
            <div class="widget-header">Quick Actions</div>
            <div class="quick-actions">
                <button class="btn" onclick="createNewDocument()">New Document</button>
                <button class="btn" onclick="openConflictResolution()">Resolve Conflicts</button>
                <button class="btn" onclick="viewTimeline()">View Timeline</button>
                <button class="btn" onclick="openPreferences()">Preferences</button>
            </div>
        </div>
        """

    def _get_dashboard_javascript(self) -> str:
        """Get dashboard JavaScript."""
        return """
        <script>
        function openDocument(docId) {
            console.log('Opening document:', docId);
            // Implementation would open document
        }

        function createNewDocument() {
            console.log('Creating new document');
            // Implementation would create new document
        }

        function openConflictResolution() {
            console.log('Opening conflict resolution');
            // Implementation would open conflict resolution interface
        }

        function viewTimeline() {
            console.log('Viewing timeline');
            // Implementation would open timeline view
        }

        function openPreferences() {
            console.log('Opening preferences');
            // Implementation would open preferences dialog
        }
        </script>
        """

    def _get_accessibility_css(self, prefs: UserPreferences) -> str:
        """Get accessibility CSS."""
        return """
        <style>
        .accessibility-controls {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .accessibility-btn {
            padding: 8px 12px;
            margin: 0 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 14px;
        }

        .accessibility-btn:hover {
            background: #f0f0f0;
        }

        .accessibility-btn:focus {
            outline: 2px solid #007bff;
            outline-offset: 2px;
        }

        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }

        .high-contrast {
            filter: contrast(150%);
        }

        .large-font {
            font-size: 120%;
        }

        .focus-visible {
            outline: 3px solid #007bff;
            outline-offset: 2px;
        }

        .reduced-motion * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
        </style>
        """

    def _create_keyboard_shortcuts_help(self) -> str:
        """Create keyboard shortcuts help."""
        shortcuts_html = []

        shortcuts_html.append(
            '<div class="keyboard-shortcuts-help" style="display: none;">'
        )
        shortcuts_html.append("<h3>Keyboard Shortcuts</h3>")
        shortcuts_html.append('<div class="shortcuts-grid">')

        for shortcut, description in self.keyboard_shortcuts.items():
            shortcuts_html.append(
                """
            <div class="shortcut-item">
                <kbd>{shortcut}</kbd>
                <span>{description}</span>
            </div>
            """
            )

        shortcuts_html.append("</div>")
        shortcuts_html.append("</div>")

        return "".join(shortcuts_html)

    def _get_accessibility_javascript(self) -> str:
        """Get accessibility JavaScript."""
        return """
        <script>
        function increaseFontSize() {
            document.body.style.fontSize = '120%';
            announceToScreenReader('Font size increased');
        }

        function decreaseFontSize() {
            document.body.style.fontSize = '100%';
            announceToScreenReader('Font size decreased');
        }

        function toggleHighContrast() {
            document.body.classList.toggle('high-contrast');
            announceToScreenReader('High contrast mode toggled');
        }

        function toggleScreenReader() {
            const announcements = document.getElementById('sr-announcements');
            announcements.style.display = announcements.style.display === 'none' ? 'block' : 'none';
            announceToScreenReader('Screen reader support toggled');
        }

        function announceToScreenReader(message) {
            const announcements = document.getElementById('sr-announcements');
            announcements.textContent = message;

            // Clear after announcement
            setTimeout(() => {
                announcements.textContent = '';
            }, 1000);
        }

        // Keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                document.body.classList.add('keyboard-navigation');
            }
        });

        document.addEventListener('mousedown', function() {
            document.body.classList.remove('keyboard-navigation');
        });

        // Auto-detect reduced motion preference
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.body.classList.add('reduced-motion');
        }
        </script>
        """

    def _create_split_view_content(self, prefs: UserPreferences) -> str:
        """Create split view content."""
        return """
        <div class="split-view-container">
            <div class="split-panel left-panel">
                <div class="panel-header">Our Version</div>
                <div class="panel-content">Our content here</div>
            </div>
            <div class="split-panel right-panel">
                <div class="panel-header">Their Version</div>
                <div class="panel-content">Their content here</div>
            </div>
        </div>
        """

    def _create_inline_view_content(self, prefs: UserPreferences) -> str:
        """Create inline view content."""
        return """
        <div class="inline-view-container">
            <div class="inline-content">
                <div class="change-marker added">+ Added content</div>
                <div class="change-marker removed">- Removed content</div>
                <div class="change-marker unchanged">Unchanged content</div>
            </div>
        </div>
        """

    def _create_side_by_side_content(self, prefs: UserPreferences) -> str:
        """Create side by side content."""
        return """
        <div class="side-by-side-container">
            <div class="side-panel">
                <div class="panel-title">Before</div>
                <div class="panel-content">Before content</div>
            </div>
            <div class="side-panel">
                <div class="panel-title">After</div>
                <div class="panel-content">After content</div>
            </div>
        </div>
        """

    def _load_user_data(self):
        """Load user data from storage."""
        try:
            # Load user preferences
            prefs_file = self.storage_path / "user_preferences.json"
            if prefs_file.exists():
                with open(prefs_file, "r") as f:
                    prefs_data = json.load(f)
                    for user_id, pref_data in prefs_data.items():
                        self.user_preferences[user_id] = UserPreferences(**pref_data)

            # Load user sessions
            sessions_file = self.storage_path / "user_sessions.json"
            if sessions_file.exists():
                with open(sessions_file, "r") as f:
                    sessions_data = json.load(f)
                    for session_id, session_data in sessions_data.items():
                        # Convert timestamp strings back to datetime
                        session_data["start_time"] = datetime.fromisoformat(
                            session_data["start_time"]
                        )
                        session_data["last_activity"] = datetime.fromisoformat(
                            session_data["last_activity"]
                        )

                        self.user_sessions[session_id] = UserSession(**session_data)

            # Load notifications
            notifications_file = self.storage_path / "notifications.json"
            if notifications_file.exists():
                with open(notifications_file, "r") as f:
                    notifications_data = json.load(f)
                    for user_id, user_notifications in notifications_data.items():
                        self.notifications[user_id] = []
                        for notif_data in user_notifications:
                            # Convert timestamp strings back to datetime
                            notif_data["timestamp"] = datetime.fromisoformat(
                                notif_data["timestamp"]
                            )

                            self.notifications[user_id].append(
                                NotificationMessage(**notif_data)
                            )

            logger.info("Loaded user data from storage")

        except Exception as e:
            logger.error(f"Failed to load user data: {e}")

    def _save_user_data(self):
        """Save user data to storage."""
        try:
            # Save user preferences
            prefs_file = self.storage_path / "user_preferences.json"
            with open(prefs_file, "w") as f:
                prefs_data = {
                    uid: prefs.to_dict() for uid, prefs in self.user_preferences.items()
                }
                json.dump(prefs_data, f, indent=2)

            # Save user sessions
            sessions_file = self.storage_path / "user_sessions.json"
            with open(sessions_file, "w") as f:
                sessions_data = {
                    sid: session.to_dict()
                    for sid, session in self.user_sessions.items()
                }
                json.dump(sessions_data, f, indent=2)

            # Save notifications
            notifications_file = self.storage_path / "notifications.json"
            with open(notifications_file, "w") as f:
                notifications_data = {
                    uid: [notif.to_dict() for notif in notifications]
                    for uid, notifications in self.notifications.items()
                }
                json.dump(notifications_data, f, indent=2)

            logger.debug("Saved user data to storage")

        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
