"""
Email Automation Package for Project Dashboard.

Provides unified email processing, notifications, and scheduling for:
- Inbox digest across email accounts
- School email automation (via SchoolEmailAutomation dependency)
- Telegram/Slack notifications
- APScheduler-based job scheduling
"""

__version__ = "0.1.0"

from .notifications import NotificationRouter, Priority
from .inbox import InboxFetcher, InboxDigest
from .school import SchoolAdapter
from .scheduling import EmailScheduler

__all__ = [
    "NotificationRouter",
    "Priority",
    "InboxFetcher",
    "InboxDigest",
    "SchoolAdapter",
    "EmailScheduler",
]
