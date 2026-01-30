"""
Database module for Project Dashboard analytics.
Uses PostgreSQL (database: nick) for storing historical snapshots.
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Any, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DB_CONFIG = {
    'dbname': 'nick',
    'host': 'localhost',
}


@contextmanager
def get_connection():
    """Get a database connection."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


# =============================================================================
# Snapshot Storage
# =============================================================================

def store_git_snapshot(repos: list[dict]) -> None:
    """Store git repository snapshot."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            for repo in repos:
                cur.execute("""
                    INSERT INTO dashboard_git_snapshots 
                    (repo_name, branch, commit_count, is_dirty, ahead, behind)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    repo.get('name'),
                    repo.get('branch'),
                    repo.get('commit_count', 0),
                    repo.get('is_dirty', False),
                    repo.get('ahead', 0),
                    repo.get('behind', 0)
                ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store git snapshot: {e}")


def store_todoist_snapshot(tasks: list[dict]) -> None:
    """Store todoist task snapshot."""
    try:
        total = len(tasks)
        overdue = sum(1 for t in tasks if t.get('is_overdue'))
        today = sum(1 for t in tasks if t.get('is_today'))
        
        # Group by project
        by_project = {}
        for t in tasks:
            proj = t.get('project', 'Unknown')
            by_project[proj] = by_project.get(proj, 0) + 1
        
        # Group by priority
        by_priority = {1: 0, 2: 0, 3: 0, 4: 0}
        for t in tasks:
            p = t.get('priority', 1)
            by_priority[p] = by_priority.get(p, 0) + 1
        
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dashboard_todoist_snapshots
                (total_tasks, overdue_tasks, today_tasks, by_project, by_priority)
                VALUES (%s, %s, %s, %s, %s)
            """, (total, overdue, today, json.dumps(by_project), json.dumps(by_priority)))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store todoist snapshot: {e}")


def store_kanban_snapshot(by_column: dict) -> None:
    """Store kanban board snapshot."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dashboard_kanban_snapshots
                (backlog_count, ready_count, in_progress_count, review_count, done_count, total_tasks)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                len(by_column.get('backlog', [])),
                len(by_column.get('ready', [])),
                len(by_column.get('in-progress', [])),
                len(by_column.get('review', [])),
                len(by_column.get('done', [])),
                sum(len(v) for v in by_column.values())
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store kanban snapshot: {e}")


def store_linear_snapshot(issues: list[dict], by_status: dict) -> None:
    """Store Linear issues snapshot."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dashboard_linear_snapshots
                (total_issues, by_status, by_assignee)
                VALUES (%s, %s, %s)
            """, (
                len(issues),
                json.dumps({k: len(v) for k, v in by_status.items()}),
                json.dumps({})  # Could add assignee grouping later
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store linear snapshot: {e}")


def update_daily_stats(git_data: dict, todoist_data: dict, kanban_data: dict) -> None:
    """Update daily aggregate stats."""
    try:
        today = date.today()
        
        git_repos = git_data.get('repos', [])
        git_commits = sum(r.get('commit_count', 0) for r in git_repos)
        git_active = sum(1 for r in git_repos if r.get('commit_count', 0) > 0)
        git_dirty = sum(1 for r in git_repos if r.get('is_dirty'))
        
        todoist_tasks = todoist_data.get('tasks', [])
        todoist_overdue = sum(1 for t in todoist_tasks if t.get('is_overdue'))
        
        kanban_cols = kanban_data.get('by_column', {})
        
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO dashboard_daily_stats 
                (stat_date, git_total_commits, git_active_repos, git_dirty_repos, todoist_overdue)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (stat_date) DO UPDATE SET
                    git_total_commits = EXCLUDED.git_total_commits,
                    git_active_repos = EXCLUDED.git_active_repos,
                    git_dirty_repos = EXCLUDED.git_dirty_repos,
                    todoist_overdue = EXCLUDED.todoist_overdue,
                    updated_at = CURRENT_TIMESTAMP
            """, (today, git_commits, git_active, git_dirty, todoist_overdue))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update daily stats: {e}")


# =============================================================================
# Analytics Queries
# =============================================================================

def get_git_trends(days: int = 30) -> list[dict]:
    """Get git activity trends over time."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    SUM(commit_count) as total_commits,
                    COUNT(DISTINCT repo_name) as repos_with_activity,
                    SUM(CASE WHEN is_dirty THEN 1 ELSE 0 END) as dirty_repos
                FROM dashboard_git_snapshots
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at)
                ORDER BY date
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get git trends: {e}")
        return []


