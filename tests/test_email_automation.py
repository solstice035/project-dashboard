"""Tests for email automation module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestNotificationBase:
    """Test notification base classes."""

    def test_priority_enum_values(self):
        from email_automation.notifications import Priority

        assert Priority.URGENT.value == "urgent"
        assert Priority.DIGEST.value == "digest"
        assert Priority.INFO.value == "info"

    def test_notification_result_success(self):
        from email_automation.notifications import NotificationResult

        result = NotificationResult(success=True, channel="telegram", message_id="123")
        assert result.success is True
        assert result.channel == "telegram"
        assert result.message_id == "123"
        assert result.sent_at is not None

    def test_notification_result_failure(self):
        from email_automation.notifications import NotificationResult

        result = NotificationResult(success=False, channel="slack", error="Connection failed")
        assert result.success is False
        assert result.error == "Connection failed"


class TestTelegramChannel:
    """Test Telegram notification channel."""

    def test_channel_not_configured(self):
        from email_automation.notifications import TelegramChannel, Priority

        channel = TelegramChannel({"enabled": False})
        assert not channel.is_available()

        result = channel.send("Test", "Body", Priority.URGENT)
        assert not result.success
        assert "not configured" in result.error.lower()

    def test_channel_name(self):
        from email_automation.notifications import TelegramChannel

        channel = TelegramChannel({"enabled": True})
        assert channel.channel_name == "telegram"

    @patch("urllib.request.urlopen")
    def test_send_success(self, mock_urlopen):
        from email_automation.notifications import TelegramChannel, Priority

        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true, "result": {"message_id": 456}}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        channel = TelegramChannel({
            "enabled": True,
            "bot_token": "test_token",
            "chat_id": "12345"
        })

        result = channel.send("Test Title", "Test body", Priority.URGENT)

        assert result.success
        assert result.message_id == "456"


class TestSlackChannel:
    """Test Slack notification channel."""

    def test_channel_not_configured(self):
        from email_automation.notifications import SlackChannel, Priority

        channel = SlackChannel({"enabled": False})
        assert not channel.is_available()

        result = channel.send("Test", "Body", Priority.DIGEST)
        assert not result.success

    def test_channel_name(self):
        from email_automation.notifications import SlackChannel

        channel = SlackChannel({"enabled": True})
        assert channel.channel_name == "slack"

    @patch("urllib.request.urlopen")
    def test_send_success(self, mock_urlopen):
        from email_automation.notifications import SlackChannel, Priority

        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        channel = SlackChannel({
            "enabled": True,
            "webhook_url": "https://hooks.slack.com/test"
        })

        result = channel.send("Test Title", "Test body", Priority.DIGEST)

        assert result.success


class TestNotificationRouter:
    """Test notification router."""

    def test_router_initialization(self):
        from email_automation.notifications import NotificationRouter

        config = {
            "telegram": {"enabled": True, "bot_token": "x", "chat_id": "y"},
            "slack": {"enabled": True, "webhook_url": "https://test"},
            "routing": {
                "urgent": ["telegram"],
                "digest": ["slack"],
                "info": ["slack"]
            }
        }

        router = NotificationRouter(config)

        assert "telegram" in router.channels
        assert "slack" in router.channels

    def test_get_status(self):
        from email_automation.notifications import NotificationRouter

        config = {
            "telegram": {"enabled": True, "bot_token": "x", "chat_id": "y"},
            "slack": {"enabled": False}
        }

        router = NotificationRouter(config)
        status = router.get_status()

        assert status["telegram"]["available"] is True
        assert status["slack"]["available"] is False


class TestInboxFetcher:
    """Test inbox fetcher."""

    def test_fetcher_initialization(self):
        from email_automation.inbox import InboxFetcher

        config = {
            "accounts": [
                {"email": "test@example.com", "name": "Test", "priority": "high", "app_password": "test"}
            ]
        }

        fetcher = InboxFetcher(config)
        assert len(fetcher.accounts) == 1

    def test_fetch_account_no_password(self):
        from email_automation.inbox import InboxFetcher

        config = {"accounts": []}
        fetcher = InboxFetcher(config)

        result = fetcher.fetch_account("test@example.com", app_password="")

        assert result.status == "error"
        assert "app_password" in result.error.lower()


class TestInboxDigest:
    """Test inbox digest formatting."""

    def test_format_for_notification(self):
        from email_automation.inbox import InboxFetcher, InboxDigest
        from email_automation.inbox.fetcher import AccountInbox, FetchResult
        from datetime import datetime
        from unittest.mock import Mock

        # Create mock fetcher that returns FetchResult
        fetcher = Mock(spec=InboxFetcher)
        fetcher.fetch_all_accounts.return_value = FetchResult(
            accounts=[
                AccountInbox(
                    account="test@example.com",
                    name="Test",
                    priority="high",
                    total_unread=10,
                    urgent=[],
                    from_people=[],
                    newsletters=5
                )
            ],
            total_unread=10,
            total_urgent=0,
            total_duration_ms=100,
            fetched_at=datetime.now(),
            errors=[]
        )

        digest = InboxDigest(fetcher)
        title, body = digest.format_for_notification()

        assert "10 unread" in title
        assert "Test" in body


class TestJobRegistry:
    """Test job registry."""

    def test_register_and_get_job(self):
        from email_automation.scheduling.jobs import JobRegistry, JobDefinition

        registry = JobRegistry()

        job = JobDefinition(
            job_id="test_job",
            name="Test Job",
            description="A test job",
            func=lambda: {"success": True}
        )

        registry.register(job)

        assert registry.get("test_job") is not None
        assert registry.get("nonexistent") is None

    def test_run_job(self):
        from email_automation.scheduling.jobs import JobRegistry, JobDefinition

        registry = JobRegistry()

        job = JobDefinition(
            job_id="test_job",
            name="Test Job",
            description="A test job",
            func=lambda: {"success": True, "count": 5}
        )
        registry.register(job)

        result = registry.run_job("test_job")

        assert result["success"] is True
        assert result["count"] == 5

    def test_run_unknown_job(self):
        from email_automation.scheduling.jobs import JobRegistry

        registry = JobRegistry()
        result = registry.run_job("unknown_job")

        assert result["success"] is False
        assert "Unknown job" in result["error"]


class TestEmailScheduler:
    """Test email scheduler."""

    def test_scheduler_disabled(self):
        from email_automation.scheduling import EmailScheduler

        scheduler = EmailScheduler({"enabled": False})

        assert not scheduler.enabled
        assert not scheduler.start()

    def test_scheduler_get_status(self):
        from email_automation.scheduling import EmailScheduler

        scheduler = EmailScheduler({"enabled": False})
        status = scheduler.get_status()

        assert "scheduler_enabled" in status
        assert "registered_jobs" in status
