"""School letter pre-processor for extracting dates and action triggers.

Provides quick pattern-based extraction before full AI processing,
enabling efficient filtering and urgency detection.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class ExtractedDate:
    """A date extracted from letter content."""
    date: date
    original_text: str
    context: str  # Surrounding text for understanding


@dataclass
class ActionTrigger:
    """An action trigger phrase detected in the letter."""
    trigger_type: str  # 'deadline', 'payment', 'permission', 'attendance', 'reply'
    phrase: str
    context: str


@dataclass
class LetterAnalysis:
    """Results of pre-processing a school letter."""
    dates: list[ExtractedDate] = field(default_factory=list)
    action_triggers: list[ActionTrigger] = field(default_factory=list)
    suggested_urgency: str = "low"  # 'high', 'medium', 'low', 'info'
    has_deadline: bool = False
    has_payment: bool = False
    earliest_date: Optional[date] = None


# UK date formats: "15th February 2026", "15/02/2026", "15 Feb 2026"
UK_DATE_PATTERNS = [
    # Full month names with ordinal: "15th February 2026"
    r'(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
    # Abbreviated months: "15 Feb 2026", "15th Feb 2026"
    r'(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})',
    # DD/MM/YYYY or DD-MM-YYYY
    r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',
    # "Friday 15th February" (year inferred)
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)',
]

MONTH_MAP = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
    'november': 11, 'nov': 11, 'december': 12, 'dec': 12
}

# Action trigger patterns grouped by type
ACTION_TRIGGERS = {
    'deadline': [
        r'please\s+return\s+by',
        r'deadline\s*[:\-]?\s*',
        r'must\s+be\s+returned?\s+by',
        r'due\s+(?:date|by)',
        r'no\s+later\s+than',
        r'by\s+(?:the\s+)?(?:end\s+of|close\s+of)',
        r'final\s+date',
        r'closing\s+date',
        r'submit\s+by',
        r'hand\s+in\s+by',
    ],
    'payment': [
        r'payment\s+(?:of|required|due)',
        r'(?:£|\$)\s*\d+',
        r'please\s+pay',
        r'cost\s*[:\-]?\s*(?:£|\$)?\s*\d+',
        r'fee\s+(?:of\s+)?(?:£|\$)?\s*\d+',
        r'contribution\s+of',
        r'payable\s+by',
    ],
    'permission': [
        r'consent\s+form',
        r'permission\s+slip',
        r'please\s+sign',
        r'parental\s+(?:consent|permission)',
        r'signed\s+(?:consent|permission)',
        r'your\s+signature',
        r'authorization\s+form',
    ],
    'attendance': [
        r'reply\s+slip',
        r'confirm\s+(?:your\s+)?(?:child\'?s?\s+)?attendance',
        r'let\s+us\s+know\s+if',
        r'please\s+(?:confirm|indicate)',
        r'rsvp',
        r'places\s+are\s+limited',
        r'register\s+(?:by|before)',
    ],
    'reply': [
        r'please\s+(?:complete|fill\s+in)',
        r'return\s+(?:this|the)\s+(?:form|slip)',
        r'respond\s+(?:to|by)',
        r'action\s+required',
        r'your\s+response',
        r'reply\s+needed',
    ],
}


def parse_letter(content: str, subject: str = "") -> LetterAnalysis:
    """Parse school letter content for dates and action triggers.

    Args:
        content: Full email body or PDF extracted text
        subject: Email subject line for additional context

    Returns:
        LetterAnalysis with extracted dates, triggers, and suggested urgency
    """
    analysis = LetterAnalysis()
    full_text = f"{subject}\n{content}".lower()
    original_text = f"{subject}\n{content}"

    # Extract dates
    analysis.dates = _extract_dates(original_text)
    if analysis.dates:
        analysis.earliest_date = min(d.date for d in analysis.dates)

    # Find action triggers
    analysis.action_triggers = _extract_triggers(full_text, original_text)

    # Check for specific action types
    trigger_types = {t.trigger_type for t in analysis.action_triggers}
    analysis.has_deadline = 'deadline' in trigger_types
    analysis.has_payment = 'payment' in trigger_types

    # Determine urgency
    analysis.suggested_urgency = _determine_urgency(analysis)

    return analysis


def _extract_dates(text: str) -> list[ExtractedDate]:
    """Extract dates from text using UK date patterns."""
    dates = []
    current_year = datetime.now().year

    for i, pattern in enumerate(UK_DATE_PATTERNS):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                if i == 0:  # Full month name
                    day = int(match.group(1))
                    month = MONTH_MAP[match.group(2).lower()]
                    year = int(match.group(3))
                elif i == 1:  # Abbreviated month
                    day = int(match.group(1))
                    month = MONTH_MAP[match.group(2).lower()]
                    year = int(match.group(3))
                elif i == 2:  # DD/MM/YYYY
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                elif i == 3:  # Weekday + date (no year)
                    day = int(match.group(1))
                    month = MONTH_MAP[match.group(2).lower()]
                    year = current_year
                    # If date is in the past, assume next year
                    if date(year, month, day) < date.today():
                        year += 1
                else:
                    continue

                extracted = date(year, month, day)
                context = _get_context(text, match.start(), match.end())

                dates.append(ExtractedDate(
                    date=extracted,
                    original_text=match.group(0),
                    context=context
                ))
            except (ValueError, KeyError):
                continue

    # Remove duplicates, keeping earliest context
    seen = {}
    for d in dates:
        if d.date not in seen:
            seen[d.date] = d

    return list(seen.values())


def _extract_triggers(lower_text: str, original_text: str) -> list[ActionTrigger]:
    """Extract action trigger phrases from text."""
    triggers = []

    for trigger_type, patterns in ACTION_TRIGGERS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, lower_text):
                context = _get_context(original_text, match.start(), match.end(), chars=100)
                triggers.append(ActionTrigger(
                    trigger_type=trigger_type,
                    phrase=match.group(0),
                    context=context
                ))

    # Deduplicate by type + approximate position
    seen = set()
    unique = []
    for t in triggers:
        key = (t.trigger_type, t.phrase[:20])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique


def _get_context(text: str, start: int, end: int, chars: int = 60) -> str:
    """Get surrounding context for a match."""
    ctx_start = max(0, start - chars // 2)
    ctx_end = min(len(text), end + chars // 2)
    context = text[ctx_start:ctx_end].strip()

    if ctx_start > 0:
        context = "..." + context
    if ctx_end < len(text):
        context = context + "..."

    return context


def _determine_urgency(analysis: LetterAnalysis) -> str:
    """Determine suggested urgency level based on analysis."""
    today = date.today()

    # High urgency: deadline within 3 days or payment required soon
    if analysis.earliest_date:
        days_until = (analysis.earliest_date - today).days
        if days_until <= 3 and (analysis.has_deadline or analysis.has_payment):
            return "high"
        if days_until <= 7 and analysis.has_payment:
            return "high"

    # Medium: deadline within a week or payment/permission needed
    if analysis.earliest_date:
        days_until = (analysis.earliest_date - today).days
        if days_until <= 7:
            return "medium"

    # Medium: any action trigger with deadline or payment
    if analysis.has_deadline or analysis.has_payment:
        return "medium"

    # Low: has action triggers but no deadline
    if analysis.action_triggers:
        return "low"

    # Info: no actionable content detected
    return "info"
