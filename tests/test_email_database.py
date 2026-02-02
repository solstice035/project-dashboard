"""Tests for email-related database functions."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestCacheInboxMessage:
    """Test cache_inbox_message function with body_text parameter."""

    @patch("database.get_connection")
    def test_cache_message_with_body_text(self, mock_get_conn):
        """Test caching message with full body text."""
        import database

        # Setup mock
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = database.cache_inbox_message(
            account="test@example.com",
            message_id="msg123",
            subject="Test Subject",
            from_name="Sender",
            from_email="sender@example.com",
            date_header="Mon, 1 Jan 2026 10:00:00",
            is_urgent=True,
            is_from_person=True,
            body_text="This is the full email body content."
        )

        assert result is True
        mock_cursor.execute.assert_called_once()

        # Verify body_text is in the SQL parameters
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "body_text" in sql
        assert "This is the full email body content." in params

    @patch("database.get_connection")
    def test_cache_message_without_body_text(self, mock_get_conn):
        """Test caching message without body_text (None default)."""
        import database

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = database.cache_inbox_message(
            account="test@example.com",
            message_id="msg456",
            subject="No Body",
            from_name="Sender",
            from_email="sender@example.com",
            date_header="Mon, 1 Jan 2026"
        )

        assert result is True

        # Verify None is passed for body_text
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # body_text should be None (last param before execute)
        assert None in params

    @patch("database.get_connection")
    def test_cache_message_db_error(self, mock_get_conn):
        """Test handling database error."""
        import database
        import psycopg2

        mock_get_conn.side_effect = psycopg2.Error("Connection failed")

        result = database.cache_inbox_message(
            account="test@example.com",
            message_id="msg789",
            subject="Error Test",
            from_name="Sender",
            from_email="sender@example.com",
            date_header="Mon, 1 Jan 2026"
        )

        assert result is False


class TestGetEmailContentForProcessing:
    """Test get_email_content_for_processing function."""

    @patch("database.get_connection")
    def test_get_content_success(self, mock_get_conn):
        """Test retrieving email content with body and attachments."""
        import database

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # First query returns message data
        mock_cursor.fetchone.side_effect = [
            {
                "subject": "Test Email",
                "from_name": "School Office",
                "from_email": "office@school.com",
                "body_text": "Dear Parents, please return the form by Friday."
            }
        ]

        # Second query returns attachments
        mock_cursor.fetchall.return_value = [
            {
                "filename": "letter.pdf",
                "content_type": "application/pdf",
                "extracted_text": "Content from the PDF attachment."
            }
        ]

        result = database.get_email_content_for_processing(
            account="parent@example.com",
            message_id="school-msg-123"
        )

        assert result["body"] == "Dear Parents, please return the form by Friday."
        assert result["subject"] == "Test Email"
        assert result["from_name"] == "School Office"
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["filename"] == "letter.pdf"
        assert "Content from the PDF" in result["attachments"][0]["text"]

    @patch("database.get_connection")
    def test_get_content_message_not_found(self, mock_get_conn):
        """Test handling when message not found."""
        import database

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # Message not found
        mock_cursor.fetchone.return_value = None

        result = database.get_email_content_for_processing(
            account="test@example.com",
            message_id="nonexistent"
        )

        assert result["body"] == ""
        assert result["error"] == "Message not found"
        assert result["attachments"] == []

    @patch("database.get_connection")
    def test_get_content_no_attachments(self, mock_get_conn):
        """Test message with no attachments."""
        import database

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {
            "subject": "Plain Email",
            "from_name": "Someone",
            "from_email": "someone@example.com",
            "body_text": "Just text, no attachments."
        }
        mock_cursor.fetchall.return_value = []  # No attachments

        result = database.get_email_content_for_processing(
            account="test@example.com",
            message_id="plain-msg"
        )

        assert result["body"] == "Just text, no attachments."
        assert result["attachments"] == []
        assert "error" not in result

    @patch("database.get_connection")
    def test_get_content_null_body(self, mock_get_conn):
        """Test handling NULL body_text in database."""
        import database

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {
            "subject": "No Body Stored",
            "from_name": "Sender",
            "from_email": "sender@example.com",
            "body_text": None  # NULL in database
        }
        mock_cursor.fetchall.return_value = []

        result = database.get_email_content_for_processing(
            account="test@example.com",
            message_id="null-body"
        )

        assert result["body"] == ""  # Should be empty string, not None


class TestStoreAttachment:
    """Test store_attachment function."""

    @patch("database.get_connection")
    def test_store_attachment_with_text(self, mock_get_conn):
        """Test storing attachment with extracted text."""
        import database

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 42}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = database.store_attachment(
            account="test@example.com",
            message_id="msg123",
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=15000,
            extracted_text="This is the PDF content.",
            extraction_status="success"
        )

        assert result == 42
        mock_cursor.execute.assert_called_once()

    @patch("database.get_connection")
    def test_store_attachment_failed_extraction(self, mock_get_conn):
        """Test storing attachment with failed extraction."""
        import database

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 43}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = database.store_attachment(
            account="test@example.com",
            message_id="msg456",
            filename="corrupted.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            extracted_text=None,
            extraction_status="failed",
            extraction_error="PDF parsing error"
        )

        assert result == 43

        # Verify error message is in parameters
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        assert "PDF parsing error" in params
