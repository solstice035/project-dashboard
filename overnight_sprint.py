"""
Overnight Sprint module for Project Dashboard.
Handles sprint log parsing, database operations, and business logic.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

import database as db

logger = logging.getLogger(__name__)

SPRINT_LOGS_PATH = Path(os.path.expanduser(
    '~/obsidian/claude/1-Projects/0-Dev/01-JeeveSprints'
))


def parse_sprint_log(file_path: Path) -> dict | None:
    """
    Parse a sprint log markdown file with YAML frontmatter.

    Args:
        file_path: Path to the markdown file

    Returns:
        Parsed sprint dict or None if parsing fails
    """
    try:
        content = file_path.read_text()
        if not content.startswith('---\n'):
            return None

        parts = content.split('---\n', 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])
        file_name = file_path.stem

        # Map activity log to items
        items = []
        for idx, entry in enumerate(frontmatter.get('activity_log', [])):
            status = 'completed' if entry.get('activity_type') in ['complete', 'progress', 'start', 'decision'] else 'failed'
            items.append({
                'id': f"{file_name}-{idx}",
                'title': entry.get('what', ''),
                'status': status,
                'started_at': str(entry.get('timestamp')) if entry.get('timestamp') else None,
                'result': entry.get('outcome', ''),
                'activity_type': entry.get('activity_type'),
                'why': entry.get('why'),
            })

        completed_items = len([i for i in items if i['status'] == 'completed'])

        # Quality gates
        qg = frontmatter.get('quality_gates', {})
        gates_passed = sum(1 for v in qg.values() if v is True)

        return {
            'id': file_name,
            'date': file_name,
            'task_id': frontmatter.get('task_id'),
            'task_title': frontmatter.get('task_title'),
            'status': frontmatter.get('status', 'pending'),
            'started_at': frontmatter.get('window_start'),
            'completed_at': frontmatter.get('window_end'),
            'tasks_completed': completed_items,
            'tasks_total': len(items) or 1,
            'summary': f"{frontmatter.get('task_title', 'Sprint')} - {frontmatter.get('status', 'pending')}",
            'handoff_notes': None,
            'items': items,
            'quality_gates': qg,
            'gates_passed': gates_passed,
            'gates_total': 8,
            'decisions': frontmatter.get('decisions', []),
            'deviations': frontmatter.get('deviations', []),
            'block_reason': frontmatter.get('block_reason'),
            'obsidian_path': str(file_path),
        }
    except Exception as e:
        logger.error(f"Failed to parse sprint log {file_path}: {e}")
        return None


def save_sprint_to_db(sprint: dict) -> int | None:
    """
    Save a sprint to the database with all related data.

    Args:
        sprint: Parsed sprint dict from parse_sprint_log

    Returns:
        Sprint ID or None on error
    """
    try:
        qg = sprint.get('quality_gates', {})

        # Upsert the main sprint record
        sprint_id = db.upsert_sprint(sprint, qg)
        if not sprint_id:
            return None

        # Clear existing related data for re-sync
        db.clear_sprint_related_data(sprint_id)

        # Insert activity items
        for item in sprint.get('items', []):
            db.insert_sprint_activity(
                sprint_id=sprint_id,
                activity_at=item.get('started_at') or datetime.now(),
                activity_type=item.get('activity_type', 'progress'),
                what=item.get('title', ''),
                why=item.get('why'),
                outcome=item.get('result')
            )

        # Insert decisions
        for d in sprint.get('decisions', []):
            if isinstance(d, dict):
                db.insert_sprint_decision(
                    sprint_id=sprint_id,
                    decided_at=d.get('timestamp') or datetime.now(),
                    question=d.get('question', ''),
                    context=d.get('context'),
                    decision=d.get('decision', ''),
                    rationale=d.get('rationale'),
                    confidence=d.get('confidence'),
                    pal_responses=d.get('pal_responses', {}),
                    consensus=d.get('consensus')
                )

        # Insert deviations
        for d in sprint.get('deviations', []):
            if isinstance(d, dict):
                db.insert_sprint_deviation(
                    sprint_id=sprint_id,
                    deviated_at=d.get('timestamp') or datetime.now(),
                    original_scope=d.get('original_scope'),
                    deviation=d.get('deviation', ''),
                    reason=d.get('reason'),
                    flagged=d.get('flagged', False)
                )

        logger.info(f"Saved sprint {sprint['date']} to database (id={sprint_id})")
        return sprint_id

    except Exception as e:
        logger.error(f"Failed to save sprint to DB: {e}")
        return None


def _build_sprint_response(row: dict) -> dict:
    """Build a sprint response dict from a database row with related data."""
    sprint_id = row['id']

    # Get related data
    activities = db.get_sprint_activities(sprint_id)
    decisions = db.get_sprint_decisions(sprint_id)
    deviations = db.get_sprint_deviations(sprint_id)

    # Build items from activities
    items = []
    for idx, a in enumerate(activities):
        status = 'completed' if a['activity_type'] in ['complete', 'progress', 'start', 'decision'] else 'failed'
        items.append({
            'id': f"{row['sprint_date']}-{idx}",
            'title': a['what'],
            'status': status,
            'started_at': str(a['activity_at']) if a['activity_at'] else None,
            'result': a['outcome'],
        })

    # Build quality gates dict from individual columns
    qg = {
        'tests_passing': row['gate_tests_passing'],
        'no_lint_errors': row['gate_no_lint_errors'],
        'docs_updated': row['gate_docs_updated'],
        'committed_to_branch': row['gate_committed'],
        'self_validated': row['gate_self_validated'],
        'happy_path_works': row['gate_happy_path'],
        'edge_cases_handled': row['gate_edge_cases'],
        'pal_reviewed': row['gate_pal_reviewed'],
    }

    return {
        'id': str(row['sprint_date']),
        'date': str(row['sprint_date']),
        'task_id': row['task_id'],
        'task_title': row['task_title'],
        'status': row['status'],
        'started_at': str(row['started_at']) if row['started_at'] else None,
        'completed_at': str(row['completed_at']) if row['completed_at'] else None,
        'tasks_completed': row['tasks_completed'],
        'tasks_total': row['tasks_total'],
        'quality_gates': qg,
        'gates_passed': row['gates_passed'],
        'gates_total': 8,
        'items': items,
        'decisions': decisions,
        'deviations': deviations,
        'block_reason': row['block_reason'],
    }


def get_sprints_from_db(limit: int = 20) -> list[dict]:
    """
    Get sprints from database with all related data.

    Args:
        limit: Maximum number of sprints to return

    Returns:
        List of sprint dicts
    """
    try:
        rows = db.get_sprints(limit=limit)
        return [_build_sprint_response(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get sprints from DB: {e}")
        return []


def get_current_sprint() -> dict:
    """
    Get current or most recent overnight sprint.

    Returns:
        dict with sprint and source, or error info
    """
    try:
        # Try DB first
        sprints = get_sprints_from_db(limit=1)
        if sprints:
            return {'sprint': sprints[0], 'source': 'database'}

        # Fallback to Obsidian
        if not SPRINT_LOGS_PATH.exists():
            return {'sprint': None}

        today = datetime.now().strftime('%Y-%m-%d')
        today_file = SPRINT_LOGS_PATH / f"{today}.md"

        if today_file.exists():
            sprint = parse_sprint_log(today_file)
            if sprint:
                save_sprint_to_db(sprint)  # Auto-migrate to DB
                return {'sprint': sprint, 'source': 'obsidian'}

        md_files = sorted(SPRINT_LOGS_PATH.glob('*.md'), reverse=True)
        for f in md_files[:1]:
            sprint = parse_sprint_log(f)
            if sprint:
                save_sprint_to_db(sprint)
                return {'sprint': sprint, 'source': 'obsidian'}

        return {'sprint': None}

    except Exception as e:
        logger.error(f"Error getting current sprint: {e}")
        return {'error': str(e)}


def get_recent_sprints(limit: int = 20) -> dict:
    """
    Get list of recent sprints.

    Args:
        limit: Maximum number of sprints to return

    Returns:
        dict with sprints list, source, and count
    """
    try:
        # Try DB first
        sprints = get_sprints_from_db(limit=limit)
        if sprints:
            return {'sprints': sprints, 'source': 'database', 'count': len(sprints)}

        # Fallback to Obsidian
        if not SPRINT_LOGS_PATH.exists():
            return {'sprints': [], 'source': 'none'}

        md_files = sorted(SPRINT_LOGS_PATH.glob('*.md'), reverse=True)[:limit]
        sprints = []

        for f in md_files:
            sprint = parse_sprint_log(f)
            if sprint:
                sprints.append(sprint)

        return {'sprints': sprints, 'source': 'obsidian', 'count': len(sprints)}

    except Exception as e:
        logger.error(f"Error getting recent sprints: {e}")
        return {'error': str(e)}


def sync_sprints_from_obsidian() -> dict:
    """
    Sync all Obsidian sprint logs to database.

    Returns:
        dict with sync status, counts, and any errors
    """
    try:
        if not SPRINT_LOGS_PATH.exists():
            return {'error': 'Sprint logs path not found', 'path': str(SPRINT_LOGS_PATH)}

        md_files = sorted(SPRINT_LOGS_PATH.glob('*.md'))
        synced = 0
        errors = []

        for f in md_files:
            sprint = parse_sprint_log(f)
            if sprint:
                result = save_sprint_to_db(sprint)
                if result:
                    synced += 1
                else:
                    errors.append(f.name)

        return {
            'status': 'ok',
            'synced': synced,
            'total_files': len(md_files),
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Error syncing sprints: {e}")
        return {'error': str(e)}
