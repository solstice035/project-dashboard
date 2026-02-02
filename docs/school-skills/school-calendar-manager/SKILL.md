---
name: school-calendar-manager
description: "Create Google Calendar events from school event actions"
---

# School Calendar Manager

Creates Google Calendar events from EVENT-type actions with proper formatting, color-coding by child, and reminders.

## Invocation

```
school:create-events --actions <json>
```

## Process

1. Receive extracted actions
2. Filter to EVENT type only
3. Check each event against deduplication database
4. Parse event date from action
5. Create calendar event with:
   - Title: `[Child] Description`
   - Description: Context + source email
   - Color: Based on child
   - Reminders: 1 day and 1 hour before
6. Store event hash for future deduplication

## Event Format

**Title:** `[Elodie] Science Museum Trip`

**Date:** 2026-02-15 (all-day event)

**Description:**
```
Year 6 trip. Children should bring packed lunch.

---
From: Science trip - permission form
```

**Color:** Blue (Elodie), Green (Nathaniel), Pink (Florence)

## Reminders

- Pop-up 1 day before
- Pop-up 1 hour before

## Deduplication

- Generates hash from: child + description + date
- Checks existing calendar for similar events ±2 days
- Fuzzy title matching (>80% similarity)

## Date Parsing

Attempts to parse dates from:
1. Action deadline field
2. Description text (e.g., "15th February")
3. Source text patterns

If no date found, event is skipped with warning.

## Usage

```bash
cd ~/clawd/projects/school-email-automation
python -m school_automation.calendar_manager.manager --list  # List upcoming events
```

## Requirements

- Google Calendar API credentials at ~/.clawdbot/credentials/gcal_token.json
- google-api-python-client library installed
