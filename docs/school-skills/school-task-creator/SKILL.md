---
name: school-task-creator
description: "Create Todoist tasks from extracted school actions"
---

# School Task Creator

Creates Todoist tasks from extracted actions with proper formatting, priorities, labels, and links back to source emails.

## Invocation

```
school:create-tasks --actions <json>
```

## Process

1. Receive extracted actions
2. Check each action against deduplication database
3. Skip INFO-only actions and duplicates
4. Create Todoist task with:
   - Title: `[Child] Description - SchoolShort`
   - Description: Context + link to email
   - Priority: Based on urgency
   - Due date: From extracted deadline
   - Labels: school, child name
5. Store task hash for future deduplication
6. Return created task details

## Task Format

**Title:** `[Elodie] Complete Science trip permission form - GC`

**Description:**
```
Please complete the attached permission form and return by 8th Feb

---
**Original Email:**
Subject: Science trip - permission form
From: office@guildfordcounty.sch.uk
Date: 2026-01-27

[View Email](https://mail.google.com/mail/u/0/#inbox/abc123)
```

## Priority Mapping

- HIGH → Priority 4 (P1 - urgent red)
- MEDIUM → Priority 3 (P2 - orange)
- LOW → Priority 2 (P3 - blue)

## Deduplication

- Generates hash from: child + description keywords + deadline + type
- Checks hash against last 30 days
- Also checks fuzzy matching (85% similarity threshold)
- Same action from email + WhatsApp = single task

## Usage

```bash
cd ~/clawd/projects/school-email-automation
python -m school_automation.task_creator.creator --list  # List pending tasks
python -m school_automation.task_creator.creator --test  # Create test task
```

## Requirements

- TODOIST_API_TOKEN environment variable
- todoist-api-python library installed
- "School Tasks" project in Todoist (auto-created if missing)
