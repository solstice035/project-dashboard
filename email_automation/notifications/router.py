"""Notification router with priority-based channel selection."""

import logging
from datetime import datetime
from typing import Optional, Callable

from .base import NotificationChannel, NotificationResult, Priority
from .telegram import TelegramChannel
from .slack import SlackChannel

logger = logging.getLogger(__name__)


class NotificationRouter:
    """Routes notifications to appropriate channels based on priority.

    Routing rules (from config):
        URGENT -> telegram (immediate attention)
        DIGEST -> slack (daily summaries)
        INFO -> slack (non-urgent updates)
    """

    def __init__(self, config: dict, db_callback: Optional[Callable] = None):
        """Initialize router with notification config.

        Args:
            config: notifications section from config.yaml
            db_callback: Optional callback to log notifications to database
                         Signature: (channel, source, title, body, priority, success, error)
        """
        self.config = config
        self.db_callback = db_callback

        # Initialize channels
        self.channels: dict[str, NotificationChannel] = {}

        telegram_config = config.get("telegram", {})
        if telegram_config:
            self.channels["telegram"] = TelegramChannel(telegram_config)

        slack_config = config.get("slack", {})
        if slack_config:
            self.channels["slack"] = SlackChannel(slack_config)

        # Load routing rules
        routing = config.get("routing", {})
        self.routing = {
            Priority.URGENT: routing.get("urgent", ["telegram"]),
            Priority.DIGEST: routing.get("digest", ["slack"]),
            Priority.INFO: routing.get("info", ["slack"]),
        }

    def send(
        self,
        title: str,
        body: str,
        priority: Priority,
        source: str = "unknown"
    ) -> list[NotificationResult]:
        """Send notification to appropriate channels based on priority.

        Args:
            title: Notification title
            body: Notification body
            priority: Priority level determining channel routing
            source: Source identifier (e.g., 'school', 'inbox')

        Returns:
            List of results from each channel attempted
        """
        results = []
        target_channels = self.routing.get(priority, ["slack"])

        for channel_name in target_channels:
            channel = self.channels.get(channel_name)

            if channel is None:
                logger.warning(f"Channel {channel_name} not configured")
                results.append(NotificationResult(
                    success=False,
                    channel=channel_name,
                    error="Channel not configured"
                ))
                continue

            if not channel.is_available():
                logger.warning(f"Channel {channel_name} not available")
                results.append(NotificationResult(
                    success=False,
                    channel=channel_name,
                    error="Channel not available"
                ))
                continue

            result = channel.send(title, body, priority)
            results.append(result)

            # Log to database if callback provided
            if self.db_callback:
                try:
                    self.db_callback(
                        channel=channel_name,
                        source=source,
                        title=title,
                        body=body,
                        priority=priority.value,
                        success=result.success,
                        error=result.error
                    )
                except Exception as e:
                    logger.warning(f"Failed to log notification: {e}")

        return results

    def send_urgent(self, title: str, body: str, source: str = "unknown") -> list[NotificationResult]:
        """Convenience method for urgent notifications."""
        return self.send(title, body, Priority.URGENT, source)

    def send_digest(self, title: str, body: str, source: str = "unknown") -> list[NotificationResult]:
        """Convenience method for digest notifications."""
        return self.send(title, body, Priority.DIGEST, source)

    def send_info(self, title: str, body: str, source: str = "unknown") -> list[NotificationResult]:
        """Convenience method for info notifications."""
        return self.send(title, body, Priority.INFO, source)

    def get_status(self) -> dict:
        """Get status of all notification channels."""
        return {
            name: {
                "available": channel.is_available(),
                "enabled": channel.enabled,
            }
            for name, channel in self.channels.items()
        }

    def test_channels(self) -> dict[str, NotificationResult]:
        """Send test message to all available channels."""
        results = {}
        for name, channel in self.channels.items():
            if channel.is_available():
                result = channel.send(
                    "Test Notification",
                    "This is a test message from Project Dashboard email automation.",
                    Priority.INFO
                )
                results[name] = result
            else:
                results[name] = NotificationResult(
                    success=False,
                    channel=name,
                    error="Channel not available"
                )
        return results