def get_todoist_trends(days: int = 30) -> list[dict]:
    """Get todoist task trends over time."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    AVG(total_tasks) as avg_tasks,
                    AVG(overdue_tasks) as avg_overdue,
                    AVG(today_tasks) as avg_today
                FROM dashboard_todoist_snapshots
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at)
                ORDER BY date
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get todoist trends: {e}")
        return []


def get_kanban_trends(days: int = 30) -> list[dict]:
    """Get kanban board trends over time."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    AVG(backlog_count) as avg_backlog,
                    AVG(ready_count) as avg_ready,
                    AVG(in_progress_count) as avg_in_progress,
                    AVG(done_count) as avg_done,
                    AVG(total_tasks) as avg_total
                FROM dashboard_kanban_snapshots
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at)
                ORDER BY date
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get kanban trends: {e}")
        return []


def get_linear_trends(days: int = 30) -> list[dict]:
    """Get Linear issues trends over time."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    AVG(total_issues) as avg_total,
                    by_status
                FROM dashboard_linear_snapshots
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at), by_status
                ORDER BY date
            """, (days,))
            rows = cur.fetchall()
            
            # Aggregate by date
            by_date = {}
            for row in rows:
                d = str(row['date'])
                if d not in by_date:
                    by_date[d] = {'date': d, 'avg_total': 0, 'statuses': {}}
                by_date[d]['avg_total'] = float(row['avg_total'] or 0)
                if row['by_status']:
                    for status, count in row['by_status'].items():
                        by_date[d]['statuses'][status] = count
            
            return list(by_date.values())
    except Exception as e:
        logger.error(f"Failed to get linear trends: {e}")
        return []


def get_daily_summary(days: int = 7) -> list[dict]:
    """Get daily summary stats."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM dashboard_daily_stats
                WHERE stat_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY stat_date DESC
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        return []


def get_repo_history(repo_name: str, days: int = 30) -> list[dict]:
    """Get history for a specific repo."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    DATE(snapshot_at) as date,
                    AVG(commit_count) as avg_commits,
                    BOOL_OR(is_dirty) as was_dirty
                FROM dashboard_git_snapshots
                WHERE repo_name = %s
                  AND snapshot_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at)
                ORDER BY date
            """, (repo_name, days))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get repo history: {e}")
        return []


# =============================================================================
# Planning Session Operations
# =============================================================================

def create_planning_session(initial_context: dict) -> dict | None:
    """Create a new planning session. Returns session info or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO planning_sessions (initial_context)
                VALUES (%s)
                RETURNING id, started_at
            """, (json.dumps(initial_context),))
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"Failed to create planning session: {e}")
        return None


def end_planning_session(session_id: int, final_state: dict) -> dict | None:
    """End a planning session. Returns session stats or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE planning_sessions
                SET ended_at = NOW(),
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER,
                    final_state = %s,
                    messages_count = (SELECT COUNT(*) FROM planning_messages WHERE session_id = %s),
                    actions_count = (SELECT COUNT(*) FROM planning_actions WHERE session_id = %s)
                WHERE id = %s
                RETURNING id, duration_seconds, messages_count, actions_count
            """, (json.dumps(final_state), session_id, session_id, session_id))
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"Failed to end planning session: {e}")
        return None


def insert_planning_action(session_id: int, action_type: str, target_type: str = None,
                           target_id: str = None, target_title: str = None,
                           details: dict = None) -> int | None:
    """Insert a planning action. Returns action ID or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO planning_actions
                (session_id, action_type, target_type, target_id, target_title, details)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (session_id, action_type, target_type, target_id, target_title,
                  json.dumps(details or {})))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to insert planning action: {e}")
        return None


