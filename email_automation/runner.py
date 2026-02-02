#!/usr/bin/env python3
"""CLI entry point for email automation tasks.

Usage:
    python -m email_automation.runner school --days 3
    python -m email_automation.runner inbox
    python -m email_automation.runner daily
    python -m email_automation.runner status
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    """Load configuration from config.yaml."""
    if not CONFIG_PATH.exists():
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def setup_notifications(config: dict):
    """Setup notification router from config."""
    from .notifications import NotificationRouter, Priority

    notifications_config = config.get("notifications", {})

    # Optional: setup database logging callback
    db_callback = None
    try:
        from database import log_notification
        db_callback = log_notification
    except ImportError:
        logger.warning("Database module not available, notifications won't be logged")

    return NotificationRouter(notifications_config, db_callback)


def cmd_school(args, config: dict) -> int:
    """Process school emails."""
    from .school import SchoolAdapter
    from .notifications import Priority

    router = setup_notifications(config)

    def notify(title: str, body: str, priority: str):
        p = Priority.URGENT if priority == "urgent" else Priority.INFO
        router.send(title, body, p, source="school")

    adapter = SchoolAdapter(notify_callback=notify)

    if not adapter.is_available():
        print("Error: SchoolEmailAutomation not available")
        return 1

    results = adapter.process_emails(
        days=args.days,
        dry_run=args.dry_run,
        child=args.child,
        min_confidence=args.min_confidence
    )

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        mode = "DRY RUN " if args.dry_run else ""
        print(f"\n{mode}School Email Processing Results:")
        print(f"  Success: {results.get('success', False)}")
        print(f"  Emails processed: {results.get('emails_processed', 0)}")
        print(f"  Actions extracted: {results.get('actions_extracted', 0)}")
        print(f"  Tasks created: {results.get('tasks_created', 0)}")
        print(f"  Events created: {results.get('events_created', 0)}")
        print(f"  Urgent items: {results.get('urgent_count', 0)}")
        if results.get('errors'):
            print(f"  Errors: {len(results['errors'])}")
        if results.get('duration_seconds'):
            print(f"  Duration: {results['duration_seconds']:.1f}s")

    return 0 if results.get('success', True) else 1


def cmd_inbox(args, config: dict) -> int:
    """Generate and send inbox digest."""
    from .inbox import InboxFetcher, InboxDigest

    # Setup database callbacks
    db_store = None
    db_log = None
    db_cache = None
    db_attachment = None
    try:
        import database as db
        db_store = db.store_inbox_snapshot
        db_log = db.log_email_fetch
        db_cache = db.cache_inbox_message
        db_attachment = db.store_attachment
        logger.info("Database callbacks configured")
    except ImportError:
        logger.warning("Database module not available")

    router = setup_notifications(config)
    email_config = config.get("email", {})

    fetcher = InboxFetcher(
        email_config,
        db_store_callback=db_store,
        db_log_callback=db_log,
        db_attachment_callback=db_attachment
    )
    digest = InboxDigest(fetcher, db_cache_message=db_cache)

    if args.json:
        data = digest.generate()
        print(json.dumps(data, indent=2, default=str))
        return 0

    # Generate and optionally send notification
    title, body = digest.format_for_notification(include_details=True)

    print(f"\n{title}")
    print("-" * 40)
    print(body)

    if args.notify:
        results = router.send_digest(title, body, source="inbox")
        for r in results:
            status = "sent" if r.success else f"failed: {r.error}"
            print(f"\nNotification ({r.channel}): {status}")

    return 0


def cmd_daily(args, config: dict) -> int:
    """Generate combined daily digest."""
    from .inbox import InboxFetcher, InboxDigest
    from .school import SchoolAdapter

    # Setup database callbacks
    db_store = None
    db_log = None
    try:
        import database as db
        db_store = db.store_inbox_snapshot
        db_log = db.log_email_fetch
    except ImportError:
        logger.warning("Database module not available")

    router = setup_notifications(config)
    email_config = config.get("email", {})

    # Gather inbox stats
    fetcher = InboxFetcher(
        email_config,
        db_store_callback=db_store,
        db_log_callback=db_log
    )
    inbox_digest = InboxDigest(fetcher)
    inbox_stats = inbox_digest.get_summary_stats()

    # Gather school stats
    school_adapter = SchoolAdapter()
    school_status = school_adapter.get_status() if school_adapter.is_available() else None

    # Format combined digest
    title = "Daily Email Summary"
    lines = []

    # Inbox section
    lines.append("*Inbox*")
    lines.append(f"  Total unread: {inbox_stats['total_unread']}")
    lines.append(f"  Urgent: {inbox_stats['total_urgent']}")
    lines.append(f"  Newsletters: {inbox_stats['total_newsletters']}")

    # School section
    if school_status and school_status.get('available'):
        lines.append("")
        lines.append("*School*")
        lines.append(f"  Children: {', '.join(school_status.get('children', []))}")
        lines.append(f"  Unresolved errors: {school_status.get('unresolved_errors', 0)}")

    body = "\n".join(lines)

    if args.json:
        print(json.dumps({
            "title": title,
            "body": body,
            "inbox": inbox_stats,
            "school": school_status
        }, indent=2, default=str))
        return 0

    print(f"\n{title}")
    print("-" * 40)
    print(body)

    if args.notify:
        results = router.send_digest(title, body, source="combined")
        for r in results:
            status = "sent" if r.success else f"failed: {r.error}"
            print(f"\nNotification ({r.channel}): {status}")

    return 0


def cmd_status(args, config: dict) -> int:
    """Show email automation status."""
    from .school import SchoolAdapter
    from .inbox import InboxFetcher

    status = {
        "config_loaded": True,
        "notifications_configured": bool(config.get("notifications")),
        "scheduling_enabled": config.get("scheduling", {}).get("enabled", False),
    }

    # Check school adapter
    school = SchoolAdapter()
    status["school_available"] = school.is_available()
    if school.is_available():
        status["school_status"] = school.get_status()

    # Check inbox
    email_config = config.get("email", {})
    status["inbox_accounts"] = len(email_config.get("accounts", []))

    # Check notifications
    router = setup_notifications(config)
    status["notification_channels"] = router.get_status()

    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print("\nEmail Automation Status")
        print("-" * 40)
        print(f"Config loaded: {status['config_loaded']}")
        print(f"Notifications configured: {status['notifications_configured']}")
        print(f"Scheduling enabled: {status['scheduling_enabled']}")
        print(f"School automation available: {status['school_available']}")
        print(f"Inbox accounts: {status['inbox_accounts']}")
        print("\nNotification Channels:")
        for channel, info in status['notification_channels'].items():
            available = "available" if info['available'] else "not available"
            print(f"  {channel}: {available}")

    return 0


def cmd_test_notifications(args, config: dict) -> int:
    """Test notification channels."""
    router = setup_notifications(config)
    results = router.test_channels()

    print("\nNotification Test Results")
    print("-" * 40)
    for channel, result in results.items():
        status = "SUCCESS" if result.success else f"FAILED: {result.error}"
        print(f"  {channel}: {status}")

    return 0 if all(r.success for r in results.values()) else 1


def main():
    parser = argparse.ArgumentParser(
        description="Email Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  school    Process school emails and create tasks/events
  inbox     Generate inbox digest
  daily     Generate combined daily digest
  status    Show automation status
  test      Test notification channels

Examples:
  python -m email_automation.runner school --days 3
  python -m email_automation.runner inbox --notify
  python -m email_automation.runner daily --notify
  python -m email_automation.runner status
  python -m email_automation.runner test
        """
    )

    parser.add_argument("command", choices=["school", "inbox", "daily", "status", "test"])
    parser.add_argument("--days", type=int, default=1, help="Days to look back (school)")
    parser.add_argument("--dry-run", action="store_true", help="Don't create tasks/events")
    parser.add_argument("--child", help="Filter to specific child (school)")
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="low",
                        help="Minimum confidence level (school)")
    parser.add_argument("--notify", action="store_true", help="Send notification after processing")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    config = load_config()

    commands = {
        "school": cmd_school,
        "inbox": cmd_inbox,
        "daily": cmd_daily,
        "status": cmd_status,
        "test": cmd_test_notifications,
    }

    return commands[args.command](args, config)


if __name__ == "__main__":
    sys.exit(main())
