---
name: school-digest-generator
description: "Generate daily digest of processed school emails for Telegram"
---

# School Digest Generator

Creates formatted daily digest of all processed school emails, categorized by urgency, for delivery via Telegram.

## Invocation

```
school:send-digest [--date YYYY-MM-DD]
```

## Process

1. Query database for items processed today (or specified date)
2. Categorize items by urgency
3. Format Telegram-friendly message
4. Send via Clawdbot Telegram integration

## Digest Format

```
📧 **School Email Digest - Jan 27**

🔴 **URGENT (2):**
- [Elodie] Trip payment due by tomorrow
- [Nathaniel] Costume needed for play (Thursday)

📋 **NEW TASKS (5):**
- [Elodie] Science trip permission form (due Feb 8)
- [Florence] Book Week costume ideas (due Feb 12)
- [All] Spring term payment schedule

📅 **NEW EVENTS (3):**
- [Nathaniel] Parent-teacher evening (Feb 5 18:30)
- [Elodie] Science Museum trip (Feb 15)
- [Florence] Sports Day (Jun 20)

ℹ️ **INFO** (12 emails processed, no action needed)

📊 **Today's Stats:**
- Emails processed: 15
- Tasks created: 5
- Events created: 3
- Duplicates skipped: 2
```

## Urgent Notifications

For HIGH urgency items, sends immediate notification:

```
🚨 **URGENT SCHOOL ACTION**

**Child:** Elodie
**Action:** Pay for Science Museum trip
**Deadline:** Tomorrow

📧 From: ParentPay payment reminder

> Your payment of £12.50 for Science Museum Trip is overdue...

[View Email](link)
```

## Weekly Summary

Generate weekly summary with:
```
school:weekly-summary
```

## Usage

```bash
cd ~/clawd/projects/school-email-automation
python -m school_automation.digest_generator.generator          # Today's digest
python -m school_automation.digest_generator.generator --weekly # Weekly summary
```

## Cron Configuration

```bash
# Daily digest at 18:00 (weekdays)
0 18 * * 1-5 clawdbot run "school:send-digest"
```

## Requirements

- SQLite database at ~/clawd/data/school-automation.db
- Clawdbot Telegram integration configured
