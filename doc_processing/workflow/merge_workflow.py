"""Merge workflow system for parallel document branches."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..converters.conflict_resolver import (
    ConflictRegion,
    ConflictResolution,
    ConflictResolver,
)
from ..converters.diff_visualizer import DocumentDiffVisualizer
from ..converters.google_docs import GoogleDocsConverter
from ..ui.conflict_interface import SplitScreenConflictInterface

logger = logging.getLogger(__name__)


@dataclass
class BranchInfo:
    """Information about a document branch."""

    branch_id: str
    branch_name: str
    document_id: str
    parent_branch: Optional[str] = None
    created_timestamp: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    author: Optional[str] = None
    description: Optional[str] = None
    commit_count: int = 0
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.created_timestamp:
            data["created_timestamp"] = self.created_timestamp.isoformat()
        if self.last_modified:
            data["last_modified"] = self.last_modified.isoformat()
        return data


@dataclass
class MergeRequest:
    """Represents a merge request between branches."""

    merge_id: str
    source_branch: str
    target_branch: str
    document_id: str
    requestor: str
    created_timestamp: datetime
    title: str
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed, cancelled
    conflicts: List[ConflictRegion] = None
    resolution: Optional[ConflictResolution] = None
    reviewers: List[str] = None
    auto_merge: bool = False

    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.reviewers is None:
            self.reviewers = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["created_timestamp"] = self.created_timestamp.isoformat()
        data["conflicts"] = [c.to_dict() for c in self.conflicts]
        if self.resolution:
            data["resolution"] = self.resolution.to_dict()
        return data


@dataclass
class MergeStrategy:
    """Configuration for merge strategy."""

    strategy_type: str  # 'three_way', 'two_way', 'fast_forward', 'recursive'
    conflict_resolution: str = "manual"  # manual, auto_ours, auto_theirs, auto_merge
    preserve_history: bool = True
    create_merge_commit: bool = True
    squash_commits: bool = False
    delete_source_branch: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class MergeResult:
    """Result of a merge operation."""

    merge_id: str
    source_branch: str
    target_branch: str
    result_branch: str
    status: str  # success, failed, conflicts
    conflicts_count: int
    resolved_conflicts: int
    merge_timestamp: datetime
    merged_by: str
    merge_strategy: MergeStrategy
    performance_metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["merge_timestamp"] = self.merge_timestamp.isoformat()
        data["merge_strategy"] = self.merge_strategy.to_dict()
        return data


class DocumentMergeWorkflow:
    """Manages merge workflows for parallel document branches."""

    def __init__(
        self,
        converter: Optional[GoogleDocsConverter] = None,
        conflict_resolver: Optional[ConflictResolver] = None,
        diff_visualizer: Optional[DocumentDiffVisualizer] = None,
        storage_path: Optional[Path] = None,
    ):
        """Initialize merge workflow manager.

        Args:
            converter: GoogleDocsConverter instance
            conflict_resolver: ConflictResolver instance
            diff_visualizer: DocumentDiffVisualizer instance
            storage_path: Path for storing workflow data
        """
        self.converter = converter or GoogleDocsConverter({})
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.diff_visualizer = diff_visualizer or DocumentDiffVisualizer()
        self.storage_path = storage_path or Path("merge_workflows")

        # Initialize storage
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Workflow state
        self.branches: Dict[str, BranchInfo] = {}
        self.merge_requests: Dict[str, MergeRequest] = {}
        self.merge_results: Dict[str, MergeResult] = {}

        # Configuration
        self.default_merge_strategy = MergeStrategy(
            strategy_type="three_way",
            conflict_resolution="manual",
            preserve_history=True,
            create_merge_commit=True,
        )

        # Load existing data
        self._load_workflow_data()

    def create_branch(
        self,
        branch_name: str,
        document_id: str,
        parent_branch: Optional[str] = None,
        author: Optional[str] = None,
        description: Optional[str] = None,
    ) -> BranchInfo:
        """Create a new document branch.

        Args:
            branch_name: Name of the new branch
            document_id: Document identifier
            parent_branch: Optional parent branch ID
            author: Branch creator
            description: Branch description

        Returns:
            BranchInfo for the created branch
        """
        branch_id = f"branch_{document_id}_{branch_name}_{int(time.time())}"

        branch_info = BranchInfo(
            branch_id=branch_id,
            branch_name=branch_name,
            document_id=document_id,
            parent_branch=parent_branch,
            created_timestamp=datetime.now(),
            last_modified=datetime.now(),
            author=author,
            description=description,
            commit_count=0,
            is_active=True,
        )

        self.branches[branch_id] = branch_info
        self._save_workflow_data()

        logger.info(
            f"Created branch {branch_name} (ID: {branch_id}) for document {document_id}"
        )
        return branch_info

    def create_merge_request(
        self,
        source_branch: str,
        target_branch: str,
        requestor: str,
        title: str,
        description: str,
        reviewers: Optional[List[str]] = None,
        auto_merge: bool = False,
    ) -> MergeRequest:
        """Create a merge request.

        Args:
            source_branch: Source branch ID
            target_branch: Target branch ID
            requestor: Person requesting the merge
            title: Merge request title
            description: Merge request description
            reviewers: Optional list of reviewers
            auto_merge: Whether to auto-merge if no conflicts

        Returns:
            MergeRequest object
        """
        # Validate branches exist
        if source_branch not in self.branches:
            raise ValueError(f"Source branch {source_branch} not found")
        if target_branch not in self.branches:
            raise ValueError(f"Target branch {target_branch} not found")

        # Ensure same document
        source_doc = self.branches[source_branch].document_id
        target_doc = self.branches[target_branch].document_id
        if source_doc != target_doc:
            raise ValueError("Source and target branches must be for the same document")

        merge_id = f"merge_{source_branch}_{target_branch}_{int(time.time())}"

        merge_request = MergeRequest(
            merge_id=merge_id,
            source_branch=source_branch,
            target_branch=target_branch,
            document_id=source_doc,
            requestor=requestor,
            created_timestamp=datetime.now(),
            title=title,
            description=description,
            status="pending",
            reviewers=reviewers or [],
            auto_merge=auto_merge,
        )

        self.merge_requests[merge_id] = merge_request
        self._save_workflow_data()

        logger.info(
            f"Created merge request {merge_id}: {source_branch} -> {target_branch}"
        )
        return merge_request

    def analyze_merge_conflicts(
        self, merge_request: MergeRequest, strategy: Optional[MergeStrategy] = None
    ) -> Tuple[List[ConflictRegion], Dict[str, Any]]:
        """Analyze conflicts for a merge request.

        Args:
            merge_request: Merge request to analyze
            strategy: Optional merge strategy

        Returns:
            Tuple of (conflicts, analysis_metadata)
        """
        if not strategy:
            strategy = self.default_merge_strategy

        # Get branch content
        source_branch = self.branches[merge_request.source_branch]
        target_branch = self.branches[merge_request.target_branch]

        # Convert branch documents to comparable format
        source_content = self._get_branch_content(source_branch)
        target_content = self._get_branch_content(target_branch)

        # Find common ancestor if using three-way merge
        base_content = None
        if strategy.strategy_type == "three_way":
            base_content = self._find_common_ancestor_content(
                source_branch, target_branch
            )

        # Detect conflicts
        if base_content:
            conflicts = self.conflict_resolver.detect_conflicts(
                base_content,
                target_content,
                source_content,
                base_label="base",
                their_label=target_branch.branch_name,
                our_label=source_branch.branch_name,
            )
        else:
            # Two-way merge
            conflicts = self.conflict_resolver.detect_conflicts(
                "",
                target_content,
                source_content,
                base_label="",
                their_label=target_branch.branch_name,
                our_label=source_branch.branch_name,
            )

        # Generate analysis metadata
        analysis_metadata = {
            "merge_strategy": strategy.to_dict(),
            "conflict_count": len(conflicts),
            "conflict_types": self._analyze_conflict_types(conflicts),
            "complexity_score": self._calculate_merge_complexity(
                conflicts, source_content, target_content
            ),
            "estimated_resolution_time": self._estimate_resolution_time(conflicts),
            "auto_resolvable": self._check_auto_resolvable(conflicts, strategy),
            "analysis_timestamp": datetime.now().isoformat(),
        }

        # Update merge request
        merge_request.conflicts = conflicts
        merge_request.status = "in_progress"
        self._save_workflow_data()

        logger.info(
            f"Analyzed merge conflicts for {merge_request.merge_id}: {len(conflicts)} conflicts found"
        )
        return conflicts, analysis_metadata

    def execute_merge(
        self,
        merge_request: MergeRequest,
        strategy: Optional[MergeStrategy] = None,
        resolver_id: Optional[str] = None,
    ) -> MergeResult:
        """Execute a merge request.

        Args:
            merge_request: Merge request to execute
            strategy: Optional merge strategy
            resolver_id: Optional resolver identifier

        Returns:
            MergeResult object
        """
        if not strategy:
            strategy = self.default_merge_strategy

        start_time = time.time()

        # Analyze conflicts if not already done
        if not merge_request.conflicts:
            conflicts, _ = self.analyze_merge_conflicts(merge_request, strategy)
        else:
            conflicts = merge_request.conflicts

        # Resolve conflicts based on strategy
        if conflicts:
            resolution = self.conflict_resolver.resolve_conflicts(
                conflicts, strategy.conflict_resolution, resolver_id
            )
            merge_request.resolution = resolution
        else:
            # No conflicts, create dummy resolution
            resolution = ConflictResolution(
                document_id=merge_request.document_id,
                conflicts=[],
                resolved_content="",
                resolution_strategy="auto",
                resolution_timestamp=datetime.now().isoformat(),
                statistics={"total_conflicts": 0, "resolved_conflicts": 0},
            )
            merge_request.resolution = resolution

        # Create result branch
        result_branch_name = f"{merge_request.target_branch}_merged"
        result_branch = self.create_branch(
            branch_name=result_branch_name,
            document_id=merge_request.document_id,
            parent_branch=merge_request.target_branch,
            author=resolver_id or merge_request.requestor,
            description=f"Merged from {merge_request.source_branch}",
        )

        # Calculate performance metrics
        execution_time = time.time() - start_time
        performance_metrics = {
            "execution_time": execution_time,
            "conflicts_analyzed": len(conflicts),
            "conflicts_resolved": resolution.statistics.get("resolved_conflicts", 0),
            "merge_strategy": strategy.strategy_type,
            "content_size": len(resolution.resolved_content),
            "memory_usage": self._estimate_memory_usage(merge_request, resolution),
        }

        # Create merge result
        merge_result = MergeResult(
            merge_id=merge_request.merge_id,
            source_branch=merge_request.source_branch,
            target_branch=merge_request.target_branch,
            result_branch=result_branch.branch_id,
            status=(
                "success"
                if resolution.statistics.get("resolved_conflicts", 0) == len(conflicts)
                else "conflicts"
            ),
            conflicts_count=len(conflicts),
            resolved_conflicts=resolution.statistics.get("resolved_conflicts", 0),
            merge_timestamp=datetime.now(),
            merged_by=resolver_id or merge_request.requestor,
            merge_strategy=strategy,
            performance_metrics=performance_metrics,
        )

        # Update merge request status
        merge_request.status = (
            "completed" if merge_result.status == "success" else "failed"
        )

        # Store results
        self.merge_results[merge_request.merge_id] = merge_result
        self._save_workflow_data()

        logger.info(f"Executed merge {merge_request.merge_id}: {merge_result.status}")
        return merge_result

    def create_merge_interface(
        self, merge_request: MergeRequest, include_preview: bool = True
    ) -> str:
        """Create interactive merge interface.

        Args:
            merge_request: Merge request to create interface for
            include_preview: Whether to include merge preview

        Returns:
            HTML interface string
        """
        # Create conflict interface if conflicts exist
        if merge_request.conflicts:
            conflict_interface = SplitScreenConflictInterface(
                conflict_resolver=self.conflict_resolver,
                diff_visualizer=self.diff_visualizer,
            )

            session_id = conflict_interface.initialize_session(
                merge_request.conflicts,
                session_id=f"merge_{merge_request.merge_id}",
                storage_path=self.storage_path / "conflict_sessions",
            )

            # Create merge-specific interface
            interface_html = self._create_merge_interface_wrapper(
                merge_request, conflict_interface, include_preview
            )

            return interface_html
        else:
            # No conflicts, create simple merge interface
            return self._create_simple_merge_interface(merge_request)

    def get_merge_preview(
        self, merge_request: MergeRequest, strategy: Optional[MergeStrategy] = None
    ) -> str:
        """Generate merge preview.

        Args:
            merge_request: Merge request to preview
            strategy: Optional merge strategy

        Returns:
            HTML preview string
        """
        if not strategy:
            strategy = self.default_merge_strategy

        # Get branch content
        source_branch = self.branches[merge_request.source_branch]
        target_branch = self.branches[merge_request.target_branch]

        source_content = self._get_branch_content(source_branch)
        target_content = self._get_branch_content(target_branch)

        # Create diff visualization
        diff_viz = self.diff_visualizer.create_diff(
            target_content,
            source_content,
            old_label=target_branch.branch_name,
            new_label=source_branch.branch_name,
        )

        # Generate preview HTML
        preview_html = self._create_merge_preview_html(
            merge_request, diff_viz, strategy
        )

        return preview_html

    def get_branch_timeline(self, branch_id: str) -> List[Dict[str, Any]]:
        """Get timeline of events for a branch.

        Args:
            branch_id: Branch identifier

        Returns:
            List of timeline events
        """
        if branch_id not in self.branches:
            return []

        branch = self.branches[branch_id]
        timeline = []

        # Branch creation event
        timeline.append(
            {
                "timestamp": (
                    branch.created_timestamp.isoformat()
                    if branch.created_timestamp
                    else ""
                ),
                "event_type": "branch_created",
                "title": f"Branch {branch.branch_name} Created",
                "description": (
                    f"Created by {branch.author}" if branch.author else "Branch created"
                ),
                "metadata": {
                    "branch_id": branch_id,
                    "parent_branch": branch.parent_branch,
                },
            }
        )

        # Merge requests involving this branch
        for merge_request in self.merge_requests.values():
            if merge_request.source_branch == branch_id:
                timeline.append(
                    {
                        "timestamp": merge_request.created_timestamp.isoformat(),
                        "event_type": "merge_request_created",
                        "title": f"Merge Request: {merge_request.title}",
                        "description": f"Request to merge into {self.branches[merge_request.target_branch].branch_name}",
                        "metadata": {
                            "merge_id": merge_request.merge_id,
                            "status": merge_request.status,
                        },
                    }
                )
            elif merge_request.target_branch == branch_id:
                timeline.append(
                    {
                        "timestamp": merge_request.created_timestamp.isoformat(),
                        "event_type": "merge_request_target",
                        "title": f"Target of Merge Request: {merge_request.title}",
                        "description": f"Merge request from {self.branches[merge_request.source_branch].branch_name}",
                        "metadata": {
                            "merge_id": merge_request.merge_id,
                            "status": merge_request.status,
                        },
                    }
                )

        # Merge results
        for merge_result in self.merge_results.values():
            if (
                merge_result.source_branch == branch_id
                or merge_result.target_branch == branch_id
            ):
                timeline.append(
                    {
                        "timestamp": merge_result.merge_timestamp.isoformat(),
                        "event_type": "merge_completed",
                        "title": f"Merge Completed: {merge_result.status.title()}",
                        "description": f"Merged {self.branches[merge_result.source_branch].branch_name} into {self.branches[merge_result.target_branch].branch_name}",
                        "metadata": {
                            "merge_id": merge_result.merge_id,
                            "conflicts_resolved": merge_result.resolved_conflicts,
                            "result_branch": merge_result.result_branch,
                        },
                    }
                )

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)

        return timeline

    def _get_branch_content(self, branch: BranchInfo) -> str:
        """Get content for a branch."""
        try:
            # In a real implementation, this would fetch the document content
            # for the specific branch from the document storage system
            conversion_result = self.converter.to_markdown(branch.document_id)
            return conversion_result.content
        except Exception as e:
            logger.error(f"Failed to get content for branch {branch.branch_id}: {e}")
            return ""

    def _find_common_ancestor_content(
        self, source_branch: BranchInfo, target_branch: BranchInfo
    ) -> str:
        """Find common ancestor content for three-way merge."""
        # In a real implementation, this would find the common ancestor
        # by traversing the branch history
        # For now, return empty string (two-way merge fallback)
        return ""

    def _analyze_conflict_types(
        self, conflicts: List[ConflictRegion]
    ) -> Dict[str, int]:
        """Analyze types of conflicts."""
        conflict_types = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1
        return conflict_types

    def _calculate_merge_complexity(
        self, conflicts: List[ConflictRegion], source_content: str, target_content: str
    ) -> float:
        """Calculate merge complexity score (0.0 to 1.0)."""
        if not conflicts:
            return 0.0

        # Base complexity from number of conflicts
        base_complexity = min(len(conflicts) / 10, 0.5)

        # Content size factor
        content_size = len(source_content) + len(target_content)
        size_factor = min(content_size / 10000, 0.3)

        # Conflict size factor
        conflict_size = sum(
            len(c.our_content) + len(c.their_content) for c in conflicts
        )
        conflict_factor = min(conflict_size / 1000, 0.2)

        return base_complexity + size_factor + conflict_factor

    def _estimate_resolution_time(self, conflicts: List[ConflictRegion]) -> int:
        """Estimate resolution time in minutes."""
        if not conflicts:
            return 0

        # Base time per conflict
        base_time = len(conflicts) * 5  # 5 minutes per conflict

        # Add complexity factor
        complexity_factor = 0
        for conflict in conflicts:
            content_length = len(conflict.our_content) + len(conflict.their_content)
            if content_length > 200:
                complexity_factor += 10
            elif content_length > 100:
                complexity_factor += 5

        return base_time + complexity_factor

    def _check_auto_resolvable(
        self, conflicts: List[ConflictRegion], strategy: MergeStrategy
    ) -> bool:
        """Check if conflicts can be auto-resolved."""
        if strategy.conflict_resolution == "manual":
            return False

        # Check if all conflicts are simple
        for conflict in conflicts:
            if conflict.conflict_type == "content":
                # Content conflicts are harder to auto-resolve
                if len(conflict.our_content) > 50 or len(conflict.their_content) > 50:
                    return False

        return True

    def _estimate_memory_usage(
        self, merge_request: MergeRequest, resolution: ConflictResolution
    ) -> int:
        """Estimate memory usage in bytes."""
        # Simple estimation based on content size
        content_size = len(resolution.resolved_content)
        conflict_size = sum(
            len(c.our_content) + len(c.their_content) for c in merge_request.conflicts
        )

        return content_size + conflict_size + 10000  # Base overhead

    def _create_merge_interface_wrapper(
        self,
        merge_request: MergeRequest,
        conflict_interface: SplitScreenConflictInterface,
        include_preview: bool,
    ) -> str:
        """Create merge interface wrapper."""
        html_parts = []

        # Add merge-specific CSS
        html_parts.append(
            """
        <style>
        .merge-interface {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
            min-height: 100vh;
        }

        .merge-header {
            background: linear-gradient(135deg, #6f42c1 0%, #007bff 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .merge-title {
            font-size: 24px;
            font-weight: 600;
            margin: 0 0 10px 0;
        }

        .merge-meta {
            font-size: 14px;
            opacity: 0.9;
        }

        .merge-actions {
            background: white;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .merge-content {
            display: flex;
            gap: 20px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .merge-sidebar {
            width: 300px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 20px;
            height: fit-content;
        }

        .merge-main {
            flex: 1;
        }

        .sidebar-section {
            margin-bottom: 20px;
        }

        .sidebar-section h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
            color: #495057;
        }

        .branch-info {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }

        .branch-name {
            font-weight: 600;
            color: #495057;
        }

        .branch-meta {
            font-size: 14px;
            color: #6c757d;
        }

        .merge-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .stat-item {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
        }

        .stat-value {
            font-size: 20px;
            font-weight: 600;
            color: #007bff;
        }

        .stat-label {
            font-size: 12px;
            color: #6c757d;
        }
        </style>
        """
        )

        # Start merge interface
        html_parts.append('<div class="merge-interface">')

        # Merge header
        source_branch = self.branches[merge_request.source_branch]
        target_branch = self.branches[merge_request.target_branch]

        html_parts.append(
            """
        <div class="merge-header">
            <h1 class="merge-title">{merge_request.title}</h1>
            <div class="merge-meta">
                Merging {source_branch.branch_name} into {target_branch.branch_name}
                | Created by {merge_request.requestor}
                | {len(merge_request.conflicts)} conflicts
            </div>
        </div>
        """
        )

        # Merge actions
        html_parts.append(
            """
        <div class="merge-actions">
            <button class="btn btn-success" onclick="completeMerge()">
                ✓ Complete Merge
            </button>
            <button class="btn btn-warning" onclick="saveMergeProgress()">
                💾 Save Progress
            </button>
            <button class="btn btn-secondary" onclick="cancelMerge()">
                ✕ Cancel Merge
            </button>
            <button class="btn btn-outline" onclick="showMergePreview()">
                👁️ Preview Result
            </button>
        </div>
        """
        )

        # Merge content
        html_parts.append('<div class="merge-content">')

        # Sidebar
        html_parts.append(self._create_merge_sidebar(merge_request))

        # Main content area
        html_parts.append('<div class="merge-main">')

        # Add conflict interface
        if merge_request.conflicts:
            conflict_html = conflict_interface.create_split_screen_interface(
                merge_request.conflicts[0], include_base=True
            )
            html_parts.append(conflict_html)

        html_parts.append("</div>")
        html_parts.append("</div>")
        html_parts.append("</div>")

        # Add merge-specific JavaScript
        html_parts.append(
            """
        <script>
        function completeMerge() {
            console.log('Completing merge...');
            // Implementation would finalize the merge
        }

        function saveMergeProgress() {
            console.log('Saving merge progress...');
            // Implementation would save current state
        }

        function cancelMerge() {
            if (confirm('Are you sure you want to cancel this merge?')) {
                console.log('Cancelling merge...');
                // Implementation would cancel the merge
            }
        }

        function showMergePreview() {
            console.log('Showing merge preview...');
            // Implementation would show preview
        }
        </script>
        """
        )

        return "".join(html_parts)

    def _create_merge_sidebar(self, merge_request: MergeRequest) -> str:
        """Create merge sidebar with branch info and stats."""
        source_branch = self.branches[merge_request.source_branch]
        target_branch = self.branches[merge_request.target_branch]

        return """
        <div class="merge-sidebar">
            <div class="sidebar-section">
                <h3>Source Branch</h3>
                <div class="branch-info">
                    <div class="branch-name">{source_branch.branch_name}</div>
                    <div class="branch-meta">
                        {source_branch.commit_count} commits
                        | {source_branch.author or 'Unknown author'}
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Target Branch</h3>
                <div class="branch-info">
                    <div class="branch-name">{target_branch.branch_name}</div>
                    <div class="branch-meta">
                        {target_branch.commit_count} commits
                        | {target_branch.author or 'Unknown author'}
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Merge Statistics</h3>
                <div class="merge-stats">
                    <div class="stat-item">
                        <div class="stat-value">{len(merge_request.conflicts)}</div>
                        <div class="stat-label">Conflicts</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len([c for c in merge_request.conflicts if c.resolution_status == "resolved"])}</div>
                        <div class="stat-label">Resolved</div>
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Reviewers</h3>
                {self._format_reviewers(merge_request.reviewers)}
            </div>
        </div>
        """

    def _format_reviewers(self, reviewers: List[str]) -> str:
        """Format reviewers list."""
        if not reviewers:
            return "<div>No reviewers assigned</div>"

        html_parts = []
        for reviewer in reviewers:
            html_parts.append(f'<div class="reviewer">{reviewer}</div>')

        return "".join(html_parts)

    def _create_simple_merge_interface(self, merge_request: MergeRequest) -> str:
        """Create simple merge interface for no-conflict merges."""
        return """
        <div class="simple-merge-interface">
            <h2>Merge Ready</h2>
            <p>No conflicts found. The merge can be completed automatically.</p>
            <button class="btn btn-success" onclick="completeMerge()">
                Complete Merge
            </button>
        </div>
        """

    def _create_merge_preview_html(
        self, merge_request: MergeRequest, diff_viz, strategy: MergeStrategy
    ) -> str:
        """Create merge preview HTML."""
        html_parts = []

        # Preview header
        html_parts.append(
            """
        <div class="merge-preview-header">
            <h2>Merge Preview</h2>
            <p>Preview of changes when merging {merge_request.source_branch} into {merge_request.target_branch}</p>
        </div>
        """
        )

        # Strategy info
        html_parts.append(
            """
        <div class="merge-strategy-info">
            <strong>Strategy:</strong> {strategy.strategy_type.title()}
            <strong>Conflict Resolution:</strong> {strategy.conflict_resolution.title()}
        </div>
        """
        )

        # Diff visualization
        html_parts.append(diff_viz.html_output or "")

        return "".join(html_parts)

    def _load_workflow_data(self):
        """Load workflow data from storage."""
        try:
            # Load branches
            branches_file = self.storage_path / "branches.json"
            if branches_file.exists():
                with open(branches_file, "r") as f:
                    branches_data = json.load(f)
                    for branch_id, branch_data in branches_data.items():
                        # Convert timestamp strings back to datetime
                        if branch_data.get("created_timestamp"):
                            branch_data["created_timestamp"] = datetime.fromisoformat(
                                branch_data["created_timestamp"]
                            )
                        if branch_data.get("last_modified"):
                            branch_data["last_modified"] = datetime.fromisoformat(
                                branch_data["last_modified"]
                            )

                        self.branches[branch_id] = BranchInfo(**branch_data)

            # Load merge requests
            merge_requests_file = self.storage_path / "merge_requests.json"
            if merge_requests_file.exists():
                with open(merge_requests_file, "r") as f:
                    merge_requests_data = json.load(f)
                    for merge_id, merge_data in merge_requests_data.items():
                        # Convert timestamp strings back to datetime
                        if merge_data.get("created_timestamp"):
                            merge_data["created_timestamp"] = datetime.fromisoformat(
                                merge_data["created_timestamp"]
                            )

                        # Handle conflicts
                        if merge_data.get("conflicts"):
                            conflicts = []
                            for conflict_data in merge_data["conflicts"]:
                                conflicts.append(ConflictRegion(**conflict_data))
                            merge_data["conflicts"] = conflicts

                        self.merge_requests[merge_id] = MergeRequest(**merge_data)

            # Load merge results
            merge_results_file = self.storage_path / "merge_results.json"
            if merge_results_file.exists():
                with open(merge_results_file, "r") as f:
                    merge_results_data = json.load(f)
                    for merge_id, result_data in merge_results_data.items():
                        # Convert timestamp strings back to datetime
                        if result_data.get("merge_timestamp"):
                            result_data["merge_timestamp"] = datetime.fromisoformat(
                                result_data["merge_timestamp"]
                            )

                        # Handle merge strategy
                        if result_data.get("merge_strategy"):
                            result_data["merge_strategy"] = MergeStrategy(
                                **result_data["merge_strategy"]
                            )

                        self.merge_results[merge_id] = MergeResult(**result_data)

            logger.info("Loaded workflow data from storage")

        except Exception as e:
            logger.error(f"Failed to load workflow data: {e}")

    def _save_workflow_data(self):
        """Save workflow data to storage."""
        try:
            # Save branches
            branches_file = self.storage_path / "branches.json"
            with open(branches_file, "w") as f:
                branches_data = {
                    bid: branch.to_dict() for bid, branch in self.branches.items()
                }
                json.dump(branches_data, f, indent=2)

            # Save merge requests
            merge_requests_file = self.storage_path / "merge_requests.json"
            with open(merge_requests_file, "w") as f:
                merge_requests_data = {
                    mid: merge_req.to_dict()
                    for mid, merge_req in self.merge_requests.items()
                }
                json.dump(merge_requests_data, f, indent=2)

            # Save merge results
            merge_results_file = self.storage_path / "merge_results.json"
            with open(merge_results_file, "w") as f:
                merge_results_data = {
                    mid: result.to_dict() for mid, result in self.merge_results.items()
                }
                json.dump(merge_results_data, f, indent=2)

            logger.debug("Saved workflow data to storage")

        except Exception as e:
            logger.error(f"Failed to save workflow data: {e}")
