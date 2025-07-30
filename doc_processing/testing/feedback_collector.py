"""User feedback collection system for beta testing program."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """Represents a single feedback entry from a beta user."""

    feedback_id: str
    user_id: str
    session_id: Optional[str]
    scenario_id: Optional[str]
    feedback_type: str  # bug_report, feature_request, usability, performance, general
    severity: str  # low, medium, high, critical
    title: str
    description: str
    steps_to_reproduce: List[str]
    expected_behavior: str
    actual_behavior: str
    browser_info: Dict[str, Any]
    system_info: Dict[str, Any]
    attachments: List[str]
    timestamp: datetime
    status: str = "new"  # new, reviewed, in_progress, resolved, closed
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class UserSatisfactionSurvey:
    """Represents a user satisfaction survey response."""

    survey_id: str
    user_id: str
    session_id: Optional[str]
    overall_satisfaction: int  # 1-5 scale
    ease_of_use: int  # 1-5 scale
    feature_completeness: int  # 1-5 scale
    performance_rating: int  # 1-5 scale
    likelihood_to_recommend: int  # 1-10 scale (NPS)
    most_valuable_feature: str
    least_valuable_feature: str
    missing_features: List[str]
    improvement_suggestions: List[str]
    additional_comments: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class UsabilityMetrics:
    """Represents usability metrics collected during testing."""

    metrics_id: str
    user_id: str
    session_id: str
    scenario_id: str
    task_completion_time: float  # seconds
    click_count: int
    error_count: int
    help_requests: int
    successful_completion: bool
    user_frustration_indicators: List[str]
    navigation_path: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class FeedbackCollector:
    """System for collecting and managing user feedback during beta testing."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize feedback collector.

        Args:
            data_dir: Directory to store feedback data
        """
        self.data_dir = data_dir or Path(".trunk/feedback")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.feedback_file = self.data_dir / "feedback_entries.json"
        self.surveys_file = self.data_dir / "satisfaction_surveys.json"
        self.metrics_file = self.data_dir / "usability_metrics.json"

        self.feedback_entries = self._load_feedback_entries()
        self.satisfaction_surveys = self._load_satisfaction_surveys()
        self.usability_metrics = self._load_usability_metrics()

    def _load_feedback_entries(self) -> Dict[str, FeedbackEntry]:
        """Load feedback entries from storage."""
        if not self.feedback_file.exists():
            return {}

        try:
            with open(self.feedback_file, "r") as f:
                data = json.load(f)

            entries = {}
            for entry_id, entry_data in data.items():
                entry_data["timestamp"] = datetime.fromisoformat(
                    entry_data["timestamp"]
                )
                entries[entry_id] = FeedbackEntry(**entry_data)

            return entries
        except Exception as e:
            logger.error(f"Failed to load feedback entries: {e}")
            return {}

    def _load_satisfaction_surveys(self) -> Dict[str, UserSatisfactionSurvey]:
        """Load satisfaction surveys from storage."""
        if not self.surveys_file.exists():
            return {}

        try:
            with open(self.surveys_file, "r") as f:
                data = json.load(f)

            surveys = {}
            for survey_id, survey_data in data.items():
                survey_data["timestamp"] = datetime.fromisoformat(
                    survey_data["timestamp"]
                )
                surveys[survey_id] = UserSatisfactionSurvey(**survey_data)

            return surveys
        except Exception as e:
            logger.error(f"Failed to load satisfaction surveys: {e}")
            return {}

    def _load_usability_metrics(self) -> Dict[str, UsabilityMetrics]:
        """Load usability metrics from storage."""
        if not self.metrics_file.exists():
            return {}

        try:
            with open(self.metrics_file, "r") as f:
                data = json.load(f)

            metrics = {}
            for metrics_id, metrics_data in data.items():
                metrics_data["timestamp"] = datetime.fromisoformat(
                    metrics_data["timestamp"]
                )
                metrics[metrics_id] = UsabilityMetrics(**metrics_data)

            return metrics
        except Exception as e:
            logger.error(f"Failed to load usability metrics: {e}")
            return {}

    def _save_feedback_entries(self):
        """Save feedback entries to storage."""
        try:
            data = {
                entry_id: entry.to_dict()
                for entry_id, entry in self.feedback_entries.items()
            }
            with open(self.feedback_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save feedback entries: {e}")

    def _save_satisfaction_surveys(self):
        """Save satisfaction surveys to storage."""
        try:
            data = {
                survey_id: survey.to_dict()
                for survey_id, survey in self.satisfaction_surveys.items()
            }
            with open(self.surveys_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save satisfaction surveys: {e}")

    def _save_usability_metrics(self):
        """Save usability metrics to storage."""
        try:
            data = {
                metrics_id: metrics.to_dict()
                for metrics_id, metrics in self.usability_metrics.items()
            }
            with open(self.metrics_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usability metrics: {e}")

    def submit_feedback(self, feedback_data: Dict[str, Any]) -> str:
        """Submit new feedback from a beta user.

        Args:
            feedback_data: Feedback information

        Returns:
            Feedback ID for the new entry
        """
        feedback_id = f"feedback_{len(self.feedback_entries) + 1:06d}"

        feedback_entry = FeedbackEntry(
            feedback_id=feedback_id,
            user_id=feedback_data["user_id"],
            session_id=feedback_data.get("session_id"),
            scenario_id=feedback_data.get("scenario_id"),
            feedback_type=feedback_data["feedback_type"],
            severity=feedback_data.get("severity", "medium"),
            title=feedback_data["title"],
            description=feedback_data["description"],
            steps_to_reproduce=feedback_data.get("steps_to_reproduce", []),
            expected_behavior=feedback_data.get("expected_behavior", ""),
            actual_behavior=feedback_data.get("actual_behavior", ""),
            browser_info=feedback_data.get("browser_info", {}),
            system_info=feedback_data.get("system_info", {}),
            attachments=feedback_data.get("attachments", []),
            timestamp=datetime.now(),
            tags=feedback_data.get("tags", []),
        )

        self.feedback_entries[feedback_id] = feedback_entry
        self._save_feedback_entries()

        logger.info(
            f"Submitted feedback: {feedback_id} from user {feedback_data['user_id']}"
        )
        return feedback_id

    def submit_satisfaction_survey(self, survey_data: Dict[str, Any]) -> str:
        """Submit satisfaction survey response.

        Args:
            survey_data: Survey response data

        Returns:
            Survey ID for the new response
        """
        survey_id = f"survey_{len(self.satisfaction_surveys) + 1:06d}"

        survey = UserSatisfactionSurvey(
            survey_id=survey_id,
            user_id=survey_data["user_id"],
            session_id=survey_data.get("session_id"),
            overall_satisfaction=survey_data["overall_satisfaction"],
            ease_of_use=survey_data["ease_of_use"],
            feature_completeness=survey_data["feature_completeness"],
            performance_rating=survey_data["performance_rating"],
            likelihood_to_recommend=survey_data["likelihood_to_recommend"],
            most_valuable_feature=survey_data.get("most_valuable_feature", ""),
            least_valuable_feature=survey_data.get("least_valuable_feature", ""),
            missing_features=survey_data.get("missing_features", []),
            improvement_suggestions=survey_data.get("improvement_suggestions", []),
            additional_comments=survey_data.get("additional_comments", ""),
            timestamp=datetime.now(),
        )

        self.satisfaction_surveys[survey_id] = survey
        self._save_satisfaction_surveys()

        logger.info(
            f"Submitted satisfaction survey: {survey_id} from user {survey_data['user_id']}"
        )
        return survey_id

    def record_usability_metrics(self, metrics_data: Dict[str, Any]) -> str:
        """Record usability metrics for a testing session.

        Args:
            metrics_data: Usability metrics data

        Returns:
            Metrics ID for the new record
        """
        metrics_id = f"metrics_{len(self.usability_metrics) + 1:06d}"

        metrics = UsabilityMetrics(
            metrics_id=metrics_id,
            user_id=metrics_data["user_id"],
            session_id=metrics_data["session_id"],
            scenario_id=metrics_data["scenario_id"],
            task_completion_time=metrics_data["task_completion_time"],
            click_count=metrics_data.get("click_count", 0),
            error_count=metrics_data.get("error_count", 0),
            help_requests=metrics_data.get("help_requests", 0),
            successful_completion=metrics_data.get("successful_completion", False),
            user_frustration_indicators=metrics_data.get(
                "user_frustration_indicators", []
            ),
            navigation_path=metrics_data.get("navigation_path", []),
            timestamp=datetime.now(),
        )

        self.usability_metrics[metrics_id] = metrics
        self._save_usability_metrics()

        logger.info(
            f"Recorded usability metrics: {metrics_id} for session {metrics_data['session_id']}"
        )
        return metrics_id

    def get_feedback_by_type(self, feedback_type: str) -> List[FeedbackEntry]:
        """Get feedback entries by type.

        Args:
            feedback_type: Type of feedback to retrieve

        Returns:
            List of feedback entries of the specified type
        """
        return [
            entry
            for entry in self.feedback_entries.values()
            if entry.feedback_type == feedback_type
        ]

    def get_feedback_by_severity(self, severity: str) -> List[FeedbackEntry]:
        """Get feedback entries by severity.

        Args:
            severity: Severity level to filter by

        Returns:
            List of feedback entries with the specified severity
        """
        return [
            entry
            for entry in self.feedback_entries.values()
            if entry.severity == severity
        ]

    def get_high_priority_feedback(self) -> List[FeedbackEntry]:
        """Get high priority feedback requiring immediate attention.

        Returns:
            List of high priority feedback entries
        """
        high_priority = []
        for entry in self.feedback_entries.values():
            if (
                entry.severity in ["high", "critical"]
                or entry.feedback_type == "bug_report"
                or entry.status == "new"
            ):
                high_priority.append(entry)

        return sorted(high_priority, key=lambda x: x.timestamp, reverse=True)

    def update_feedback_status(
        self, feedback_id: str, new_status: str, notes: str = ""
    ):
        """Update the status of a feedback entry.

        Args:
            feedback_id: ID of the feedback entry
            new_status: New status value
            notes: Optional notes about the status change
        """
        if feedback_id not in self.feedback_entries:
            raise ValueError(f"Feedback {feedback_id} not found")

        self.feedback_entries[feedback_id].status = new_status
        if notes:
            self.feedback_entries[feedback_id].tags.append(f"status_update: {notes}")

        self._save_feedback_entries()
        logger.info(f"Updated feedback {feedback_id} status to {new_status}")

    def get_satisfaction_trends(self) -> Dict[str, Any]:
        """Get satisfaction trends and analytics.

        Returns:
            Dictionary with satisfaction trends and metrics
        """
        if not self.satisfaction_surveys:
            return {"error": "No satisfaction surveys available"}

        surveys = list(self.satisfaction_surveys.values())

        # Calculate averages
        avg_satisfaction = sum(s.overall_satisfaction for s in surveys) / len(surveys)
        avg_ease_of_use = sum(s.ease_of_use for s in surveys) / len(surveys)
        avg_feature_completeness = sum(s.feature_completeness for s in surveys) / len(
            surveys
        )
        avg_performance = sum(s.performance_rating for s in surveys) / len(surveys)
        avg_nps = sum(s.likelihood_to_recommend for s in surveys) / len(surveys)

        # Calculate NPS score
        promoters = len([s for s in surveys if s.likelihood_to_recommend >= 9])
        detractors = len([s for s in surveys if s.likelihood_to_recommend <= 6])
        nps_score = ((promoters - detractors) / len(surveys)) * 100

        # Most mentioned features
        valuable_features = {}
        for survey in surveys:
            if survey.most_valuable_feature:
                valuable_features[survey.most_valuable_feature] = (
                    valuable_features.get(survey.most_valuable_feature, 0) + 1
                )

        # Most requested improvements
        improvement_requests = {}
        for survey in surveys:
            for suggestion in survey.improvement_suggestions:
                improvement_requests[suggestion] = (
                    improvement_requests.get(suggestion, 0) + 1
                )

        return {
            "survey_count": len(surveys),
            "averages": {
                "overall_satisfaction": avg_satisfaction,
                "ease_of_use": avg_ease_of_use,
                "feature_completeness": avg_feature_completeness,
                "performance_rating": avg_performance,
                "nps_score": nps_score,
            },
            "nps_breakdown": {
                "promoters": promoters,
                "passives": len(surveys) - promoters - detractors,
                "detractors": detractors,
            },
            "top_valuable_features": sorted(
                valuable_features.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "top_improvement_requests": sorted(
                improvement_requests.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def get_usability_analytics(self) -> Dict[str, Any]:
        """Get usability analytics and metrics.

        Returns:
            Dictionary with usability analytics
        """
        if not self.usability_metrics:
            return {"error": "No usability metrics available"}

        metrics = list(self.usability_metrics.values())

        # Calculate averages
        avg_completion_time = sum(m.task_completion_time for m in metrics) / len(
            metrics
        )
        avg_click_count = sum(m.click_count for m in metrics) / len(metrics)
        avg_error_count = sum(m.error_count for m in metrics) / len(metrics)
        success_rate = len([m for m in metrics if m.successful_completion]) / len(
            metrics
        )

        # Group by scenario
        scenario_metrics = {}
        for metric in metrics:
            if metric.scenario_id not in scenario_metrics:
                scenario_metrics[metric.scenario_id] = []
            scenario_metrics[metric.scenario_id].append(metric)

        scenario_analytics = {}
        for scenario_id, scenario_metrics_list in scenario_metrics.items():
            scenario_analytics[scenario_id] = {
                "attempts": len(scenario_metrics_list),
                "success_rate": len(
                    [m for m in scenario_metrics_list if m.successful_completion]
                )
                / len(scenario_metrics_list),
                "avg_completion_time": sum(
                    m.task_completion_time for m in scenario_metrics_list
                )
                / len(scenario_metrics_list),
                "avg_errors": sum(m.error_count for m in scenario_metrics_list)
                / len(scenario_metrics_list),
            }

        # Common frustration indicators
        frustration_indicators = {}
        for metric in metrics:
            for indicator in metric.user_frustration_indicators:
                frustration_indicators[indicator] = (
                    frustration_indicators.get(indicator, 0) + 1
                )

        return {
            "metrics_count": len(metrics),
            "overall_averages": {
                "task_completion_time": avg_completion_time,
                "click_count": avg_click_count,
                "error_count": avg_error_count,
                "success_rate": success_rate,
            },
            "scenario_performance": scenario_analytics,
            "common_frustration_indicators": sorted(
                frustration_indicators.items(), key=lambda x: x[1], reverse=True
            ),
        }

    def generate_feedback_report(self) -> Dict[str, Any]:
        """Generate comprehensive feedback report.

        Returns:
            Dictionary with complete feedback analysis
        """
        report = {
            "report_generated": datetime.now().isoformat(),
            "feedback_summary": {
                "total_feedback_entries": len(self.feedback_entries),
                "by_type": {},
                "by_severity": {},
                "by_status": {},
            },
            "satisfaction_trends": self.get_satisfaction_trends(),
            "usability_analytics": self.get_usability_analytics(),
            "high_priority_issues": len(self.get_high_priority_feedback()),
            "recommendations": [],
        }

        # Feedback breakdown
        for entry in self.feedback_entries.values():
            report["feedback_summary"]["by_type"][entry.feedback_type] = (
                report["feedback_summary"]["by_type"].get(entry.feedback_type, 0) + 1
            )
            report["feedback_summary"]["by_severity"][entry.severity] = (
                report["feedback_summary"]["by_severity"].get(entry.severity, 0) + 1
            )
            report["feedback_summary"]["by_status"][entry.status] = (
                report["feedback_summary"]["by_status"].get(entry.status, 0) + 1
            )

        # Generate recommendations
        recommendations = []

        # High priority issues
        critical_issues = len(
            [e for e in self.feedback_entries.values() if e.severity == "critical"]
        )
        if critical_issues > 0:
            recommendations.append(
                f"Address {critical_issues} critical issues immediately"
            )

        # Low satisfaction scores
        satisfaction_trends = report["satisfaction_trends"]
        if (
            not isinstance(satisfaction_trends, dict)
            or "averages" not in satisfaction_trends
        ):
            recommendations.append("Collect more satisfaction survey data")
        else:
            avg_satisfaction = satisfaction_trends["averages"]["overall_satisfaction"]
            if avg_satisfaction < 3.0:
                recommendations.append(
                    "Overall satisfaction is low - investigate major pain points"
                )

            nps_score = satisfaction_trends["averages"]["nps_score"]
            if nps_score < 0:
                recommendations.append(
                    "NPS score is negative - focus on user experience improvements"
                )

        # Usability issues
        usability_analytics = report["usability_analytics"]
        if (
            not isinstance(usability_analytics, dict)
            or "overall_averages" not in usability_analytics
        ):
            recommendations.append("Collect more usability metrics data")
        else:
            success_rate = usability_analytics["overall_averages"]["success_rate"]
            if success_rate < 0.8:
                recommendations.append(
                    "Task success rate is low - simplify user workflows"
                )

            avg_errors = usability_analytics["overall_averages"]["error_count"]
            if avg_errors > 2:
                recommendations.append(
                    "High error rate detected - improve error handling and user guidance"
                )

        report["recommendations"] = recommendations

        return report