def insert_planning_message(session_id: int, role: str, content: str,
                            tokens_used: int = None) -> int | None:
    """Insert a planning message. Returns message ID or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO planning_messages
                (session_id, role, content, tokens_used)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (session_id, role, content, tokens_used))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to insert planning message: {e}")
        return None


def get_planning_sessions(days: int = 30, limit: int = 20) -> list[dict]:
    """Get recent planning sessions."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, started_at, ended_at, duration_seconds,
                       messages_count, actions_count
                FROM planning_sessions
                WHERE started_at > NOW() - INTERVAL '%s days'
                ORDER BY started_at DESC
                LIMIT %s
            """, (days, limit))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get planning sessions: {e}")
        return []


def get_planning_action_breakdown(days: int = 30) -> list[dict]:
    """Get action type breakdown for planning analytics."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT action_type, COUNT(*) as count
                FROM planning_actions
                WHERE action_at > NOW() - INTERVAL '%s days'
                GROUP BY action_type
                ORDER BY count DESC
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get planning action breakdown: {e}")
        return []


def get_planning_totals(days: int = 30) -> dict:
    """Get planning session totals for analytics."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    COALESCE(SUM(duration_seconds), 0) as total_duration,
                    COALESCE(SUM(messages_count), 0) as total_messages,
                    COALESCE(SUM(actions_count), 0) as total_actions,
                    COALESCE(AVG(duration_seconds), 0) as avg_duration
                FROM planning_sessions
                WHERE started_at > NOW() - INTERVAL '%s days'
                  AND ended_at IS NOT NULL
            """, (days,))
            result = cur.fetchone()
            return dict(result) if result else {}
    except Exception as e:
        logger.error(f"Failed to get planning totals: {e}")
        return {}


# =============================================================================
# Overnight Sprint Operations
# =============================================================================

def upsert_sprint(sprint: dict, quality_gates: dict) -> int | None:
    """
    Insert or update a sprint record.
    Returns sprint ID or None on error.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO overnight_sprints (
                    sprint_date, task_id, task_title, status,
                    started_at, completed_at, window_start, window_end,
                    gate_tests_passing, gate_no_lint_errors, gate_docs_updated,
                    gate_committed, gate_self_validated, gate_happy_path,
                    gate_edge_cases, gate_pal_reviewed,
                    tasks_completed, tasks_total, gates_passed,
                    block_reason, obsidian_path, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (sprint_date) DO UPDATE SET
                    task_id = EXCLUDED.task_id,
                    task_title = EXCLUDED.task_title,
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    gate_tests_passing = EXCLUDED.gate_tests_passing,
                    gate_no_lint_errors = EXCLUDED.gate_no_lint_errors,
                    gate_docs_updated = EXCLUDED.gate_docs_updated,
                    gate_committed = EXCLUDED.gate_committed,
                    gate_self_validated = EXCLUDED.gate_self_validated,
                    gate_happy_path = EXCLUDED.gate_happy_path,
                    gate_edge_cases = EXCLUDED.gate_edge_cases,
                    gate_pal_reviewed = EXCLUDED.gate_pal_reviewed,
                    tasks_completed = EXCLUDED.tasks_completed,
                    tasks_total = EXCLUDED.tasks_total,
                    gates_passed = EXCLUDED.gates_passed,
                    block_reason = EXCLUDED.block_reason,
                    obsidian_path = EXCLUDED.obsidian_path,
                    updated_at = NOW()
                RETURNING id
            """, (
                sprint['date'], sprint.get('task_id'), sprint.get('task_title'),
                sprint.get('status', 'pending'),
                sprint.get('started_at'), sprint.get('completed_at'),
                sprint.get('started_at'), sprint.get('completed_at'),
                quality_gates.get('tests_passing', False),
                quality_gates.get('no_lint_errors', False),
                quality_gates.get('docs_updated', False),
                quality_gates.get('committed_to_branch', False),
                quality_gates.get('self_validated', False),
                quality_gates.get('happy_path_works', False),
                quality_gates.get('edge_cases_handled', False),
                quality_gates.get('pal_reviewed', False),
                sprint.get('tasks_completed', 0), sprint.get('tasks_total', 0),
                sprint.get('gates_passed', 0),
                sprint.get('block_reason'), sprint.get('obsidian_path')
            ))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to upsert sprint: {e}")
        return None


