"""
Database module for Project Dashboard analytics.
Uses PostgreSQL for storing historical snapshots with connection pooling.
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

from config_loader import get_config

logger = logging.getLogger(__name__)

# =============================================================================
# Connection Pool Management
# =============================================================================

# Module-level connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


class PoolConfig:
    """Connection pool configuration constants."""
    MIN_CONNECTIONS = 2
    MAX_CONNECTIONS = 10


def init_pool() -> bool:
    """
    Initialize the database connection pool.

    Should be called once at application startup.

    Returns:
        True if pool initialized successfully, False otherwise
    """
    global _connection_pool

    if _connection_pool is not None:
        logger.debug("Connection pool already initialized")
        return True

    try:
        config = get_config()
        db_params = config.database.to_psycopg2_params()

        _connection_pool = pool.ThreadedConnectionPool(
            minconn=PoolConfig.MIN_CONNECTIONS,
            maxconn=PoolConfig.MAX_CONNECTIONS,
            cursor_factory=RealDictCursor,
            **db_params
        )
        logger.info(
            f"Database connection pool initialized: "
            f"min={PoolConfig.MIN_CONNECTIONS}, max={PoolConfig.MAX_CONNECTIONS}, "
            f"host={db_params.get('host')}, dbname={db_params.get('dbname')}"
        )
        return True

    except psycopg2.Error as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        return False


def close_pool() -> None:
    """Close the connection pool. Call during application shutdown."""
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


def get_pool_status() -> dict:
    """Get current status of the connection pool."""
    if _connection_pool is None:
        return {
            "initialized": False,
            "min_connections": PoolConfig.MIN_CONNECTIONS,
            "max_connections": PoolConfig.MAX_CONNECTIONS
        }

    # psycopg2's ThreadedConnectionPool doesn't expose usage stats directly,
    # but we can report configuration
    return {
        "initialized": True,
        "min_connections": PoolConfig.MIN_CONNECTIONS,
        "max_connections": PoolConfig.MAX_CONNECTIONS,
        "closed": _connection_pool.closed
    }


@contextmanager
def get_connection():
    """
    Get a database connection from the pool.

    If the pool is not initialized, falls back to creating a single connection.
    Connections are automatically returned to the pool when the context exits.
    """
    global _connection_pool
    conn = None

    try:
        if _connection_pool is not None:
            # Get from pool
            conn = _connection_pool.getconn()
            yield conn
        else:
            # Fallback: create direct connection (pool not initialized)
            config = get_config()
            conn = psycopg2.connect(**config.database.to_psycopg2_params(), cursor_factory=RealDictCursor)
            yield conn

    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

    finally:
        if conn:
            if _connection_pool is not None:
                # Return to pool
                _connection_pool.putconn(conn)
            else:
                # Close direct connection
                conn.close()


def check_health() -> dict:
    """
    Check database health by executing a simple query.

    Returns:
        Dict with 'healthy' bool and 'latency_ms' or 'error' string
    """
    import time

    start = time.time()
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()

        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "healthy": True,
            "latency_ms": latency_ms,
            "pool": get_pool_status()
        }

    except psycopg2.Error as e:
        return {
            "healthy": False,
            "error": str(e),
            "pool": get_pool_status()
        }


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


def store_inbox_snapshot(accounts_data: list[dict]) -> None:
    """Store inbox digest snapshot."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            for account in accounts_data:
                cur.execute("""
                    INSERT INTO dashboard_inbox_snapshots
                    (account, account_name, total_unread, urgent_count, 
                     from_people_count, newsletter_count, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    account.get('account', ''),
                    account.get('name', ''),
                    account.get('total_unread', 0),
                    len(account.get('urgent', [])),
                    len(account.get('from_people', [])),
                    account.get('newsletters', 0),
                    account.get('status', 'unknown')
                ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store inbox snapshot: {e}")


def store_school_snapshot(by_child: dict, by_urgency: dict) -> None:
    """Store school email snapshot."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            for child, stats in by_child.items():
                cur.execute("""
                    INSERT INTO dashboard_school_snapshots
                    (child, email_count, action_count, high_urgency, 
                     medium_urgency, low_urgency, info_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    child,
                    stats.get('emails', 0),
                    stats.get('actions', 0),
                    by_urgency.get('HIGH', 0),
                    by_urgency.get('MEDIUM', 0),
                    by_urgency.get('LOW', 0),
                    by_urgency.get('INFO', 0)
                ))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store school snapshot: {e}")


def get_inbox_trends(days: int = 7) -> list[dict]:
    """Get inbox trends for the last N days."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    account,
                    AVG(total_unread) as avg_unread,
                    MAX(urgent_count) as max_urgent
                FROM dashboard_inbox_snapshots
                WHERE snapshot_at > NOW() - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at), account
                ORDER BY date DESC
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get inbox trends: {e}")
        return []


def get_school_trends(days: int = 30) -> list[dict]:
    """Get school email trends for the last N days."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(snapshot_at) as date,
                    child,
                    SUM(email_count) as emails,
                    SUM(action_count) as actions,
                    SUM(high_urgency) as high_urgency
                FROM dashboard_school_snapshots
                WHERE snapshot_at > NOW() - INTERVAL '%s days'
                GROUP BY DATE(snapshot_at), child
                ORDER BY date DESC
            """, (days,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get school trends: {e}")
        return []


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
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                WHERE snapshot_at >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                WHERE stat_date >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                  AND snapshot_at >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                WHERE started_at > NOW() - INTERVAL '1 day' * %s
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
                WHERE action_at > NOW() - INTERVAL '1 day' * %s
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
                WHERE started_at > NOW() - INTERVAL '1 day' * %s
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


# =============================================================================
# Configuration Tables
# =============================================================================

def get_activity_types(active_only: bool = True) -> list[dict]:
    """Get all activity types for XP logging."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT code, name, description, area_code, base_xp, icon, color,
                       duration_bonus, active, sort_order
                FROM activity_types
            """
            if active_only:
                query += " WHERE active = TRUE"
            query += " ORDER BY sort_order, name"
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get activity types: {e}")
        return []


def get_activity_type(code: str) -> Optional[dict]:
    """Get a single activity type by code."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT code, name, description, area_code, base_xp, icon, color,
                       duration_bonus, active, sort_order
                FROM activity_types
                WHERE code = %s
            """, (code,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get activity type {code}: {e}")
        return None


def upsert_activity_type(data: dict) -> bool:
    """Create or update an activity type."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO activity_types (code, name, description, area_code, base_xp,
                                           icon, color, duration_bonus, active, sort_order)
                VALUES (%(code)s, %(name)s, %(description)s, %(area_code)s, %(base_xp)s,
                        %(icon)s, %(color)s, %(duration_bonus)s, %(active)s, %(sort_order)s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    area_code = EXCLUDED.area_code,
                    base_xp = EXCLUDED.base_xp,
                    icon = EXCLUDED.icon,
                    color = EXCLUDED.color,
                    duration_bonus = EXCLUDED.duration_bonus,
                    active = EXCLUDED.active,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = NOW()
            """, data)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to upsert activity type: {e}")
        return False


def delete_activity_type(code: str) -> bool:
    """Delete an activity type."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM activity_types WHERE code = %s", (code,))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete activity type: {e}")
        return False


def get_game_config(key: str = None) -> Any:
    """Get game configuration value(s)."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if key:
                cur.execute("""
                    SELECT key, value, data_type, description, category
                    FROM game_config WHERE key = %s
                """, (key,))
                row = cur.fetchone()
                if row:
                    return _convert_config_value(row['value'], row['data_type'])
                return None
            else:
                cur.execute("""
                    SELECT key, value, data_type, description, category
                    FROM game_config ORDER BY category, key
                """)
                return {row['key']: _convert_config_value(row['value'], row['data_type'])
                        for row in cur.fetchall()}
    except Exception as e:
        logger.error(f"Failed to get game config: {e}")
        return {} if key is None else None


def _convert_config_value(value: str, data_type: str) -> Any:
    """Convert config value to appropriate Python type."""
    if data_type == 'integer':
        return int(value)
    elif data_type == 'float':
        return float(value)
    elif data_type == 'boolean':
        return value.lower() in ('true', '1', 'yes')
    elif data_type == 'json':
        return json.loads(value)
    return value


def set_game_config(key: str, value: Any, data_type: str = 'string',
                    description: str = None, category: str = 'general') -> bool:
    """Set a game configuration value."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO game_config (key, value, data_type, description, category)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    data_type = EXCLUDED.data_type,
                    description = COALESCE(EXCLUDED.description, game_config.description),
                    category = COALESCE(EXCLUDED.category, game_config.category),
                    updated_at = NOW()
            """, (key, str(value), data_type, description, category))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to set game config: {e}")
        return False


def get_kanban_columns(active_only: bool = True) -> list[dict]:
    """Get all kanban column definitions."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT code, title, label, icon, color, wip_limit, sort_order, active
                FROM kanban_columns
            """
            if active_only:
                query += " WHERE active = TRUE"
            query += " ORDER BY sort_order"
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get kanban columns: {e}")
        return []


def upsert_kanban_column(data: dict) -> bool:
    """Create or update a kanban column."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO kanban_columns (code, title, label, icon, color, wip_limit, sort_order, active)
                VALUES (%(code)s, %(title)s, %(label)s, %(icon)s, %(color)s,
                        %(wip_limit)s, %(sort_order)s, %(active)s)
                ON CONFLICT (code) DO UPDATE SET
                    title = EXCLUDED.title,
                    label = EXCLUDED.label,
                    icon = EXCLUDED.icon,
                    color = EXCLUDED.color,
                    wip_limit = EXCLUDED.wip_limit,
                    sort_order = EXCLUDED.sort_order,
                    active = EXCLUDED.active
            """, data)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to upsert kanban column: {e}")
        return False


