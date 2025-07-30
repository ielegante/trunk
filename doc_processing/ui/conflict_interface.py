"""Split-screen conflict resolution interface for document merging."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..converters.conflict_resolver import (
    ConflictRegion,
    ConflictResolution,
    ConflictResolver,
)
from ..converters.diff_visualizer import DocumentDiffVisualizer
from ..converters.google_docs import GoogleDocsConverter

logger = logging.getLogger(__name__)


@dataclass
class ConflictUIState:
    """State management for conflict resolution UI."""

    current_conflict_index: int = 0
    total_conflicts: int = 0
    resolved_conflicts: int = 0
    ui_mode: str = "split"  # split, inline, comparison
    show_base_content: bool = True
    auto_save_enabled: bool = True
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class ConflictAction:
    """Represents a user action on a conflict."""

    action_id: str
    conflict_id: str
    action_type: str  # take_ours, take_theirs, merge, custom
    action_data: Dict[str, Any]
    timestamp: str
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class SplitScreenConflictInterface:
    """Interactive split-screen interface for resolving document conflicts."""

    def __init__(
        self,
        conflict_resolver: Optional[ConflictResolver] = None,
        diff_visualizer: Optional[DocumentDiffVisualizer] = None,
        auto_save_interval: int = 30,
    ):
        """Initialize conflict resolution interface.

        Args:
            conflict_resolver: ConflictResolver instance
            diff_visualizer: DocumentDiffVisualizer instance
            auto_save_interval: Auto-save interval in seconds
        """
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.diff_visualizer = diff_visualizer or DocumentDiffVisualizer()
        self.auto_save_interval = auto_save_interval

        # UI state management
        self.ui_state = ConflictUIState()
        self.action_history: List[ConflictAction] = []
        self.current_conflicts: List[ConflictRegion] = []
        self.resolved_content: Dict[str, str] = {}

        # Session management
        self.session_storage_path: Optional[Path] = None
        self.last_auto_save = time.time()

    def initialize_session(
        self,
        conflicts: List[ConflictRegion],
        session_id: Optional[str] = None,
        storage_path: Optional[Path] = None,
    ) -> str:
        """Initialize a new conflict resolution session.

        Args:
            conflicts: List of conflicts to resolve
            session_id: Optional session identifier
            storage_path: Optional path for session storage

        Returns:
            Session ID
        """
        if not session_id:
            session_id = f"conflict_session_{int(time.time())}"

        self.ui_state.session_id = session_id
        self.ui_state.total_conflicts = len(conflicts)
        self.ui_state.resolved_conflicts = 0
        self.ui_state.current_conflict_index = 0

        self.current_conflicts = conflicts
        self.action_history = []
        self.resolved_content = {}

        if storage_path:
            self.session_storage_path = storage_path
            self.session_storage_path.mkdir(parents=True, exist_ok=True)

        # Save initial session state
        self._save_session_state()

        logger.info(
            f"Initialized conflict resolution session {session_id} with {len(conflicts)} conflicts"
        )
        return session_id

    def create_split_screen_interface(
        self, conflict: ConflictRegion, include_base: bool = True
    ) -> str:
        """Create HTML split-screen interface for a single conflict.

        Args:
            conflict: Conflict to display
            include_base: Whether to include base content panel

        Returns:
            HTML interface string
        """
        html_parts = []

        # Add comprehensive CSS for split-screen interface
        html_parts.append(self._get_split_screen_css())

        # Start interface container
        html_parts.append('<div id="conflict-interface" class="conflict-interface">')

        # Add header with conflict info and navigation
        html_parts.append(self._create_interface_header(conflict))

        # Add toolbar with actions
        html_parts.append(self._create_interface_toolbar(conflict))

        # Create main content area
        html_parts.append('<div class="conflict-content">')

        if include_base and conflict.base_content:
            # Three-panel layout with base content
            html_parts.append(self._create_three_panel_layout(conflict))
        else:
            # Two-panel layout (ours vs theirs)
            html_parts.append(self._create_two_panel_layout(conflict))

        html_parts.append("</div>")

        # Add resolution area
        html_parts.append(self._create_resolution_area(conflict))

        # Add status and progress area
        html_parts.append(self._create_status_area())

        # End interface container
        html_parts.append("</div>")

        # Add JavaScript for interactive functionality
        html_parts.append(self._get_split_screen_javascript())

        return "".join(html_parts)

    def create_batch_interface(self, conflicts: List[ConflictRegion]) -> str:
        """Create batch processing interface for multiple conflicts.

        Args:
            conflicts: List of conflicts to process

        Returns:
            HTML interface string
        """
        html_parts = []

        # Add CSS
        html_parts.append(self._get_batch_interface_css())

        # Start container
        html_parts.append('<div id="batch-interface" class="batch-interface">')

        # Add header
        html_parts.append(
            """
        <div class="batch-header">
            <h1>Batch Conflict Resolution</h1>
            <div class="batch-stats">
                <span class="stat">Total Conflicts: {len(conflicts)}</span>
                <span class="stat">Resolved: <span id="resolved-count">0</span></span>
                <span class="stat">Remaining: <span id="remaining-count">{len(conflicts)}</span></span>
            </div>
        </div>
        """
        )

        # Add batch actions toolbar
        html_parts.append(self._create_batch_toolbar())

        # Add conflicts list
        html_parts.append('<div class="conflicts-list">')

        for i, conflict in enumerate(conflicts):
            html_parts.append(self._create_conflict_preview(conflict, i))

        html_parts.append("</div>")

        # Add batch resolution area
        html_parts.append(self._create_batch_resolution_area())

        # End container
        html_parts.append("</div>")

        # Add JavaScript
        html_parts.append(self._get_batch_interface_javascript())

        return "".join(html_parts)

    def handle_conflict_action(
        self,
        conflict_id: str,
        action_type: str,
        action_data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> ConflictAction:
        """Handle a user action on a conflict.

        Args:
            conflict_id: ID of the conflict
            action_type: Type of action (take_ours, take_theirs, merge, custom)
            action_data: Additional action data
            user_id: Optional user identifier

        Returns:
            ConflictAction representing the action taken
        """
        action_id = f"action_{conflict_id}_{int(time.time())}"

        action = ConflictAction(
            action_id=action_id,
            conflict_id=conflict_id,
            action_type=action_type,
            action_data=action_data,
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
        )

        # Find the conflict
        conflict = None
        for c in self.current_conflicts:
            if c.conflict_id == conflict_id:
                conflict = c
                break

        if not conflict:
            raise ValueError(f"Conflict {conflict_id} not found")

        # Apply the action
        if action_type == "take_ours":
            conflict.resolution_content = conflict.our_content
            conflict.resolution_status = "resolved"
        elif action_type == "take_theirs":
            conflict.resolution_content = conflict.their_content
            conflict.resolution_status = "resolved"
        elif action_type == "merge":
            conflict.resolution_content = (
                f"{conflict.our_content}\n\n{conflict.their_content}"
            )
            conflict.resolution_status = "resolved"
        elif action_type == "custom":
            conflict.resolution_content = action_data.get("custom_content", "")
            conflict.resolution_status = "resolved"
        else:
            raise ValueError(f"Unknown action type: {action_type}")

        # Update metadata
        conflict.resolution_timestamp = datetime.now().isoformat()
        conflict.resolver = user_id

        # Add to action history
        self.action_history.append(action)

        # Update UI state
        self._update_resolution_progress()

        # Auto-save if enabled
        if self.ui_state.auto_save_enabled:
            self._auto_save_if_needed()

        logger.info(f"Applied action {action_type} to conflict {conflict_id}")
        return action

    def navigate_to_conflict(self, index: int) -> Optional[ConflictRegion]:
        """Navigate to a specific conflict by index.

        Args:
            index: Index of conflict to navigate to

        Returns:
            ConflictRegion if found, None otherwise
        """
        if 0 <= index < len(self.current_conflicts):
            self.ui_state.current_conflict_index = index
            self._save_session_state()
            return self.current_conflicts[index]
        return None

    def get_next_unresolved_conflict(self) -> Optional[Tuple[int, ConflictRegion]]:
        """Get the next unresolved conflict.

        Returns:
            Tuple of (index, conflict) if found, None otherwise
        """
        for i, conflict in enumerate(self.current_conflicts):
            if conflict.resolution_status == "pending":
                return i, conflict
        return None

    def export_resolution_session(self, output_path: Path) -> Dict[str, Any]:
        """Export the current resolution session.

        Args:
            output_path: Path to export session data

        Returns:
            Dictionary with session export data
        """
        session_data = {
            "session_id": self.ui_state.session_id,
            "ui_state": self.ui_state.to_dict(),
            "conflicts": [conflict.to_dict() for conflict in self.current_conflicts],
            "action_history": [action.to_dict() for action in self.action_history],
            "resolved_content": self.resolved_content,
            "export_timestamp": datetime.now().isoformat(),
        }

        # Save to file
        export_file = output_path / f"conflict_session_{self.ui_state.session_id}.json"
        with open(export_file, "w") as f:
            json.dump(session_data, f, indent=2)

        logger.info(f"Exported resolution session to {export_file}")
        return session_data

    def _get_split_screen_css(self) -> str:
        """Get CSS for split-screen interface."""
        return """
        <style>
        .conflict-interface {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 100%;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
            min-height: 100vh;
        }

        .interface-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
        }

        .conflict-title {
            font-size: 24px;
            font-weight: 600;
            margin: 0;
        }

        .conflict-meta {
            font-size: 14px;
            opacity: 0.9;
            margin-top: 8px;
        }

        .progress-info {
            text-align: right;
            font-size: 14px;
        }

        .progress-bar {
            width: 200px;
            height: 6px;
            background-color: rgba(255,255,255,0.3);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.3s ease;
        }

        .interface-toolbar {
            background-color: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            padding: 15px 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .toolbar-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
        }

        .toolbar-section {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary {
            background-color: #007bff;
            color: white;
        }

        .btn-primary:hover {
            background-color: #0056b3;
            transform: translateY(-1px);
        }

        .btn-success {
            background-color: #28a745;
            color: white;
        }

        .btn-success:hover {
            background-color: #1e7e34;
            transform: translateY(-1px);
        }

        .btn-warning {
            background-color: #ffc107;
            color: #212529;
        }

        .btn-warning:hover {
            background-color: #d39e00;
            transform: translateY(-1px);
        }

        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background-color: #545b62;
            transform: translateY(-1px);
        }

        .btn-outline {
            background-color: transparent;
            color: #007bff;
            border: 2px solid #007bff;
        }

        .btn-outline:hover {
            background-color: #007bff;
            color: white;
        }

        .conflict-content {
            display: flex;
            gap: 20px;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
            min-height: 500px;
        }

        .content-panel {
            flex: 1;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .panel-header {
            background-color: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-header.ours {
            border-left: 4px solid #007bff;
        }

        .panel-header.theirs {
            border-left: 4px solid #28a745;
        }

        .panel-header.base {
            border-left: 4px solid #6c757d;
        }

        .panel-content {
            padding: 20px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            background-color: #fafafa;
        }

        .resolution-area {
            background-color: white;
            margin: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 1200px;
            margin: 20px auto;
        }

        .resolution-header {
            background-color: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 600;
        }

        .resolution-content {
            padding: 20px;
        }

        .resolution-textarea {
            width: 100%;
            min-height: 150px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            transition: border-color 0.2s ease;
        }

        .resolution-textarea:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
        }

        .resolution-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            justify-content: flex-end;
        }

        .status-area {
            background-color: white;
            margin: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 1200px;
            margin: 20px auto;
        }

        .status-content {
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .status-info {
            display: flex;
            gap: 30px;
        }

        .status-item {
            text-align: center;
        }

        .status-value {
            font-size: 24px;
            font-weight: 600;
            color: #007bff;
        }

        .status-label {
            font-size: 14px;
            color: #6c757d;
            margin-top: 5px;
        }

        .navigation-controls {
            display: flex;
            gap: 10px;
        }

        .diff-highlight {
            background-color: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
        }

        .diff-added {
            background-color: #d4edda;
            color: #155724;
        }

        .diff-removed {
            background-color: #f8d7da;
            color: #721c24;
            text-decoration: line-through;
        }

        @media (max-width: 768px) {
            .conflict-content {
                flex-direction: column;
            }

            .header-content {
                flex-direction: column;
                text-align: center;
                gap: 15px;
            }

            .toolbar-content {
                flex-direction: column;
                gap: 15px;
            }
        }
        </style>
        """

    def _create_interface_header(self, conflict: ConflictRegion) -> str:
        """Create interface header with conflict information."""
        progress_percentage = (
            (self.ui_state.resolved_conflicts / self.ui_state.total_conflicts) * 100
            if self.ui_state.total_conflicts > 0
            else 0
        )

        return """
        <div class="interface-header">
            <div class="header-content">
                <div class="conflict-info">
                    <h1 class="conflict-title">Conflict Resolution</h1>
                    <div class="conflict-meta">
                        {conflict.conflict_type.title()} conflict in lines {conflict.start_line}-{conflict.end_line}
                        | ID: {conflict.conflict_id}
                    </div>
                </div>
                <div class="progress-info">
                    <div>Progress: {self.ui_state.resolved_conflicts}/{self.ui_state.total_conflicts} resolved</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {progress_percentage}%"></div>
                    </div>
                </div>
            </div>
        </div>
        """

    def _create_interface_toolbar(self, conflict: ConflictRegion) -> str:
        """Create interface toolbar with actions."""
        return """
        <div class="interface-toolbar">
            <div class="toolbar-content">
                <div class="toolbar-section">
                    <button class="btn btn-primary" onclick="takeOurs()">
                        ✓ Take Ours
                    </button>
                    <button class="btn btn-success" onclick="takeTheirs()">
                        ✓ Take Theirs
                    </button>
                    <button class="btn btn-warning" onclick="mergeContent()">
                        ⚡ Merge Both
                    </button>
                    <button class="btn btn-outline" onclick="toggleCustomResolution()">
                        ✏️ Custom Resolution
                    </button>
                </div>
                <div class="toolbar-section">
                    <button class="btn btn-secondary" onclick="previousConflict()">
                        ← Previous
                    </button>
                    <button class="btn btn-secondary" onclick="nextConflict()">
                        Next →
                    </button>
                    <button class="btn btn-outline" onclick="saveSession()">
                        💾 Save Session
                    </button>
                </div>
            </div>
        </div>
        """

    def _create_three_panel_layout(self, conflict: ConflictRegion) -> str:
        """Create three-panel layout with base content."""
        return """
        <div class="content-panel">
            <div class="panel-header base">
                <span>Base Content</span>
                <small>Original version</small>
            </div>
            <div class="panel-content">{self._escape_html(conflict.base_content)}</div>
        </div>

        <div class="content-panel">
            <div class="panel-header ours">
                <span>Our Version</span>
                <small>{conflict.metadata.get('our_label', 'Our changes')}</small>
            </div>
            <div class="panel-content">{self._escape_html(conflict.our_content)}</div>
        </div>

        <div class="content-panel">
            <div class="panel-header theirs">
                <span>Their Version</span>
                <small>{conflict.metadata.get('their_label', 'Their changes')}</small>
            </div>
            <div class="panel-content">{self._escape_html(conflict.their_content)}</div>
        </div>
        """

    def _create_two_panel_layout(self, conflict: ConflictRegion) -> str:
        """Create two-panel layout (ours vs theirs)."""
        return """
        <div class="content-panel">
            <div class="panel-header ours">
                <span>Our Version</span>
                <small>{conflict.metadata.get('our_label', 'Our changes')}</small>
            </div>
            <div class="panel-content">{self._escape_html(conflict.our_content)}</div>
        </div>

        <div class="content-panel">
            <div class="panel-header theirs">
                <span>Their Version</span>
                <small>{conflict.metadata.get('their_label', 'Their changes')}</small>
            </div>
            <div class="panel-content">{self._escape_html(conflict.their_content)}</div>
        </div>
        """

    def _create_resolution_area(self, conflict: ConflictRegion) -> str:
        """Create resolution area for custom resolution."""
        return """
        <div class="resolution-area" id="resolution-area" style="display: none;">
            <div class="resolution-header">
                Custom Resolution
            </div>
            <div class="resolution-content">
                <textarea
                    class="resolution-textarea"
                    id="resolution-textarea"
                    placeholder="Enter your custom resolution here..."
                ></textarea>
                <div class="resolution-actions">
                    <button class="btn btn-secondary" onclick="cancelCustomResolution()">
                        Cancel
                    </button>
                    <button class="btn btn-primary" onclick="applyCustomResolution()">
                        Apply Resolution
                    </button>
                </div>
            </div>
        </div>
        """

    def _create_status_area(self) -> str:
        """Create status area with progress information."""
        return """
        <div class="status-area">
            <div class="status-content">
                <div class="status-info">
                    <div class="status-item">
                        <div class="status-value" id="current-conflict">{self.ui_state.current_conflict_index + 1}</div>
                        <div class="status-label">Current Conflict</div>
                    </div>
                    <div class="status-item">
                        <div class="status-value" id="total-conflicts">{self.ui_state.total_conflicts}</div>
                        <div class="status-label">Total Conflicts</div>
                    </div>
                    <div class="status-item">
                        <div class="status-value" id="resolved-conflicts">{self.ui_state.resolved_conflicts}</div>
                        <div class="status-label">Resolved</div>
                    </div>
                    <div class="status-item">
                        <div class="status-value" id="remaining-conflicts">{self.ui_state.total_conflicts - self.ui_state.resolved_conflicts}</div>
                        <div class="status-label">Remaining</div>
                    </div>
                </div>
                <div class="navigation-controls">
                    <button class="btn btn-outline" onclick="goToConflict()">
                        🔍 Go to Conflict
                    </button>
                    <button class="btn btn-outline" onclick="showConflictList()">
                        📋 Show All Conflicts
                    </button>
                </div>
            </div>
        </div>
        """

    def _get_split_screen_javascript(self) -> str:
        """Get JavaScript for split-screen interface."""
        return """
        <script>
        class ConflictInterface {
            constructor() {
                this.currentConflictId = null;
                this.customResolutionVisible = false;
                this.autoSaveEnabled = true;
                this.autoSaveInterval = 30000; // 30 seconds

                this.initializeInterface();
            }

            initializeInterface() {
                // Set up auto-save if enabled
                if (this.autoSaveEnabled) {
                    setInterval(() => this.autoSave(), this.autoSaveInterval);
                }

                // Set up keyboard shortcuts
                document.addEventListener('keydown', (e) => this.handleKeyboard(e));

                // Set up before unload warning
                window.addEventListener('beforeunload', (e) => this.handleBeforeUnload(e));

                console.log('Conflict interface initialized');
            }

            handleKeyboard(event) {
                if (event.ctrlKey || event.metaKey) {
                    switch(event.key) {
                        case '1':
                            event.preventDefault();
                            this.takeOurs();
                            break;
                        case '2':
                            event.preventDefault();
                            this.takeTheirs();
                            break;
                        case '3':
                            event.preventDefault();
                            this.mergeContent();
                            break;
                        case 'ArrowLeft':
                            event.preventDefault();
                            this.previousConflict();
                            break;
                        case 'ArrowRight':
                            event.preventDefault();
                            this.nextConflict();
                            break;
                        case 's':
                            event.preventDefault();
                            this.saveSession();
                            break;
                    }
                }
            }

            handleBeforeUnload(event) {
                // Check if there are unsaved changes
                const unresolvedCount = document.getElementById('remaining-conflicts').textContent;
                if (parseInt(unresolvedCount) > 0) {
                    event.preventDefault();
                    event.returnValue = 'You have unresolved conflicts. Are you sure you want to leave?';
                }
            }

            autoSave() {
                if (this.autoSaveEnabled) {
                    console.log('Auto-saving session...');
                    // Implementation would send current state to server
                }
            }
        }

        // Initialize interface
        const conflictInterface = new ConflictInterface();

        // Action handlers
        function takeOurs() {
            console.log('Taking ours');
            // Implementation would call server endpoint
            conflictInterface.applyAction('take_ours');
        }

        function takeTheirs() {
            console.log('Taking theirs');
            // Implementation would call server endpoint
            conflictInterface.applyAction('take_theirs');
        }

        function mergeContent() {
            console.log('Merging content');
            // Implementation would call server endpoint
            conflictInterface.applyAction('merge');
        }

        function toggleCustomResolution() {
            const resolutionArea = document.getElementById('resolution-area');
            const isVisible = resolutionArea.style.display !== 'none';

            if (isVisible) {
                resolutionArea.style.display = 'none';
                conflictInterface.customResolutionVisible = false;
            } else {
                resolutionArea.style.display = 'block';
                conflictInterface.customResolutionVisible = true;
                document.getElementById('resolution-textarea').focus();
            }
        }

        function cancelCustomResolution() {
            document.getElementById('resolution-area').style.display = 'none';
            document.getElementById('resolution-textarea').value = '';
            conflictInterface.customResolutionVisible = false;
        }

        function applyCustomResolution() {
            const customContent = document.getElementById('resolution-textarea').value;
            if (customContent.trim()) {
                console.log('Applying custom resolution:', customContent);
                // Implementation would call server endpoint
                conflictInterface.applyAction('custom', { custom_content: customContent });
                cancelCustomResolution();
            } else {
                alert('Please enter custom resolution content');
            }
        }

        function previousConflict() {
            console.log('Previous conflict');
            // Implementation would navigate to previous conflict
        }

        function nextConflict() {
            console.log('Next conflict');
            // Implementation would navigate to next conflict
        }

        function saveSession() {
            console.log('Saving session');
            // Implementation would save current session state
        }

        function goToConflict() {
            const conflictNumber = prompt('Enter conflict number to navigate to:');
            if (conflictNumber) {
                const index = parseInt(conflictNumber) - 1;
                if (index >= 0) {
                    console.log('Navigating to conflict:', index);
                    // Implementation would navigate to specified conflict
                }
            }
        }

        function showConflictList() {
            console.log('Showing conflict list');
            // Implementation would show overview of all conflicts
        }

        // Extend ConflictInterface with action handling
        ConflictInterface.prototype.applyAction = function(actionType, actionData = {}) {
            // Update UI state
            this.updateResolutionProgress();

            // Show success feedback
            this.showActionFeedback(actionType);

            // Auto-advance to next conflict if available
            if (this.shouldAutoAdvance()) {
                setTimeout(() => this.nextConflict(), 1000);
            }
        };

        ConflictInterface.prototype.updateResolutionProgress = function() {
            // Update progress indicators
            const resolvedCount = document.getElementById('resolved-conflicts');
            const remainingCount = document.getElementById('remaining-conflicts');

            const resolved = parseInt(resolvedCount.textContent) + 1;
            const remaining = parseInt(remainingCount.textContent) - 1;

            resolvedCount.textContent = resolved;
            remainingCount.textContent = remaining;

            // Update progress bar
            const progressFill = document.querySelector('.progress-fill');
            const totalConflicts = parseInt(document.getElementById('total-conflicts').textContent);
            const progressPercentage = (resolved / totalConflicts) * 100;
            progressFill.style.width = progressPercentage + '%';
        };

        ConflictInterface.prototype.showActionFeedback = function(actionType) {
            // Show temporary success message
            const feedback = document.createElement('div');
            feedback.className = 'action-feedback';
            feedback.textContent = `Resolution applied: ${actionType.replace('_', ' ').toUpperCase()}`;
            feedback.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                padding: 15px 20px;
                border-radius: 6px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                animation: slideIn 0.3s ease;
            `;

            document.body.appendChild(feedback);

            setTimeout(() => {
                feedback.remove();
            }, 3000);
        };

        ConflictInterface.prototype.shouldAutoAdvance = function() {
            // Check if there are more conflicts and auto-advance is enabled
            const remaining = parseInt(document.getElementById('remaining-conflicts').textContent);
            return remaining > 0;
        };

        // Add CSS for action feedback animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
        </script>
        """

    def _get_batch_interface_css(self) -> str:
        """Get CSS for batch interface."""
        return """
        <style>
        .batch-interface {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }

        .batch-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }

        .batch-stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 20px;
        }

        .stat {
            font-size: 18px;
            font-weight: 500;
        }

        .conflicts-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .conflict-preview {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s ease;
        }

        .conflict-preview:hover {
            transform: translateY(-2px);
        }

        .conflict-preview.resolved {
            border-left: 4px solid #28a745;
        }

        .conflict-preview.pending {
            border-left: 4px solid #ffc107;
        }

        .preview-header {
            background-color: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #e0e0e0;
        }

        .preview-title {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .preview-meta {
            font-size: 14px;
            color: #6c757d;
        }

        .preview-content {
            padding: 15px;
            font-size: 14px;
            max-height: 100px;
            overflow: hidden;
        }

        .preview-actions {
            padding: 10px 15px;
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }

        .btn-small {
            padding: 5px 10px;
            font-size: 12px;
        }
        </style>
        """

    def _create_batch_toolbar(self) -> str:
        """Create batch operations toolbar."""
        return """
        <div class="batch-toolbar">
            <div class="toolbar-actions">
                <button class="btn btn-primary" onclick="resolveAllWithOurs()">
                    Resolve All with Ours
                </button>
                <button class="btn btn-success" onclick="resolveAllWithTheirs()">
                    Resolve All with Theirs
                </button>
                <button class="btn btn-warning" onclick="mergeAllConflicts()">
                    Merge All Conflicts
                </button>
                <button class="btn btn-secondary" onclick="exportResolutions()">
                    Export Resolutions
                </button>
            </div>
        </div>
        """

    def _create_conflict_preview(self, conflict: ConflictRegion, index: int) -> str:
        """Create preview card for a conflict."""
        status_class = (
            "resolved" if conflict.resolution_status == "resolved" else "pending"
        )

        return """
        <div class="conflict-preview {status_class}" data-conflict-id="{conflict.conflict_id}">
            <div class="preview-header">
                <div class="preview-title">Conflict #{index + 1}: {conflict.conflict_type.title()}</div>
                <div class="preview-meta">
                    Lines {conflict.start_line}-{conflict.end_line} |
                    Status: {conflict.resolution_status.title()}
                </div>
            </div>
            <div class="preview-content">
                <strong>Ours:</strong> {self._escape_html(conflict.our_content[:50])}...<br>
                <strong>Theirs:</strong> {self._escape_html(conflict.their_content[:50])}...
            </div>
            <div class="preview-actions">
                <button class="btn btn-primary btn-small" onclick="openConflict('{conflict.conflict_id}')">
                    Resolve
                </button>
                <button class="btn btn-outline btn-small" onclick="viewConflict('{conflict.conflict_id}')">
                    View
                </button>
            </div>
        </div>
        """

    def _create_batch_resolution_area(self) -> str:
        """Create batch resolution area."""
        return """
        <div class="batch-resolution-area">
            <div class="resolution-summary">
                <h3>Resolution Summary</h3>
                <div id="resolution-results"></div>
            </div>
        </div>
        """

    def _get_batch_interface_javascript(self) -> str:
        """Get JavaScript for batch interface."""
        return """
        <script>
        function resolveAllWithOurs() {
            console.log('Resolving all conflicts with ours');
            // Implementation would batch resolve all conflicts
        }

        function resolveAllWithTheirs() {
            console.log('Resolving all conflicts with theirs');
            // Implementation would batch resolve all conflicts
        }

        function mergeAllConflicts() {
            console.log('Merging all conflicts');
            // Implementation would batch merge all conflicts
        }

        function exportResolutions() {
            console.log('Exporting resolutions');
            // Implementation would export resolution data
        }

        function openConflict(conflictId) {
            console.log('Opening conflict:', conflictId);
            // Implementation would open detailed conflict view
        }

        function viewConflict(conflictId) {
            console.log('Viewing conflict:', conflictId);
            // Implementation would show conflict details
        }
        </script>
        """

    def _create_batch_resolution_area(self) -> str:
        """Create batch resolution area."""
        return """
        <div class="batch-resolution-area">
            <div class="resolution-summary">
                <h3>Resolution Summary</h3>
                <div id="resolution-results"></div>
            </div>
        </div>
        """

    def _update_resolution_progress(self):
        """Update resolution progress tracking."""
        resolved_count = sum(
            1 for c in self.current_conflicts if c.resolution_status == "resolved"
        )
        self.ui_state.resolved_conflicts = resolved_count

    def _auto_save_if_needed(self):
        """Auto-save session if interval has passed."""
        current_time = time.time()
        if current_time - self.last_auto_save >= self.auto_save_interval:
            self._save_session_state()
            self.last_auto_save = current_time

    def _save_session_state(self):
        """Save current session state."""
        if self.session_storage_path:
            session_file = (
                self.session_storage_path / f"session_{self.ui_state.session_id}.json"
            )
            session_data = {
                "ui_state": self.ui_state.to_dict(),
                "conflicts": [c.to_dict() for c in self.current_conflicts],
                "action_history": [a.to_dict() for a in self.action_history],
                "last_saved": datetime.now().isoformat(),
            }

            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2)

    def _escape_html(self, text: str) -> str:
        """Escape HTML characters in text."""
        import html

        return html.escape(str(text))
