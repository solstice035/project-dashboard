---
name: school-email-processor
description: "Fetch and process school emails from Gmail, extract content from attachments"
---

# School Email Processor

Fetches unprocessed school emails from Gmail, extracts text from PDF attachments, and identifies which child each email relates to.

## Invocation

```
school:process-emails [--days N] [--dry-run] [--child NAME]
```

## Options

- `--days N`: Number of days to look back (default: 1)
- `--dry-run`: Preview emails without marking as processed
- `--child NAME`: Filter to specific child (Elodie, Nathaniel, Florence)

## Process

1. Connect to Gmail API using stored credentials
2. Search for emails matching school patterns (configured in ~/clawd/school-config.yaml)
3. Filter out already-processed emails (tracked in SQLite database)
4. For each email:
   - Extract body text
   - Download PDF attachments
   - Extract text from PDFs using PyPDF2
   - Identify which child based on sender address
5. Pass to action extractor for AI processing
6. Mark as processed in database

## Configuration

See `~/clawd/school-config.yaml` for:
- Children and their school email addresses
- Email patterns to monitor
- Gmail API credentials location

## Output

Returns list of processed emails with:
- Email ID, subject, from address, date
- Body text
- Attachment text (from PDFs)
- Identified child name

## Usage

```bash
# Process last 24 hours
cd ~/clawd/projects/school-email-automation
python -m school_automation.orchestrator process

# Dry run for last 7 days
python -m school_automation.orchestrator process --days 7 --dry-run

# Process only Elodie's emails
python -m school_automation.orchestrator process --child Elodie
```

## Requirements

- Gmail API credentials at ~/.clawdbot/credentials/gmail_token.json
- PyPDF2 installed (`pip install PyPDF2`)
- School config at ~/clawd/school-config.yaml
