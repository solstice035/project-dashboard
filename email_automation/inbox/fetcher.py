"""Inbox fetching using IMAP with PDF attachment extraction."""

import email
import imaplib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Gmail IMAP settings
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
IMAP_TIMEOUT = 30  # seconds

# Attachment settings
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB max for PDF extraction
EXTRACTABLE_TYPES = ['application/pdf', 'text/plain', 'text/html']


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, Optional[str]]:
    """Extract text from PDF bytes.

    Returns:
        Tuple of (extracted_text, error_message)
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))

        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        logger.debug(f"Extracted {len(full_text)} chars from PDF ({len(reader.pages)} pages)")
        return full_text, None

    except ImportError:
        return "", "pypdf not installed"
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return "", str(e)


@dataclass
class EmailAttachment:
    """An email attachment with optional extracted content."""
    filename: str
    content_type: str
    size_bytes: int
    extracted_text: Optional[str] = None
    extraction_status: str = "skipped"  # success, failed, skipped
    extraction_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "has_text": bool(self.extracted_text),
            "text_length": len(self.extracted_text) if self.extracted_text else 0,
            "extraction_status": self.extraction_status,
            "extraction_error": self.extraction_error,
        }


@dataclass
class EmailMessage:
    """A single email message summary with attachments."""
    id: str
    subject: str
    from_name: str
    from_email: str
    date: str
    attachments: list[EmailAttachment] = field(default_factory=list)
    body_preview: str = ""
    body_full: str = ""  # Full body text for processing

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0

    @property
    def has_pdf(self) -> bool:
        return any(a.content_type == 'application/pdf' for a in self.attachments)

    @property
    def attachment_summary(self) -> str:
        if not self.attachments:
            return ""
        names = [a.filename for a in self.attachments[:3]]
        if len(self.attachments) > 3:
            names.append(f"+{len(self.attachments) - 3} more")
        return ", ".join(names)


@dataclass
class AccountInbox:
    """Inbox data for a single email account."""
    account: str
    name: str
    priority: str
    status: str = "ok"
    total_unread: int = 0
    urgent: list[EmailMessage] = field(default_factory=list)
    from_people: list[EmailMessage] = field(default_factory=list)
    newsletters: int = 0
    error: Optional[str] = None
    fetch_duration_ms: int = 0
    attachments_processed: int = 0
    pdfs_extracted: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "account": self.account,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "total_unread": self.total_unread,
            "urgent": [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "from": m.from_name,
                    "date": m.date,
                    "has_attachments": m.has_attachments,
                    "has_pdf": m.has_pdf,
                    "attachment_summary": m.attachment_summary,
                }
                for m in self.urgent
            ],
            "from_people": [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "from": m.from_name,
                    "date": m.date,
                    "has_attachments": m.has_attachments,
                    "has_pdf": m.has_pdf,
                    "attachment_summary": m.attachment_summary,
                }
                for m in self.from_people
            ],
            "newsletters": self.newsletters,
            "error": self.error,
            "fetch_duration_ms": self.fetch_duration_ms,
            "attachments_processed": self.attachments_processed,
            "pdfs_extracted": self.pdfs_extracted,
        }


@dataclass
class FetchResult:
    """Result of a complete inbox fetch operation."""
    accounts: list[AccountInbox]
    total_unread: int
    total_urgent: int
    total_duration_ms: int
    fetched_at: datetime
    errors: list[str]
    total_attachments: int = 0
    total_pdfs_extracted: int = 0

    def to_dict(self) -> dict:
        return {
            "accounts": [a.to_dict() for a in self.accounts],
            "total_unread": self.total_unread,
            "total_urgent": self.total_urgent,
            "total_duration_ms": self.total_duration_ms,
            "fetched_at": self.fetched_at.isoformat(),
            "errors": self.errors,
            "total_attachments": self.total_attachments,
            "total_pdfs_extracted": self.total_pdfs_extracted,
        }


class InboxFetcher:
    """Fetches inbox summaries using IMAP with attachment extraction."""

    # Automated sender patterns to filter out
    AUTOMATED_PATTERNS = [
        "noreply", "no-reply", "notifications", "mailer-daemon",
        "postmaster", "donotreply", "automated", "newsletter",
        "updates@", "news@", "info@", "support@", "team@",
        "marketing@", "hello@", "contact@", "billing@"
    ]

    def __init__(
        self,
        config: dict,
        db_store_callback: Optional[Callable[[list[dict]], None]] = None,
        db_log_callback: Optional[Callable[[str, str, str, bool, Optional[str]], None]] = None,
        db_attachment_callback: Optional[Callable] = None
    ):
        """Initialize with email config section.

        Args:
            config: The 'email' section from config.yaml
            db_store_callback: Callback to store inbox snapshot
            db_log_callback: Callback to log fetch operations
            db_attachment_callback: Callback to store attachments
                Signature: (account, message_id, filename, content_type,
                           size_bytes, extracted_text, status, error) -> id
        """
        self.accounts = config.get("accounts", [])
        self.db_store = db_store_callback
        self.db_log = db_log_callback
        self.db_attachment = db_attachment_callback
        self.extract_pdfs = config.get("extract_pdfs", True)
        logger.info(f"InboxFetcher initialized with {len(self.accounts)} accounts, PDF extraction: {self.extract_pdfs}")

    def fetch_all_accounts(self, max_results: int = 50, store_to_db: bool = True) -> FetchResult:
        """Fetch inbox data for all configured accounts."""
        start_time = datetime.now()
        logger.info(f"Starting inbox fetch for {len(self.accounts)} accounts")

        results = []
        errors = []
        total_attachments = 0
        total_pdfs = 0

        for account_info in self.accounts:
            account_email = account_info["email"]
            logger.debug(f"Fetching inbox for {account_email}")

            inbox = self.fetch_account(
                account=account_email,
                app_password=account_info.get("app_password", ""),
                name=account_info.get("name", account_email),
                priority=account_info.get("priority", "medium"),
                max_results=max_results
            )
            results.append(inbox)
            total_attachments += inbox.attachments_processed
            total_pdfs += inbox.pdfs_extracted

            if inbox.status != "ok":
                errors.append(f"{account_email}: {inbox.error}")

        total_duration = int((datetime.now() - start_time).total_seconds() * 1000)
        total_unread = sum(a.total_unread for a in results if a.status == "ok")
        total_urgent = sum(len(a.urgent) for a in results if a.status == "ok")

        logger.info(
            f"Inbox fetch complete: {len(results)} accounts, "
            f"{total_unread} unread, {total_urgent} urgent, "
            f"{total_attachments} attachments, {total_pdfs} PDFs extracted, "
            f"{total_duration}ms, {len(errors)} errors"
        )

        # Store to database
        if store_to_db and self.db_store:
            try:
                self.db_store([a.to_dict() for a in results])
                logger.debug("Inbox snapshot stored to database")
            except Exception as e:
                logger.error(f"Failed to store inbox snapshot: {e}")
                errors.append(f"DB storage failed: {e}")

        return FetchResult(
            accounts=results,
            total_unread=total_unread,
            total_urgent=total_urgent,
            total_duration_ms=total_duration,
            fetched_at=start_time,
            errors=errors,
            total_attachments=total_attachments,
            total_pdfs_extracted=total_pdfs
        )

    def fetch_account(
        self,
        account: str,
        app_password: str,
        name: str = "",
        priority: str = "medium",
        max_results: int = 50
    ) -> AccountInbox:
        """Fetch inbox summary for a single email account via IMAP."""
        start_time = datetime.now()
        result = AccountInbox(
            account=account,
            name=name or account,
            priority=priority
        )

        if not app_password:
            result.status = "error"
            result.error = "No app_password configured"
            logger.warning(f"[{account}] No app_password configured")
            self._log_fetch(account, "connect", "No app_password", False, result.error)
            return result

        mail = None
        try:
            # Connect to Gmail IMAP
            logger.debug(f"[{account}] Connecting to IMAP server")
            imaplib.IMAP4_SSL.timeout = IMAP_TIMEOUT
            mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)

            logger.debug(f"[{account}] Authenticating")
            mail.login(account, app_password)
            self._log_fetch(account, "auth", "Login successful", True, None)

            logger.debug(f"[{account}] Selecting INBOX")
            mail.select("INBOX", readonly=True)

            # Get total unread count
            logger.debug(f"[{account}] Searching for unread messages")
            _, unread_data = mail.search(None, "UNSEEN")
            unread_ids = unread_data[0].split() if unread_data[0] else []
            result.total_unread = len(unread_ids)
            logger.debug(f"[{account}] Found {result.total_unread} unread messages")

            # Get urgent (flagged/starred)
            logger.debug(f"[{account}] Searching for flagged messages")
            _, flagged_data = mail.search(None, "UNSEEN", "FLAGGED")
            flagged_ids = flagged_data[0].split() if flagged_data[0] else []
            urgent_messages, urgent_attach, urgent_pdfs = self._fetch_messages(
                mail, flagged_ids[:5], account, extract_attachments=True
            )
            result.urgent = urgent_messages
            result.attachments_processed += urgent_attach
            result.pdfs_extracted += urgent_pdfs
            logger.debug(f"[{account}] Found {len(result.urgent)} urgent messages")

            # Get messages from real people (filter out automated)
            if unread_ids:
                recent_ids = unread_ids[-min(max_results, len(unread_ids)):]
                logger.debug(f"[{account}] Fetching {len(recent_ids)} recent messages")
                all_messages, all_attach, all_pdfs = self._fetch_messages(
                    mail, recent_ids, account, extract_attachments=True
                )
                result.attachments_processed += all_attach
                result.pdfs_extracted += all_pdfs

                # Filter out automated senders
                result.from_people = [
                    m for m in all_messages
                    if not self._is_automated_sender(m.from_name, m.from_email)
                ][:7]

                # Count newsletters
                result.newsletters = len([
                    m for m in all_messages
                    if self._is_automated_sender(m.from_name, m.from_email)
                ])
                logger.debug(
                    f"[{account}] Filtered: {len(result.from_people)} from people, "
                    f"{result.newsletters} newsletters"
                )

            mail.logout()
            logger.debug(f"[{account}] Disconnected successfully")

            result.fetch_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._log_fetch(
                account, "fetch",
                f"unread={result.total_unread}, urgent={len(result.urgent)}, "
                f"attachments={result.attachments_processed}, pdfs={result.pdfs_extracted}",
                True, None
            )

            logger.info(
                f"[{account}] Fetch complete: {result.total_unread} unread, "
                f"{len(result.urgent)} urgent, {result.attachments_processed} attachments, "
                f"{result.pdfs_extracted} PDFs, {result.fetch_duration_ms}ms"
            )

        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            logger.error(f"[{account}] IMAP error: {error_msg}")
            result.status = "error"
            result.error = f"IMAP error: {error_msg}"
            self._log_fetch(account, "imap_error", error_msg, False, result.error)

        except TimeoutError:
            logger.warning(f"[{account}] Connection timed out after {IMAP_TIMEOUT}s")
            result.status = "timeout"
            result.error = f"Connection timed out after {IMAP_TIMEOUT}s"
            self._log_fetch(account, "timeout", f"Timeout after {IMAP_TIMEOUT}s", False, result.error)

        except ConnectionRefusedError as e:
            logger.error(f"[{account}] Connection refused: {e}")
            result.status = "error"
            result.error = "Connection refused"
            self._log_fetch(account, "connection_refused", str(e), False, result.error)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{account}] Unexpected error: {error_msg}", exc_info=True)
            result.status = "error"
            result.error = error_msg
            self._log_fetch(account, "error", error_msg, False, result.error)

        finally:
            if mail:
                try:
                    mail.logout()
                except (imaplib.IMAP4.error, OSError) as e:
                    logger.debug(f"[{account}] Error during IMAP logout (connection may already be closed): {e}")
            result.fetch_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return result

    def _fetch_messages(
        self,
        mail: imaplib.IMAP4_SSL,
        message_ids: list,
        account: str,
        extract_attachments: bool = True
    ) -> tuple[list[EmailMessage], int, int]:
        """Fetch message details including attachments.

        Returns:
            Tuple of (messages, attachment_count, pdf_count)
        """
        messages = []
        total_attachments = 0
        total_pdfs = 0

        for msg_id in reversed(message_ids):  # Newest first
            try:
                # Fetch full message for attachment parsing
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)

                subject = self._decode_header(email_message.get("Subject", "(no subject)"))
                from_field = self._decode_header(email_message.get("From", "unknown"))
                date_field = email_message.get("Date", "")

                # Parse from field
                from_name, from_email_addr = self._parse_from_field(from_field)
                msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)

                # Extract attachments
                attachments = []
                if extract_attachments:
                    attachments, pdfs_extracted = self._extract_attachments(
                        email_message, account, msg_id_str
                    )
                    total_attachments += len(attachments)
                    total_pdfs += pdfs_extracted

                # Get body text
                body_preview, body_full = self._get_email_body(email_message)

                messages.append(EmailMessage(
                    id=msg_id_str,
                    subject=subject[:100],
                    from_name=from_name[:50],
                    from_email=from_email_addr[:100],
                    date=date_field[:30],
                    attachments=attachments,
                    body_preview=body_preview,
                    body_full=body_full
                ))

            except Exception as e:
                logger.debug(f"[{account}] Error parsing message {msg_id}: {e}")
                continue

        return messages, total_attachments, total_pdfs

    def _extract_attachments(
        self,
        email_message: email.message.Message,
        account: str,
        message_id: str
    ) -> tuple[list[EmailAttachment], int]:
        """Extract attachments from email, including PDF text.

        Returns:
            Tuple of (attachments, pdfs_extracted_count)
        """
        attachments = []
        pdfs_extracted = 0

        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip non-attachments
            if "attachment" not in content_disposition:
                continue

            filename = part.get_filename()
            if not filename:
                continue

            filename = self._decode_header(filename)

            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                size_bytes = len(payload)
                extracted_text = None
                extraction_status = "skipped"
                extraction_error = None

                # Extract text from PDFs
                if content_type == "application/pdf" and self.extract_pdfs:
                    if size_bytes <= MAX_ATTACHMENT_SIZE:
                        logger.debug(f"[{account}] Extracting PDF: {filename} ({size_bytes} bytes)")
                        extracted_text, extraction_error = extract_pdf_text(payload)
                        extraction_status = "success" if extracted_text else "failed"
                        if extracted_text:
                            pdfs_extracted += 1
                            logger.info(f"[{account}] Extracted {len(extracted_text)} chars from {filename}")
                    else:
                        extraction_status = "skipped"
                        extraction_error = f"File too large: {size_bytes} bytes"
                        logger.debug(f"[{account}] Skipping large PDF: {filename}")

                # Extract plain text attachments
                elif content_type == "text/plain":
                    try:
                        extracted_text = payload.decode('utf-8', errors='replace')
                        extraction_status = "success"
                    except (UnicodeDecodeError, AttributeError) as e:
                        extraction_status = "failed"
                        extraction_error = f"Text decode error: {e}"
                        logger.debug(f"[{account}] Failed to decode text attachment: {e}")

                attachment = EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    extracted_text=extracted_text,
                    extraction_status=extraction_status,
                    extraction_error=extraction_error
                )
                attachments.append(attachment)

                # Store to database
                if self.db_attachment:
                    try:
                        self.db_attachment(
                            account=account,
                            message_id=message_id,
                            filename=filename,
                            content_type=content_type,
                            size_bytes=size_bytes,
                            extracted_text=extracted_text,
                            extraction_status=extraction_status,
                            extraction_error=extraction_error
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store attachment: {e}")

            except Exception as e:
                logger.warning(f"[{account}] Error processing attachment {filename}: {e}")
                attachments.append(EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    size_bytes=0,
                    extraction_status="failed",
                    extraction_error=str(e)
                ))

        return attachments, pdfs_extracted

    def _get_email_body(self, email_message: email.message.Message, preview_length: int = 200) -> tuple[str, str]:
        """Extract email body text.

        Returns:
            Tuple of (preview, full_text) where preview is truncated for display
        """
        for part in email_message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        full_text = payload.decode('utf-8', errors='replace')
                        # Clean up whitespace for full text
                        full_text = '\n'.join(line.strip() for line in full_text.splitlines())
                        # Create preview (single line, truncated)
                        preview = ' '.join(full_text.split())[:preview_length]
                        return preview, full_text
                except (UnicodeDecodeError, AttributeError) as e:
                    logger.debug(f"Failed to extract email body: {e}")
        return "", ""

    def _parse_from_field(self, from_field: str) -> tuple[str, str]:
        """Parse from field into name and email."""
        if "<" in from_field and ">" in from_field:
            name = from_field.split("<")[0].strip().strip('"').strip("'")
            email_addr = from_field.split("<")[1].split(">")[0].strip()
        else:
            name = ""
            email_addr = from_field.strip()

        if not name:
            name = email_addr.split("@")[0]

        return name, email_addr

    def _decode_header(self, header_value: str) -> str:
        """Decode email header handling various encodings."""
        if not header_value:
            return ""

        try:
            decoded_parts = decode_header(header_value)
            result = []
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(encoding or "utf-8", errors="replace"))
                else:
                    result.append(part)
            return " ".join(result)
        except (UnicodeDecodeError, LookupError, TypeError) as e:
            logger.debug(f"Header decode fallback for '{header_value[:50]}...': {e}")
            return str(header_value)

    def _is_automated_sender(self, from_name: str, from_email: str) -> bool:
        """Check if sender appears to be automated/newsletter."""
        combined = f"{from_name} {from_email}".lower()
        return any(pattern in combined for pattern in self.AUTOMATED_PATTERNS)

    def _log_fetch(
        self,
        account: str,
        operation: str,
        details: str,
        success: bool,
        error: Optional[str]
    ):
        """Log fetch operation to database if callback configured."""
        if self.db_log:
            try:
                self.db_log(account, operation, details, success, error)
            except Exception as e:
                logger.warning(f"Failed to log fetch operation: {e}")
