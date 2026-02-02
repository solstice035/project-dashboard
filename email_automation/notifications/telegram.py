"""Telegram notification channel using Bot API."""

import logging
import urllib.request
import urllib.parse
import json
from typing import Optional

from .base import NotificationChannel, NotificationResult, Priority

logger = logging.getLogger(__name__)


class TelegramChannel(NotificationChannel):
    """Telegram Bot API notification channel for urgent alerts."""

    @property
    def channel_name(self) -> str:
        return "telegram"

    def __init__(self, config: dict):
        """Initialize Telegram channel.

        Config expects:
            bot_token: Telegram bot token from BotFather
            chat_id: Target chat/channel ID
            enabled: bool
        """
        super().__init__(config)
        self.bot_token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")

    def is_available(self) -> bool:
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)

    def send(self, title: str, body: str, priority: Priority) -> NotificationResult:
        """Send message via Telegram Bot API."""
        if not self.is_available():
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error="Telegram not configured or disabled"
            )

        message = self.format_message(title, body, priority)

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": "true"
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))

            if result.get("ok"):
                message_id = str(result.get("result", {}).get("message_id", ""))
                logger.info(f"Telegram message sent: {message_id}")
                return NotificationResult(
                    success=True,
                    channel=self.channel_name,
                    message_id=message_id
                )
            else:
                error = result.get("description", "Unknown error")
                logger.error(f"Telegram API error: {error}")
                return NotificationResult(
                    success=False,
                    channel=self.channel_name,
                    error=error
                )

        except urllib.error.URLError as e:
            logger.error(f"Telegram network error: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error=f"Network error: {e}"
            )
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel_name,
                error=str(e)
            )

    def format_message(self, title: str, body: str, priority: Priority) -> str:
        """Format message for Telegram with emoji indicators."""
        if priority == Priority.URGENT:
            return f"*{title}*\n\n{body}"
        elif priority == Priority.DIGEST:
            return f"*{title}*\n\n{body}"
        else:
            return f"*{title}*\n{body}"
