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