def get_xp_rules(source: str = None, active_only: bool = True) -> list[dict]:
    """Get XP calculation rules."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT code, name, description, source, area_code, rule_type,
                       condition, xp_per_unit, max_xp, active
                FROM xp_rules
                WHERE 1=1
            """
            params = []
            if active_only:
                query += " AND active = TRUE"
            if source:
                query += " AND source = %s"
                params.append(source)
            query += " ORDER BY source, code"
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get XP rules: {e}")
        return []


def upsert_xp_rule(data: dict) -> bool:
    """Create or update an XP rule."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            condition_json = json.dumps(data.get('condition', {})) if isinstance(data.get('condition'), dict) else data.get('condition')
            cur.execute("""
                INSERT INTO xp_rules (code, name, description, source, area_code, rule_type,
                                     condition, xp_per_unit, max_xp, active)
                VALUES (%(code)s, %(name)s, %(description)s, %(source)s, %(area_code)s,
                        %(rule_type)s, %(condition)s::jsonb, %(xp_per_unit)s, %(max_xp)s, %(active)s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    source = EXCLUDED.source,
                    area_code = EXCLUDED.area_code,
                    rule_type = EXCLUDED.rule_type,
                    condition = EXCLUDED.condition,
                    xp_per_unit = EXCLUDED.xp_per_unit,
                    max_xp = EXCLUDED.max_xp,
                    active = EXCLUDED.active
            """, {**data, 'condition': condition_json})
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to upsert XP rule: {e}")
        return False


def get_priority_levels() -> list[dict]:
    """Get all priority level definitions."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT level, code, name, color, emoji, sort_order
                FROM priority_levels
                ORDER BY sort_order
            """)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get priority levels: {e}")
        return []


# =============================================================================
# Email Automation: Notification History
# =============================================================================

def log_notification(
    channel: str,
    source: str,
    title: str,
    body: str,
    priority: str,
    success: bool,
    error: Optional[str] = None,
    message_id: Optional[str] = None
) -> Optional[int]:
    """Log a notification to history. Returns notification ID or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO notification_history
                (channel, source, title, body, priority, success, error_message, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (channel, source, title, body, priority, success, error, message_id))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to log notification: {e}")
        return None


def get_notification_history(
    days: int = 7,
    channel: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100
) -> list[dict]:
    """Get notification history with optional filters."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT id, channel, source, title, body, priority,
                       sent_at, success, error_message, message_id
                FROM notification_history
                WHERE sent_at > NOW() - INTERVAL '%s days'
            """
            params = [days]

            if channel:
                query += " AND channel = %s"
                params.append(channel)
            if source:
                query += " AND source = %s"
                params.append(source)

            query += " ORDER BY sent_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get notification history: {e}")
        return []