def clear_sprint_related_data(sprint_id: int) -> bool:
    """Delete activity, decisions, and deviations for a sprint (for re-sync)."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM overnight_activity WHERE sprint_id = %s", (sprint_id,))
            cur.execute("DELETE FROM overnight_decisions WHERE sprint_id = %s", (sprint_id,))
            cur.execute("DELETE FROM overnight_deviations WHERE sprint_id = %s", (sprint_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to clear sprint related data: {e}")
        return False


def insert_sprint_activity(sprint_id: int, activity_at, activity_type: str,
                           what: str, why: str = None, outcome: str = None) -> bool:
    """Insert a sprint activity record."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO overnight_activity (sprint_id, activity_at, activity_type, what, why, outcome)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sprint_id, activity_at, activity_type, what, why, outcome))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to insert sprint activity: {e}")
        return False


def insert_sprint_decision(sprint_id: int, decided_at, question: str,
                           context: str = None, decision: str = '',
                           rationale: str = None, confidence: str = None,
                           pal_responses: dict = None, consensus: str = None) -> bool:
    """Insert a sprint decision record."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO overnight_decisions
                (sprint_id, decided_at, question, context, decision, rationale, confidence, pal_responses, consensus)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (sprint_id, decided_at, question, context, decision, rationale,
                  confidence, json.dumps(pal_responses or {}), consensus))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to insert sprint decision: {e}")
        return False


def insert_sprint_deviation(sprint_id: int, deviated_at, original_scope: str = None,
                            deviation: str = '', reason: str = None,
                            flagged: bool = False) -> bool:
    """Insert a sprint deviation record."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO overnight_deviations
                (sprint_id, deviated_at, original_scope, deviation, reason, flagged)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sprint_id, deviated_at, original_scope, deviation, reason, flagged))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to insert sprint deviation: {e}")
        return False


def get_sprints(limit: int = 20) -> list[dict]:
    """Get recent sprints from database."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, sprint_date, task_id, task_title, status,
                       started_at, completed_at,
                       gate_tests_passing, gate_no_lint_errors, gate_docs_updated,
                       gate_committed, gate_self_validated, gate_happy_path,
                       gate_edge_cases, gate_pal_reviewed,
                       tasks_completed, tasks_total, gates_passed,
                       block_reason, obsidian_path
                FROM overnight_sprints
                ORDER BY sprint_date DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get sprints: {e}")
        return []


def get_sprint_activities(sprint_id: int) -> list[dict]:
    """Get activities for a sprint."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT activity_at, activity_type, what, why, outcome
                FROM overnight_activity
                WHERE sprint_id = %s
                ORDER BY activity_at
            """, (sprint_id,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get sprint activities: {e}")
        return []


def get_sprint_decisions(sprint_id: int) -> list[dict]:
    """Get decisions for a sprint."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT decided_at, question, context, decision, rationale,
                       confidence, pal_responses, consensus
                FROM overnight_decisions
                WHERE sprint_id = %s
                ORDER BY decided_at
            """, (sprint_id,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get sprint decisions: {e}")
        return []


def get_sprint_deviations(sprint_id: int) -> list[dict]:
    """Get deviations for a sprint."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT deviated_at, original_scope, deviation, reason, flagged
                FROM overnight_deviations
                WHERE sprint_id = %s
                ORDER BY deviated_at
            """, (sprint_id,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get sprint deviations: {e}")
        return []
