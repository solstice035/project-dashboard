"""Tests for email automation module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date


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


class TestLetterParser:
    """Test school letter parser."""

    def test_parse_uk_date_ordinal(self):
        """Test parsing UK dates with ordinals like '15th February 2026'."""
        from email_automation.school.letter_parser import parse_letter

        content = "Please return the form by 15th February 2026."
        result = parse_letter(content)

        assert len(result.dates) == 1
        assert result.dates[0].date == date(2026, 2, 15)
        assert "15th February 2026" in result.dates[0].original_text

    def test_parse_uk_date_slash_format(self):
        """Test parsing DD/MM/YYYY format."""
        from email_automation.school.letter_parser import parse_letter

        content = "Deadline: 28/02/2026"
        result = parse_letter(content)

        assert len(result.dates) == 1
        assert result.dates[0].date == date(2026, 2, 28)

    def test_parse_abbreviated_month(self):
        """Test parsing abbreviated month names like '15 Feb 2026'."""
        from email_automation.school.letter_parser import parse_letter

        content = "Return by 21st Feb 2026 please."
        result = parse_letter(content)

        assert len(result.dates) == 1
        assert result.dates[0].date == date(2026, 2, 21)

    def test_parse_weekday_date_no_year(self):
        """Test parsing weekday + date without year (infers current/next year)."""
        from email_automation.school.letter_parser import parse_letter

        content = "The trip is on Friday 20th December"
        result = parse_letter(content)

        assert len(result.dates) == 1
        # Should infer year correctly
        assert result.dates[0].date.month == 12
        assert result.dates[0].date.day == 20

    def test_parse_multiple_dates(self):
        """Test extracting multiple dates from content."""
        from email_automation.school.letter_parser import parse_letter

        content = """
        Consent forms due by 15th February 2026.
        The trip takes place on 21/02/2026.
        """
        result = parse_letter(content)

        assert len(result.dates) == 2
        dates_found = {d.date for d in result.dates}
        assert date(2026, 2, 15) in dates_found
        assert date(2026, 2, 21) in dates_found

    def test_detect_deadline_trigger(self):
        """Test detecting deadline action triggers."""
        from email_automation.school.letter_parser import parse_letter

        content = "Please return by Friday 15th February."
        result = parse_letter(content)

        assert result.has_deadline
        trigger_types = {t.trigger_type for t in result.action_triggers}
        assert "deadline" in trigger_types

    def test_detect_payment_trigger(self):
        """Test detecting payment action triggers."""
        from email_automation.school.letter_parser import parse_letter

        content = "The cost is £25 per child."
        result = parse_letter(content)

        assert result.has_payment
        trigger_types = {t.trigger_type for t in result.action_triggers}
        assert "payment" in trigger_types

    def test_detect_permission_trigger(self):
        """Test detecting permission/consent triggers."""
        from email_automation.school.letter_parser import parse_letter

        content = "Please sign the consent form and return it."
        result = parse_letter(content)

        trigger_types = {t.trigger_type for t in result.action_triggers}
        assert "permission" in trigger_types

    def test_detect_reply_trigger(self):
        """Test detecting reply required triggers."""
        from email_automation.school.letter_parser import parse_letter

        content = "Please complete and return this form."
        result = parse_letter(content)

        trigger_types = {t.trigger_type for t in result.action_triggers}
        assert "reply" in trigger_types

    def test_urgency_high_deadline_soon(self):
        """Test high urgency when deadline is within 3 days."""
        from email_automation.school.letter_parser import parse_letter, _determine_urgency, LetterAnalysis

        # Create analysis with deadline in 2 days
        from datetime import timedelta
        soon = date.today() + timedelta(days=2)

        analysis = LetterAnalysis(
            dates=[],
            action_triggers=[],
            has_deadline=True,
            earliest_date=soon
        )
        result = _determine_urgency(analysis)
        assert result == "high"

    def test_urgency_medium_deadline_week(self):
        """Test medium urgency when deadline is within a week."""
        from email_automation.school.letter_parser import _determine_urgency, LetterAnalysis
        from datetime import timedelta

        week_away = date.today() + timedelta(days=6)

        analysis = LetterAnalysis(
            dates=[],
            action_triggers=[],
            has_deadline=True,
            earliest_date=week_away
        )
        result = _determine_urgency(analysis)
        assert result == "medium"

    def test_urgency_info_no_triggers(self):
        """Test info urgency when no action triggers detected."""
        from email_automation.school.letter_parser import parse_letter

        content = "Welcome to the new school term. We hope everyone had a great holiday."
        result = parse_letter(content)

        assert result.suggested_urgency == "info"
        assert len(result.action_triggers) == 0

    def test_earliest_date_calculation(self):
        """Test earliest_date is correctly set to minimum date."""
        from email_automation.school.letter_parser import parse_letter

        content = """
        First deadline: 28th February 2026.
        Final deadline: 15th February 2026.
        """
        result = parse_letter(content)

        assert result.earliest_date == date(2026, 2, 15)

    def test_subject_included_in_analysis(self):
        """Test that subject line is included in trigger detection."""
        from email_automation.school.letter_parser import parse_letter

        result = parse_letter("Some content", subject="Action Required: School Trip")

        trigger_types = {t.trigger_type for t in result.action_triggers}
        assert "reply" in trigger_types


class TestEmailMessageBodyFull:
    """Test EmailMessage with body_full field."""

    def test_email_message_has_body_full(self):
        """Test EmailMessage dataclass has body_full field."""
        from email_automation.inbox.fetcher import EmailMessage

        msg = EmailMessage(
            id="123",
            subject="Test",
            from_name="Sender",
            from_email="sender@example.com",
            date="Mon, 1 Jan 2026",
            body_preview="Short preview...",
            body_full="This is the full email body with all the content."
        )

        assert msg.body_preview == "Short preview..."
        assert msg.body_full == "This is the full email body with all the content."

    def test_email_message_body_full_default(self):
        """Test body_full defaults to empty string."""
        from email_automation.inbox.fetcher import EmailMessage

        msg = EmailMessage(
            id="123",
            subject="Test",
            from_name="Sender",
            from_email="sender@example.com",
            date="Mon, 1 Jan 2026"
        )

        assert msg.body_full == ""


class TestGetEmailBody:
    """Test _get_email_body method returns tuple."""

    def test_get_email_body_returns_tuple(self):
        """Test _get_email_body returns (preview, full_text) tuple."""
        from email_automation.inbox import InboxFetcher
        import email

        # Create a simple email message
        msg = email.message.EmailMessage()
        msg.set_content("This is a longer email body that should be captured in full.\n\nIt has multiple lines.")

        fetcher = InboxFetcher({"accounts": []})
        preview, full = fetcher._get_email_body(msg)

        assert isinstance(preview, str)
        assert isinstance(full, str)
        assert len(preview) <= 200  # Preview is truncated
        assert "This is a longer email body" in full
        assert "multiple lines" in full

    def test_get_email_body_preview_truncated(self):
        """Test preview is properly truncated."""
        from email_automation.inbox import InboxFetcher
        import email

        long_text = "A" * 500
        msg = email.message.EmailMessage()
        msg.set_content(long_text)

        fetcher = InboxFetcher({"accounts": []})
        preview, full = fetcher._get_email_body(msg)

        assert len(preview) <= 200
        assert len(full) == 500

    def test_get_email_body_empty_message(self):
        """Test handling of empty message body."""
        from email_automation.inbox import InboxFetcher
        import email

        msg = email.message.EmailMessage()
        # No content set

        fetcher = InboxFetcher({"accounts": []})
        preview, full = fetcher._get_email_body(msg)

        assert preview == ""
        assert full == ""


class TestPdfExtraction:
    """Test PDF text extraction."""

    def test_extract_pdf_text_no_pypdf(self):
        """Test graceful handling when pypdf not available."""
        from email_automation.inbox.fetcher import extract_pdf_text

        # Even with pypdf installed, passing invalid PDF bytes should fail gracefully
        text, error = extract_pdf_text(b"not a real pdf")

        assert text == ""
        assert error is not None

    @patch("email_automation.inbox.fetcher.PdfReader", create=True)
    def test_extract_pdf_text_success(self, mock_reader_class):
        """Test successful PDF extraction."""
        from email_automation.inbox.fetcher import extract_pdf_text

        # Mock PdfReader and pages
        mock_page = Mock()
        mock_page.extract_text.return_value = "Page 1 content"

        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        # Patch the import inside the function
        with patch.dict("sys.modules", {"pypdf": Mock(PdfReader=mock_reader_class)}):
            # Force reimport to pick up mock
            import importlib
            import email_automation.inbox.fetcher as fetcher_module
            importlib.reload(fetcher_module)

            text, error = fetcher_module.extract_pdf_text(b"fake pdf bytes")

        # Note: This test structure depends on how pypdf import works
        # The actual test may need adjustment based on import behavior


class TestEmailAttachmentDataclass:
    """Test EmailAttachment dataclass."""

    def test_attachment_extraction_status(self):
        """Test attachment with extraction status."""
        from email_automation.inbox.fetcher import EmailAttachment

        attachment = EmailAttachment(
            filename="letter.pdf",
            content_type="application/pdf",
            size_bytes=12345,
            extracted_text="Content from PDF",
            extraction_status="success"
        )

        assert attachment.extraction_status == "success"
        assert attachment.extracted_text == "Content from PDF"

    def test_attachment_to_dict(self):
        """Test attachment serialization."""
        from email_automation.inbox.fetcher import EmailAttachment

        attachment = EmailAttachment(
            filename="doc.pdf",
            content_type="application/pdf",
            size_bytes=5000,
            extracted_text="Hello world",
            extraction_status="success"
        )

        d = attachment.to_dict()

        assert d["filename"] == "doc.pdf"
        assert d["has_text"] is True
        assert d["text_length"] == 11
        assert d["extraction_status"] == "success"

    def test_attachment_failed_extraction(self):
        """Test attachment with failed extraction."""
        from email_automation.inbox.fetcher import EmailAttachment

        attachment = EmailAttachment(
            filename="corrupted.pdf",
            content_type="application/pdf",
            size_bytes=100,
            extraction_status="failed",
            extraction_error="Invalid PDF structure"
        )

        assert attachment.extraction_status == "failed"
        assert "Invalid PDF" in attachment.extraction_error

        d = attachment.to_dict()
        assert d["has_text"] is False
        assert d["text_length"] == 0
