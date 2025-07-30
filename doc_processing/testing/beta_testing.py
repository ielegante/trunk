"""Beta testing program framework for document processing features."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..converters.accuracy_tester import AccuracyTester, AccuracyTestResult
from ..converters.google_docs import GoogleDocsConverter
from ..ui.user_experience import UserExperienceManager

logger = logging.getLogger(__name__)


@dataclass
class BetaTester:
    """Information about a beta tester."""

    tester_id: str
    email: str
    name: str
    organization: Optional[str] = None
    role: str = "tester"  # tester, power_user, admin
    joined_date: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    test_cases_completed: int = 0
    bugs_reported: int = 0
    feedback_provided: int = 0
    is_active: bool = True
    specializations: List[str] = None

    def __post_init__(self):
        if self.specializations is None:
            self.specializations = []
        if self.joined_date is None:
            self.joined_date = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.joined_date:
            data["joined_date"] = self.joined_date.isoformat()
        if self.last_activity:
            data["last_activity"] = self.last_activity.isoformat()
        return data


@dataclass
class TestCase:
    """Represents a test case for beta testing."""

    test_id: str
    title: str
    description: str
    category: str  # conversion, conflict_resolution, ui, performance
    priority: str = "medium"  # low, medium, high, critical
    estimated_time: int = 30  # minutes
    prerequisites: List[str] = None
    test_steps: List[str] = None
    expected_results: List[str] = None
    actual_results: List[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    assigned_testers: List[str] = None
    created_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None

    def __post_init__(self):
        if self.prerequisites is None:
            self.prerequisites = []
        if self.test_steps is None:
            self.test_steps = []
        if self.expected_results is None:
            self.expected_results = []
        if self.actual_results is None:
            self.actual_results = []
        if self.assigned_testers is None:
            self.assigned_testers = []
        if self.created_date is None:
            self.created_date = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.created_date:
            data["created_date"] = self.created_date.isoformat()
        if self.completion_date:
            data["completion_date"] = self.completion_date.isoformat()
        return data


@dataclass
class TestResult:
    """Result of a test case execution."""

    result_id: str
    test_id: str
    tester_id: str
    status: str  # passed, failed, blocked, skipped
    execution_time: int  # minutes
    completion_date: datetime
    notes: str
    issues_found: List[str] = None
    suggestions: List[str] = None
    screenshots: List[str] = None
    logs: List[str] = None

    def __post_init__(self):
        if self.issues_found is None:
            self.issues_found = []
        if self.suggestions is None:
            self.suggestions = []
        if self.screenshots is None:
            self.screenshots = []
        if self.logs is None:
            self.logs = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["completion_date"] = self.completion_date.isoformat()
        return data


@dataclass
class BugReport:
    """Bug report from beta testing."""

    bug_id: str
    title: str
    description: str
    severity: str  # low, medium, high, critical
    category: str  # ui, performance, functionality, crash
    steps_to_reproduce: List[str]
    expected_behavior: str
    actual_behavior: str
    reporter_id: str
    reported_date: datetime
    status: str = "open"  # open, in_progress, resolved, closed, duplicate
    assigned_to: Optional[str] = None
    resolution_date: Optional[datetime] = None
    test_case_id: Optional[str] = None
    attachments: List[str] = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["reported_date"] = self.reported_date.isoformat()
        if self.resolution_date:
            data["resolution_date"] = self.resolution_date.isoformat()
        return data


@dataclass
class FeedbackReport:
    """User feedback from beta testing."""

    feedback_id: str
    category: str  # usability, feature_request, general
    rating: int  # 1-5 scale
    title: str
    content: str
    tester_id: str
    submitted_date: datetime
    feature_area: str  # conversion, conflict_resolution, ui, workflow
    priority: str = "medium"  # low, medium, high
    status: str = "pending"  # pending, reviewed, implemented, rejected

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["submitted_date"] = self.submitted_date.isoformat()
        return data


class BetaTestingProgram:
    """Manages beta testing program for document processing features."""

    def __init__(
        self,
        converter: Optional[GoogleDocsConverter] = None,
        accuracy_tester: Optional[AccuracyTester] = None,
        ux_manager: Optional[UserExperienceManager] = None,
        storage_path: Optional[Path] = None,
    ):
        """Initialize beta testing program.

        Args:
            converter: GoogleDocsConverter instance
            accuracy_tester: AccuracyTester instance
            ux_manager: UserExperienceManager instance
            storage_path: Path for storing testing data
        """
        self.converter = converter or GoogleDocsConverter({})
        self.accuracy_tester = accuracy_tester or AccuracyTester(self.converter)
        self.ux_manager = ux_manager or UserExperienceManager()
        self.storage_path = storage_path or Path("beta_testing")

        # Initialize storage
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Testing data
        self.testers: Dict[str, BetaTester] = {}
        self.test_cases: Dict[str, TestCase] = {}
        self.test_results: Dict[str, TestResult] = {}
        self.bug_reports: Dict[str, BugReport] = {}
        self.feedback_reports: Dict[str, FeedbackReport] = {}

        # Load existing data
        self._load_testing_data()

        # Initialize default test cases
        self._initialize_default_test_cases()

    def register_tester(
        self,
        email: str,
        name: str,
        organization: Optional[str] = None,
        role: str = "tester",
        specializations: Optional[List[str]] = None,
    ) -> BetaTester:
        """Register a new beta tester.

        Args:
            email: Tester email address
            name: Tester name
            organization: Optional organization
            role: Tester role
            specializations: Optional list of specializations

        Returns:
            BetaTester object
        """
        tester_id = (
            f"tester_{int(time.time())}_{email.replace('@', '_').replace('.', '_')}"
        )

        tester = BetaTester(
            tester_id=tester_id,
            email=email,
            name=name,
            organization=organization,
            role=role,
            specializations=specializations or [],
        )

        self.testers[tester_id] = tester
        self._save_testing_data()

        logger.info(f"Registered beta tester: {name} ({email})")
        return tester

    def create_test_case(
        self,
        title: str,
        description: str,
        category: str,
        priority: str = "medium",
        estimated_time: int = 30,
        prerequisites: Optional[List[str]] = None,
        test_steps: Optional[List[str]] = None,
        expected_results: Optional[List[str]] = None,
    ) -> TestCase:
        """Create a new test case.

        Args:
            title: Test case title
            description: Test case description
            category: Test category
            priority: Test priority
            estimated_time: Estimated time in minutes
            prerequisites: Optional prerequisites
            test_steps: Optional test steps
            expected_results: Optional expected results

        Returns:
            TestCase object
        """
        test_id = f"test_{category}_{int(time.time())}"

        test_case = TestCase(
            test_id=test_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            estimated_time=estimated_time,
            prerequisites=prerequisites or [],
            test_steps=test_steps or [],
            expected_results=expected_results or [],
        )

        self.test_cases[test_id] = test_case
        self._save_testing_data()

        logger.info(f"Created test case: {title} ({test_id})")
        return test_case

    def assign_test_case(self, test_id: str, tester_id: str) -> bool:
        """Assign a test case to a tester.

        Args:
            test_id: Test case ID
            tester_id: Tester ID

        Returns:
            True if assignment successful, False otherwise
        """
        if test_id not in self.test_cases or tester_id not in self.testers:
            return False

        test_case = self.test_cases[test_id]
        if tester_id not in test_case.assigned_testers:
            test_case.assigned_testers.append(tester_id)
            self._save_testing_data()

            logger.info(f"Assigned test case {test_id} to tester {tester_id}")
            return True

        return False

    def submit_test_result(
        self,
        test_id: str,
        tester_id: str,
        status: str,
        execution_time: int,
        notes: str,
        issues_found: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
        screenshots: Optional[List[str]] = None,
        logs: Optional[List[str]] = None,
    ) -> TestResult:
        """Submit a test result.

        Args:
            test_id: Test case ID
            tester_id: Tester ID
            status: Test result status
            execution_time: Time taken in minutes
            notes: Test notes
            issues_found: Optional list of issues found
            suggestions: Optional list of suggestions
            screenshots: Optional list of screenshot paths
            logs: Optional list of log entries

        Returns:
            TestResult object
        """
        result_id = f"result_{test_id}_{tester_id}_{int(time.time())}"

        test_result = TestResult(
            result_id=result_id,
            test_id=test_id,
            tester_id=tester_id,
            status=status,
            execution_time=execution_time,
            completion_date=datetime.now(),
            notes=notes,
            issues_found=issues_found or [],
            suggestions=suggestions or [],
            screenshots=screenshots or [],
            logs=logs or [],
        )

        self.test_results[result_id] = test_result

        # Update test case status
        if test_id in self.test_cases:
            test_case = self.test_cases[test_id]
            if status == "passed":
                test_case.status = "completed"
                test_case.completion_date = datetime.now()

        # Update tester statistics
        if tester_id in self.testers:
            tester = self.testers[tester_id]
            tester.test_cases_completed += 1
            tester.last_activity = datetime.now()

        self._save_testing_data()

        logger.info(f"Submitted test result for {test_id} by {tester_id}: {status}")
        return test_result

    def report_bug(
        self,
        title: str,
        description: str,
        severity: str,
        category: str,
        steps_to_reproduce: List[str],
        expected_behavior: str,
        actual_behavior: str,
        reporter_id: str,
        test_case_id: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> BugReport:
        """Report a bug found during testing.

        Args:
            title: Bug title
            description: Bug description
            severity: Bug severity
            category: Bug category
            steps_to_reproduce: Steps to reproduce
            expected_behavior: Expected behavior
            actual_behavior: Actual behavior
            reporter_id: Reporter ID
            test_case_id: Optional test case ID
            attachments: Optional attachments

        Returns:
            BugReport object
        """
        bug_id = f"bug_{category}_{int(time.time())}"

        bug_report = BugReport(
            bug_id=bug_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            steps_to_reproduce=steps_to_reproduce,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            reporter_id=reporter_id,
            reported_date=datetime.now(),
            test_case_id=test_case_id,
            attachments=attachments or [],
        )

        self.bug_reports[bug_id] = bug_report

        # Update tester statistics
        if reporter_id in self.testers:
            tester = self.testers[reporter_id]
            tester.bugs_reported += 1
            tester.last_activity = datetime.now()

        self._save_testing_data()

        logger.info(f"Bug reported: {title} ({bug_id}) by {reporter_id}")
        return bug_report

    def submit_feedback(
        self,
        category: str,
        rating: int,
        title: str,
        content: str,
        tester_id: str,
        feature_area: str,
        priority: str = "medium",
    ) -> FeedbackReport:
        """Submit user feedback.

        Args:
            category: Feedback category
            rating: Rating (1-5)
            title: Feedback title
            content: Feedback content
            tester_id: Tester ID
            feature_area: Feature area
            priority: Priority level

        Returns:
            FeedbackReport object
        """
        feedback_id = f"feedback_{category}_{int(time.time())}"

        feedback = FeedbackReport(
            feedback_id=feedback_id,
            category=category,
            rating=rating,
            title=title,
            content=content,
            tester_id=tester_id,
            submitted_date=datetime.now(),
            feature_area=feature_area,
            priority=priority,
        )

        self.feedback_reports[feedback_id] = feedback

        # Update tester statistics
        if tester_id in self.testers:
            tester = self.testers[tester_id]
            tester.feedback_provided += 1
            tester.last_activity = datetime.now()

        self._save_testing_data()

        logger.info(f"Feedback submitted: {title} ({feedback_id}) by {tester_id}")
        return feedback

    def get_testing_dashboard(self) -> str:
        """Generate testing dashboard HTML.

        Returns:
            HTML string with testing dashboard
        """
        html_parts = []

        # Add CSS
        html_parts.append(self._get_testing_dashboard_css())

        # Start dashboard
        html_parts.append('<div class="testing-dashboard">')

        # Dashboard header
        html_parts.append(self._create_dashboard_header())

        # Dashboard content
        html_parts.append('<div class="dashboard-content">')

        # Statistics overview
        html_parts.append(self._create_statistics_overview())

        # Test progress
        html_parts.append(self._create_test_progress_section())

        # Bug tracking
        html_parts.append(self._create_bug_tracking_section())

        # Feedback summary
        html_parts.append(self._create_feedback_summary_section())

        # Tester leaderboard
        html_parts.append(self._create_tester_leaderboard())

        html_parts.append("</div>")
        html_parts.append("</div>")

        # Add JavaScript
        html_parts.append(self._get_testing_dashboard_javascript())

        return "".join(html_parts)

    def get_tester_interface(self, tester_id: str) -> str:
        """Create tester interface for a specific tester.

        Args:
            tester_id: Tester ID

        Returns:
            HTML string with tester interface
        """
        if tester_id not in self.testers:
            return "<div class='error'>Tester not found</div>"

        tester = self.testers[tester_id]

        # Get assigned test cases
        assigned_tests = [
            test
            for test in self.test_cases.values()
            if tester_id in test.assigned_testers
        ]

        # Get tester results
        tester_results = [
            result
            for result in self.test_results.values()
            if result.tester_id == tester_id
        ]

        html_parts = []

        # Add CSS
        html_parts.append(self._get_tester_interface_css())

        # Start interface
        html_parts.append('<div class="tester-interface">')

        # Tester header
        html_parts.append(self._create_tester_header(tester))

        # Interface content
        html_parts.append('<div class="tester-content">')

        # Assigned tests
        html_parts.append(self._create_assigned_tests_section(assigned_tests))

        # Test results
        html_parts.append(self._create_test_results_section(tester_results))

        # Bug reporting
        html_parts.append(self._create_bug_reporting_section())

        # Feedback form
        html_parts.append(self._create_feedback_form())

        html_parts.append("</div>")
        html_parts.append("</div>")

        # Add JavaScript
        html_parts.append(self._get_tester_interface_javascript())

        return "".join(html_parts)

    def generate_testing_report(self, include_details: bool = True) -> Dict[str, Any]:
        """Generate comprehensive testing report.

        Args:
            include_details: Whether to include detailed data

        Returns:
            Dictionary with testing report data
        """
        # Calculate statistics
        total_testers = len(self.testers)
        active_testers = len([t for t in self.testers.values() if t.is_active])
        total_test_cases = len(self.test_cases)
        completed_tests = len(
            [t for t in self.test_cases.values() if t.status == "completed"]
        )
        total_bugs = len(self.bug_reports)
        critical_bugs = len(
            [b for b in self.bug_reports.values() if b.severity == "critical"]
        )
        total_feedback = len(self.feedback_reports)

        # Calculate test completion rate
        completion_rate = (
            (completed_tests / total_test_cases) * 100 if total_test_cases > 0 else 0
        )

        # Calculate average rating
        ratings = [f.rating for f in self.feedback_reports.values()]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # Bug severity distribution
        bug_severity_dist = {}
        for bug in self.bug_reports.values():
            bug_severity_dist[bug.severity] = bug_severity_dist.get(bug.severity, 0) + 1

        # Test category distribution
        test_category_dist = {}
        for test in self.test_cases.values():
            test_category_dist[test.category] = (
                test_category_dist.get(test.category, 0) + 1
            )

        report = {
            "report_generated": datetime.now().isoformat(),
            "summary": {
                "total_testers": total_testers,
                "active_testers": active_testers,
                "total_test_cases": total_test_cases,
                "completed_tests": completed_tests,
                "completion_rate": completion_rate,
                "total_bugs": total_bugs,
                "critical_bugs": critical_bugs,
                "total_feedback": total_feedback,
                "average_rating": avg_rating,
            },
            "distributions": {
                "bug_severity": bug_severity_dist,
                "test_categories": test_category_dist,
            },
            "top_testers": self._get_top_testers(5),
            "recent_activity": self._get_recent_activity(10),
        }

        if include_details:
            report["detailed_data"] = {
                "testers": [t.to_dict() for t in self.testers.values()],
                "test_cases": [t.to_dict() for t in self.test_cases.values()],
                "test_results": [r.to_dict() for r in self.test_results.values()],
                "bug_reports": [b.to_dict() for b in self.bug_reports.values()],
                "feedback_reports": [
                    f.to_dict() for f in self.feedback_reports.values()
                ],
            }

        return report

    def _initialize_default_test_cases(self):
        """Initialize default test cases."""
        if not self.test_cases:  # Only create if no test cases exist
            # Google Docs conversion test cases
            self.create_test_case(
                title="Google Docs to Markdown Conversion",
                description="Test basic Google Docs to Markdown conversion functionality",
                category="conversion",
                priority="high",
                estimated_time=45,
                test_steps=[
                    "Open a Google Docs document with various formatting",
                    "Initiate conversion to Markdown",
                    "Verify formatting preservation",
                    "Check for any conversion errors",
                ],
                expected_results=[
                    "Document converts successfully",
                    "Formatting is preserved",
                    "No conversion errors occur",
                ],
            )

            self.create_test_case(
                title="Markdown to Google Docs Conversion",
                description="Test Markdown to Google Docs conversion with round-trip accuracy",
                category="conversion",
                priority="high",
                estimated_time=45,
                test_steps=[
                    "Create or open a Markdown document",
                    "Convert to Google Docs format",
                    "Verify formatting and structure",
                    "Test round-trip conversion",
                ],
                expected_results=[
                    "Markdown converts to Google Docs successfully",
                    "Formatting is preserved",
                    "Round-trip conversion maintains accuracy",
                ],
            )

            # Conflict resolution test cases
            self.create_test_case(
                title="Split-Screen Conflict Resolution",
                description="Test the split-screen conflict resolution interface",
                category="conflict_resolution",
                priority="high",
                estimated_time=30,
                test_steps=[
                    "Create a document with merge conflicts",
                    "Open split-screen conflict resolution",
                    "Try different resolution strategies",
                    "Verify resolution is applied correctly",
                ],
                expected_results=[
                    "Split-screen interface loads correctly",
                    "All resolution options work",
                    "Conflicts are resolved properly",
                ],
            )

            self.create_test_case(
                title="Batch Conflict Resolution",
                description="Test resolving multiple conflicts in batch",
                category="conflict_resolution",
                priority="medium",
                estimated_time=25,
                test_steps=[
                    "Create document with multiple conflicts",
                    "Open batch resolution interface",
                    "Apply batch resolution strategies",
                    "Verify all conflicts are resolved",
                ],
                expected_results=[
                    "Batch interface shows all conflicts",
                    "Batch resolution works correctly",
                    "All conflicts are resolved",
                ],
            )

            # UI/UX test cases
            self.create_test_case(
                title="Timeline View Navigation",
                description="Test the document timeline view functionality",
                category="ui",
                priority="medium",
                estimated_time=20,
                test_steps=[
                    "Open document timeline view",
                    "Navigate through different time periods",
                    "Filter by event types",
                    "Test timeline interactions",
                ],
                expected_results=[
                    "Timeline loads and displays correctly",
                    "Navigation works smoothly",
                    "Filtering functions properly",
                ],
            )

            self.create_test_case(
                title="User Preferences and Themes",
                description="Test user preferences and theme switching",
                category="ui",
                priority="low",
                estimated_time=15,
                test_steps=[
                    "Open user preferences",
                    "Change theme settings",
                    "Modify font size and other preferences",
                    "Verify changes are applied",
                ],
                expected_results=[
                    "Preferences interface is accessible",
                    "Theme changes apply correctly",
                    "Settings are saved properly",
                ],
            )

            # Performance test cases
            self.create_test_case(
                title="Large Document Performance",
                description="Test performance with large documents",
                category="performance",
                priority="high",
                estimated_time=60,
                test_steps=[
                    "Open a large document (50+ pages)",
                    "Perform conversion operations",
                    "Monitor performance metrics",
                    "Test responsiveness",
                ],
                expected_results=[
                    "Large documents load within acceptable time",
                    "Conversions complete without errors",
                    "Interface remains responsive",
                ],
            )

            logger.info("Initialized default test cases")

    def _get_top_testers(self, limit: int) -> List[Dict[str, Any]]:
        """Get top testers by activity."""
        testers = list(self.testers.values())
        testers.sort(
            key=lambda t: t.test_cases_completed
            + t.bugs_reported
            + t.feedback_provided,
            reverse=True,
        )

        return [
            {
                "tester_id": t.tester_id,
                "name": t.name,
                "tests_completed": t.test_cases_completed,
                "bugs_reported": t.bugs_reported,
                "feedback_provided": t.feedback_provided,
                "total_activity": t.test_cases_completed
                + t.bugs_reported
                + t.feedback_provided,
            }
            for t in testers[:limit]
        ]

    def _get_recent_activity(self, limit: int) -> List[Dict[str, Any]]:
        """Get recent testing activity."""
        activities = []

        # Add recent test results
        for result in self.test_results.values():
            activities.append(
                {
                    "type": "test_result",
                    "timestamp": result.completion_date,
                    "description": f"Test {result.test_id} completed by {result.tester_id}",
                    "status": result.status,
                }
            )

        # Add recent bug reports
        for bug in self.bug_reports.values():
            activities.append(
                {
                    "type": "bug_report",
                    "timestamp": bug.reported_date,
                    "description": f"Bug reported: {bug.title}",
                    "severity": bug.severity,
                }
            )

        # Add recent feedback
        for feedback in self.feedback_reports.values():
            activities.append(
                {
                    "type": "feedback",
                    "timestamp": feedback.submitted_date,
                    "description": f"Feedback: {feedback.title}",
                    "rating": feedback.rating,
                }
            )

        # Sort by timestamp and limit
        activities.sort(key=lambda a: a["timestamp"], reverse=True)

        return [
            {**activity, "timestamp": activity["timestamp"].isoformat()}
            for activity in activities[:limit]
        ]

    def _get_testing_dashboard_css(self) -> str:
        """Get CSS for testing dashboard."""
        return """
        <style>
        .testing-dashboard {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }

        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }

        .dashboard-title {
            font-size: 32px;
            font-weight: 600;
            margin: 0 0 10px 0;
        }

        .dashboard-subtitle {
            font-size: 18px;
            opacity: 0.9;
        }

        .dashboard-content {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }

        .dashboard-section {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 20px;
        }

        .section-header {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }

        .stat-card {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 15px;
            text-align: center;
        }

        .stat-value {
            font-size: 24px;
            font-weight: 600;
            color: #007bff;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 14px;
            color: #6c757d;
        }

        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
            transition: width 0.3s ease;
        }

        .item-list {
            max-height: 300px;
            overflow-y: auto;
        }

        .list-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #e9ecef;
        }

        .list-item:hover {
            background-color: #f8f9fa;
        }

        .severity-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }

        .severity-critical {
            background-color: #dc3545;
            color: white;
        }

        .severity-high {
            background-color: #fd7e14;
            color: white;
        }

        .severity-medium {
            background-color: #ffc107;
            color: #212529;
        }

        .severity-low {
            background-color: #6c757d;
            color: white;
        }

        .leaderboard-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #e9ecef;
        }

        .leaderboard-rank {
            font-size: 20px;
            font-weight: 600;
            color: #007bff;
            margin-right: 15px;
            min-width: 30px;
        }

        .leaderboard-info {
            flex: 1;
        }

        .leaderboard-name {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .leaderboard-stats {
            font-size: 14px;
            color: #6c757d;
        }

        .leaderboard-score {
            font-size: 18px;
            font-weight: 600;
            color: #28a745;
        }
        </style>
        """

    def _create_dashboard_header(self) -> str:
        """Create dashboard header."""
        return """
        <div class="dashboard-header">
            <h1 class="dashboard-title">Beta Testing Dashboard</h1>
            <p class="dashboard-subtitle">Document Processing Feature Testing Program</p>
        </div>
        """

    def _create_statistics_overview(self) -> str:
        """Create statistics overview section."""
        total_testers = len(self.testers)
        active_testers = len([t for t in self.testers.values() if t.is_active])
        total_tests = len(self.test_cases)
        completed_tests = len(
            [t for t in self.test_cases.values() if t.status == "completed"]
        )
        total_bugs = len(self.bug_reports)
        critical_bugs = len(
            [b for b in self.bug_reports.values() if b.severity == "critical"]
        )

        completion_rate = (
            (completed_tests / total_tests) * 100 if total_tests > 0 else 0
        )

        return """
        <div class="dashboard-section">
            <div class="section-header">Testing Statistics</div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{total_testers}</div>
                    <div class="stat-label">Total Testers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{active_testers}</div>
                    <div class="stat-label">Active Testers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_tests}</div>
                    <div class="stat-label">Total Tests</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{completed_tests}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_bugs}</div>
                    <div class="stat-label">Bugs Found</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{critical_bugs}</div>
                    <div class="stat-label">Critical Bugs</div>
                </div>
            </div>
            <div class="progress-section">
                <div>Test Completion Rate: {completion_rate:.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {completion_rate}%"></div>
                </div>
            </div>
        </div>
        """

    def _create_test_progress_section(self) -> str:
        """Create test progress section."""
        test_categories = {}
        for test in self.test_cases.values():
            if test.category not in test_categories:
                test_categories[test.category] = {"total": 0, "completed": 0}
            test_categories[test.category]["total"] += 1
            if test.status == "completed":
                test_categories[test.category]["completed"] += 1

        html_parts = []

        html_parts.append(
            """
        <div class="dashboard-section">
            <div class="section-header">Test Progress by Category</div>
            <div class="item-list">
        """
        )

        for category, stats in test_categories.items():
            completion_rate = (
                (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            )

            html_parts.append(
                """
            <div class="list-item">
                <div>
                    <div class="category-name">{category.title()}</div>
                    <div class="category-stats">{stats["completed"]}/{stats["total"]} tests completed</div>
                </div>
                <div class="category-progress">
                    <div class="progress-bar" style="width: 150px;">
                        <div class="progress-fill" style="width: {completion_rate}%"></div>
                    </div>
                </div>
            </div>
            """
            )

        html_parts.append("</div></div>")

        return "".join(html_parts)

    def _create_bug_tracking_section(self) -> str:
        """Create bug tracking section."""
        recent_bugs = sorted(
            self.bug_reports.values(), key=lambda b: b.reported_date, reverse=True
        )[:5]

        html_parts = []

        html_parts.append(
            """
        <div class="dashboard-section">
            <div class="section-header">Recent Bug Reports</div>
            <div class="item-list">
        """
        )

        for bug in recent_bugs:
            html_parts.append(
                """
            <div class="list-item">
                <div>
                    <div class="bug-title">{bug.title}</div>
                    <div class="bug-meta">
                        Reported by {bug.reporter_id} • {bug.reported_date.strftime("%m/%d %I:%M %p")}
                    </div>
                </div>
                <div class="severity-badge severity-{bug.severity}">
                    {bug.severity}
                </div>
            </div>
            """
            )

        html_parts.append("</div></div>")

        return "".join(html_parts)

    def _create_feedback_summary_section(self) -> str:
        """Create feedback summary section."""
        recent_feedback = sorted(
            self.feedback_reports.values(), key=lambda f: f.submitted_date, reverse=True
        )[:5]

        # Calculate average rating
        ratings = [f.rating for f in self.feedback_reports.values()]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        html_parts = []

        html_parts.append(
            """
        <div class="dashboard-section">
            <div class="section-header">User Feedback</div>
            <div class="feedback-summary">
                <div class="average-rating">
                    Average Rating: {avg_rating:.1f}/5 ({len(ratings)} reviews)
                </div>
            </div>
            <div class="item-list">
        """
        )

        for feedback in recent_feedback:
            stars = "★" * feedback.rating + "☆" * (5 - feedback.rating)
            html_parts.append(
                """
            <div class="list-item">
                <div>
                    <div class="feedback-title">{feedback.title}</div>
                    <div class="feedback-meta">
                        {stars} • {feedback.submitted_date.strftime("%m/%d %I:%M %p")}
                    </div>
                </div>
                <div class="feedback-category">{feedback.category}</div>
            </div>
            """
            )

        html_parts.append("</div></div>")

        return "".join(html_parts)

    def _create_tester_leaderboard(self) -> str:
        """Create tester leaderboard."""
        top_testers = self._get_top_testers(5)

        html_parts = []

        html_parts.append(
            """
        <div class="dashboard-section">
            <div class="section-header">Top Testers</div>
            <div class="leaderboard">
        """
        )

        for i, tester in enumerate(top_testers, 1):
            html_parts.append(
                """
            <div class="leaderboard-item">
                <div class="leaderboard-rank">#{i}</div>
                <div class="leaderboard-info">
                    <div class="leaderboard-name">{tester["name"]}</div>
                    <div class="leaderboard-stats">
                        {tester["tests_completed"]} tests • {tester["bugs_reported"]} bugs • {tester["feedback_provided"]} feedback
                    </div>
                </div>
                <div class="leaderboard-score">{tester["total_activity"]}</div>
            </div>
            """
            )

        html_parts.append("</div></div>")

        return "".join(html_parts)

    def _get_testing_dashboard_javascript(self) -> str:
        """Get JavaScript for testing dashboard."""
        return """
        <script>
        // Auto-refresh dashboard every 30 seconds
        setInterval(function() {
            location.reload();
        }, 30000);

        // Add interactivity to dashboard elements
        document.addEventListener('DOMContentLoaded', function() {
            // Add click handlers for list items
            document.querySelectorAll('.list-item').forEach(item => {
                item.addEventListener('click', function() {
                    console.log('Clicked item:', this);
                    // Add item click functionality
                });
            });
        });
        </script>
        """

    def _get_tester_interface_css(self) -> str:
        """Get CSS for tester interface."""
        return """
        <style>
        .tester-interface {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }

        .tester-header {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }

        .tester-name {
            font-size: 28px;
            font-weight: 600;
            margin: 0 0 10px 0;
        }

        .tester-stats {
            font-size: 16px;
            opacity: 0.9;
        }

        .tester-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .tester-section {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 20px;
        }

        .section-header {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #495057;
        }

        .test-item {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid #007bff;
        }

        .test-title {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .test-meta {
            font-size: 14px;
            color: #6c757d;
            margin-bottom: 10px;
        }

        .test-actions {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s ease;
        }

        .btn-primary {
            background-color: #007bff;
            color: white;
        }

        .btn-primary:hover {
            background-color: #0056b3;
        }

        .btn-success {
            background-color: #28a745;
            color: white;
        }

        .btn-success:hover {
            background-color: #1e7e34;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
        }

        .form-input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }

        .form-textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-height: 100px;
            resize: vertical;
        }

        .form-select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }

        @media (max-width: 768px) {
            .tester-content {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """

    def _create_tester_header(self, tester: BetaTester) -> str:
        """Create tester header."""
        return """
        <div class="tester-header">
            <h1 class="tester-name">Welcome, {tester.name}</h1>
            <div class="tester-stats">
                {tester.test_cases_completed} tests completed •
                {tester.bugs_reported} bugs reported •
                {tester.feedback_provided} feedback submitted
            </div>
        </div>
        """

    def _create_assigned_tests_section(self, assigned_tests: List[TestCase]) -> str:
        """Create assigned tests section."""
        html_parts = []

        html_parts.append(
            """
        <div class="tester-section">
            <div class="section-header">Assigned Tests</div>
        """
        )

        if assigned_tests:
            for test in assigned_tests:
                html_parts.append(
                    """
                <div class="test-item">
                    <div class="test-title">{test.title}</div>
                    <div class="test-meta">
                        {test.category.title()} • {test.priority.title()} Priority •
                        Est. {test.estimated_time} min
                    </div>
                    <div class="test-description">{test.description}</div>
                    <div class="test-actions">
                        <button class="btn btn-primary" onclick="startTest('{test.test_id}')">
                            Start Test
                        </button>
                        <button class="btn btn-success" onclick="viewTestDetails('{test.test_id}')">
                            View Details
                        </button>
                    </div>
                </div>
                """
                )
        else:
            html_parts.append('<div class="empty-state">No tests assigned</div>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_test_results_section(self, test_results: List[TestResult]) -> str:
        """Create test results section."""
        html_parts = []

        html_parts.append(
            """
        <div class="tester-section">
            <div class="section-header">Your Test Results</div>
        """
        )

        if test_results:
            for result in test_results[:10]:  # Show last 10 results
                html_parts.append(
                    """
                <div class="test-item">
                    <div class="test-title">Test {result.test_id}</div>
                    <div class="test-meta">
                        Status: {result.status.title()} •
                        Completed: {result.completion_date.strftime("%m/%d %I:%M %p")} •
                        Time: {result.execution_time} min
                    </div>
                    <div class="test-notes">{result.notes}</div>
                </div>
                """
                )
        else:
            html_parts.append('<div class="empty-state">No test results yet</div>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _create_bug_reporting_section(self) -> str:
        """Create bug reporting section."""
        return """
        <div class="tester-section">
            <div class="section-header">Report a Bug</div>
            <form id="bug-report-form">
                <div class="form-group">
                    <label class="form-label">Bug Title</label>
                    <input type="text" class="form-input" id="bug-title" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Severity</label>
                    <select class="form-select" id="bug-severity" required>
                        <option value="">Select severity</option>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <select class="form-select" id="bug-category" required>
                        <option value="">Select category</option>
                        <option value="ui">UI/UX</option>
                        <option value="functionality">Functionality</option>
                        <option value="performance">Performance</option>
                        <option value="crash">Crash/Error</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <textarea class="form-textarea" id="bug-description" required></textarea>
                </div>
                <div class="form-group">
                    <button type="submit" class="btn btn-primary">Submit Bug Report</button>
                </div>
            </form>
        </div>
        """

    def _create_feedback_form(self) -> str:
        """Create feedback form."""
        return """
        <div class="tester-section">
            <div class="section-header">Submit Feedback</div>
            <form id="feedback-form">
                <div class="form-group">
                    <label class="form-label">Feedback Title</label>
                    <input type="text" class="form-input" id="feedback-title" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <select class="form-select" id="feedback-category" required>
                        <option value="">Select category</option>
                        <option value="usability">Usability</option>
                        <option value="feature_request">Feature Request</option>
                        <option value="general">General</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Rating (1-5)</label>
                    <select class="form-select" id="feedback-rating" required>
                        <option value="">Select rating</option>
                        <option value="1">1 - Poor</option>
                        <option value="2">2 - Fair</option>
                        <option value="3">3 - Good</option>
                        <option value="4">4 - Very Good</option>
                        <option value="5">5 - Excellent</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Feedback</label>
                    <textarea class="form-textarea" id="feedback-content" required></textarea>
                </div>
                <div class="form-group">
                    <button type="submit" class="btn btn-primary">Submit Feedback</button>
                </div>
            </form>
        </div>
        """

    def _get_tester_interface_javascript(self) -> str:
        """Get JavaScript for tester interface."""
        return """
        <script>
        function startTest(testId) {
            console.log('Starting test:', testId);
            // Implementation would start test execution
            alert('Test started: ' + testId);
        }

        function viewTestDetails(testId) {
            console.log('Viewing test details:', testId);
            // Implementation would show test details
            alert('Test details: ' + testId);
        }

        // Bug report form handler
        document.getElementById('bug-report-form').addEventListener('submit', function(e) {
            e.preventDefault();

            const bugData = {
                title: document.getElementById('bug-title').value,
                severity: document.getElementById('bug-severity').value,
                category: document.getElementById('bug-category').value,
                description: document.getElementById('bug-description').value
            };

            console.log('Bug report submitted:', bugData);
            alert('Bug report submitted successfully!');

            // Reset form
            this.reset();
        });

        // Feedback form handler
        document.getElementById('feedback-form').addEventListener('submit', function(e) {
            e.preventDefault();

            const feedbackData = {
                title: document.getElementById('feedback-title').value,
                category: document.getElementById('feedback-category').value,
                rating: document.getElementById('feedback-rating').value,
                content: document.getElementById('feedback-content').value
            };

            console.log('Feedback submitted:', feedbackData);
            alert('Feedback submitted successfully!');

            // Reset form
            this.reset();
        });
        </script>
        """

    def _load_testing_data(self):
        """Load testing data from storage."""
        try:
            # Load testers
            testers_file = self.storage_path / "testers.json"
            if testers_file.exists():
                with open(testers_file, "r") as f:
                    testers_data = json.load(f)
                    for tester_id, tester_data in testers_data.items():
                        # Convert timestamp strings back to datetime
                        if tester_data.get("joined_date"):
                            tester_data["joined_date"] = datetime.fromisoformat(
                                tester_data["joined_date"]
                            )
                        if tester_data.get("last_activity"):
                            tester_data["last_activity"] = datetime.fromisoformat(
                                tester_data["last_activity"]
                            )

                        self.testers[tester_id] = BetaTester(**tester_data)

            # Load test cases
            test_cases_file = self.storage_path / "test_cases.json"
            if test_cases_file.exists():
                with open(test_cases_file, "r") as f:
                    test_cases_data = json.load(f)
                    for test_id, test_data in test_cases_data.items():
                        # Convert timestamp strings back to datetime
                        if test_data.get("created_date"):
                            test_data["created_date"] = datetime.fromisoformat(
                                test_data["created_date"]
                            )
                        if test_data.get("completion_date"):
                            test_data["completion_date"] = datetime.fromisoformat(
                                test_data["completion_date"]
                            )

                        self.test_cases[test_id] = TestCase(**test_data)

            # Load other data files similarly...

            logger.info("Loaded testing data from storage")

        except Exception as e:
            logger.error(f"Failed to load testing data: {e}")

    def _save_testing_data(self):
        """Save testing data to storage."""
        try:
            # Save testers
            testers_file = self.storage_path / "testers.json"
            with open(testers_file, "w") as f:
                testers_data = {
                    tid: tester.to_dict() for tid, tester in self.testers.items()
                }
                json.dump(testers_data, f, indent=2)

            # Save test cases
            test_cases_file = self.storage_path / "test_cases.json"
            with open(test_cases_file, "w") as f:
                test_cases_data = {
                    tid: test_case.to_dict()
                    for tid, test_case in self.test_cases.items()
                }
                json.dump(test_cases_data, f, indent=2)

            # Save test results
            test_results_file = self.storage_path / "test_results.json"
            with open(test_results_file, "w") as f:
                test_results_data = {
                    rid: result.to_dict() for rid, result in self.test_results.items()
                }
                json.dump(test_results_data, f, indent=2)

            # Save bug reports
            bug_reports_file = self.storage_path / "bug_reports.json"
            with open(bug_reports_file, "w") as f:
                bug_reports_data = {
                    bid: bug.to_dict() for bid, bug in self.bug_reports.items()
                }
                json.dump(bug_reports_data, f, indent=2)

            # Save feedback reports
            feedback_reports_file = self.storage_path / "feedback_reports.json"
            with open(feedback_reports_file, "w") as f:
                feedback_reports_data = {
                    fid: feedback.to_dict()
                    for fid, feedback in self.feedback_reports.items()
                }
                json.dump(feedback_reports_data, f, indent=2)

            logger.debug("Saved testing data to storage")

        except Exception as e:
            logger.error(f"Failed to save testing data: {e}")