def get_notification_stats(days: int = 7) -> dict:
    """Get notification statistics for the last N days."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    channel,
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed
                FROM notification_history
                WHERE sent_at > NOW() - INTERVAL '%s days'
                GROUP BY channel
            """, (days,))
            by_channel = {row['channel']: dict(row) for row in cur.fetchall()}

            cur.execute("""
                SELECT
                    source,
                    COUNT(*) as total
                FROM notification_history
                WHERE sent_at > NOW() - INTERVAL '%s days'
                GROUP BY source
            """, (days,))
            by_source = {row['source']: row['total'] for row in cur.fetchall()}

            return {
                'by_channel': by_channel,
                'by_source': by_source,
                'days': days
            }
    except Exception as e:
        logger.error(f"Failed to get notification stats: {e}")
        return {}


# =============================================================================
# Email Automation: Scheduled Job Tracking
# =============================================================================

def start_job_run(job_id: str, trigger_type: str = 'scheduled') -> Optional[int]:
    """Record start of a scheduled job run. Returns run ID or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO scheduled_job_runs (job_id, trigger_type, status)
                VALUES (%s, %s, 'running')
                RETURNING id
            """, (job_id, trigger_type))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to start job run: {e}")
        return None


def complete_job_run(
    run_id: int,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None
) -> bool:
    """Record completion of a scheduled job run."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE scheduled_job_runs
                SET completed_at = NOW(),
                    status = %s,
                    result = %s,
                    error_message = %s,
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))
                WHERE id = %s
            """, (status, json.dumps(result) if result else None, error, run_id))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to complete job run: {e}")
        return False


