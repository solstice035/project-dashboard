"""Adapter wrapping SchoolEmailAutomation for dashboard integration."""

import logging
import sys
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Add SchoolEmailAutomation to path if not installed as package
SCHOOL_AUTOMATION_PATH = Path("/Users/nick/dev/SchoolEmailAutomation/src")
if SCHOOL_AUTOMATION_PATH.exists() and str(SCHOOL_AUTOMATION_PATH) not in sys.path:
    sys.path.insert(0, str(SCHOOL_AUTOMATION_PATH))


class SchoolAdapter:
    """Adapter wrapping SchoolEmailAutomation orchestrator.

    Provides:
    - Direct Python API instead of subprocess calls
    - Integration with dashboard notification system
    - Unified result format for job tracking
    """

    def __init__(
        self,
        notify_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """Initialize school email adapter.

        Args:
            notify_callback: Optional callback for sending notifications.
                            Signature: (title, body, priority) where priority
                            is 'urgent', 'digest', or 'info'
        """
        self.notify_callback = notify_callback
        self._automation = None

    @property
    def automation(self):
        """Lazy-load SchoolAutomation to avoid import errors if not available."""
        if self._automation is None:
            try:
                from school_automation.orchestrator import SchoolAutomation
                self._automation = SchoolAutomation()
                logger.info("SchoolAutomation loaded successfully")
            except ImportError as e:
                logger.error(f"Failed to import SchoolAutomation: {e}")
                raise RuntimeError(
                    "SchoolEmailAutomation not available. "
                    "Ensure it's installed or the path is correct."
                ) from e
            except FileNotFoundError as e:
                logger.error(f"SchoolAutomation config not found: {e}")
                raise RuntimeError(
                    f"SchoolEmailAutomation config missing: {e}"
                ) from e
            except Exception as e:
                logger.error(f"Failed to initialize SchoolAutomation: {e}")
                raise RuntimeError(
                    f"SchoolEmailAutomation initialization failed: {e}"
                ) from e
        return self._automation

    def is_available(self) -> bool:
        """Check if SchoolAutomation is available."""
        try:
            _ = self.automation
            return True
        except (RuntimeError, FileNotFoundError, Exception) as e:
            logger.debug(f"SchoolAutomation not available: {e}")
            return False

    def process_emails(
        self,
        days: int = 1,
        dry_run: bool = False,
        child: Optional[str] = None,
        min_confidence: str = "low"
    ) -> dict:
        """Process school emails and send notifications for urgent items.

        Args:
            days: Number of days to look back
            dry_run: If True, don't create tasks/events
            child: Optional filter to specific child
            min_confidence: Minimum confidence level (low/medium/high)

        Returns:
            Processing results dictionary
        """
        logger.info(f"Processing school emails: days={days}, dry_run={dry_run}")

        try:
            results = self.automation.process_emails(
                days=days,
                dry_run=dry_run,
                child=child,
                preview=False,
                min_confidence=min_confidence
            )

            # Send notifications for urgent items
            if not dry_run and results.get("urgent_notifications", 0) > 0:
                self._notify_urgent(results)

            return {
                "success": True,
                "emails_processed": results.get("emails_processed", 0),
                "actions_extracted": results.get("actions_extracted", 0),
                "tasks_created": results.get("tasks_created", 0),
                "events_created": results.get("events_created", 0),
                "urgent_count": results.get("urgent_notifications", 0),
                "errors": results.get("errors", []),
                "duration_seconds": results.get("duration_seconds", 0),
            }

        except Exception as e:
            logger.error(f"School email processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "emails_processed": 0,
                "tasks_created": 0,
            }

    def get_status(self) -> dict:
        """Get current school automation status.

        Returns:
            Status dictionary with metrics and error counts
        """
        try:
            status = self.automation.get_status()
            return {
                "available": True,
                "date": status.get("date"),
                "children": status.get("children", []),
                "unresolved_errors": status.get("unresolved_errors", 0),
                "metrics": status.get("metrics", {}),
            }
        except Exception as e:
            logger.error(f"Failed to get school status: {e}")
            return {
                "available": False,
                "error": str(e),
            }

    def preview_actions(self, days: int = 1) -> list[dict]:
        """Preview what actions would be extracted without creating tasks.

        Args:
            days: Number of days to look back

        Returns:
            List of extracted actions
        """
        try:
            return self.automation.preview_actions(days=days)
        except Exception as e:
            logger.error(f"Failed to preview actions: {e}")
            return []

    def generate_digest(self) -> Optional[str]:
        """Generate daily digest text.

        Returns:
            Digest text or None if nothing to report
        """
        try:
            return self.automation.send_daily_digest()
        except Exception as e:
            logger.error(f"Failed to generate digest: {e}")
            return None

    def _notify_urgent(self, results: dict) -> None:
        """Send notification for urgent school items."""
        if not self.notify_callback:
            logger.warning("No notification callback configured for urgent school items")
            return

        urgent_count = results.get("urgent_notifications", 0)
        tasks_created = results.get("tasks_created", 0)

        title = f"School: {urgent_count} Urgent Action(s)"
        body = f"Processed {results.get('emails_processed', 0)} emails\n"
        body += f"Created {tasks_created} tasks, {results.get('events_created', 0)} events\n"
        body += f"\n{urgent_count} items require immediate attention."

        try:
            self.notify_callback(title, body, "urgent")
        except Exception as e:
            logger.error(f"Failed to send urgent notification: {e}")

    def format_digest_notification(self, results: dict) -> tuple[str, str]:
        """Format processing results as digest notification.

        Args:
            results: Processing results from process_emails()

        Returns:
            Tuple of (title, body) for notification
        """
        emails = results.get("emails_processed", 0)
        tasks = results.get("tasks_created", 0)
        events = results.get("events_created", 0)

        title = f"School Email Summary: {emails} processed"

        lines = [
            f"*Processed*: {emails} emails",
            f"*Tasks created*: {tasks}",
            f"*Events created*: {events}",
        ]

        if results.get("errors"):
            lines.append(f"*Errors*: {len(results['errors'])}")

        body = "\n".join(lines)
        return title, body
