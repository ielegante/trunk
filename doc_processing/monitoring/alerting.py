"""Alerting system for production monitoring."""

import asyncio
import json
import logging
import smtplib
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Alert instance."""

    alert_id: str
    name: str
    message: str
    severity: AlertSeverity
    source: str
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    metadata: Dict[str, Any] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


@dataclass
class AlertRule:
    """Alert rule definition."""

    rule_id: str
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity
    message_template: str
    cooldown_minutes: int = 15
    enabled: bool = True

    # Runtime state
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


class AlertChannel:
    """Base class for alert channels."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)

    async def send_alert(self, alert: Alert) -> bool:
        """Send an alert through this channel.

        Args:
            alert: Alert to send

        Returns:
            True if successful
        """
        raise NotImplementedError()


class EmailAlertChannel(AlertChannel):
    """Email alert channel."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.smtp_server = config.get("smtp_server", "localhost")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username")
        self.password = config.get("password")
        self.from_email = config.get("from_email", "alerts@trunk.dev")
        self.to_emails = config.get("to_emails", [])
        self.use_tls = config.get("use_tls", True)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.name}"

            # Create email body
            body = self._create_email_body(alert)
            msg.attach(MIMEText(body, "html"))

            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.send_message(msg)
            server.quit()

            logger.info(f"Email alert sent for {alert.alert_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _create_email_body(self, alert: Alert) -> str:
        """Create HTML email body."""
        severity_colors = {
            AlertSeverity.INFO: "#3498db",
            AlertSeverity.WARNING: "#f39c12",
            AlertSeverity.ERROR: "#e74c3c",
            AlertSeverity.CRITICAL: "#c0392b",
        }

        color = severity_colors.get(alert.severity, "#95a5a6")

        return """
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="border-left: 4px solid {color}; padding-left: 20px;">
                <h2 style="color: {color}; margin: 0;">{alert.name}</h2>
                <p style="color: #666; margin: 5px 0;"><strong>Severity:</strong> {alert.severity.value.upper()}</p>
                <p style="color: #666; margin: 5px 0;"><strong>Source:</strong> {alert.source}</p>
                <p style="color: #666; margin: 5px 0;"><strong>Time:</strong> {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p style="color: #666; margin: 5px 0;"><strong>Alert ID:</strong> {alert.alert_id}</p>
            </div>

            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px 0; color: #333;">Message</h3>
                <p style="margin: 0; color: #555;">{alert.message}</p>
            </div>

            {self._format_metadata(alert.metadata)}

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    This is an automated alert from the Trunk Document Processing System.
                </p>
            </div>
        </body>
        </html>
        """

    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata for email display."""
        if not metadata:
            return ""

        rows = []
        for key, value in metadata.items():
            formatted_key = key.replace("_", " ").title()
            formatted_value = str(value)
            if len(formatted_value) > 100:
                formatted_value = formatted_value[:100] + "..."
            rows.append(
                f"<tr><td style='padding: 5px; border: 1px solid #ddd;'>{formatted_key}</td><td style='padding: 5px; border: 1px solid #ddd;'>{formatted_value}</td></tr>"
            )

        return """
        <div style="margin: 20px 0;">
            <h3 style="margin: 0 0 10px 0; color: #333;">Additional Information</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Field</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """


class WebhookAlertChannel(AlertChannel):
    """Webhook alert channel."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.url = config.get("url")
        self.headers = config.get("headers", {})
        self.method = config.get("method", "POST")
        self.timeout = config.get("timeout", 30)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            import aiohttp

            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self.method,
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status < 400:
                        logger.info(f"Webhook alert sent for {alert.alert_id}")
                        return True
                    else:
                        logger.error(f"Webhook alert failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class LogAlertChannel(AlertChannel):
    """Log alert channel."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.log_file = config.get("log_file")
        self.log_level = config.get("log_level", "INFO")

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to log."""
        try:
            log_message = f"ALERT [{alert.severity.value.upper()}] {alert.name}: {alert.message} (ID: {alert.alert_id})"

            # Log to application logger
            if alert.severity == AlertSeverity.CRITICAL:
                logger.critical(log_message)
            elif alert.severity == AlertSeverity.ERROR:
                logger.error(log_message)
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(log_message)
            else:
                logger.info(log_message)

            # Log to file if specified
            if self.log_file:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} - {log_message}\n")

            return True

        except Exception as e:
            logger.error(f"Failed to send log alert: {e}")
            return False


class AlertManager:
    """Manages alerts and alert rules."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize alert manager.

        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[str, AlertChannel] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.lock = threading.RLock()
        self.is_running = False
        self.evaluation_task: Optional[asyncio.Task] = None

        # Configuration
        self.evaluation_interval = self.config.get("evaluation_interval", 60)
        self.max_history = self.config.get("max_history", 1000)
        self.alert_file = self.config.get("alert_file")

        # Initialize default channels
        self._setup_default_channels()

        # Initialize default rules
        self._setup_default_rules()

    def _setup_default_channels(self):
        """Set up default alert channels."""
        # Log channel (always available)
        log_config = self.config.get("log_channel", {})
        log_config.setdefault("enabled", True)
        self.channels["log"] = LogAlertChannel("log", log_config)

        # Email channel if configured
        email_config = self.config.get("email_channel")
        if email_config and email_config.get("enabled"):
            self.channels["email"] = EmailAlertChannel("email", email_config)

        # Webhook channel if configured
        webhook_config = self.config.get("webhook_channel")
        if webhook_config and webhook_config.get("enabled"):
            self.channels["webhook"] = WebhookAlertChannel("webhook", webhook_config)

    def _setup_default_rules(self):
        """Set up default alert rules."""
        # High CPU usage
        self.add_rule(
            AlertRule(
                rule_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage is critically high",
                condition=lambda metrics: metrics.get("system.cpu_percent", 0) > 90,
                severity=AlertSeverity.CRITICAL,
                message_template="CPU usage is at {cpu_percent:.1f}%",
                cooldown_minutes=5,
            )
        )

        # High memory usage
        self.add_rule(
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage is critically high",
                condition=lambda metrics: metrics.get("system.memory_percent", 0) > 90,
                severity=AlertSeverity.CRITICAL,
                message_template="Memory usage is at {memory_percent:.1f}%",
                cooldown_minutes=5,
            )
        )

        # High disk usage
        self.add_rule(
            AlertRule(
                rule_id="high_disk_usage",
                name="High Disk Usage",
                description="Disk usage is critically high",
                condition=lambda metrics: metrics.get("system.disk_usage_percent", 0)
                > 85,
                severity=AlertSeverity.ERROR,
                message_template="Disk usage is at {disk_usage_percent:.1f}%",
                cooldown_minutes=30,
            )
        )

        # High error rate
        self.add_rule(
            AlertRule(
                rule_id="high_error_rate",
                name="High Error Rate",
                description="Document processing error rate is high",
                condition=lambda metrics: metrics.get(
                    "conversion_error_rate_percent", 0
                )
                > 10,
                severity=AlertSeverity.ERROR,
                message_template="Error rate is at {conversion_error_rate_percent:.1f}%",
                cooldown_minutes=10,
            )
        )

        # Service unavailable
        self.add_rule(
            AlertRule(
                rule_id="service_unavailable",
                name="Service Unavailable",
                description="Document processing service is unavailable",
                condition=lambda metrics: metrics.get("health_status") == "critical",
                severity=AlertSeverity.CRITICAL,
                message_template="Service health status is critical: {health_message}",
                cooldown_minutes=2,
            )
        )

    def add_rule(self, rule: AlertRule):
        """Add an alert rule.

        Args:
            rule: Alert rule to add
        """
        with self.lock:
            self.rules[rule.rule_id] = rule
            logger.info(f"Added alert rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str):
        """Remove an alert rule.

        Args:
            rule_id: ID of rule to remove
        """
        with self.lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                logger.info(f"Removed alert rule: {rule_id}")

    def add_channel(self, channel: AlertChannel):
        """Add an alert channel.

        Args:
            channel: Alert channel to add
        """
        with self.lock:
            self.channels[channel.name] = channel
            logger.info(f"Added alert channel: {channel.name}")

    def remove_channel(self, channel_name: str):
        """Remove an alert channel.

        Args:
            channel_name: Name of channel to remove
        """
        with self.lock:
            if channel_name in self.channels:
                del self.channels[channel_name]
                logger.info(f"Removed alert channel: {channel_name}")

    async def evaluate_rules(self, metrics: Dict[str, Any]):
        """Evaluate alert rules against metrics.

        Args:
            metrics: Metrics to evaluate
        """
        with self.lock:
            current_time = datetime.now()

            for rule in self.rules.values():
                if not rule.enabled:
                    continue

                # Check cooldown
                if (
                    rule.last_triggered
                    and (current_time - rule.last_triggered).total_seconds()
                    < rule.cooldown_minutes * 60
                ):
                    continue

                try:
                    # Evaluate condition
                    if rule.condition(metrics):
                        await self._trigger_alert(rule, metrics)
                        rule.last_triggered = current_time
                        rule.trigger_count += 1

                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.rule_id}: {e}")

    async def _trigger_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        """Trigger an alert.

        Args:
            rule: Alert rule that was triggered
            metrics: Metrics that triggered the alert
        """
        # Create alert ID
        alert_id = f"{rule.rule_id}_{int(datetime.now().timestamp())}"

        # Format message
        try:
            message = rule.message_template.format(**metrics)
        except (KeyError, ValueError):
            message = rule.message_template

        # Create alert
        alert = Alert(
            alert_id=alert_id,
            name=rule.name,
            message=message,
            severity=rule.severity,
            source="alert_manager",
            timestamp=datetime.now(),
            metadata={"rule_id": rule.rule_id, "trigger_count": rule.trigger_count},
        )

        # Store alert
        with self.lock:
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)

            # Trim history if needed
            if len(self.alert_history) > self.max_history:
                self.alert_history = self.alert_history[-self.max_history :]

        # Send alert through channels
        await self._send_alert(alert)

        # Save to file if configured
        if self.alert_file:
            await self._save_alert_to_file(alert)

        logger.warning(f"Alert triggered: {alert.name} (ID: {alert_id})")

    async def _send_alert(self, alert: Alert):
        """Send alert through all enabled channels.

        Args:
            alert: Alert to send
        """
        tasks = []

        for channel in self.channels.values():
            if channel.enabled:
                tasks.append(channel.send_alert(alert))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            logger.info(f"Alert sent through {success_count}/{len(tasks)} channels")

    async def _save_alert_to_file(self, alert: Alert):
        """Save alert to file.

        Args:
            alert: Alert to save
        """
        try:
            alert_file = Path(self.alert_file)
            alert_file.parent.mkdir(parents=True, exist_ok=True)

            with open(alert_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")

        except Exception as e:
            logger.error(f"Failed to save alert to file: {e}")

    def resolve_alert(self, alert_id: str, resolved_by: str = "system"):
        """Resolve an active alert.

        Args:
            alert_id: ID of alert to resolve
            resolved_by: Who resolved the alert
        """
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                alert.resolved_by = resolved_by

                del self.active_alerts[alert_id]
                logger.info(f"Alert resolved: {alert_id}")

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts.

        Returns:
            List of active alerts
        """
        with self.lock:
            return list(self.active_alerts.values())

    def get_alert_history(self, hours_back: int = 24) -> List[Alert]:
        """Get alert history.

        Args:
            hours_back: Hours to look back

        Returns:
            List of alerts
        """
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            return [a for a in self.alert_history if a.timestamp > cutoff_time]

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary.

        Returns:
            Dictionary with alert statistics
        """
        with self.lock:
            # Count alerts by severity
            severity_counts = {}
            for alert in self.active_alerts.values():
                severity = alert.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Count recent alerts (last 24 hours)
            recent_alerts = self.get_alert_history(24)
            recent_count = len(recent_alerts)

            return {
                "active_alerts": len(self.active_alerts),
                "severity_counts": severity_counts,
                "recent_alerts_24h": recent_count,
                "total_rules": len(self.rules),
                "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
                "active_channels": len(
                    [c for c in self.channels.values() if c.enabled]
                ),
            }

    async def start(self):
        """Start the alert manager."""
        if self.is_running:
            logger.warning("Alert manager is already running")
            return

        self.is_running = True
        logger.info("Alert manager started")

    async def stop(self):
        """Stop the alert manager."""
        if not self.is_running:
            return

        self.is_running = False

        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass

        logger.info("Alert manager stopped")
