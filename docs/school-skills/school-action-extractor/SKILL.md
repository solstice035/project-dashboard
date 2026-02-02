---
name: school-action-extractor
description: "Extract actionable items from school emails using Claude AI"
---

# School Action Extractor

Uses Claude AI to intelligently extract parent actions from school emails, classify urgency, and identify deadlines.

## Invocation

```
school:extract-actions --email-data <json>
```

## Process

1. Receive email data (body + attachment text)
2. Build prompt with context (child, school, date)
3. Call Claude Sonnet to extract actions
4. Parse JSON response
5. Classify urgency (HIGH/MEDIUM/LOW)
6. Return structured action list

## Action Structure

Each extracted action contains:

```json
{
  "description": "What needs to be done",
  "child": "Elodie",
  "deadline": "2026-02-08",
  "urgency": "MEDIUM",
  "type": "PERMISSION",
  "source_text": "Quote from email"
}
```

## Urgency Classification

- **HIGH**: Deadline within 48 hours OR explicit urgent language
- **MEDIUM**: Deadline 3-7 days away OR requires action (forms, payments)
- **LOW**: Deadline > 7 days OR informational

## Action Types

- FORM - Form to fill out
- PAYMENT - Payment required
- PERMISSION - Permission slip
- REPLY - Response needed
- EVENT - Calendar event
- INFO - Informational only
- OTHER - Other action type

## AI Prompt

The AI is given:
- Email metadata (from, subject, date, child)
- Email body text
- Attachment text (from PDFs)
- Today's date for deadline context
- List of urgent keywords

It returns ONLY valid JSON array of actions.

## Usage

This skill is typically called automatically by the email processor.
For testing:

```bash
cd ~/clawd/projects/school-email-automation
python -m school_automation.action_extractor.extractor --test
```

## Requirements

- ANTHROPIC_API_KEY environment variable
- anthropic library installed
