"""Test coordinator for automating feedback loops and testing protocols."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AutomatedAction:
    """Represents an automated action in the feedback loop."""

    action_id: str
    trigger_type: str  # threshold, schedule, event, manual
    condition: Dict[str, Any]
    action_type: str  # notification, report, escalation, auto_response
    action_config: Dict[str, Any]
    is_active: bool = True
    last_executed: Optional[datetime] = None
    execution_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.last_executed:
            data["last_executed"] = self.last_executed.isoformat()
        return data


class TestCoordinator:
    """Coordinates testing activities and automates feedback loops."""

    def __init__(
        self,
        beta_framework,
        feedback_collector,
        analytics,
        data_dir: Optional[Path] = None,
    ):
        """Initialize test coordinator.

        Args:
            beta_framework: BetaTestingFramework instance
            feedback_collector: FeedbackCollector instance
            analytics: TestingAnalytics instance
            data_dir: Directory for coordinator data
        """
        self.beta_framework = beta_framework
        self.feedback_collector = feedback_collector
        self.analytics = analytics
        self.data_dir = data_dir or Path(".trunk/coordination")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.actions_file = self.data_dir / "automated_actions.json"
        self.execution_log_file = self.data_dir / "execution_log.json"

        self.automated_actions = self._load_automated_actions()
        self.execution_log = self._load_execution_log()

        self._initialize_default_actions()

    def _load_automated_actions(self) -> Dict[str, AutomatedAction]:
        """Load automated actions from storage."""
        if not self.actions_file.exists():
            return {}

        try:
            with open(self.actions_file, "r") as f:
                data = json.load(f)

            actions = {}
            for action_id, action_data in data.items():
                if action_data.get("last_executed"):
                    action_data["last_executed"] = datetime.fromisoformat(
                        action_data["last_executed"]
                    )
                actions[action_id] = AutomatedAction(**action_data)

            return actions
        except Exception as e:
            logger.error(f"Failed to load automated actions: {e}")
            return {}

    def _load_execution_log(self) -> List[Dict[str, Any]]:
        """Load execution log from storage."""
        if not self.execution_log_file.exists():
            return []

        try:
            with open(self.execution_log_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load execution log: {e}")
            return []

    def _save_automated_actions(self):
        """Save automated actions to storage."""
        try:
            data = {
                action_id: action.to_dict()
                for action_id, action in self.automated_actions.items()
            }
            with open(self.actions_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save automated actions: {e}")

    def _save_execution_log(self):
        """Save execution log to storage."""
        try:
            with open(self.execution_log_file, "w") as f:
                json.dump(self.execution_log, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save execution log: {e}")

    def _initialize_default_actions(self):
        """Initialize default automated actions."""
        if self.automated_actions:
            return

        default_actions = [
            AutomatedAction(
                action_id="critical_feedback_alert",
                trigger_type="threshold",
                condition={"feedback_severity": "critical", "count_threshold": 1},
                action_type="notification",
                action_config={
                    "notification_type": "email",
                    "recipients": ["dev-team@trunk.legal"],
                    "subject": "Critical Feedback Alert",
                    "template": "critical_feedback_notification",
                },
            ),
            AutomatedAction(
                action_id="low_success_rate_alert",
                trigger_type="threshold",
                condition={"success_rate_threshold": 0.7, "minimum_sessions": 10},
                action_type="escalation",
                action_config={
                    "escalation_level": "high",
                    "stakeholders": ["product_manager", "dev_lead"],
                    "action_required": "investigate_usability_issues",
                },
            ),
            AutomatedAction(
                action_id="daily_metrics_report",
                trigger_type="schedule",
                condition={"schedule": "daily", "time": "09:00"},
                action_type="report",
                action_config={
                    "report_type": "daily_summary",
                    "recipients": ["team@trunk.legal"],
                    "include_metrics": [
                        "sessions",
                        "completion_rate",
                        "feedback_count",
                    ],
                },
            ),
            AutomatedAction(
                action_id="weekly_analytics_report",
                trigger_type="schedule",
                condition={"schedule": "weekly", "day": "monday", "time": "10:00"},
                action_type="report",
                action_config={
                    "report_type": "comprehensive",
                    "recipients": ["management@trunk.legal"],
                    "include_insights": True,
                },
            ),
            AutomatedAction(
                action_id="user_followup_low_engagement",
                trigger_type="threshold",
                condition={
                    "user_engagement_threshold": 2,
                    "days_since_last_session": 7,
                },
                action_type="auto_response",
                action_config={
                    "response_type": "email",
                    "template": "engagement_followup",
                    "personalized": True,
                },
            ),
        ]

        for action in default_actions:
            self.automated_actions[action.action_id] = action

        self._save_automated_actions()
        logger.info(f"Initialized {len(default_actions)} default automated actions")

    def check_and_execute_actions(self):
        """Check conditions and execute automated actions."""
        executed_actions = []

        for action in self.automated_actions.values():
            if not action.is_active:
                continue

            should_execute = False

            if action.trigger_type == "threshold":
                should_execute = self._check_threshold_condition(action)
            elif action.trigger_type == "schedule":
                should_execute = self._check_schedule_condition(action)
            elif action.trigger_type == "event":
                should_execute = self._check_event_condition(action)

            if should_execute:
                try:
                    self._execute_action(action)
                    executed_actions.append(action.action_id)

                    # Update execution tracking
                    action.last_executed = datetime.now()
                    action.execution_count += 1

                    # Log execution
                    self.execution_log.append(
                        {
                            "action_id": action.action_id,
                            "executed_at": datetime.now().isoformat(),
                            "trigger_type": action.trigger_type,
                            "condition_met": action.condition,
                            "status": "success",
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to execute action {action.action_id}: {e}")
                    self.execution_log.append(
                        {
                            "action_id": action.action_id,
                            "executed_at": datetime.now().isoformat(),
                            "trigger_type": action.trigger_type,
                            "status": "failed",
                            "error": str(e),
                        }
                    )

        if executed_actions:
            self._save_automated_actions()
            self._save_execution_log()
            logger.info(f"Executed {len(executed_actions)} automated actions")

        return executed_actions

    def _check_threshold_condition(self, action: AutomatedAction) -> bool:
        """Check if threshold condition is met."""
        condition = action.condition

        if "feedback_severity" in condition:
            severity = condition["feedback_severity"]
            count_threshold = condition.get("count_threshold", 1)

            recent_feedback = [
                f
                for f in self.feedback_collector.feedback_entries.values()
                if f.severity == severity
                and f.timestamp >= datetime.now() - timedelta(hours=24)
            ]

            return len(recent_feedback) >= count_threshold

        elif "success_rate_threshold" in condition:
            threshold = condition["success_rate_threshold"]
            min_sessions = condition.get("minimum_sessions", 1)

            stats = self.beta_framework.get_testing_statistics()
            total_sessions = stats.get("total_sessions", 0)
            success_rate = stats.get("success_rate", 0.0)

            return total_sessions >= min_sessions and success_rate < threshold

        elif "user_engagement_threshold" in condition:
            threshold = condition["user_engagement_threshold"]
            days_since = condition.get("days_since_last_session", 7)

            cutoff_date = datetime.now() - timedelta(days=days_since)
            low_engagement_users = []

            for user_id, user in self.beta_framework.beta_users.items():
                user_sessions = [
                    s
                    for s in self.beta_framework.test_sessions.values()
                    if s.user_id == user_id and s.start_time >= cutoff_date
                ]

                if len(user_sessions) <= threshold:
                    low_engagement_users.append(user_id)

            return len(low_engagement_users) > 0

        return False

    def _check_schedule_condition(self, action: AutomatedAction) -> bool:
        """Check if schedule condition is met."""
        condition = action.condition
        now = datetime.now()

        if condition.get("schedule") == "daily":
            target_time = condition.get("time", "09:00")
            hour, minute = map(int, target_time.split(":"))

            # Check if it's time to execute (within 1 hour window)
            if (
                now.hour == hour
                and action.last_executed is None
                or action.last_executed.date() < now.date()
            ):
                return True

        elif condition.get("schedule") == "weekly":
            target_day = condition.get("day", "monday")
            target_time = condition.get("time", "10:00")

            day_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }

            if now.weekday() == day_map.get(target_day, 0) and (
                action.last_executed is None
                or action.last_executed < now - timedelta(days=6)
            ):
                return True

        return False

    def _check_event_condition(self, action: AutomatedAction) -> bool:
        """Check if event condition is met."""
        # Event conditions would be set by other parts of the system
        # For now, return False as events are handled separately
        return False

    def _execute_action(self, action: AutomatedAction):
        """Execute an automated action."""
        if action.action_type == "notification":
            self._send_notification(action)
        elif action.action_type == "report":
            self._generate_report(action)
        elif action.action_type == "escalation":
            self._handle_escalation(action)
        elif action.action_type == "auto_response":
            self._send_auto_response(action)

    def _send_notification(self, action: AutomatedAction):
        """Send notification based on action configuration."""
        config = action.action_config

        # In a real implementation, this would integrate with email/Slack/etc.
        # For now, log the notification
        logger.info(
            f"NOTIFICATION: {config.get('subject', 'Alert')} to {config.get('recipients', [])}"
        )

        if action.action_id == "critical_feedback_alert":
            critical_feedback = self.feedback_collector.get_feedback_by_severity(
                "critical"
            )
            logger.info(f"Critical feedback details: {len(critical_feedback)} items")

    def _generate_report(self, action: AutomatedAction):
        """Generate and send report based on action configuration."""
        config = action.action_config
        report_type = config.get("report_type", "daily_summary")

        if report_type == "daily_summary":
            # Generate daily summary
            stats = self.beta_framework.get_testing_statistics()
            recent_feedback = [
                f
                for f in self.feedback_collector.feedback_entries.values()
                if f.timestamp >= datetime.now() - timedelta(days=1)
            ]

            summary = {
                "date": datetime.now().date().isoformat(),
                "total_sessions": stats.get("total_sessions", 0),
                "success_rate": stats.get("success_rate", 0.0),
                "feedback_count": len(recent_feedback),
                "active_users": stats.get("active_users", 0),
            }

            logger.info(f"Daily summary generated: {summary}")

        elif report_type == "comprehensive":
            # Generate comprehensive analytics report
            report_path = self.analytics.export_analytics_report("comprehensive")
            logger.info(f"Comprehensive report generated: {report_path}")

    def _handle_escalation(self, action: AutomatedAction):
        """Handle escalation based on action configuration."""
        config = action.action_config
        escalation_level = config.get("escalation_level", "medium")
        stakeholders = config.get("stakeholders", [])

        logger.warning(
            f"ESCALATION ({escalation_level}): {config.get('action_required', 'Investigation needed')} - Stakeholders: {stakeholders}"
        )

        # In a real implementation, this would create tickets, send alerts, etc.
        if action.action_id == "low_success_rate_alert":
            stats = self.beta_framework.get_testing_statistics()
            logger.warning(
                f"Low success rate detected: {stats.get('success_rate', 0.0):.2%}"
            )

    def _send_auto_response(self, action: AutomatedAction):
        """Send automated response based on action configuration."""
        config = action.action_config
        response_type = config.get("response_type", "email")

        if action.action_id == "user_followup_low_engagement":
            # Find users with low engagement
            cutoff_date = datetime.now() - timedelta(days=7)
            low_engagement_users = []

            for user_id, user in self.beta_framework.beta_users.items():
                user_sessions = [
                    s
                    for s in self.beta_framework.test_sessions.values()
                    if s.user_id == user_id and s.start_time >= cutoff_date
                ]

                if len(user_sessions) <= 2:
                    low_engagement_users.append(user.email)

            if low_engagement_users:
                logger.info(
                    f"Auto-response sent to {len(low_engagement_users)} users with low engagement"
                )

    def add_custom_action(self, action_data: Dict[str, Any]) -> str:
        """Add custom automated action.

        Args:
            action_data: Action configuration data

        Returns:
            Action ID for the new action
        """
        action_id = f"custom_{len(self.automated_actions) + 1:04d}"

        action = AutomatedAction(
            action_id=action_id,
            trigger_type=action_data["trigger_type"],
            condition=action_data["condition"],
            action_type=action_data["action_type"],
            action_config=action_data["action_config"],
        )

        self.automated_actions[action_id] = action
        self._save_automated_actions()

        logger.info(f"Added custom action: {action_id}")
        return action_id

    def disable_action(self, action_id: str):
        """Disable an automated action.

        Args:
            action_id: ID of action to disable
        """
        if action_id in self.automated_actions:
            self.automated_actions[action_id].is_active = False
            self._save_automated_actions()
            logger.info(f"Disabled action: {action_id}")

    def get_action_status(self) -> Dict[str, Any]:
        """Get status of all automated actions.

        Returns:
            Dictionary with action status information
        """
        status = {
            "total_actions": len(self.automated_actions),
            "active_actions": len(
                [a for a in self.automated_actions.values() if a.is_active]
            ),
            "recent_executions": len(
                [
                    log
                    for log in self.execution_log
                    if datetime.fromisoformat(log["executed_at"])
                    >= datetime.now() - timedelta(days=1)
                ]
            ),
            "action_details": {},
            "execution_summary": {},
        }

        # Action details
        for action_id, action in self.automated_actions.items():
            status["action_details"][action_id] = {
                "trigger_type": action.trigger_type,
                "action_type": action.action_type,
                "is_active": action.is_active,
                "execution_count": action.execution_count,
                "last_executed": (
                    action.last_executed.isoformat() if action.last_executed else None
                ),
            }

        # Execution summary
        execution_counts = {}
        for log_entry in self.execution_log:
            action_id = log_entry["action_id"]
            execution_counts[action_id] = execution_counts.get(action_id, 0) + 1

        status["execution_summary"] = execution_counts

        return status

    def run_coordination_cycle(self):
        """Run one cycle of test coordination and automation."""
        logger.info("Starting coordination cycle")

        # Check and execute automated actions
        executed_actions = self.check_and_execute_actions()

        # Generate new insights
        new_insights = self.analytics.generate_insights()

        # Update testing statistics
        stats = self.beta_framework.get_testing_statistics()

        cycle_summary = {
            "executed_actions": executed_actions,
            "new_insights": len(new_insights),
            "current_stats": {
                "total_sessions": stats.get("total_sessions", 0),
                "success_rate": stats.get("success_rate", 0.0),
                "active_users": stats.get("active_users", 0),
            },
        }

        logger.info(f"Coordination cycle completed: {cycle_summary}")
        return cycle_summary
