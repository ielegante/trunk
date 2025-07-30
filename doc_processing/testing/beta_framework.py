"""Beta testing framework for document processing functionality."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BetaUser:
    """Represents a beta testing user."""

    user_id: str
    email: str
    organization: str
    user_type: str  # legal_professional, law_student, firm_admin
    experience_level: str  # beginner, intermediate, advanced
    consent_date: datetime
    testing_groups: List[str]
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["consent_date"] = self.consent_date.isoformat()
        return data


@dataclass
class TestingScenario:
    """Represents a testing scenario for beta users."""

    scenario_id: str
    name: str
    description: str
    category: str  # conversion, permissions, templates, references
    complexity_level: str  # simple, medium, complex
    expected_duration_minutes: int
    prerequisites: List[str]
    success_criteria: List[str]
    test_data_files: List[str]
    instructions: str
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class TestSession:
    """Represents a beta testing session."""

    session_id: str
    user_id: str
    scenario_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "in_progress"  # in_progress, completed, abandoned, failed
    completion_percentage: float = 0.0
    errors_encountered: List[str] = None
    performance_metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.errors_encountered is None:
            self.errors_encountered = []
        if self.performance_metrics is None:
            self.performance_metrics = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        return data


class BetaTestingFramework:
    """Framework for coordinating beta testing activities."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize beta testing framework.

        Args:
            data_dir: Directory to store testing data
        """
        self.data_dir = data_dir or Path(".trunk/beta_testing")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.users_file = self.data_dir / "beta_users.json"
        self.scenarios_file = self.data_dir / "testing_scenarios.json"
        self.sessions_file = self.data_dir / "test_sessions.json"

        self.beta_users = self._load_beta_users()
        self.testing_scenarios = self._load_testing_scenarios()
        self.test_sessions = self._load_test_sessions()

        self._initialize_default_scenarios()

    def _load_beta_users(self) -> Dict[str, BetaUser]:
        """Load beta users from storage."""
        if not self.users_file.exists():
            return {}

        try:
            with open(self.users_file, "r") as f:
                data = json.load(f)

            users = {}
            for user_id, user_data in data.items():
                user_data["consent_date"] = datetime.fromisoformat(
                    user_data["consent_date"]
                )
                users[user_id] = BetaUser(**user_data)

            return users
        except Exception as e:
            logger.error(f"Failed to load beta users: {e}")
            return {}

    def _load_testing_scenarios(self) -> Dict[str, TestingScenario]:
        """Load testing scenarios from storage."""
        if not self.scenarios_file.exists():
            return {}

        try:
            with open(self.scenarios_file, "r") as f:
                data = json.load(f)

            scenarios = {}
            for scenario_id, scenario_data in data.items():
                scenarios[scenario_id] = TestingScenario(**scenario_data)

            return scenarios
        except Exception as e:
            logger.error(f"Failed to load testing scenarios: {e}")
            return {}

    def _load_test_sessions(self) -> Dict[str, TestSession]:
        """Load test sessions from storage."""
        if not self.sessions_file.exists():
            return {}

        try:
            with open(self.sessions_file, "r") as f:
                data = json.load(f)

            sessions = {}
            for session_id, session_data in data.items():
                session_data["start_time"] = datetime.fromisoformat(
                    session_data["start_time"]
                )
                if session_data["end_time"]:
                    session_data["end_time"] = datetime.fromisoformat(
                        session_data["end_time"]
                    )
                sessions[session_id] = TestSession(**session_data)

            return sessions
        except Exception as e:
            logger.error(f"Failed to load test sessions: {e}")
            return {}

    def _save_beta_users(self):
        """Save beta users to storage."""
        try:
            data = {
                user_id: user.to_dict() for user_id, user in self.beta_users.items()
            }
            with open(self.users_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save beta users: {e}")

    def _save_testing_scenarios(self):
        """Save testing scenarios to storage."""
        try:
            data = {
                scenario_id: scenario.to_dict()
                for scenario_id, scenario in self.testing_scenarios.items()
            }
            with open(self.scenarios_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save testing scenarios: {e}")

    def _save_test_sessions(self):
        """Save test sessions to storage."""
        try:
            data = {
                session_id: session.to_dict()
                for session_id, session in self.test_sessions.items()
            }
            with open(self.sessions_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save test sessions: {e}")

    def _initialize_default_scenarios(self):
        """Initialize default testing scenarios if none exist."""
        if self.testing_scenarios:
            return

        default_scenarios = [
            TestingScenario(
                scenario_id="google_docs_basic",
                name="Basic Google Docs Conversion",
                description="Convert a simple Google Docs document to text and back",
                category="conversion",
                complexity_level="simple",
                expected_duration_minutes=10,
                prerequisites=["google_account"],
                success_criteria=[
                    "Document converts without errors",
                    "Round-trip conversion preserves content",
                    "Formatting is maintained",
                ],
                test_data_files=["sample_legal_memo.gdoc"],
                instructions="1. Open the provided Google Docs document\n2. Use Trunk to convert to text\n3. Convert back to Google Docs\n4. Verify content accuracy",
            ),
            TestingScenario(
                scenario_id="permission_sync_basic",
                name="Basic Permission Synchronization",
                description="Test Google Drive permission sync with git repository",
                category="permissions",
                complexity_level="medium",
                expected_duration_minutes=15,
                prerequisites=["google_drive_admin", "git_repository"],
                success_criteria=[
                    "Drive permissions are accurately mapped",
                    "Git repository access matches Drive access",
                    "Permission changes sync in real-time",
                ],
                test_data_files=["shared_contract.gdoc"],
                instructions="1. Share Google Drive document with team\n2. Sync permissions to git\n3. Verify team access levels\n4. Change permissions and verify sync",
            ),
            TestingScenario(
                scenario_id="template_redaction",
                name="Template Creation with Redaction",
                description="Create template from document with sensitive information redaction",
                category="templates",
                complexity_level="complex",
                expected_duration_minutes=20,
                prerequisites=["legal_document", "redaction_training"],
                success_criteria=[
                    "Sensitive information is correctly identified",
                    "Redaction process is user-friendly",
                    "Template is reusable",
                    "Confidentiality is maintained",
                ],
                test_data_files=["confidential_contract.docx"],
                instructions="1. Upload confidential legal document\n2. Use redaction tools to mark sensitive data\n3. Create template from redacted version\n4. Test template with new data",
            ),
        ]

        for scenario in default_scenarios:
            self.testing_scenarios[scenario.scenario_id] = scenario

        self._save_testing_scenarios()
        logger.info(f"Initialized {len(default_scenarios)} default testing scenarios")

    def register_beta_user(self, user_data: Dict[str, Any]) -> str:
        """Register a new beta testing user.

        Args:
            user_data: User information dictionary

        Returns:
            User ID for the registered user
        """
        user_id = f"beta_{len(self.beta_users) + 1:04d}"

        beta_user = BetaUser(
            user_id=user_id,
            email=user_data["email"],
            organization=user_data.get("organization", ""),
            user_type=user_data.get("user_type", "legal_professional"),
            experience_level=user_data.get("experience_level", "intermediate"),
            consent_date=datetime.now(),
            testing_groups=user_data.get("testing_groups", ["general"]),
        )

        self.beta_users[user_id] = beta_user
        self._save_beta_users()

        logger.info(f"Registered new beta user: {user_id} ({beta_user.email})")
        return user_id

    def get_scenarios_for_user(self, user_id: str) -> List[TestingScenario]:
        """Get appropriate testing scenarios for a user.

        Args:
            user_id: Beta user ID

        Returns:
            List of testing scenarios suitable for the user
        """
        if user_id not in self.beta_users:
            return []

        user = self.beta_users[user_id]
        suitable_scenarios = []

        for scenario in self.testing_scenarios.values():
            if not scenario.is_active:
                continue

            # Filter by user experience level
            if (
                user.experience_level == "beginner"
                and scenario.complexity_level == "complex"
            ):
                continue

            # Filter by user type (legal professionals get all scenarios)
            if user.user_type == "law_student" and scenario.category == "permissions":
                continue

            suitable_scenarios.append(scenario)

        return suitable_scenarios

    def start_test_session(self, user_id: str, scenario_id: str) -> str:
        """Start a new testing session.

        Args:
            user_id: Beta user ID
            scenario_id: Testing scenario ID

        Returns:
            Session ID for the new session
        """
        if user_id not in self.beta_users:
            raise ValueError(f"User {user_id} not found")

        if scenario_id not in self.testing_scenarios:
            raise ValueError(f"Scenario {scenario_id} not found")

        session_id = f"session_{len(self.test_sessions) + 1:06d}"

        session = TestSession(
            session_id=session_id,
            user_id=user_id,
            scenario_id=scenario_id,
            start_time=datetime.now(),
        )

        self.test_sessions[session_id] = session
        self._save_test_sessions()

        logger.info(f"Started test session: {session_id} for user {user_id}")
        return session_id

    def update_session_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """Update progress for a testing session.

        Args:
            session_id: Session ID
            progress_data: Progress update data
        """
        if session_id not in self.test_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.test_sessions[session_id]

        if "completion_percentage" in progress_data:
            session.completion_percentage = progress_data["completion_percentage"]

        if "errors" in progress_data:
            session.errors_encountered.extend(progress_data["errors"])

        if "performance_metrics" in progress_data:
            session.performance_metrics.update(progress_data["performance_metrics"])

        self._save_test_sessions()

        logger.debug(f"Updated session {session_id} progress: {progress_data}")

    def complete_test_session(self, session_id: str, completion_data: Dict[str, Any]):
        """Complete a testing session.

        Args:
            session_id: Session ID
            completion_data: Session completion data
        """
        if session_id not in self.test_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.test_sessions[session_id]
        session.end_time = datetime.now()
        session.status = completion_data.get("status", "completed")
        session.completion_percentage = completion_data.get(
            "completion_percentage", 100.0
        )

        if "final_errors" in completion_data:
            session.errors_encountered.extend(completion_data["final_errors"])

        if "final_metrics" in completion_data:
            session.performance_metrics.update(completion_data["final_metrics"])

        self._save_test_sessions()

        logger.info(f"Completed test session: {session_id}")

    def get_testing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive testing statistics.

        Returns:
            Dictionary with testing statistics
        """
        stats = {
            "total_users": len(self.beta_users),
            "active_users": len([u for u in self.beta_users.values() if u.is_active]),
            "total_scenarios": len(self.testing_scenarios),
            "active_scenarios": len(
                [s for s in self.testing_scenarios.values() if s.is_active]
            ),
            "total_sessions": len(self.test_sessions),
            "completed_sessions": len(
                [s for s in self.test_sessions.values() if s.status == "completed"]
            ),
            "success_rate": 0.0,
            "average_completion_time": 0.0,
            "user_distribution": {},
            "scenario_completion_rates": {},
            "common_errors": [],
        }

        # Calculate success rate
        completed_sessions = [
            s for s in self.test_sessions.values() if s.status == "completed"
        ]
        if self.test_sessions:
            stats["success_rate"] = len(completed_sessions) / len(self.test_sessions)

        # Calculate average completion time
        if completed_sessions:
            total_time = sum(
                (s.end_time - s.start_time).total_seconds() / 60
                for s in completed_sessions
                if s.end_time
            )
            stats["average_completion_time"] = total_time / len(completed_sessions)

        # User distribution by type
        user_types = {}
        for user in self.beta_users.values():
            user_types[user.user_type] = user_types.get(user.user_type, 0) + 1
        stats["user_distribution"] = user_types

        # Scenario completion rates
        scenario_stats = {}
        for scenario_id in self.testing_scenarios.keys():
            scenario_sessions = [
                s for s in self.test_sessions.values() if s.scenario_id == scenario_id
            ]
            completed = len([s for s in scenario_sessions if s.status == "completed"])
            scenario_stats[scenario_id] = {
                "total_attempts": len(scenario_sessions),
                "completed": completed,
                "success_rate": (
                    completed / len(scenario_sessions) if scenario_sessions else 0.0
                ),
            }
        stats["scenario_completion_rates"] = scenario_stats

        # Common errors
        all_errors = []
        for session in self.test_sessions.values():
            all_errors.extend(session.errors_encountered)

        error_counts = {}
        for error in all_errors:
            error_counts[error] = error_counts.get(error, 0) + 1

        stats["common_errors"] = sorted(
            error_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return stats
