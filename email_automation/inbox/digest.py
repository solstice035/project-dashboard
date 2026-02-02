"""Inbox digest formatting for notifications with database integration."""

import logging
from datetime import datetime
from typing import Optional, Callable

from .fetcher import InboxFetcher, FetchResult

logger = logging.getLogger(__name__)


class InboxDigest:
    """Generates formatted inbox digests for notifications."""

    def __init__(
        self,
        fetcher: InboxFetcher,
        db_cache_message: Optional[Callable] = None
    ):
        """Initialize with an InboxFetcher instance.

        Args:
            fetcher: Configured InboxFetcher to use for data retrieval
            db_cache_message: Optional callback to cache messages to database
                             Signature matches database.cache_inbox_message
        """
        self.fetcher = fetcher
        self.db_cache_message = db_cache_message

    def generate(self, store_to_db: bool = True) -> dict:
        """Generate complete inbox digest data.

        Args:
            store_to_db: Whether to store results to database

        Returns:
            Dict with summary and per-account data
        """
        logger.info("Generating inbox digest")
        result = self.fetcher.fetch_all_accounts(store_to_db=store_to_db)

        # Cache individual messages if callback provided
        if self.db_cache_message:
            self._cache_messages(result)

        return {
            "generated_at": result.fetched_at.isoformat(),
            "fetch_time_ms": result.total_duration_ms,
            "summary": {
                "total_unread": result.total_unread,
                "total_urgent": result.total_urgent,
                "accounts_checked": len(result.accounts),
                "errors": len(result.errors),
            },
            "accounts": [a.to_dict() for a in result.accounts],
            "errors": result.errors,
        }

    def _cache_messages(self, result: FetchResult) -> None:
        """Cache messages to database for analytics."""
        cached_count = 0
        for account in result.accounts:
            if account.status != "ok":
                continue

            # Cache urgent messages
            for msg in account.urgent:
                try:
                    self.db_cache_message(
                        account=account.account,
                        message_id=msg.id,
                        subject=msg.subject,
                        from_name=msg.from_name,
                        from_email=msg.from_email,
                        date_header=msg.date,
                        is_urgent=True,
                        is_from_person=True
                    )
                    cached_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cache urgent message: {e}")

            # Cache messages from people
            for msg in account.from_people:
                try:
                    self.db_cache_message(
                        account=account.account,
                        message_id=msg.id,
                        subject=msg.subject,
                        from_name=msg.from_name,
                        from_email=msg.from_email,
                        date_header=msg.date,
                        is_urgent=False,
                        is_from_person=True
                    )
                    cached_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cache person message: {e}")

        if cached_count > 0:
            logger.debug(f"Cached {cached_count} messages to database")

    def format_for_notification(self, include_details: bool = True) -> tuple[str, str]:
        """Generate digest formatted for notification delivery.

        Args:
            include_details: Whether to include per-account details

        Returns:
            Tuple of (title, body) for notification
        """
        data = self.generate()
        summary = data["summary"]

        title = f"Inbox: {summary['total_unread']} unread"
        if summary["total_urgent"] > 0:
            title += f" ({summary['total_urgent']} urgent)"

        lines = []

        if include_details:
            for account in data["accounts"]:
                if account["status"] != "ok":
                    lines.append(f"*{account['name']}*: {account['error']}")
                    continue

                line = f"*{account['name']}*: {account['total_unread']} unread"
                if account["urgent"]:
                    line += f" ({len(account['urgent'])} urgent)"
                lines.append(line)

                # List urgent items
                for msg in account["urgent"][:3]:
                    lines.append(f"  - {msg['subject'][:40]}")

                # List messages from people
                if account["from_people"]:
                    people_line = f"  From people: {len(account['from_people'])} messages"
                    lines.append(people_line)

        else:
            # Compact format
            lines.append(f"Total: {summary['total_unread']} unread across {summary['accounts_checked']} accounts")
            if summary["total_urgent"] > 0:
                lines.append(f"Urgent: {summary['total_urgent']} messages need attention")

        if summary["errors"] > 0:
            lines.append(f"\n_{summary['errors']} account(s) had errors_")

        body = "\n".join(lines)
        return title, body

    def format_urgent_only(self) -> Optional[tuple[str, str]]:
        """Generate notification only if there are urgent items.

        Returns:
            Tuple of (title, body) or None if no urgent items
        """
        data = self.generate()

        urgent_items = []
        for account in data["accounts"]:
            if account["status"] == "ok":
                for msg in account["urgent"]:
                    urgent_items.append({
                        "account": account["name"],
                        "subject": msg["subject"],
                        "from": msg["from"],
                    })

        if not urgent_items:
            logger.debug("No urgent items found")
            return None

        logger.info(f"Found {len(urgent_items)} urgent items")
        title = f"{len(urgent_items)} Urgent Email(s)"

        lines = []
        for item in urgent_items[:5]:
            lines.append(f"*{item['account']}*: {item['subject']}")
            lines.append(f"  From: {item['from']}")

        if len(urgent_items) > 5:
            lines.append(f"... and {len(urgent_items) - 5} more")

        body = "\n".join(lines)
        return title, body

    def get_summary_stats(self) -> dict:
        """Get summary statistics without full message details.

        Returns:
            Dict with account-level stats only
        """
        result = self.fetcher.fetch_all_accounts(store_to_db=False)

        stats = {
            "total_unread": result.total_unread,
            "total_urgent": result.total_urgent,
            "total_newsletters": 0,
            "fetch_duration_ms": result.total_duration_ms,
            "accounts": {},
            "errors": result.errors,
        }

        for account in result.accounts:
            if account.status == "ok":
                stats["total_newsletters"] += account.newsletters
                stats["accounts"][account.name] = {
                    "unread": account.total_unread,
                    "urgent": len(account.urgent),
                    "from_people": len(account.from_people),
                    "newsletters": account.newsletters,
                    "fetch_duration_ms": account.fetch_duration_ms,
                }
            else:
                stats["accounts"][account.name] = {
                    "error": account.error,
                    "status": account.status,
                }

        return stats