def get_job_runs(
    job_id: Optional[str] = None,
    days: int = 7,
    limit: int = 50
) -> list[dict]:
    """Get recent job runs with optional job ID filter."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT id, job_id, started_at, completed_at, status,
                       trigger_type, result, error_message, duration_seconds
                FROM scheduled_job_runs
                WHERE started_at > NOW() - INTERVAL '%s days'
            """
            params = [days]

            if job_id:
                query += " AND job_id = %s"
                params.append(job_id)

            query += " ORDER BY started_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get job runs: {e}")
        return []


def get_last_successful_run(job_id: str) -> Optional[dict]:
    """Get the last successful run of a job."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, job_id, started_at, completed_at, result, duration_seconds
                FROM scheduled_job_runs
                WHERE job_id = %s AND status = 'success'
                ORDER BY completed_at DESC
                LIMIT 1
            """, (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get last successful run: {e}")
        return None


# =============================================================================
# Email Automation: Fetch Logging
# =============================================================================

def log_email_fetch(
    account: str,
    operation: str,
    details: str,
    success: bool,
    error: Optional[str] = None
) -> Optional[int]:
    """Log an email fetch operation. Returns log ID or None on error."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO email_fetch_logs
                (account, operation, details, success, error_message)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (account, operation, details, success, error))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to log email fetch: {e}")
        return None


def get_email_fetch_logs(
    account: Optional[str] = None,
    hours: int = 24,
    success_only: bool = False,
    limit: int = 100
) -> list[dict]:
    """Get email fetch logs with optional filters."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT id, account, operation, details, success, error_message, logged_at
                FROM email_fetch_logs
                WHERE logged_at > NOW() - INTERVAL '%s hours'
            """
            params = [hours]

            if account:
                query += " AND account = %s"
                params.append(account)
            if success_only:
                query += " AND success = TRUE"

            query += " ORDER BY logged_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get email fetch logs: {e}")
        return []


def get_email_fetch_stats(hours: int = 24) -> dict:
    """Get email fetch statistics."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    account,
                    COUNT(*) as total_ops,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed,
                    MAX(logged_at) as last_fetch
                FROM email_fetch_logs
                WHERE logged_at > NOW() - INTERVAL '%s hours'
                GROUP BY account
            """, (hours,))
            by_account = {row['account']: dict(row) for row in cur.fetchall()}

            cur.execute("""
                SELECT
                    operation,
                    COUNT(*) as count,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
                FROM email_fetch_logs
                WHERE logged_at > NOW() - INTERVAL '%s hours'
                GROUP BY operation
            """, (hours,))
            by_operation = {row['operation']: dict(row) for row in cur.fetchall()}

            return {
                'by_account': by_account,
                'by_operation': by_operation,
                'hours': hours
            }
    except Exception as e:
        logger.error(f"Failed to get email fetch stats: {e}")
        return {}


def cache_inbox_message(
    account: str,
    message_id: str,
    subject: str,
    from_name: str,
    from_email: str,
    date_header: str,
    is_urgent: bool = False,
    is_from_person: bool = False,
    body_text: Optional[str] = None
) -> bool:
    """Cache an inbox message for analytics. Upserts on conflict."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO inbox_message_cache
                (account, message_id, subject, from_name, from_email, date_header,
                 is_urgent, is_from_person, body_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account, message_id) DO UPDATE SET
                    last_seen_at = CURRENT_TIMESTAMP,
                    is_urgent = EXCLUDED.is_urgent,
                    is_from_person = EXCLUDED.is_from_person,
                    body_text = COALESCE(EXCLUDED.body_text, inbox_message_cache.body_text)
            """, (account, message_id, subject, from_name, from_email, date_header,
                  is_urgent, is_from_person, body_text))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to cache inbox message: {e}")
        return False


def get_email_content_for_processing(account: str, message_id: str) -> dict:
    """Get full email content for AI/action processing.

    Combines body text from inbox_message_cache with extracted attachment
    text from email_attachments for comprehensive content analysis.

    Returns:
        {'body': str, 'subject': str, 'from_name': str, 'from_email': str,
         'attachments': [{'filename': str, 'text': str, 'content_type': str}]}
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Get message body and metadata
            cur.execute("""
                SELECT subject, from_name, from_email, body_text
                FROM inbox_message_cache
                WHERE account = %s AND message_id = %s
            """, (account, message_id))
            msg_row = cur.fetchone()

            if not msg_row:
                return {'body': '', 'subject': '', 'from_name': '', 'from_email': '',
                        'attachments': [], 'error': 'Message not found'}

            # Get attachment content
            cur.execute("""
                SELECT filename, content_type, extracted_text
                FROM email_attachments
                WHERE account = %s AND message_id = %s
                  AND extraction_status = 'success'
                  AND extracted_text IS NOT NULL
                ORDER BY filename
            """, (account, message_id))
            attachments = [
                {'filename': row['filename'],
                 'content_type': row['content_type'],
                 'text': row['extracted_text']}
                for row in cur.fetchall()
            ]

            return {
                'body': msg_row['body_text'] or '',
                'subject': msg_row['subject'] or '',
                'from_name': msg_row['from_name'] or '',
                'from_email': msg_row['from_email'] or '',
                'attachments': attachments
            }
    except Exception as e:
        logger.error(f"Failed to get email content for processing: {e}")
        return {'body': '', 'subject': '', 'from_name': '', 'from_email': '',
                'attachments': [], 'error': str(e)}


def get_inbox_message_stats(days: int = 7) -> dict:
    """Get inbox message cache statistics."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    account,
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN is_urgent THEN 1 ELSE 0 END) as urgent_count,
                    SUM(CASE WHEN is_from_person THEN 1 ELSE 0 END) as from_people_count,
                    MIN(first_seen_at) as earliest,
                    MAX(last_seen_at) as latest
                FROM inbox_message_cache
                WHERE last_seen_at > NOW() - INTERVAL '%s days'
                GROUP BY account
            """, (days,))
            return {row['account']: dict(row) for row in cur.fetchall()}
    except Exception as e:
        logger.error(f"Failed to get inbox message stats: {e}")
        return {}


