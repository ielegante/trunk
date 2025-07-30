"""Testing analytics and data pipeline for beta testing program."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TestingInsight:
    """Represents an analytical insight from testing data."""

    insight_id: str
    insight_type: str  # trend, anomaly, recommendation, alert
    title: str
    description: str
    confidence_score: float  # 0.0 to 1.0
    impact_level: str  # low, medium, high, critical
    data_sources: List[str]
    metrics_supporting: Dict[str, Any]
    recommended_actions: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class TestingAnalytics:
    """Advanced analytics system for beta testing data."""

    def __init__(
        self, beta_framework, feedback_collector, data_dir: Optional[Path] = None
    ):
        """Initialize testing analytics.

        Args:
            beta_framework: BetaTestingFramework instance
            feedback_collector: FeedbackCollector instance
            data_dir: Directory for analytics data
        """
        self.beta_framework = beta_framework
        self.feedback_collector = feedback_collector
        self.data_dir = data_dir or Path(".trunk/analytics")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.insights_file = self.data_dir / "testing_insights.json"
        self.reports_dir = self.data_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        self.testing_insights = self._load_testing_insights()

    def _load_testing_insights(self) -> Dict[str, TestingInsight]:
        """Load testing insights from storage."""
        if not self.insights_file.exists():
            return {}

        try:
            with open(self.insights_file, "r") as f:
                data = json.load(f)

            insights = {}
            for insight_id, insight_data in data.items():
                insight_data["timestamp"] = datetime.fromisoformat(
                    insight_data["timestamp"]
                )
                insights[insight_id] = TestingInsight(**insight_data)

            return insights
        except Exception as e:
            logger.error(f"Failed to load testing insights: {e}")
            return {}

    def _save_testing_insights(self):
        """Save testing insights to storage."""
        try:
            data = {
                insight_id: insight.to_dict()
                for insight_id, insight in self.testing_insights.items()
            }
            with open(self.insights_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save testing insights: {e}")

    def analyze_user_behavior_patterns(self) -> Dict[str, Any]:
        """Analyze user behavior patterns from testing sessions.

        Returns:
            Dictionary with behavior pattern analysis
        """
        sessions = list(self.beta_framework.test_sessions.values())
        if not sessions:
            return {"error": "No testing sessions available"}

        # Convert to DataFrame for analysis
        session_data = []
        for session in sessions:
            session_data.append(
                {
                    "user_id": session.user_id,
                    "scenario_id": session.scenario_id,
                    "status": session.status,
                    "completion_percentage": session.completion_percentage,
                    "duration_minutes": (
                        (session.end_time - session.start_time).total_seconds() / 60
                        if session.end_time
                        else None
                    ),
                    "error_count": len(session.errors_encountered),
                    "start_hour": session.start_time.hour,
                    "day_of_week": session.start_time.weekday(),
                }
            )

        df = pd.DataFrame(session_data)

        analysis = {
            "session_patterns": {},
            "user_patterns": {},
            "temporal_patterns": {},
            "error_patterns": {},
        }

        # Session completion patterns
        analysis["session_patterns"] = {
            "completion_rate_by_scenario": df.groupby("scenario_id")[
                "completion_percentage"
            ]
            .mean()
            .to_dict(),
            "average_duration_by_scenario": df.groupby("scenario_id")[
                "duration_minutes"
            ]
            .mean()
            .to_dict(),
            "success_rate_by_scenario": df.groupby("scenario_id")
            .apply(lambda x: (x["status"] == "completed").mean())
            .to_dict(),
        }

        # User engagement patterns
        user_session_counts = df.groupby("user_id").size()
        analysis["user_patterns"] = {
            "sessions_per_user": user_session_counts.describe().to_dict(),
            "high_engagement_users": user_session_counts[
                user_session_counts > user_session_counts.quantile(0.8)
            ].index.tolist(),
            "low_engagement_users": user_session_counts[
                user_session_counts < user_session_counts.quantile(0.2)
            ].index.tolist(),
        }

        # Temporal patterns
        analysis["temporal_patterns"] = {
            "sessions_by_hour": df.groupby("start_hour").size().to_dict(),
            "sessions_by_day": df.groupby("day_of_week").size().to_dict(),
            "completion_rate_by_hour": df.groupby("start_hour")["completion_percentage"]
            .mean()
            .to_dict(),
        }

        # Error patterns
        analysis["error_patterns"] = {
            "average_errors_per_session": df["error_count"].mean(),
            "errors_by_scenario": df.groupby("scenario_id")["error_count"]
            .mean()
            .to_dict(),
            "error_correlation_with_completion": df[
                ["error_count", "completion_percentage"]
            ]
            .corr()
            .iloc[0, 1],
        }

        return analysis

    def detect_usability_issues(self) -> List[Dict[str, Any]]:
        """Detect usability issues from feedback and metrics data.

        Returns:
            List of detected usability issues
        """
        issues = []

        # Analyze feedback for usability issues
        usability_feedback = self.feedback_collector.get_feedback_by_type("usability")
        if usability_feedback:
            # Group by similar issues
            issue_clusters = {}
            for feedback in usability_feedback:
                key_words = set(feedback.title.lower().split())

                # Find similar issues
                similar_key = None
                for existing_key in issue_clusters.keys():
                    if len(key_words.intersection(set(existing_key.split()))) >= 2:
                        similar_key = existing_key
                        break

                if similar_key:
                    issue_clusters[similar_key].append(feedback)
                else:
                    issue_clusters[feedback.title.lower()] = [feedback]

            # Convert clusters to issues
            for cluster_name, cluster_feedback in issue_clusters.items():
                if len(cluster_feedback) >= 2:  # Multiple reports of same issue
                    issues.append(
                        {
                            "issue_type": "recurring_usability_problem",
                            "title": f"Recurring issue: {cluster_name}",
                            "severity": (
                                "high" if len(cluster_feedback) >= 3 else "medium"
                            ),
                            "report_count": len(cluster_feedback),
                            "affected_users": [f.user_id for f in cluster_feedback],
                            "common_patterns": [f.title for f in cluster_feedback],
                        }
                    )

        # Analyze usability metrics for issues
        usability_analytics = self.feedback_collector.get_usability_analytics()
        if (
            not isinstance(usability_analytics, dict)
            or "overall_averages" not in usability_analytics
        ):
            return issues

        overall_averages = usability_analytics["overall_averages"]

        # Check for high error rates
        if overall_averages["error_count"] > 3:
            issues.append(
                {
                    "issue_type": "high_error_rate",
                    "title": "High error rate detected across sessions",
                    "severity": "high",
                    "metrics": {"average_errors": overall_averages["error_count"]},
                    "description": "Users are encountering too many errors during testing sessions",
                }
            )

        # Check for low success rates
        if overall_averages["success_rate"] < 0.7:
            issues.append(
                {
                    "issue_type": "low_success_rate",
                    "title": "Low task completion success rate",
                    "severity": "critical",
                    "metrics": {"success_rate": overall_averages["success_rate"]},
                    "description": "Many users are unable to complete testing scenarios successfully",
                }
            )

        # Check for long completion times
        if overall_averages["task_completion_time"] > 600:  # 10 minutes
            issues.append(
                {
                    "issue_type": "long_completion_time",
                    "title": "Tasks taking too long to complete",
                    "severity": "medium",
                    "metrics": {
                        "avg_completion_time": overall_averages["task_completion_time"]
                    },
                    "description": "Users are taking longer than expected to complete testing tasks",
                }
            )

        # Check scenario-specific issues
        if "scenario_performance" in usability_analytics:
            for scenario_id, performance in usability_analytics[
                "scenario_performance"
            ].items():
                if performance["success_rate"] < 0.5:
                    issues.append(
                        {
                            "issue_type": "scenario_difficulty",
                            "title": f"Scenario {scenario_id} has low success rate",
                            "severity": "high",
                            "scenario_id": scenario_id,
                            "metrics": performance,
                            "description": f"Scenario {scenario_id} may be too difficult or poorly designed",
                        }
                    )

        return issues

    def generate_performance_trends(self, days: int = 30) -> Dict[str, Any]:
        """Generate performance trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance trend analysis
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Filter recent sessions
        recent_sessions = [
            session
            for session in self.beta_framework.test_sessions.values()
            if session.start_time >= cutoff_date
        ]

        if not recent_sessions:
            return {"error": "No recent sessions found"}

        # Group sessions by day
        daily_metrics = {}
        for session in recent_sessions:
            day_key = session.start_time.date().isoformat()
            if day_key not in daily_metrics:
                daily_metrics[day_key] = {
                    "sessions": [],
                    "total_sessions": 0,
                    "completed_sessions": 0,
                    "total_errors": 0,
                    "avg_completion_percentage": 0.0,
                }

            daily_metrics[day_key]["sessions"].append(session)
            daily_metrics[day_key]["total_sessions"] += 1
            if session.status == "completed":
                daily_metrics[day_key]["completed_sessions"] += 1
            daily_metrics[day_key]["total_errors"] += len(session.errors_encountered)

        # Calculate daily averages
        for day_data in daily_metrics.values():
            sessions = day_data["sessions"]
            day_data["completion_rate"] = (
                day_data["completed_sessions"] / day_data["total_sessions"]
            )
            day_data["avg_errors_per_session"] = (
                day_data["total_errors"] / day_data["total_sessions"]
            )
            day_data["avg_completion_percentage"] = sum(
                s.completion_percentage for s in sessions
            ) / len(sessions)

            # Remove sessions list to avoid JSON serialization issues
            del day_data["sessions"]

        # Calculate trends
        dates = sorted(daily_metrics.keys())
        completion_rates = [daily_metrics[date]["completion_rate"] for date in dates]
        error_rates = [daily_metrics[date]["avg_errors_per_session"] for date in dates]

        trends = {
            "daily_metrics": daily_metrics,
            "trend_analysis": {
                "completion_rate_trend": self._calculate_trend(completion_rates),
                "error_rate_trend": self._calculate_trend(error_rates),
                "overall_direction": (
                    "improving"
                    if self._calculate_trend(completion_rates) > 0
                    else "declining"
                ),
            },
            "period_summary": {
                "total_sessions": len(recent_sessions),
                "avg_completion_rate": sum(completion_rates) / len(completion_rates),
                "avg_error_rate": sum(error_rates) / len(error_rates),
                "best_day": max(
                    dates, key=lambda d: daily_metrics[d]["completion_rate"]
                ),
                "worst_day": min(
                    dates, key=lambda d: daily_metrics[d]["completion_rate"]
                ),
            },
        }

        return trends

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend direction from a list of values.

        Args:
            values: List of numeric values

        Returns:
            Trend value (positive = increasing, negative = decreasing)
        """
        if len(values) < 2:
            return 0.0

        # Simple linear trend calculation
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))

        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        return slope

    def generate_insights(self) -> List[TestingInsight]:
        """Generate analytical insights from testing data.

        Returns:
            List of new testing insights
        """
        new_insights = []

        # Analyze user behavior patterns
        behavior_analysis = self.analyze_user_behavior_patterns()
        if not isinstance(behavior_analysis, dict) or "error" in behavior_analysis:
            logger.warning("Cannot generate insights - insufficient behavior data")
            return new_insights

        # Insight: Low engagement users
        if "user_patterns" in behavior_analysis:
            low_engagement_users = behavior_analysis["user_patterns"].get(
                "low_engagement_users", []
            )
            if len(low_engagement_users) > 0:
                insight = TestingInsight(
                    insight_id=f"insight_{len(self.testing_insights) + 1:06d}",
                    insight_type="alert",
                    title="Low User Engagement Detected",
                    description=f"{len(low_engagement_users)} users have low engagement (few testing sessions)",
                    confidence_score=0.8,
                    impact_level="medium",
                    data_sources=["session_data"],
                    metrics_supporting={"low_engagement_users": low_engagement_users},
                    recommended_actions=[
                        "Reach out to low-engagement users for feedback",
                        "Simplify onboarding process",
                        "Provide more guidance for testing scenarios",
                    ],
                    timestamp=datetime.now(),
                )
                new_insights.append(insight)

        # Insight: Scenario difficulty
        if "session_patterns" in behavior_analysis:
            scenario_success_rates = behavior_analysis["session_patterns"].get(
                "success_rate_by_scenario", {}
            )
            difficult_scenarios = [
                scenario
                for scenario, rate in scenario_success_rates.items()
                if rate < 0.6
            ]

            if difficult_scenarios:
                insight = TestingInsight(
                    insight_id=f"insight_{len(self.testing_insights) + len(new_insights) + 1:06d}",
                    insight_type="recommendation",
                    title="Difficult Testing Scenarios Identified",
                    description=f"Scenarios with low success rates: {', '.join(difficult_scenarios)}",
                    confidence_score=0.9,
                    impact_level="high",
                    data_sources=["session_data"],
                    metrics_supporting={
                        "difficult_scenarios": {
                            s: scenario_success_rates[s] for s in difficult_scenarios
                        }
                    },
                    recommended_actions=[
                        "Review and simplify difficult scenarios",
                        "Provide additional guidance for complex tasks",
                        "Break down complex scenarios into smaller steps",
                    ],
                    timestamp=datetime.now(),
                )
                new_insights.append(insight)

        # Insight: Temporal patterns
        if "temporal_patterns" in behavior_analysis:
            peak_hours = behavior_analysis["temporal_patterns"].get(
                "sessions_by_hour", {}
            )
            if peak_hours:
                peak_hour = max(peak_hours, key=peak_hours.get)
                insight = TestingInsight(
                    insight_id=f"insight_{len(self.testing_insights) + len(new_insights) + 1:06d}",
                    insight_type="trend",
                    title="Peak Testing Hours Identified",
                    description=f"Most testing activity occurs around hour {peak_hour}",
                    confidence_score=0.7,
                    impact_level="low",
                    data_sources=["session_data"],
                    metrics_supporting={"peak_testing_hours": peak_hours},
                    recommended_actions=[
                        "Schedule system maintenance outside peak hours",
                        "Provide additional support during peak times",
                        "Consider targeted communications during high-activity periods",
                    ],
                    timestamp=datetime.now(),
                )
                new_insights.append(insight)

        # Detect usability issues
        usability_issues = self.detect_usability_issues()
        for issue in usability_issues:
            if issue["severity"] in ["high", "critical"]:
                insight = TestingInsight(
                    insight_id=f"insight_{len(self.testing_insights) + len(new_insights) + 1:06d}",
                    insight_type="alert",
                    title=f"Usability Issue: {issue['title']}",
                    description=issue.get("description", ""),
                    confidence_score=0.85,
                    impact_level=issue["severity"],
                    data_sources=["feedback_data", "usability_metrics"],
                    metrics_supporting=issue.get("metrics", {}),
                    recommended_actions=[
                        "Investigate root cause of usability issue",
                        "Implement fixes based on user feedback",
                        "Conduct follow-up testing to verify improvements",
                    ],
                    timestamp=datetime.now(),
                )
                new_insights.append(insight)

        # Save new insights
        for insight in new_insights:
            self.testing_insights[insight.insight_id] = insight

        if new_insights:
            self._save_testing_insights()
            logger.info(f"Generated {len(new_insights)} new testing insights")

        return new_insights

    def create_executive_dashboard(self) -> Dict[str, Any]:
        """Create executive dashboard with key metrics and insights.

        Returns:
            Dictionary with executive dashboard data
        """
        dashboard = {
            "generated_at": datetime.now().isoformat(),
            "key_metrics": {},
            "recent_insights": [],
            "performance_summary": {},
            "user_engagement": {},
            "feedback_summary": {},
            "recommendations": [],
        }

        # Key metrics
        testing_stats = self.beta_framework.get_testing_statistics()
        dashboard["key_metrics"] = {
            "total_beta_users": testing_stats.get("total_users", 0),
            "active_users": testing_stats.get("active_users", 0),
            "total_sessions": testing_stats.get("total_sessions", 0),
            "success_rate": testing_stats.get("success_rate", 0.0),
            "avg_completion_time": testing_stats.get("average_completion_time", 0.0),
        }

        # Recent insights (last 7 days)
        cutoff_date = datetime.now() - timedelta(days=7)
        recent_insights = [
            insight
            for insight in self.testing_insights.values()
            if insight.timestamp >= cutoff_date
        ]
        dashboard["recent_insights"] = [
            {
                "title": insight.title,
                "type": insight.insight_type,
                "impact": insight.impact_level,
                "confidence": insight.confidence_score,
            }
            for insight in recent_insights
        ]

        # Performance trends
        performance_trends = self.generate_performance_trends(days=14)
        if "period_summary" in performance_trends:
            dashboard["performance_summary"] = performance_trends["period_summary"]

        # User engagement
        behavior_analysis = self.analyze_user_behavior_patterns()
        if "user_patterns" in behavior_analysis:
            dashboard["user_engagement"] = behavior_analysis["user_patterns"]

        # Feedback summary
        feedback_report = self.feedback_collector.generate_feedback_report()
        dashboard["feedback_summary"] = {
            "total_feedback": feedback_report.get("feedback_summary", {}).get(
                "total_feedback_entries", 0
            ),
            "satisfaction_score": feedback_report.get("satisfaction_trends", {})
            .get("averages", {})
            .get("overall_satisfaction", 0.0),
            "nps_score": feedback_report.get("satisfaction_trends", {})
            .get("averages", {})
            .get("nps_score", 0.0),
        }

        # Top recommendations
        all_recommendations = []
        for insight in self.testing_insights.values():
            if insight.impact_level in ["high", "critical"]:
                all_recommendations.extend(insight.recommended_actions)

        # Count recommendation frequency
        recommendation_counts = {}
        for rec in all_recommendations:
            recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1

        dashboard["recommendations"] = sorted(
            recommendation_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return dashboard

    def export_analytics_report(self, report_type: str = "comprehensive") -> str:
        """Export analytics report to file.

        Args:
            report_type: Type of report to generate

        Returns:
            Path to generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = (
            self.reports_dir / f"analytics_report_{report_type}_{timestamp}.json"
        )

        if report_type == "comprehensive":
            report_data = {
                "report_type": report_type,
                "generated_at": datetime.now().isoformat(),
                "executive_dashboard": self.create_executive_dashboard(),
                "user_behavior_patterns": self.analyze_user_behavior_patterns(),
                "usability_issues": self.detect_usability_issues(),
                "performance_trends": self.generate_performance_trends(),
                "all_insights": {
                    insight_id: insight.to_dict()
                    for insight_id, insight in self.testing_insights.items()
                },
                "testing_statistics": self.beta_framework.get_testing_statistics(),
                "feedback_report": self.feedback_collector.generate_feedback_report(),
            }
        else:
            report_data = self.create_executive_dashboard()

        try:
            with open(report_file, "w") as f:
                json.dump(report_data, f, indent=2)

            logger.info(f"Analytics report exported to {report_file}")
            return str(report_file)

        except Exception as e:
            logger.error(f"Failed to export analytics report: {e}")
            raise
