"""Base notification channel abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Priority(Enum):
    """Notification priority levels."""
    URGENT = "urgent"    # Immediate attention needed (Telegram)
    DIGEST = "digest"    # Daily/periodic summaries (Slack)
    INFO = "info"        # Non-urgent updates (Slack)


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: Optional[datetime] = None

    def __post_init__(self):
        if self.sent_at is None and self.success:
            self.sent_at = datetime.now()


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    def __init__(self, config: dict):
        """Initialize channel with configuration.

        Args:
            config: Channel-specific configuration dict
        """
        self.config = config
        self.enabled = config.get("enabled", False)

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the channel identifier (e.g., 'telegram', 'slack')."""
        pass

    @abstractmethod
    def send(self, title: str, body: str, priority: Priority) -> NotificationResult:
        """Send a notification.

        Args:
            title: Notification title/subject
            body: Notification body/content
            priority: Priority level

        Returns:
            NotificationResult indicating success/failure
        """
        pass

    def is_available(self) -> bool:
        """Check if channel is configured and available."""
        return self.enabled

    def format_message(self, title: str, body: str, priority: Priority) -> str:
        """Format message for this channel. Override in subclasses."""
        if priority == Priority.URGENT:
            return f"*{title}*\n\n{body}"
        return f"*{title}*\n{body}"