# =============================================================================
# Email Automation: Attachment Storage
# =============================================================================

def store_attachment(
    account: str,
    message_id: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    extracted_text: Optional[str] = None,
    extraction_status: str = 'success',
    extraction_error: Optional[str] = None
) -> Optional[int]:
    """Store email attachment metadata and extracted content."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO email_attachments
                (account, message_id, filename, content_type, size_bytes,
                 extracted_text, extraction_status, extraction_error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account, message_id, filename) DO UPDATE SET
                    extracted_text = EXCLUDED.extracted_text,
                    extraction_status = EXCLUDED.extraction_status,
                    extraction_error = EXCLUDED.extraction_error
                RETURNING id
            """, (account, message_id, filename, content_type, size_bytes,
                  extracted_text, extraction_status, extraction_error))
            result = cur.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        logger.error(f"Failed to store attachment: {e}")
        return None


def get_attachments_for_message(account: str, message_id: str) -> list[dict]:
    """Get all attachments for a specific message."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, filename, content_type, size_bytes,
                       extracted_text, extraction_status, extraction_error,
                       first_seen_at
                FROM email_attachments
                WHERE account = %s AND message_id = %s
                ORDER BY filename
            """, (account, message_id))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get attachments: {e}")
        return []


def search_attachment_content(
    query: str,
    account: Optional[str] = None,
    days: int = 30,
    limit: int = 50
) -> list[dict]:
    """Full-text search across attachment content."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            sql = """
                SELECT a.id, a.account, a.message_id, a.filename,
                       a.content_type, a.size_bytes, a.first_seen_at,
                       ts_headline('english', a.extracted_text, plainto_tsquery('english', %s),
                                   'MaxWords=50, MinWords=20') as snippet
                FROM email_attachments a
                WHERE a.extracted_text IS NOT NULL
                  AND to_tsvector('english', a.extracted_text) @@ plainto_tsquery('english', %s)
                  AND a.first_seen_at > NOW() - INTERVAL '%s days'
            """
            params = [query, query, days]

            if account:
                sql += " AND a.account = %s"
                params.append(account)

            sql += " ORDER BY a.first_seen_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to search attachments: {e}")
        return []


def get_attachment_stats(days: int = 7) -> dict:
    """Get attachment statistics."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total_attachments,
                    SUM(size_bytes) as total_bytes,
                    COUNT(CASE WHEN extraction_status = 'success' THEN 1 END) as extracted,
                    COUNT(CASE WHEN extraction_status = 'failed' THEN 1 END) as failed,
                    COUNT(CASE WHEN content_type LIKE 'application/pdf%%' THEN 1 END) as pdfs
                FROM email_attachments
                WHERE first_seen_at > NOW() - INTERVAL '%s days'
            """, (days,))
            row = cur.fetchone()
            return dict(row) if row else {}
    except Exception as e:
        logger.error(f"Failed to get attachment stats: {e}")
        return {}
