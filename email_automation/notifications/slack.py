"""Slack webhook notification channel."""

import logging
import urllib.request
import json
from typing import Optional

from .base import NotificationChannel, NotificationResult, Priority

logger = logging.getLogger(__name__)


class SlackChannel(NotificationChannel):
    """Slack webhook notification channel for digests and non-urgent updates."""

    @property
    def channel_name(self) -> str:
        return "slack"

    def __init__(self, config: dict):
        """Initialize Slack channel.

        Config expects:
            webhook_url: Slack incoming webhook URL
            channel: Target channel (optional, uses webhook default)
            enabled: bool
        """
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
        self.default_channel = config.get("channel", "")

    def is_available(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    def send(self, title: str, body: str, priority: Priority) -> NotificationResult:
        """Send message via Slack webhook."""
        if not self.is_available():
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error="Slack not configured or disabled"
            )

        payload = self._build_payload(title, body, priority)

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                method="POST"
            )
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=10) as response:
                response_text = response.read().decode("utf-8")

            if response_text == "ok":
                logger.info("Slack message sent successfully")
                return NotificationResult(
                    success=True,
                    channel=self.channel_name
                )
            else:
                logger.error(f"Slack webhook error: {response_text}")
                return NotificationResult(
                    success=False,
                    channel=self.channel_name,
                    error=response_text
                )

        except urllib.error.URLError as e:
            logger.error(f"Slack network error: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error=f"Network error: {e}"
            )
        except Exception as e:
            logger.error(f"Slack send error: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error=str(e)
            )

    def _build_payload(self, title: str, body: str, priority: Priority) -> dict:
        """Build Slack message payload with blocks for rich formatting."""
        color = self._priority_color(priority)

        payload = {
            "attachments": [{
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title,
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": body
                        }
                    }
                ]
            }]
        }

        if self.default_channel:
            payload["channel"] = self.default_channel

        return payload

    def _priority_color(self, priority: Priority) -> str:
        """Get Slack attachment color for priority."""
        colors = {
            Priority.URGENT: "#dc2626",   # Red
            Priority.DIGEST: "#2563eb",   # Blue
            Priority.INFO: "#6b7280",     # Gray
        }
        return colors.get(priority, "#6b7280")

    def format_message(self, title: str, body: str, priority: Priority) -> str:
        """Format message for Slack mrkdwn."""
        return f"*{title}*\n{body}"
