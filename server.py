#!/usr/bin/env python3
"""
Project Intelligence Dashboard - Flask Backend

Aggregates data from multiple sources:
- Git repositories (commits, branch status, dirty state)
- Todoist (tasks filtered by project)
- Kanban board (integrated, PostgreSQL)
- Linear (GraphQL API)
"""

import json
import os
import subprocess
import logging
from datetime import datetime, timedelta, date
from enum import Enum
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
import requests
from flask import Flask, jsonify, send_from_directory, request

from utils import group_items_by_key
from config_loader import get_config, get_config_dict, ConfigurationError
from resilience import (
    retry, retry_with_circuit_breaker, CircuitBreakerError,
    todoist_circuit, linear_circuit, weather_circuit, get_circuit_status
)


# =============================================================================
# Status Constants
# =============================================================================

class Status:
    """API response status constants to prevent magic string typos."""
    OK = 'ok'
    ERROR = 'error'
    NOT_CONFIGURED = 'not_configured'
    UNAVAILABLE = 'unavailable'
    OFFLINE = 'offline'
    SKIPPED = 'skipped'


class DataSource:
    """Data source identifiers."""
    API = 'api'
    DATABASE = 'database'
    HEALTH_ANALYTICS = 'health-analytics'
    MONZO_ANALYSIS = 'monzo-analysis'


class Defaults:
    """Default values for configuration and requests."""
    # Timeouts (seconds)
    API_TIMEOUT_SHORT = 5
    API_TIMEOUT_MEDIUM = 10
    SUBPROCESS_TIMEOUT = 5

    # Thread pool
    MAX_WORKERS = 4

    # Date ranges
    HISTORY_DAYS_DEFAULT = 7
    ANALYTICS_DAYS_DEFAULT = 30
    ANALYTICS_DAYS_MAX = 365
    ACTIVITY_DAYS_MAX = 90

    # XP settings
    BUDGET_UNDER_XP = 10
    DURATION_BONUS_PER_10MIN = 5
    DURATION_BONUS_MAX = 25

    # Display limits
    MAX_COMMITS_DISPLAY = 5
    MAX_UPCOMING_TASKS = 5
    MAX_READY_TASKS = 5
    MAX_URGENT_EMAILS = 5
    MAX_PEOPLE_EMAILS = 7

    # Sprint quality gates
    QUALITY_GATES_TOTAL = 8


class Kanban:
    """Kanban board constants and validation limits."""
    # Fallback columns if database is unavailable
    DEFAULT_COLUMNS = {'backlog', 'ready', 'in-progress', 'review', 'done'}
    MAX_TITLE_LENGTH = 255
    MAX_DESCRIPTION_LENGTH = 10000
    MAX_TAGS = 20
    MAX_TAG_LENGTH = 50
    MAX_LINKS = 50
    MAX_LINK_URL_LENGTH = 2000
    MAX_LINK_TITLE_LENGTH = 200
    PRIORITY_MIN = 1
    PRIORITY_MAX = 4

    _cached_columns = None
    _cache_time = None

    @classmethod
    def get_valid_columns(cls):
        """Get valid column codes from database, with caching."""
        import time
        # Cache for 60 seconds
        if cls._cached_columns and cls._cache_time and (time.time() - cls._cache_time) < 60:
            return cls._cached_columns

        try:
            if DB_AVAILABLE:
                columns = db.get_kanban_columns(active_only=True)
                if columns:
                    cls._cached_columns = {col['code'] for col in columns}
                    cls._cache_time = time.time()
                    return cls._cached_columns
        except Exception:
            pass

        return cls.DEFAULT_COLUMNS


# Import database, planning, and overnight sprint modules
try:
    import database as db
    import planning
    import overnight_sprint
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None
    logging.warning(f"Database modules unavailable: {e}. Analytics and planning features disabled.")


def get_db_connection():
    """Get a basic database connection using centralized config."""
    app_config = get_config()
    return psycopg2.connect(**app_config.database.to_psycopg2_params())


def get_dict_db_connection():
    """Get a database connection with RealDictCursor for dict-like row access."""
    app_config = get_config()
    return psycopg2.connect(**app_config.database.to_psycopg2_params(), cursor_factory=RealDictCursor)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Load configuration using centralized loader
CONFIG_PATH = Path(__file__).parent / 'config.yaml'

# Initialize config - using dict-like proxy for backward compatibility
try:
    config = get_config_dict()
    app_config = get_config()
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    raise SystemExit(f"Configuration error: {e}")


# =============================================================================
# Data Fetchers
# =============================================================================

def fetch_git_repos() -> dict[str, Any]:
    """Scan git repositories for status."""
    result = {'status': Status.OK, 'repos': [], 'error': None}
    
    try:
        scan_paths = config['git'].get('scan_paths', ['~/clawd/projects'])
        history_days = config['git'].get('history_days', 7)
        since_date = (datetime.now() - timedelta(days=history_days)).strftime('%Y-%m-%d')
        
        for scan_path in scan_paths:
            expanded_path = Path(os.path.expanduser(scan_path))
            if not expanded_path.exists():
                continue
                
            for repo_dir in expanded_path.iterdir():
                if not repo_dir.is_dir() or repo_dir.name.startswith('.'):
                    continue
                    
                git_dir = repo_dir / '.git'
                if not git_dir.exists():
                    continue
                
                repo_info = {
                    'name': repo_dir.name,
                    'path': str(repo_dir),
                    'branch': None,
                    'commits': [],
                    'commit_count': 0,
                    'is_dirty': False,
                    'ahead': 0,
                    'behind': 0
                }
                
                try:
                    # Get current branch
                    branch_result = subprocess.run(
                        ['git', '-C', str(repo_dir), 'branch', '--show-current'],
                        capture_output=True, text=True, timeout=Defaults.SUBPROCESS_TIMEOUT
                    )
                    if branch_result.returncode == 0:
                        repo_info['branch'] = branch_result.stdout.strip() or 'HEAD'
                    
                    # Get recent commits
                    log_result = subprocess.run(
                        ['git', '-C', str(repo_dir), 'log', '--oneline', '-10', f'--since={since_date}'],
                        capture_output=True, text=True, timeout=Defaults.SUBPROCESS_TIMEOUT
                    )
                    if log_result.returncode == 0 and log_result.stdout.strip():
                        commits = log_result.stdout.strip().split('\n')
                        repo_info['commits'] = commits[:Defaults.MAX_COMMITS_DISPLAY]
                        repo_info['commit_count'] = len(commits)
                    
                    # Check if dirty
                    status_result = subprocess.run(
                        ['git', '-C', str(repo_dir), 'status', '--porcelain'],
                        capture_output=True, text=True, timeout=Defaults.SUBPROCESS_TIMEOUT
                    )
                    if status_result.returncode == 0:
                        repo_info['is_dirty'] = bool(status_result.stdout.strip())
                    
                    # Get ahead/behind (if tracking remote)
                    try:
                        rev_result = subprocess.run(
                            ['git', '-C', str(repo_dir), 'rev-list', '--left-right', '--count', '@{u}...HEAD'],
                            capture_output=True, text=True, timeout=Defaults.SUBPROCESS_TIMEOUT
                        )
                        if rev_result.returncode == 0:
                            parts = rev_result.stdout.strip().split()
                            if len(parts) == 2:
                                repo_info['behind'] = int(parts[0])
                                repo_info['ahead'] = int(parts[1])
                    except subprocess.TimeoutExpired:
                        logger.debug(f"Timeout checking upstream status for {repo_dir}")
                    except subprocess.SubprocessError:
                        pass  # Expected: no upstream tracking configured
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse upstream status for {repo_dir}: {e}")
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"Timeout scanning repo: {repo_dir}")
                except Exception as e:
                    logger.warning(f"Error scanning repo {repo_dir}: {e}")
                
                result['repos'].append(repo_info)
        
        # Sort by activity (commit count + dirty)
        result['repos'].sort(key=lambda x: (x['is_dirty'], x['commit_count']), reverse=True)
        
    except Exception as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Git fetch error: {e}")
    
    return result


@retry_with_circuit_breaker(
    todoist_circuit,
    max_attempts=3,
    base_delay=1.0,
    exceptions=(requests.exceptions.RequestException,)
)
def _todoist_api_get(endpoint: str, headers: dict) -> dict:
    """Make a GET request to Todoist API with retry logic."""
    resp = requests.get(
        f'https://api.todoist.com/rest/v2/{endpoint}',
        headers=headers,
        timeout=Defaults.API_TIMEOUT_MEDIUM
    )
    resp.raise_for_status()
    return resp.json()


def fetch_todoist() -> dict[str, Any]:
    """Fetch tasks from Todoist."""
    result = {'status': Status.OK, 'tasks': [], 'error': None}

    token = config['todoist'].get('token', '')
    if not token:
        result['status'] = Status.NOT_CONFIGURED
        result['error'] = 'Todoist token not configured'
        return result

    try:
        headers = {'Authorization': f'Bearer {token}'}
        all_tasks = _todoist_api_get('tasks', headers)
        projects_data = _todoist_api_get('projects', headers)
        projects = {p['id']: p['name'] for p in projects_data}

        # Filter by configured projects (if any)
        allowed_projects = config['todoist'].get('projects', [])
        today = datetime.now().strftime('%Y-%m-%d')

        for task in all_tasks:
            project_name = projects.get(task.get('project_id'), 'Unknown')

            # Filter by project if configured
            if allowed_projects and project_name not in allowed_projects:
                continue

            due = task.get('due', {})
            due_date = due.get('date', '') if due else ''

            task_info = {
                'id': task['id'],
                'content': task['content'],
                'project': project_name,
                'priority': task.get('priority', 1),
                'due_date': due_date,
                'is_overdue': due_date < today if due_date else False,
                'is_today': due_date == today if due_date else False,
                'url': task.get('url', '')
            }
            result['tasks'].append(task_info)

        # Sort: overdue first, then today, then by priority
        result['tasks'].sort(key=lambda x: (
            not x['is_overdue'],
            not x['is_today'],
            -x['priority'],
            x['due_date'] or 'z'
        ))

    except CircuitBreakerError as e:
        result['status'] = Status.UNAVAILABLE
        result['error'] = f'Todoist service temporarily unavailable (retry at {e.reset_time.strftime("%H:%M")})'
        logger.warning(f"Todoist circuit breaker open: {e}")
    except requests.exceptions.RequestException as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Todoist fetch error: {e}")
    except Exception as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Todoist processing error: {e}")

    return result


def fetch_kanban() -> dict[str, Any]:
    """Fetch tasks from integrated kanban (PostgreSQL direct)."""
    result = {
        'status': Status.OK,
        'tasks': [],
        'by_column': {},
        'error': None,
        'source': DataSource.DATABASE
    }

    if not DB_AVAILABLE:
        result['status'] = Status.ERROR
        result['error'] = 'Database not available'
        return result

    try:
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, description, column_name as column, tags,
                       priority, position, created_at, updated_at
                FROM kanban_tasks
                ORDER BY column_name, position
            """)
            tasks = [dict(row) for row in cur.fetchall()]

        result['tasks'] = tasks
        result['by_column'] = group_items_by_key(tasks, 'column')

    except Exception as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Kanban fetch error: {e}")

    return result


# =============================================================================
# Kanban CRUD Helpers
# =============================================================================

def kanban_task_to_dict(task: dict) -> dict:
    """Convert database task row to API response dictionary."""
    return {
        'id': task['id'],
        'title': task['title'],
        'description': task.get('description') or '',
        'tags': task.get('tags') or [],
        'links': task.get('links') or [],
        'priority': task.get('priority', 2),
        'column': task.get('column_name') or task.get('column'),
        'position': task.get('position', 0),
        'created_at': task['created_at'].isoformat() if hasattr(task.get('created_at'), 'isoformat') else task.get('created_at'),
        'updated_at': task['updated_at'].isoformat() if hasattr(task.get('updated_at'), 'isoformat') else task.get('updated_at'),
    }


def validate_kanban_task(data: dict, require_title: bool = True) -> str | None:
    """
    Validate kanban task data.
    Returns error message if invalid, None if valid.
    """
    # Validate title
    if require_title:
        if 'title' not in data or not data['title']:
            return "Title is required"
        if not isinstance(data['title'], str):
            return "Title must be a string"
        if len(data['title']) > Kanban.MAX_TITLE_LENGTH:
            return f"Title must be {Kanban.MAX_TITLE_LENGTH} characters or less"

    # Validate description
    if 'description' in data and data['description']:
        if not isinstance(data['description'], str):
            return "Description must be a string"
        if len(data['description']) > Kanban.MAX_DESCRIPTION_LENGTH:
            return f"Description must be {Kanban.MAX_DESCRIPTION_LENGTH} characters or less"

    # Validate tags
    if 'tags' in data and data['tags']:
        if not isinstance(data['tags'], list):
            return "Tags must be an array"
        if len(data['tags']) > Kanban.MAX_TAGS:
            return f"Maximum {Kanban.MAX_TAGS} tags allowed"
        for tag in data['tags']:
            if not isinstance(tag, str):
                return "All tags must be strings"
            if len(tag) > Kanban.MAX_TAG_LENGTH:
                return f"Each tag must be {Kanban.MAX_TAG_LENGTH} characters or less"

    # Validate column
    if 'column' in data:
        if not isinstance(data['column'], str):
            return "Column must be a string"
        valid_columns = Kanban.get_valid_columns()
        if data['column'] not in valid_columns:
            return f"Column must be one of: {', '.join(valid_columns)}"

    # Validate position
    if 'position' in data:
        if not isinstance(data['position'], int):
            return "Position must be an integer"
        if data['position'] < 0:
            return "Position must be non-negative"

    # Validate priority
    if 'priority' in data:
        if not isinstance(data['priority'], int):
            return "Priority must be an integer"
        if data['priority'] < Kanban.PRIORITY_MIN or data['priority'] > Kanban.PRIORITY_MAX:
            return f"Priority must be between {Kanban.PRIORITY_MIN} and {Kanban.PRIORITY_MAX}"

    # Validate links
    if 'links' in data and data['links']:
        if not isinstance(data['links'], list):
            return "Links must be an array"
        if len(data['links']) > Kanban.MAX_LINKS:
            return f"Maximum {Kanban.MAX_LINKS} links allowed"
        for link in data['links']:
            if not isinstance(link, dict):
                return "All links must be objects"
            if 'url' not in link or not isinstance(link['url'], str):
                return "Each link must have a 'url' string field"
            if len(link['url']) > Kanban.MAX_LINK_URL_LENGTH:
                return f"Link URL must be {Kanban.MAX_LINK_URL_LENGTH} characters or less"
            if 'type' in link and not isinstance(link['type'], str):
                return "Link 'type' must be a string"
            if 'title' in link:
                if not isinstance(link['title'], str):
                    return "Link 'title' must be a string"
                if len(link['title']) > Kanban.MAX_LINK_TITLE_LENGTH:
                    return f"Link title must be {Kanban.MAX_LINK_TITLE_LENGTH} characters or less"

    return None


@retry_with_circuit_breaker(
    linear_circuit,
    max_attempts=3,
    base_delay=1.0,
    exceptions=(requests.exceptions.RequestException,)
)
def _linear_graphql_query(query: str, api_key: str) -> dict:
    """Execute Linear GraphQL query with retry logic."""
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    resp = requests.post(
        'https://api.linear.app/graphql',
        headers=headers,
        json={'query': query},
        timeout=Defaults.API_TIMEOUT_MEDIUM
    )
    resp.raise_for_status()
    return resp.json()


def fetch_linear() -> dict[str, Any]:
    """Fetch issues from Linear."""
    result = {'status': Status.OK, 'issues': [], 'by_status': {}, 'error': None}

    api_key = config['linear'].get('api_key', '')
    if not api_key:
        result['status'] = Status.NOT_CONFIGURED
        result['error'] = 'Linear API key not configured'
        return result

    try:
        # GraphQL query for assigned issues
        query = """
        query {
            viewer {
                assignedIssues(first: 50, orderBy: updatedAt) {
                    nodes {
                        id
                        identifier
                        title
                        priority
                        state {
                            name
                            type
                        }
                        project {
                            name
                        }
                        dueDate
                        createdAt
                        updatedAt
                    }
                }
            }
        }
        """

        data = _linear_graphql_query(query, api_key)

        if 'errors' in data:
            result['status'] = Status.ERROR
            result['error'] = data['errors'][0].get('message', 'Unknown error')
            return result

        issues = data.get('data', {}).get('viewer', {}).get('assignedIssues', {}).get('nodes', [])

        for issue in issues:
            state = issue.get('state', {})
            state_name = state.get('name', 'Unknown')
            state_type = state.get('type', 'unknown')

            issue_info = {
                'id': issue.get('id'),
                'identifier': issue.get('identifier'),
                'title': issue.get('title'),
                'priority': issue.get('priority', 0),
                'state': state_name,
                'state_type': state_type,
                'project': issue.get('project', {}).get('name') if issue.get('project') else None,
                'due_date': issue.get('dueDate'),
                'updated_at': issue.get('updatedAt')
            }
            result['issues'].append(issue_info)

            # Group by status
            if state_name not in result['by_status']:
                result['by_status'][state_name] = []
            result['by_status'][state_name].append(issue_info)

        # Sort by priority (higher = more urgent in Linear: 1=urgent, 4=low, 0=none)
        result['issues'].sort(key=lambda x: (x['priority'] or 5))

    except CircuitBreakerError as e:
        result['status'] = Status.UNAVAILABLE
        result['error'] = f'Linear service temporarily unavailable (retry at {e.reset_time.strftime("%H:%M")})'
        logger.warning(f"Linear circuit breaker open: {e}")
    except requests.exceptions.RequestException as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Linear fetch error: {e}")
    except Exception as e:
        result['status'] = Status.ERROR
        result['error'] = str(e)
        logger.error(f"Linear processing error: {e}")

    return result


# =============================================================================
# API Routes
# =============================================================================

@app.route('/')
def serve_index():
    """Serve the dashboard frontend."""
    return send_from_directory('.', 'index.html')


@app.route('/api/health')
def health_check():
    """
    Comprehensive health check endpoint.

    Returns status of all components: database, external services, circuit breakers.
    """
    health = {
        'status': Status.OK,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'components': {}
    }

    # Database health
    if DB_AVAILABLE:
        db_health = db.check_health()
        health['components']['database'] = db_health
        if not db_health.get('healthy'):
            health['status'] = Status.ERROR
    else:
        health['components']['database'] = {
            'healthy': False,
            'error': 'Database module not available'
        }

    # Configuration status
    health['components']['config'] = {
        'todoist_configured': app_config.todoist.is_configured,
        'linear_configured': app_config.linear.is_configured,
        'email_accounts': len(app_config.email.configured_accounts),
        'telegram_configured': app_config.notifications.telegram.is_configured,
        'slack_configured': app_config.notifications.slack.is_configured
    }

    # Circuit breaker status
    health['components']['circuit_breakers'] = get_circuit_status()

    # Determine overall status
    # If any critical component is unhealthy, mark overall as degraded
    if health['components']['database'].get('healthy') is False:
        health['status'] = Status.ERROR

    # Check if any circuit breaker is open
    open_circuits = [
        name for name, status in health['components']['circuit_breakers'].items()
        if status.get('state') == 'open'
    ]
    if open_circuits:
        if health['status'] == Status.OK:
            health['status'] = 'degraded'
        health['components']['circuit_breakers']['open_circuits'] = open_circuits

    return jsonify(health)


@app.route('/api/dashboard')
def get_dashboard():
    """Fetch all dashboard data in parallel."""
    start_time = datetime.now()
    store_snapshot = request.args.get('store', 'true').lower() == 'true'
    
    # Fetch all sources in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=Defaults.MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_git_repos): 'git',
            executor.submit(fetch_todoist): 'todoist',
            executor.submit(fetch_kanban): 'kanban',
            executor.submit(fetch_linear): 'linear'
        }
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                results[source] = future.result()
            except Exception as e:
                logger.error(f"Error fetching {source}: {e}")
                results[source] = {'status': Status.ERROR, 'error': str(e)}
    
    # Store snapshots to database (for analytics)
    storage_status = Status.OK if DB_AVAILABLE and store_snapshot else Status.SKIPPED
    storage_error = None

    if DB_AVAILABLE and store_snapshot:
        try:
            if results['git'].get('status') == Status.OK:
                db.store_git_snapshot(results['git'].get('repos', []))
            if results['todoist'].get('status') == Status.OK:
                db.store_todoist_snapshot(results['todoist'].get('tasks', []))
            if results['kanban'].get('status') == Status.OK:
                db.store_kanban_snapshot(results['kanban'].get('by_column', {}))
            if results['linear'].get('status') == Status.OK:
                db.store_linear_snapshot(
                    results['linear'].get('issues', []),
                    results['linear'].get('by_status', {})
                )
            # Update daily aggregates
            db.update_daily_stats(results['git'], results['todoist'], results['kanban'])
        except Exception as e:
            storage_status = Status.ERROR
            storage_error = str(e)
            logger.error(f"Failed to store snapshots: {e}")

    # Build response
    elapsed = (datetime.now() - start_time).total_seconds()

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'fetch_time_seconds': round(elapsed, 2),
        'refresh_interval': config['server'].get('refresh_interval', 300),
        'db_available': DB_AVAILABLE,
        'storage_status': storage_status,
        'storage_error': storage_error,
        'sources': results
    })


@app.route('/api/analytics/trends')
def get_trends():
    """Get trend data for all sources."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 1), 365)  # Clamp between 1-365
    
    return jsonify({
        'days': days,
        'git': db.get_git_trends(days),
        'todoist': db.get_todoist_trends(days),
        'kanban': db.get_kanban_trends(days),
        'linear': db.get_linear_trends(days)
    })


@app.route('/api/analytics/daily')
def get_daily():
    """Get daily summary stats."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 7, type=int)
    days = min(max(days, 1), 90)
    
    return jsonify({
        'days': days,
        'stats': db.get_daily_summary(days)
    })


@app.route('/api/analytics/repo/<repo_name>')
def get_repo_analytics(repo_name):
    """Get analytics for a specific repo."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 30, type=int)
    
    return jsonify({
        'repo': repo_name,
        'days': days,
        'history': db.get_repo_history(repo_name, days)
    })


@app.route('/api/config')
def get_config_status():
    """Return configuration status (not the actual secrets)."""
    return jsonify({
        'todoist': {
            'configured': bool(config['todoist'].get('token')),
            'projects': config['todoist'].get('projects', [])
        },
        'linear': {
            'configured': bool(config['linear'].get('api_key'))
        },
        'git': {
            'scan_paths': config['git'].get('scan_paths', []),
            'history_days': config['git'].get('history_days', 7)
        },
        'kanban': {
            'integrated': True,
            'source': 'postgresql'
        },
        'server': {
            'refresh_interval': config['server'].get('refresh_interval', 300)
        }
    })


# =============================================================================
# Kanban CRUD API
# =============================================================================

@app.route('/api/kanban/tasks', methods=['GET'])
def kanban_get_tasks():
    """Get all kanban tasks."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, description, tags, links, priority, column_name, position,
                   created_at, updated_at
            FROM kanban_tasks
            ORDER BY column_name, position, id
        """)
        tasks = [kanban_task_to_dict(dict(row)) for row in cur.fetchall()]
        return jsonify(tasks)
    except Exception as e:
        logger.error(f"Kanban get_tasks error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/kanban/tasks', methods=['POST'])
def kanban_create_task():
    """Create a new kanban task."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    validation_error = validate_kanban_task(data, require_title=True)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        
        column = data.get('column', 'backlog')
        cur.execute("""
            SELECT COALESCE(MAX(position), -1) + 1 as next_pos
            FROM kanban_tasks
            WHERE column_name = %s
        """, (column,))
        next_pos = cur.fetchone()['next_pos']
        
        cur.execute("""
            INSERT INTO kanban_tasks (title, description, tags, links, priority, column_name, position)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, title, description, tags, links, priority, column_name, position, created_at, updated_at
        """, (
            data['title'],
            data.get('description', ''),
            data.get('tags', []),
            data.get('links', []),
            data.get('priority', 2),
            column,
            next_pos
        ))
        
        task = kanban_task_to_dict(dict(cur.fetchone()))
        conn.commit()
        
        logger.info(f"Created kanban task {task['id']}: {task['title']}")
        return jsonify(task), 201
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Kanban create_task error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/kanban/tasks/<int:task_id>', methods=['PUT'])
def kanban_update_task(task_id):
    """Update a kanban task."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    validation_error = validate_kanban_task(data, require_title=False)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        
        # Build update query with whitelisted fields only
        allowed_fields = {
            'title': 'title',
            'description': 'description',
            'tags': 'tags',
            'links': 'links',
            'priority': 'priority',
            'column': 'column_name',
            'position': 'position'
        }
        
        updates = []
        values = []
        
        for data_key, db_column in allowed_fields.items():
            if data_key in data:
                updates.append(f'{db_column} = %s')
                values.append(data[data_key])
        
        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        updates.append('updated_at = NOW()')
        values.append(task_id)
        
        query = f"""
            UPDATE kanban_tasks
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING id, title, description, tags, links, priority, column_name, position, created_at, updated_at
        """
        
        cur.execute(query, values)
        row = cur.fetchone()
        conn.commit()
        
        if not row:
            return jsonify({'error': 'Task not found'}), 404
        
        task = kanban_task_to_dict(dict(row))
        logger.info(f"Updated kanban task {task_id}")
        return jsonify(task)
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Kanban update_task error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/kanban/tasks/<int:task_id>', methods=['DELETE'])
def kanban_delete_task(task_id):
    """Delete a kanban task."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        
        cur.execute('DELETE FROM kanban_tasks WHERE id = %s RETURNING id', (task_id,))
        deleted = cur.fetchone()
        conn.commit()
        
        if not deleted:
            return jsonify({'error': 'Task not found'}), 404
        
        logger.info(f"Deleted kanban task {task_id}")
        return jsonify({'deleted': True, 'id': task_id})
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Kanban delete_task error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    finally:
        if conn:
            conn.close()


# Legacy endpoint for backward compatibility with jeeves-kanban skill
@app.route('/api/tasks', methods=['GET'])
def legacy_kanban_get_tasks():
    """Legacy endpoint - redirects to /api/kanban/tasks."""
    return kanban_get_tasks()


@app.route('/api/tasks', methods=['POST'])
def legacy_kanban_create_task():
    """Legacy endpoint - redirects to /api/kanban/tasks."""
    return kanban_create_task()


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def legacy_kanban_update_task(task_id):
    """Legacy endpoint - redirects to /api/kanban/tasks/<id>."""
    return kanban_update_task(task_id)


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def legacy_kanban_delete_task(task_id):
    """Legacy endpoint - redirects to /api/kanban/tasks/<id>."""
    return kanban_delete_task(task_id)


# =============================================================================
# Standup & Planning API
# =============================================================================

@retry_with_circuit_breaker(
    weather_circuit,
    max_attempts=2,  # Weather is non-critical, fewer retries
    base_delay=0.5,
    exceptions=(requests.exceptions.RequestException,)
)
def _weather_api_get() -> dict:
    """Fetch weather data with retry logic."""
    resp = requests.get('https://wttr.in/London?format=j1', timeout=Defaults.API_TIMEOUT_SHORT)
    resp.raise_for_status()
    return resp.json()


def fetch_weather() -> dict:
    """Fetch current weather."""
    try:
        data = _weather_api_get()
        current = data.get('current_condition', [{}])[0]
        return {
            'status': Status.OK,
            'temp_c': current.get('temp_C'),
            'condition': current.get('weatherDesc', [{}])[0].get('value'),
            'humidity': current.get('humidity'),
            'wind_kph': current.get('windspeedKmph')
        }
    except CircuitBreakerError as e:
        logger.debug(f"Weather circuit breaker open: {e}")
        return {'status': Status.UNAVAILABLE, 'error': 'Weather service temporarily unavailable'}
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")
        return {'status': Status.ERROR, 'error': 'Failed to fetch weather'}


@app.route('/api/standup')
def get_standup():
    """Get morning standup data - tasks, calendar, weather, projects."""
    start_time = datetime.now()
    today = start_time.strftime('%Y-%m-%d')
    
    # Fetch all data
    todoist = fetch_todoist()
    kanban = fetch_kanban()
    weather = fetch_weather()
    
    # Process tasks
    tasks = todoist.get('tasks', [])
    overdue = [t for t in tasks if t.get('is_overdue')]
    today_tasks = [t for t in tasks if t.get('is_today')]
    upcoming = [t for t in tasks if not t.get('is_overdue') and not t.get('is_today') and t.get('due_date')]
    
    # Kanban summary
    kanban_cols = kanban.get('by_column', {})
    in_progress = kanban_cols.get('in-progress', [])
    ready = kanban_cols.get('ready', [])
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    return jsonify({
        'generated_at': start_time.isoformat(),
        'date': today,
        'day_name': start_time.strftime('%A'),
        'fetch_time_seconds': round(elapsed, 2),
        'weather': weather,
        'tasks': {
            'overdue': overdue,
            'today': today_tasks,
            'upcoming': upcoming[:Defaults.MAX_UPCOMING_TASKS]
        },
        'kanban': {
            'in_progress': in_progress,
            'ready': ready[:Defaults.MAX_READY_TASKS]
        },
        'summary': {
            'overdue_count': len(overdue),
            'today_count': len(today_tasks),
            'in_progress_count': len(in_progress)
        }
    })


# =============================================================================
# Inbox Digest API
# =============================================================================

def get_email_accounts():
    """Get email accounts from config."""
    return config.get('email', {}).get('accounts', [])

def fetch_inbox_for_account(account: str, max_results: int = 50) -> dict:
    """Fetch inbox summary for a single email account using gog CLI."""
    import subprocess
    import json as json_module
    
    result = {
        'account': account,
        'status': 'ok',
        'total_unread': 0,
        'urgent': [],
        'from_people': [],
        'newsletters': 0,
        'error': None
    }
    
    try:
        # Get total unread count
        proc = subprocess.run(
            ['gog', 'gmail', 'messages', 'search', 'in:inbox is:unread', 
             '--max', str(max_results), '--account', account, '--json'],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            messages = json_module.loads(proc.stdout)
            result['total_unread'] = len(messages)
        
        # Get urgent (starred/important)
        proc = subprocess.run(
            ['gog', 'gmail', 'messages', 'search', 
             'in:inbox is:unread (is:starred OR is:important)', 
             '--max', '10', '--account', account, '--json'],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            urgent = json_module.loads(proc.stdout)
            result['urgent'] = [{
                'id': m.get('id'),
                'subject': m.get('subject', '(no subject)')[:60],
                'from': m.get('from', 'unknown').split('<')[0].strip()[:30],
                'date': m.get('date', '')
            } for m in urgent[:Defaults.MAX_URGENT_EMAILS]]
        
        # Get from real people (not automated)
        proc = subprocess.run(
            ['gog', 'gmail', 'messages', 'search',
             'in:inbox is:unread -from:noreply -from:no-reply -from:notifications -category:promotions newer_than:3d',
             '--max', '15', '--account', account, '--json'],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            people = json_module.loads(proc.stdout)
            result['from_people'] = [{
                'id': m.get('id'),
                'subject': m.get('subject', '(no subject)')[:60],
                'from': m.get('from', 'unknown').split('<')[0].strip()[:30],
                'date': m.get('date', '')
            } for m in people[:Defaults.MAX_PEOPLE_EMAILS]]
        
        # Get newsletter/promo count
        proc = subprocess.run(
            ['gog', 'gmail', 'messages', 'search',
             'in:inbox is:unread (category:promotions OR category:updates)',
             '--max', '100', '--account', account, '--json'],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            newsletters = json_module.loads(proc.stdout)
            result['newsletters'] = len(newsletters)
            
    except subprocess.TimeoutExpired:
        result['status'] = 'timeout'
        result['error'] = 'Gmail API timed out'
    except FileNotFoundError:
        result['status'] = 'error'
        result['error'] = 'gog CLI not found'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


@app.route('/api/inbox/digest')
def get_inbox_digest():
    """Get unified inbox digest across all email accounts."""
    start_time = datetime.now()
    
    accounts_data = []
    total_unread = 0
    total_urgent = 0
    
    for account_info in get_email_accounts():
        account_data = fetch_inbox_for_account(account_info['email'])
        account_data['name'] = account_info['name']
        account_data['priority'] = account_info['priority']
        accounts_data.append(account_data)
        
        if account_data['status'] == 'ok':
            total_unread += account_data.get('total_unread', 0)
            total_urgent += len(account_data.get('urgent', []))
    
    # Store snapshot for analytics
    if DB_AVAILABLE:
        try:
            db.store_inbox_snapshot(accounts_data)
        except Exception as e:
            logger.warning(f"Failed to store inbox snapshot: {e}")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    return jsonify({
        'generated_at': start_time.isoformat(),
        'fetch_time_seconds': round(elapsed, 2),
        'summary': {
            'total_unread': total_unread,
            'total_urgent': total_urgent,
            'accounts_checked': len(get_email_accounts())
        },
        'accounts': accounts_data
    })


@app.route('/api/inbox/account/<account>')
def get_inbox_account(account):
    """Get inbox data for a specific account."""
    # Validate account
    valid_accounts = [a['email'] for a in get_email_accounts()]
    if account not in valid_accounts:
        return jsonify({'error': f'Unknown account. Valid: {valid_accounts}'}), 400
    
    data = fetch_inbox_for_account(account)
    return jsonify(data)


# =============================================================================
# Health Data API (Life Tab)
# =============================================================================

def get_health_data_path():
    """Get health analytics data path from config."""
    return os.path.expanduser(
        config.get('integrations', {}).get('health_data', '~/dev/dashboards/healthAnalytics/dashboard/data')
    )


def load_health_json(filename: str) -> dict | None:
    """Load a health analytics JSON file."""
    filepath = Path(get_health_data_path()) / filename
    if not filepath.exists():
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load health data {filename}: {e}")
        return None


@app.route('/api/life/health')
def get_health_data():
    """Get health analytics data for Life tab."""
    health_path = Path(get_health_data_path())
    
    if not health_path.exists():
        return jsonify({
            'status': Status.NOT_CONFIGURED,
            'message': 'Health analytics data not found. Run: cd ~/dev/dashboards/healthAnalytics && ./health generate',
            'path': str(health_path)
        })
    
    # Load all relevant health data files
    summary = load_health_json('summary_stats.json')
    health_score = load_health_json('health_score.json')
    trends = load_health_json('daily_trends.json')
    insights = load_health_json('insights.json')
    goals = load_health_json('goals_progress.json')
    prs = load_health_json('personal_records.json')
    
    # Get metadata for freshness check
    metadata = load_health_json('metadata.json')
    
    if not summary:
        return jsonify({
            'status': Status.ERROR,
            'message': 'Health summary data missing. Run: ./health generate',
            'path': str(health_path)
        })
    
    # Build today's metrics from most recent trend data
    today_metrics = {}
    if trends and trends.get('dates'):
        # Get most recent day's data
        idx = -1  # Last index
        today_metrics = {
            'steps': trends['steps'][idx] if trends.get('steps') else 0,
            'distance_km': trends['distance'][idx] if trends.get('distance') else 0,
            'active_energy': trends['active_energy'][idx] if trends.get('active_energy') else 0,
            'exercise_minutes': trends['exercise_minutes'][idx] if trends.get('exercise_minutes') else 0,
            'stand_hours': trends['stand_hours'][idx] if trends.get('stand_hours') else 0,
            'resting_hr': trends['resting_hr'][idx] if trends.get('resting_hr') else None,
            'hrv': trends['hrv'][idx] if trends.get('hrv') else None,
            'date': trends['dates'][idx] if trends.get('dates') else None
        }
    
    return jsonify({
        'status': Status.OK,
        'source': DataSource.HEALTH_ANALYTICS,
        'today': today_metrics,
        'summary': summary,
        'health_score': health_score,
        'trends': {
            'dates': trends.get('dates', [])[-14:] if trends else [],  # Last 14 days
            'steps': trends.get('steps', [])[-14:] if trends else [],
            'exercise': trends.get('exercise_minutes', [])[-14:] if trends else [],
            'resting_hr': trends.get('resting_hr', [])[-14:] if trends else []
        },
        'insights': insights.get('insights', []) if insights else [],
        'goals': goals,
        'personal_records': prs,
        'metadata': metadata,
        'data_path': str(health_path)
    })


@app.route('/api/life/health/refresh', methods=['POST'])
def refresh_health_data():
    """Trigger health data regeneration."""
    import subprocess
    
    health_root = Path(get_health_data_path()).parent.parent  # Go up from dashboard/data to healthAnalytics
    health_cli = health_root / 'health'
    
    if not health_cli.exists():
        return jsonify({
            'status': Status.ERROR,
            'message': 'Health CLI not found',
            'path': str(health_cli)
        }), 404
    
    try:
        result = subprocess.run(
            [str(health_cli), 'generate'],
            capture_output=True, text=True, timeout=60,
            cwd=str(health_root)
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': Status.OK,
                'message': 'Health data regenerated successfully',
                'output': result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            })
        else:
            return jsonify({
                'status': Status.ERROR,
                'message': 'Health data generation failed',
                'error': result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': Status.ERROR,
            'message': 'Health data generation timed out'
        }), 504
    except Exception as e:
        return jsonify({
            'status': Status.ERROR,
            'message': str(e)
        }), 500


# =============================================================================
# School Email API
# =============================================================================

def get_school_db_path():
    """Get school database path from config."""
    return os.path.expanduser(
        config.get('integrations', {}).get('school_db', '~/clawd/data/school-automation.db')
    )
CHILDREN = ['Elodie', 'Nathaniel', 'Florence']


def get_school_db():
    """Get connection to school automation database."""
    import sqlite3
    if not os.path.exists(get_school_db_path()):
        return None
    conn = sqlite3.connect(get_school_db_path())
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/school/summary')
def get_school_summary():
    """Get school email summary - recent emails and actions by child."""
    conn = get_school_db()
    
    if conn is None:
        return jsonify({
            'status': 'not_configured',
            'message': 'School automation database not found. Run school-email-processor first.',
            'db_path': get_school_db_path()
        })
    
    try:
        cur = conn.cursor()
        
        # Get recent emails (last 7 days)
        cur.execute("""
            SELECT email_id, processed_at, from_address, subject, child, urgency, actions_count
            FROM processed_emails
            WHERE processed_at > datetime('now', '-7 days')
            ORDER BY processed_at DESC
            LIMIT 20
        """)
        recent_emails = [dict(row) for row in cur.fetchall()]
        
        # Get emails by child
        cur.execute("""
            SELECT child, COUNT(*) as count, SUM(actions_count) as actions
            FROM processed_emails
            WHERE processed_at > datetime('now', '-30 days')
            GROUP BY child
        """)
        by_child = {row['child']: {'emails': row['count'], 'actions': row['actions'] or 0} 
                    for row in cur.fetchall()}
        
        # Get urgency breakdown
        cur.execute("""
            SELECT urgency, COUNT(*) as count
            FROM processed_emails
            WHERE processed_at > datetime('now', '-7 days')
            GROUP BY urgency
        """)
        by_urgency = {row['urgency']: row['count'] for row in cur.fetchall()}
        
        # Get pending actions (not yet completed)
        cur.execute("""
            SELECT COUNT(*) as count FROM action_hashes 
            WHERE todoist_task_id IS NULL OR todoist_task_id = ''
        """)
        pending_row = cur.fetchone()
        pending_actions = pending_row['count'] if pending_row else 0
        
        # Get error count
        cur.execute("""
            SELECT COUNT(*) as count FROM error_queue WHERE resolved_at IS NULL
        """)
        error_row = cur.fetchone()
        error_count = error_row['count'] if error_row else 0
        
        conn.close()
        
        # Store snapshot for analytics
        if DB_AVAILABLE and by_child:
            try:
                db.store_school_snapshot(by_child, by_urgency)
            except Exception as e:
                logger.warning(f"Failed to store school snapshot: {e}")
        
        return jsonify({
            'status': 'ok',
            'summary': {
                'recent_email_count': len(recent_emails),
                'pending_actions': pending_actions,
                'errors': error_count,
                'children': CHILDREN
            },
            'by_child': by_child,
            'by_urgency': by_urgency,
            'recent_emails': recent_emails[:10]  # Limit for dashboard
        })
        
    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"School summary error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/school/actions')
def get_school_actions():
    """Get recent school actions (tasks/events created)."""
    conn = get_school_db()
    
    if conn is None:
        return jsonify({'status': 'not_configured'})
    
    try:
        cur = conn.cursor()
        
        # Get recent actions
        cur.execute("""
            SELECT ah.hash, ah.action_data, ah.created_at, ah.todoist_task_id,
                   pe.child, pe.subject as email_subject
            FROM action_hashes ah
            LEFT JOIN processed_emails pe ON ah.source_email_id = pe.email_id
            ORDER BY ah.created_at DESC
            LIMIT 20
        """)
        
        actions = []
        for row in cur.fetchall():
            action = dict(row)
            # Parse JSON action_data
            if action.get('action_data'):
                try:
                    action['action_data'] = json.loads(action['action_data'])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.debug(f"Failed to parse action_data JSON: {e}")
            actions.append(action)
        
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'actions': actions
        })
        
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/inbox/trends')
def get_inbox_trends():
    """Get inbox trends for analytics."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 7, type=int)
    trends = db.get_inbox_trends(days)
    
    return jsonify({
        'status': 'ok',
        'days': days,
        'trends': trends
    })


@app.route('/api/school/trends')
def get_school_trends():
    """Get school email trends for analytics."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 30, type=int)
    trends = db.get_school_trends(days)
    
    return jsonify({
        'status': 'ok',
        'days': days,
        'trends': trends
    })


@app.route('/api/school/process', methods=['POST'])
def trigger_school_process():
    """Trigger school email processing (runs in background)."""
    import subprocess
    
    try:
        # Run the orchestrator in background
        proc = subprocess.Popen(
            ['python', '-m', 'school_automation.orchestrator', 'process', '--days', '3'],
            cwd=os.path.expanduser('~/dev/SchoolEmailAutomation'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return jsonify({
            'status': 'started',
            'message': 'School email processing started in background',
            'pid': proc.pid
        })
        
    except Exception as e:
        logger.error(f"School process trigger error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/school/tab')
def get_school_tab():
    """Get school data structured for the dedicated School tab.

    Returns actions grouped by child with processing status.
    """
    conn = get_school_db()

    if conn is None:
        return jsonify({
            'status': 'not_configured',
            'message': 'School automation database not found',
            'children': [],
            'processing_status': None,
            'totals': {'total': 0, 'high': 0}
        })

    try:
        cur = conn.cursor()

        # Get actions with child and email context (last 7 days)
        cur.execute("""
            SELECT
                ah.hash as id,
                ah.action_data,
                ah.created_at,
                ah.todoist_task_id,
                ah.calendar_event_id,
                pe.child,
                pe.subject as email_subject,
                pe.from_address as email_from,
                pe.urgency
            FROM action_hashes ah
            LEFT JOIN processed_emails pe ON ah.source_email_id = pe.email_id
            WHERE ah.created_at > datetime('now', '-7 days')
            ORDER BY pe.child,
                CASE pe.urgency
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3
                    ELSE 4
                END,
                ah.created_at DESC
        """)

        raw_actions = cur.fetchall()

        # Get processing status
        cur.execute("""
            SELECT
                MAX(processed_at) as last_run,
                COUNT(*) as emails_processed,
                SUM(actions_count) as actions_extracted
            FROM processed_emails
            WHERE processed_at > datetime('now', '-1 day')
        """)
        status_row = cur.fetchone()

        # Get error count
        cur.execute("""
            SELECT COUNT(*) as count FROM error_queue WHERE resolved_at IS NULL
        """)
        error_row = cur.fetchone()

        conn.close()

        # Group actions by child
        children_data = {}
        for child in CHILDREN:
            children_data[child] = {
                'name': child,
                'actions': [],
                'summary': {'total': 0, 'high': 0, 'medium': 0, 'low': 0}
            }

        total_actions = 0
        total_high = 0

        for row in raw_actions:
            action = dict(row)
            child = action.get('child') or 'Unknown'

            # Parse action_data JSON
            action_details = {}
            if action.get('action_data'):
                try:
                    action_details = json.loads(action['action_data'])
                except json.JSONDecodeError:
                    action_details = {}

            urgency = action.get('urgency') or action_details.get('urgency') or 'LOW'

            # Calculate relative deadline
            deadline = action_details.get('deadline')
            deadline_relative = None
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
                    days_until = (deadline_date - date.today()).days
                    if days_until < 0:
                        deadline_relative = f"{abs(days_until)} days ago"
                    elif days_until == 0:
                        deadline_relative = "today"
                    elif days_until == 1:
                        deadline_relative = "tomorrow"
                    else:
                        deadline_relative = f"in {days_until} days"
                except (ValueError, TypeError):
                    pass

            # Calculate relative last run time
            formatted_action = {
                'id': action['id'],
                'description': action_details.get('description', 'Action'),
                'type': action_details.get('type', 'TASK'),
                'urgency': urgency,
                'deadline': deadline,
                'deadline_relative': deadline_relative,
                'source_text': action_details.get('source_text', ''),
                'source_email': {
                    'subject': action.get('email_subject', ''),
                    'from': action.get('email_from', '')
                },
                'todoist_task_id': action.get('todoist_task_id'),
                'calendar_event_id': action.get('calendar_event_id')
            }

            if child in children_data:
                children_data[child]['actions'].append(formatted_action)
                children_data[child]['summary']['total'] += 1
                if urgency == 'HIGH':
                    children_data[child]['summary']['high'] += 1
                    total_high += 1
                elif urgency == 'MEDIUM':
                    children_data[child]['summary']['medium'] += 1
                elif urgency == 'LOW':
                    children_data[child]['summary']['low'] += 1
                total_actions += 1

        # Format processing status
        processing_status = None
        if status_row and status_row['last_run']:
            last_run = status_row['last_run']
            last_run_relative = None
            try:
                last_run_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                delta = datetime.now() - last_run_dt.replace(tzinfo=None)
                hours = int(delta.total_seconds() // 3600)
                if hours < 1:
                    minutes = int(delta.total_seconds() // 60)
                    last_run_relative = f"{minutes} minutes ago"
                elif hours < 24:
                    last_run_relative = f"{hours} hours ago"
                else:
                    days = hours // 24
                    last_run_relative = f"{days} days ago"
            except (ValueError, TypeError):
                pass

            processing_status = {
                'last_run': last_run,
                'last_run_relative': last_run_relative,
                'emails_processed': status_row['emails_processed'] or 0,
                'actions_extracted': status_row['actions_extracted'] or 0,
                'errors': error_row['count'] if error_row else 0
            }

        return jsonify({
            'status': 'ok',
            'children': [children_data[child] for child in CHILDREN],
            'processing_status': processing_status,
            'totals': {
                'total': total_actions,
                'high': total_high
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"School tab error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/planning/session', methods=['POST'])
def manage_planning_session():
    """Start or end a planning session."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    action = data.get('action')

    if action == 'start':
        def get_context():
            return {
                'tasks': fetch_todoist().get('tasks', [])[:20],
                'kanban': fetch_kanban().get('by_column', {})
            }
        result = planning.start_planning_session(get_context)
        if result.get('status') == 'error':
            return jsonify(result), 500
        return jsonify(result)

    elif action == 'end':
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        result = planning.end_planning_session(session_id, data.get('final_state', {}))
        if result.get('error') == 'Session not found':
            return jsonify(result), 404
        if result.get('status') == 'error':
            return jsonify(result), 500
        return jsonify(result)

    else:
        return jsonify({'error': 'Invalid action. Use start or end'}), 400


@app.route('/api/planning/action', methods=['POST'])
def log_planning_action():
    """Log a planning action (task change)."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    required = ['session_id', 'action_type']

    if not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {required}'}), 400

    result = planning.log_action(
        session_id=data['session_id'],
        action_type=data['action_type'],
        target_type=data.get('target_type'),
        target_id=data.get('target_id'),
        target_title=data.get('target_title'),
        details=data.get('details', {})
    )

    if result.get('status') == 'error':
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/planning/message', methods=['POST'])
def log_planning_message():
    """Log a chat message in the planning session."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    required = ['session_id', 'role', 'content']

    if not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {required}'}), 400

    result = planning.log_message(
        session_id=data['session_id'],
        role=data['role'],
        content=data['content'],
        tokens_used=data.get('tokens_used')
    )

    if result.get('status') == 'error':
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/planning/analytics')
def get_planning_analytics():
    """Get planning analytics and trends."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    days = request.args.get('days', 30, type=int)
    return jsonify(planning.get_analytics(days))


# =============================================================================
# Overnight Sprint
# =============================================================================

@app.route('/api/overnight/current')
def get_overnight_current():
    """Get current or most recent overnight sprint."""
    result = overnight_sprint.get_current_sprint()
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/overnight/sprints')
def get_overnight_sprints():
    """Get list of recent sprints. Prefers database, falls back to Obsidian."""
    limit = request.args.get('limit', 20, type=int)
    result = overnight_sprint.get_recent_sprints(limit=limit)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/overnight/sync', methods=['POST'])
def sync_overnight_sprints():
    """Sync all Obsidian sprint logs to database."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    result = overnight_sprint.sync_sprints_from_obsidian()
    if 'error' in result and 'path' in result:
        return jsonify(result), 404
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)


# =============================================================================
# Life Balance API
# =============================================================================

@app.route('/api/life/dashboard')
def get_life_dashboard():
    """Get complete life dashboard data."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        today = date.today()
        
        # Get life areas with totals
        cur.execute("""
            SELECT la.code, la.name, la.icon, la.color, la.daily_xp_cap,
                   COALESCE(lt.total_xp, 0) as total_xp,
                   COALESCE(lt.level, 1) as level,
                   COALESCE(lx.xp_earned, 0) as today_xp
            FROM life_areas la
            LEFT JOIN life_totals lt ON la.code = lt.area_code
            LEFT JOIN life_xp lx ON la.code = lx.area_code AND lx.date = %s
            ORDER BY la.sort_order
        """, (today,))
        areas = [dict(row) for row in cur.fetchall()]
        
        # Get overall totals
        cur.execute("""
            SELECT total_xp, level FROM life_totals WHERE area_code = 'total'
        """)
        total_row = cur.fetchone()
        total_xp = total_row['total_xp'] if total_row else 0
        total_level = total_row['level'] if total_row else 1
        
        # Get today's total XP
        cur.execute("""
            SELECT COALESCE(SUM(xp_earned), 0) as today_total
            FROM life_xp WHERE date = %s
        """, (today,))
        today_total = cur.fetchone()['today_total']
        
        # Get streaks
        cur.execute("""
            SELECT activity, area_code, current_streak, longest_streak, last_activity_date
            FROM streaks ORDER BY current_streak DESC
        """)
        streaks = [dict(row) for row in cur.fetchall()]
        
        # Get recent achievements
        cur.execute("""
            SELECT a.code, a.name, a.description, a.icon, a.xp_reward, a.rarity,
                   ua.earned_at
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_code = a.code
            ORDER BY ua.earned_at DESC
            LIMIT 5
        """)
        achievements = [dict(row) for row in cur.fetchall()]
        
        # Get weekly XP by area for radar chart
        cur.execute("""
            SELECT area_code, SUM(xp_earned) as weekly_xp
            FROM life_xp
            WHERE date >= %s - INTERVAL '7 days'
            GROUP BY area_code
        """, (today,))
        weekly_xp = {row['area_code']: row['weekly_xp'] for row in cur.fetchall()}
        
        # Get daily XP for heatmap (last 12 weeks)
        cur.execute("""
            SELECT date, SUM(xp_earned) as daily_xp
            FROM life_xp
            WHERE date >= %s - INTERVAL '84 days'
            GROUP BY date
            ORDER BY date
        """, (today,))
        heatmap_data = [{'date': str(row['date']), 'xp': row['daily_xp']} for row in cur.fetchall()]
        
        # Calculate level progress
        def xp_for_level(level):
            if level <= 5: return level * 100
            if level <= 10: return 500 + (level - 5) * 300
            if level <= 20: return 2000 + (level - 10) * 800
            if level <= 50: return 10000 + (level - 20) * 1500
            return 50000 + (level - 50) * 3000
        
        current_level_xp = xp_for_level(total_level)
        next_level_xp = xp_for_level(total_level + 1)
        xp_in_level = total_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        level_progress = (xp_in_level / xp_needed * 100) if xp_needed > 0 else 0
        
        # Level titles
        level_titles = {
            1: 'Novice', 5: 'Apprentice', 10: 'Journeyman',
            20: 'Expert', 50: 'Master', 100: 'Legend'
        }
        title = 'Legend'
        for lvl, t in sorted(level_titles.items()):
            if total_level < lvl:
                title = level_titles.get(lvl - 1, 'Novice') if lvl > 1 else 'Novice'
                break
            title = t
        
        return jsonify({
            'total_xp': total_xp,
            'level': total_level,
            'level_title': title,
            'level_progress': round(level_progress, 1),
            'xp_to_next': next_level_xp - total_xp,
            'today_xp': today_total,
            'areas': areas,
            'weekly_xp': weekly_xp,
            'streaks': streaks,
            'achievements': achievements,
            'heatmap': heatmap_data
        })

    except Exception as e:
        logger.error(f"Life dashboard error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/life/xp', methods=['POST'])
def add_life_xp():
    """Add XP for an activity."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    area_code = data.get('area')
    xp = data.get('xp', 0)
    activity = data.get('activity', 'manual')

    if not area_code or xp <= 0:
        return jsonify({'error': 'area and positive xp required'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        today = date.today()

        # Check daily cap
        cur.execute("""
            SELECT daily_xp_cap FROM life_areas WHERE code = %s
        """, (area_code,))
        cap_row = cur.fetchone()
        if not cap_row:
            return jsonify({'error': 'Invalid area code'}), 400
        daily_cap = cap_row[0]

        # Get current daily XP with row lock to prevent race conditions
        # This ensures concurrent requests can't both read the same value
        cur.execute("""
            SELECT xp_earned FROM life_xp
            WHERE area_code = %s AND date = %s
            FOR UPDATE
        """, (area_code, today))
        current_row = cur.fetchone()
        current_xp = current_row[0] if current_row else 0

        # Cap the XP
        actual_xp = min(xp, daily_cap - current_xp)
        if actual_xp <= 0:
            conn.rollback()  # Release the lock
            return jsonify({'message': 'Daily cap reached', 'xp_added': 0})

        # Upsert daily XP
        cur.execute("""
            INSERT INTO life_xp (area_code, date, xp_earned, activities)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (area_code, date) DO UPDATE SET
                xp_earned = life_xp.xp_earned + %s,
                activities = life_xp.activities || %s::jsonb,
                updated_at = NOW()
            RETURNING xp_earned
        """, (
            area_code, today, actual_xp,
            json.dumps([{'activity': activity, 'xp': actual_xp}]),
            actual_xp,
            json.dumps([{'activity': activity, 'xp': actual_xp}])
        ))
        new_total = cur.fetchone()[0]
        
        # Update area totals
        cur.execute("""
            UPDATE life_totals SET
                total_xp = total_xp + %s,
                level = CASE
                    WHEN total_xp + %s < 500 THEN GREATEST(1, (total_xp + %s) / 100)
                    WHEN total_xp + %s < 2000 THEN 5 + (total_xp + %s - 500) / 300
                    WHEN total_xp + %s < 10000 THEN 10 + (total_xp + %s - 2000) / 800
                    ELSE 20 + (total_xp + %s - 10000) / 1500
                END,
                updated_at = NOW()
            WHERE area_code = %s
        """, (actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, area_code))
        
        # Update overall totals
        cur.execute("""
            UPDATE life_totals SET
                total_xp = total_xp + %s,
                level = CASE
                    WHEN total_xp + %s < 500 THEN GREATEST(1, (total_xp + %s) / 100)
                    WHEN total_xp + %s < 2000 THEN 5 + (total_xp + %s - 500) / 300
                    WHEN total_xp + %s < 10000 THEN 10 + (total_xp + %s - 2000) / 800
                    ELSE 20 + (total_xp + %s - 10000) / 1500
                END,
                updated_at = NOW()
            WHERE area_code = 'total'
        """, (actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp, actual_xp))
        
        conn.commit()

        # Check for new achievements
        new_achievements = check_achievements()

        return jsonify({
            'status': Status.OK,
            'xp_added': actual_xp,
            'daily_total': new_total,
            'capped': actual_xp < xp,
            'achievements': [{'code': a['code'], 'name': a['name'], 'xp': a['xp_reward']} for a in new_achievements]
        })

    except Exception as e:
        logger.error(f"Add XP error: {e}")
        if conn:
            conn.rollback()  # Ensure partial changes are rolled back
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/life/achievements')
def get_all_achievements():
    """Get all achievements with earned status."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT a.code, a.name, a.description, a.icon, a.xp_reward, a.area_code, a.rarity,
                   ua.earned_at IS NOT NULL as earned,
                   ua.earned_at
            FROM achievements a
            LEFT JOIN user_achievements ua ON a.code = ua.achievement_code
            ORDER BY a.rarity DESC, a.xp_reward DESC
        """)
        achievements = [dict(row) for row in cur.fetchall()]

        return jsonify({'achievements': achievements})

    except Exception as e:
        logger.error(f"Achievements error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/life/log', methods=['POST'])
def log_manual_activity():
    """Quick log for manual activities (workout, meal, meditation, etc.)"""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    activity_type = data.get('type')
    duration = data.get('duration', 0)  # minutes
    notes = data.get('notes', '')

    if not activity_type:
        return jsonify({'error': 'Activity type is required'}), 400

    # Get activity type from database
    activity_info = db.get_activity_type(activity_type)
    if not activity_info:
        return jsonify({'error': f'Unknown activity type: {activity_type}'}), 400

    if not activity_info.get('active', True):
        return jsonify({'error': f'Activity type {activity_type} is not active'}), 400

    area_code = activity_info['area_code']
    base_xp = activity_info['base_xp']

    # Bonus XP for duration (if activity supports it)
    if duration > 0 and activity_info.get('duration_bonus', False):
        # Get duration bonus config from database, fallback to defaults
        bonus_per_10min = db.get_game_config('DURATION_BONUS_PER_10MIN') or Defaults.DURATION_BONUS_PER_10MIN
        bonus_max = db.get_game_config('DURATION_BONUS_MAX') or Defaults.DURATION_BONUS_MAX
        duration_bonus = min(duration // 10 * bonus_per_10min, bonus_max)
        base_xp += duration_bonus

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        today = date.today()

        # Get daily cap
        cur.execute("SELECT daily_xp_cap FROM life_areas WHERE code = %s", (area_code,))
        cap_row = cur.fetchone()
        daily_cap = cap_row[0] if cap_row else 200

        # Get current daily XP with row lock to prevent race conditions
        cur.execute("""
            SELECT xp_earned FROM life_xp
            WHERE area_code = %s AND date = %s
            FOR UPDATE
        """, (area_code, today))
        current_row = cur.fetchone()
        current_xp = current_row[0] if current_row else 0

        # Cap the XP
        actual_xp = min(base_xp, daily_cap - current_xp)
        if actual_xp <= 0:
            conn.rollback()  # Release the lock
            return jsonify({'message': 'Daily cap reached', 'xp_added': 0})

        # Add XP
        activity_data = json.dumps([{
            'activity': activity_type,
            'xp': actual_xp,
            'duration': duration,
            'notes': notes
        }])
        
        cur.execute("""
            INSERT INTO life_xp (area_code, date, xp_earned, activities)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (area_code, date) DO UPDATE SET
                xp_earned = life_xp.xp_earned + %s,
                activities = life_xp.activities || %s::jsonb,
                updated_at = NOW()
            RETURNING xp_earned
        """, (area_code, today, actual_xp, activity_data, actual_xp, activity_data))
        
        new_total = cur.fetchone()[0]
        
        # Update totals
        cur.execute("""
            UPDATE life_totals SET total_xp = total_xp + %s, updated_at = NOW()
            WHERE area_code = %s OR area_code = 'total'
        """, (actual_xp, area_code))
        
        # Update streak
        streak_map = {
            'workout': 'workout',
            'meditation': 'meditation',
            'reading': 'reading',
            'meal': 'meal_logging'
        }
        
        if activity_type in streak_map:
            streak_activity = streak_map[activity_type]
            cur.execute("""
                UPDATE streaks SET
                    current_streak = CASE
                        WHEN last_activity_date = %s - INTERVAL '1 day' THEN current_streak + 1
                        WHEN last_activity_date = %s THEN current_streak
                        ELSE 1
                    END,
                    longest_streak = GREATEST(longest_streak, 
                        CASE
                            WHEN last_activity_date = %s - INTERVAL '1 day' THEN current_streak + 1
                            ELSE 1
                        END),
                    last_activity_date = %s,
                    updated_at = NOW()
                WHERE activity = %s
            """, (today, today, today, today, streak_activity))
        
        conn.commit()

        # Check for new achievements
        new_achievements = check_achievements()

        return jsonify({
            'status': Status.OK,
            'activity': activity_type,
            'area': area_code,
            'xp_added': actual_xp,
            'daily_total': new_total,
            'message': f'+{actual_xp} XP for {activity_type}!',
            'achievements': [{'code': a['code'], 'name': a['name'], 'xp': a['xp_reward']} for a in new_achievements]
        })

    except Exception as e:
        logger.error(f"Log activity error: {e}")
        if conn:
            conn.rollback()  # Ensure partial changes are rolled back
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


def check_achievements(user_data=None):
    """Check and award any earned achievements.

    Called after XP updates to check if any achievements are now unlocked.
    Returns list of newly earned achievements.
    """
    if not DB_AVAILABLE:
        return []

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        today = date.today()
        newly_earned = []

        # Get unearned achievements
        cur.execute("""
            SELECT a.code, a.name, a.description, a.icon, a.xp_reward, a.area_code, a.criteria, a.rarity
            FROM achievements a
            WHERE NOT EXISTS (
                SELECT 1 FROM user_achievements ua WHERE ua.achievement_code = a.code
            )
        """)
        unearned = [dict(row) for row in cur.fetchall()]
        
        # Get current stats for checking
        cur.execute("SELECT area_code, total_xp, level FROM life_totals")
        totals = {row['area_code']: row for row in cur.fetchall()}
        
        cur.execute("SELECT activity, current_streak, longest_streak FROM streaks")
        streaks = {row['activity']: row for row in cur.fetchall()}
        
        cur.execute("SELECT area_code, SUM(xp_earned) as total FROM life_xp WHERE date = %s GROUP BY area_code", (today,))
        today_xp = {row['area_code']: row['total'] for row in cur.fetchall()}
        
        # Check each achievement
        for ach in unearned:
            criteria = ach.get('criteria') or {}
            earned = False
            
            # Level-based achievements
            if 'min_level' in criteria:
                area = criteria.get('area', 'total')
                if area in totals and totals[area]['level'] >= criteria['min_level']:
                    earned = True
            
            # XP-based achievements
            if 'min_xp' in criteria:
                area = criteria.get('area', 'total')
                if area in totals and totals[area]['total_xp'] >= criteria['min_xp']:
                    earned = True
            
            # Streak-based achievements
            if 'streak' in criteria:
                activity = criteria['streak']
                min_streak = criteria.get('min_streak', 1)
                if activity in streaks and streaks[activity]['current_streak'] >= min_streak:
                    earned = True
            
            # Daily XP achievements
            if 'daily_xp' in criteria:
                area = criteria.get('area')
                min_xp = criteria['daily_xp']
                if area:
                    if area in today_xp and today_xp[area] >= min_xp:
                        earned = True
                else:
                    total_today = sum(today_xp.values())
                    if total_today >= min_xp:
                        earned = True
            
            # First time achievements (just by having any XP in area)
            if 'first_xp' in criteria:
                area = criteria['first_xp']
                if area in totals and totals[area]['total_xp'] > 0:
                    earned = True
            
            # Award if earned
            if earned:
                cur.execute("""
                    INSERT INTO user_achievements (achievement_code, earned_at)
                    VALUES (%s, NOW())
                    ON CONFLICT DO NOTHING
                    RETURNING achievement_code
                """, (ach['code'],))
                
                if cur.fetchone():
                    newly_earned.append(ach)
                    logger.info(f"Achievement unlocked: {ach['name']}")
        
        conn.commit()

        return newly_earned

    except Exception as e:
        logger.error(f"Achievement check error: {e}")
        if conn:
            conn.rollback()  # Ensure partial changes are rolled back
        return []
    finally:
        if conn:
            conn.close()


@app.route('/api/life/check-achievements', methods=['POST'])
def trigger_achievement_check():
    """Manually trigger achievement check."""
    earned = check_achievements()
    return jsonify({
        'checked': True,
        'newly_earned': [{'code': a['code'], 'name': a['name'], 'xp': a['xp_reward']} for a in earned]
    })


@app.route('/api/life/goals')
def get_life_goals():
    """Get life goals with current progress."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        today = date.today()

        cur.execute("""
            SELECT g.area_code, g.metric, g.target_value, g.period,
                   la.name as area_name, la.color
            FROM life_goals g
            JOIN life_areas la ON g.area_code = la.code
            WHERE g.active = TRUE
            ORDER BY la.sort_order, g.metric
        """)
        goals = [dict(row) for row in cur.fetchall()]

        # Get today's metrics for progress
        cur.execute("""
            SELECT * FROM daily_metrics WHERE date = %s
        """, (today,))
        today_metrics = cur.fetchone()

        return jsonify({
            'goals': goals,
            'today_metrics': dict(today_metrics) if today_metrics else {}
        })

    except Exception as e:
        logger.error(f"Goals error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# =============================================================================
# Health Analytics Integration (Legacy endpoints for gamification)
# =============================================================================

@app.route('/api/integrations/health')
def get_health_integration_data():
    """Get health data from the Health Analytics app (legacy endpoint for gamification)."""
    try:
        data = {}
        health_path = get_health_data_path()
        
        # Health score
        score_path = os.path.join(health_path, 'health_score.json')
        if os.path.exists(score_path):
            with open(score_path) as f:
                data['health_score'] = json.load(f)
        
        # Goals progress
        goals_path = os.path.join(health_path, 'goals_progress.json')
        if os.path.exists(goals_path):
            with open(goals_path) as f:
                data['goals'] = json.load(f)
        
        # Summary stats
        stats_path = os.path.join(health_path, 'summary_stats.json')
        if os.path.exists(stats_path):
            with open(stats_path) as f:
                data['stats'] = json.load(f)
        
        # Daily trends
        trends_path = os.path.join(health_path, 'daily_trends.json')
        if os.path.exists(trends_path):
            with open(trends_path) as f:
                data['trends'] = json.load(f)
        
        # Insights
        insights_path = os.path.join(health_path, 'insights.json')
        if os.path.exists(insights_path):
            with open(insights_path) as f:
                data['insights'] = json.load(f)
        
        return jsonify({
            'status': Status.OK,
            'source': DataSource.HEALTH_ANALYTICS,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Health integration error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/life/health/award-xp', methods=['POST'])
def award_health_xp():
    """Award XP based on health goals achieved."""
    import os
    from datetime import date
    
    try:
        # Load health data - use goals_progress for daily goal tracking
        goals_path = os.path.join(get_health_data_path(), 'goals_progress.json')
        stats_path = os.path.join(get_health_data_path(), 'summary_stats.json')
        
        if not os.path.exists(goals_path):
            return jsonify({'error': 'Health data not available'}), 404
        
        with open(goals_path) as f:
            goals = json.load(f)
        
        # Get most recent day's goals (last index)
        steps_met = goals.get('steps_goal', [0])[-1] == 1
        exercise_met = goals.get('exercise_goal', [0])[-1] == 1
        stand_met = goals.get('stand_goal', [0])[-1] == 1
        
        xp_awarded = 0
        goal_details = []
        
        # Award XP for goals met
        if steps_met:
            xp_awarded += 25
            goal_details.append('steps_10k')
        if exercise_met:
            xp_awarded += 30
            goal_details.append('exercise_30m')
        if stand_met:
            xp_awarded += 15
            goal_details.append('stand_12h')
        
        achievements = []
        conn = None

        if xp_awarded > 0:
            # Add to Health area
            if DB_AVAILABLE:
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    today = date.today()

                    cur.execute("""
                        INSERT INTO life_xp (area_code, date, xp_earned, activities)
                        VALUES ('health', %s, %s, %s::jsonb)
                        ON CONFLICT (area_code, date) DO UPDATE SET
                            xp_earned = life_xp.xp_earned + %s,
                            activities = life_xp.activities || %s::jsonb
                        RETURNING xp_earned
                    """, (
                        today, xp_awarded,
                        json.dumps([{'activity': 'health_goals', 'xp': xp_awarded}]),
                        xp_awarded,
                        json.dumps([{'activity': 'health_goals', 'xp': xp_awarded}])
                    ))

                    # Update totals
                    cur.execute("""
                        UPDATE life_totals SET total_xp = total_xp + %s WHERE area_code IN ('health', 'total')
                    """, (xp_awarded,))

                    conn.commit()

                    # Check achievements
                    achievements = check_achievements()
                finally:
                    if conn:
                        conn.close()

        return jsonify({
            'status': Status.OK,
            'xp_awarded': xp_awarded,
            'goals_met': goal_details,
            'steps_met': steps_met,
            'exercise_met': exercise_met,
            'stand_met': stand_met,
            'achievements': [{'code': a['code'], 'name': a['name']} for a in achievements]
        })

    except Exception as e:
        logger.error(f"Health XP award error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Monzo Integration (Stubs)
# =============================================================================

def get_monzo_api_base():
    """Get Monzo API base URL from config."""
    return config.get('integrations', {}).get('monzo_api', 'http://localhost/api/v1')

@app.route('/api/integrations/monzo')
def get_monzo_data():
    """Get finance data from the Monzo Analysis app."""
    import requests

    try:
        # Try to get summary from Monzo API
        resp = requests.get(f'{get_monzo_api_base()}/dashboard/summary', timeout=Defaults.API_TIMEOUT_SHORT)
        if resp.status_code == 200:
            return jsonify({
                'status': Status.OK,
                'source': DataSource.MONZO_ANALYSIS,
                'data': resp.json()
            })
        else:
            return jsonify({
                'status': Status.UNAVAILABLE,
                'message': 'Monzo service not responding',
                'code': resp.status_code
            }), 503

    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': Status.OFFLINE,
            'message': 'Monzo service not running. Start with: cd ~/clawd/projects/monzo-analysis && docker compose up -d'
        }), 503
    except Exception as e:
        logger.error(f"Monzo integration error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/integrations/monzo/award-xp', methods=['POST'])
def award_monzo_xp():
    """Award XP based on finance goals (budget adherence)."""
    import requests
    
    try:
        # Get budget status from Monzo
        resp = requests.get(f'{get_monzo_api_base()}/budgets/status', timeout=Defaults.API_TIMEOUT_SHORT)
        if resp.status_code != 200:
            return jsonify({'status': Status.UNAVAILABLE}), 503
        
        budget_data = resp.json()
        xp_awarded = 0
        
        # Award XP for staying under budget
        under_budget_count = sum(1 for b in budget_data.get('budgets', []) if b.get('status') == 'under')
        xp_awarded = under_budget_count * Defaults.BUDGET_UNDER_XP
        
        conn = None
        if xp_awarded > 0 and DB_AVAILABLE:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                today = date.today()

                cur.execute("""
                    INSERT INTO life_xp (area_code, date, xp_earned, activities)
                    VALUES ('finance', %s, %s, %s::jsonb)
                    ON CONFLICT (area_code, date) DO UPDATE SET
                        xp_earned = life_xp.xp_earned + %s,
                        activities = life_xp.activities || %s::jsonb
                """, (
                    today, xp_awarded,
                    json.dumps([{'activity': 'budget_control', 'xp': xp_awarded}]),
                    xp_awarded,
                    json.dumps([{'activity': 'budget_control', 'xp': xp_awarded}])
                ))

                cur.execute("""
                    UPDATE life_totals SET total_xp = total_xp + %s WHERE area_code IN ('finance', 'total')
                """, (xp_awarded,))

                conn.commit()
            finally:
                if conn:
                    conn.close()

        return jsonify({
            'status': Status.OK,
            'xp_awarded': xp_awarded,
            'budgets_under': under_budget_count
        })

    except requests.exceptions.ConnectionError:
        return jsonify({'status': Status.OFFLINE, 'message': 'Monzo service not running'}), 503
    except Exception as e:
        logger.error(f"Monzo XP award error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/integrations/monzo/trends')
def get_monzo_trends():
    """Get spending trend data from Monzo Analysis app."""
    import requests as req
    
    days = request.args.get('days', 30, type=int)
    
    try:
        # Note: The Monzo API requires account_id - this will need to be configured
        resp = req.get(
            f'{get_monzo_api_base()}/dashboard/trends',
            params={'days': days},
            timeout=Defaults.API_TIMEOUT_SHORT
        )
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({'status': Status.UNAVAILABLE}), 503
    except req.exceptions.ConnectionError:
        return jsonify({'status': Status.OFFLINE}), 503
    except Exception as e:
        logger.error(f"Monzo trends error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/integrations/monzo/recurring')
def get_monzo_recurring():
    """Get recurring/subscription data from Monzo Analysis app."""
    import requests as req
    
    try:
        resp = req.get(
            f'{get_monzo_api_base()}/dashboard/recurring',
            timeout=Defaults.API_TIMEOUT_SHORT
        )
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({'status': Status.UNAVAILABLE}), 503
    except req.exceptions.ConnectionError:
        return jsonify({'status': Status.OFFLINE}), 503
    except Exception as e:
        logger.error(f"Monzo recurring error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Days Since API
# =============================================================================

@app.route('/api/days-since')
def get_days_since():
    """Get all days-since events with calculated days."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()
        today = date.today()

        cur.execute("""
            SELECT code, name, icon, category, warning_days, alert_days,
                   last_occurred, notes, sort_order
            FROM days_since_events
            ORDER BY sort_order, name
        """)

        events = []
        for row in cur.fetchall():
            event = dict(row)
            if event['last_occurred']:
                days = (today - event['last_occurred']).days
                event['days'] = days
                if days >= event['alert_days']:
                    event['status'] = 'alert'
                elif days >= event['warning_days']:
                    event['status'] = 'warning'
                else:
                    event['status'] = 'ok'
            else:
                event['days'] = None
                event['status'] = 'never'
            events.append(event)

        return jsonify({'events': events})

    except Exception as e:
        logger.error(f"Days since error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/days-since/<code>/log', methods=['POST'])
def log_days_since(code):
    """Log an occurrence of a days-since event."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    occurred_date = data.get('date')  # Optional, defaults to today
    notes = data.get('notes', '')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if occurred_date:
            occurred = datetime.strptime(occurred_date, '%Y-%m-%d').date()
        else:
            occurred = date.today()

        # Update last_occurred
        cur.execute("""
            UPDATE days_since_events
            SET last_occurred = %s, updated_at = NOW()
            WHERE code = %s
            RETURNING name
        """, (occurred, code))

        result = cur.fetchone()
        if not result:
            return jsonify({'error': f'Event not found: {code}'}), 404

        event_name = result[0]

        # Add to history
        cur.execute("""
            INSERT INTO days_since_history (event_code, occurred_at, notes)
            VALUES (%s, %s, %s)
        """, (code, occurred, notes))

        conn.commit()

        return jsonify({
            'status': Status.OK,
            'message': f'Logged {event_name}',
            'date': str(occurred)
        })

    except Exception as e:
        logger.error(f"Log days since error: {e}")
        if conn:
            conn.rollback()  # Ensure partial changes are rolled back
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/days-since/<code>/history')
def get_days_since_history(code):
    """Get history for a specific days-since event."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    conn = None
    try:
        conn = get_dict_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT occurred_at, notes, created_at
            FROM days_since_history
            WHERE event_code = %s
            ORDER BY occurred_at DESC
            LIMIT 20
        """, (code,))

        history = [dict(row) for row in cur.fetchall()]

        return jsonify({'history': history})

    except Exception as e:
        logger.error(f"Days since history error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# =============================================================================
# Configuration API (Database-Driven Settings)
# =============================================================================

@app.route('/api/config/activity-types')
def get_activity_types():
    """Get all activity types for XP logging."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    include_inactive = request.args.get('all', 'false').lower() == 'true'
    activities = db.get_activity_types(active_only=not include_inactive)

    return jsonify({
        'activity_types': activities,
        'count': len(activities)
    })


@app.route('/api/config/activity-types/<code>', methods=['GET', 'PUT', 'DELETE'])
def activity_type_crud(code):
    """CRUD operations for a single activity type."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    if request.method == 'GET':
        activity = db.get_activity_type(code)
        if not activity:
            return jsonify({'error': f'Activity type not found: {code}'}), 404
        return jsonify(activity)

    elif request.method == 'PUT':
        data = request.get_json() or {}
        data['code'] = code
        # Set defaults for required fields
        data.setdefault('name', code.replace('_', ' ').title())
        data.setdefault('area_code', 'work')
        data.setdefault('base_xp', 10)
        data.setdefault('duration_bonus', False)
        data.setdefault('active', True)
        data.setdefault('sort_order', 99)

        if db.upsert_activity_type(data):
            return jsonify({'status': Status.OK, 'activity_type': data})
        return jsonify({'error': 'Failed to save activity type'}), 500

    elif request.method == 'DELETE':
        if db.delete_activity_type(code):
            return jsonify({'status': Status.OK, 'deleted': code})
        return jsonify({'error': f'Activity type not found: {code}'}), 404


@app.route('/api/config/game')
def get_game_config_all():
    """Get all game configuration values."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    config_values = db.get_game_config()
    return jsonify({
        'config': config_values,
        'count': len(config_values)
    })


@app.route('/api/config/game/<key>', methods=['GET', 'PUT'])
def game_config_crud(key):
    """Get or set a game configuration value."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    if request.method == 'GET':
        value = db.get_game_config(key)
        if value is None:
            return jsonify({'error': f'Config key not found: {key}'}), 404
        return jsonify({'key': key, 'value': value})

    elif request.method == 'PUT':
        data = request.get_json() or {}
        value = data.get('value')
        if value is None:
            return jsonify({'error': 'Value is required'}), 400

        data_type = data.get('data_type', 'string')
        description = data.get('description')
        category = data.get('category', 'general')

        if db.set_game_config(key, value, data_type, description, category):
            return jsonify({'status': Status.OK, 'key': key, 'value': value})
        return jsonify({'error': 'Failed to save config'}), 500


@app.route('/api/config/kanban-columns')
def get_kanban_columns():
    """Get all kanban column definitions."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    include_inactive = request.args.get('all', 'false').lower() == 'true'
    columns = db.get_kanban_columns(active_only=not include_inactive)

    return jsonify({
        'columns': columns,
        'count': len(columns)
    })


@app.route('/api/config/kanban-columns/<code>', methods=['PUT'])
def update_kanban_column(code):
    """Update a kanban column."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    data['code'] = code
    data.setdefault('title', code.replace('-', ' ').title())
    data.setdefault('active', True)
    data.setdefault('sort_order', 99)

    if db.upsert_kanban_column(data):
        return jsonify({'status': Status.OK, 'column': data})
    return jsonify({'error': 'Failed to save column'}), 500


@app.route('/api/config/xp-rules')
def get_xp_rules():
    """Get all XP calculation rules."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    source = request.args.get('source')
    include_inactive = request.args.get('all', 'false').lower() == 'true'
    rules = db.get_xp_rules(source=source, active_only=not include_inactive)

    return jsonify({
        'rules': rules,
        'count': len(rules)
    })


@app.route('/api/config/xp-rules/<code>', methods=['GET', 'PUT'])
def xp_rule_crud(code):
    """CRUD operations for XP rules."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    if request.method == 'GET':
        rules = db.get_xp_rules()
        rule = next((r for r in rules if r['code'] == code), None)
        if not rule:
            return jsonify({'error': f'XP rule not found: {code}'}), 404
        return jsonify(rule)

    elif request.method == 'PUT':
        data = request.get_json() or {}
        data['code'] = code
        data.setdefault('name', code.replace('_', ' ').title())
        data.setdefault('source', 'manual')
        data.setdefault('area_code', 'work')
        data.setdefault('rule_type', 'count')
        data.setdefault('xp_per_unit', 1)
        data.setdefault('active', True)

        if db.upsert_xp_rule(data):
            return jsonify({'status': Status.OK, 'rule': data})
        return jsonify({'error': 'Failed to save XP rule'}), 500


@app.route('/api/config/priority-levels')
def get_priority_levels():
    """Get all priority level definitions."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    levels = db.get_priority_levels()
    return jsonify({
        'levels': levels,
        'count': len(levels)
    })


@app.route('/api/life/calculate-dashboard-xp', methods=['POST'])
def calculate_dashboard_xp():
    """Calculate XP from dashboard activity using database rules."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}
    dashboard_data = data.get('dashboard', {})

    # Get all active XP rules
    rules = db.get_xp_rules(active_only=True)

    xp_awards = []
    total_xp = 0

    for rule in rules:
        source = rule['source']
        rule_type = rule['rule_type']
        condition = rule.get('condition', {})
        xp_per_unit = rule['xp_per_unit']
        max_xp = rule.get('max_xp')

        source_data = dashboard_data.get(source, {})
        calculated_xp = 0

        if rule_type == 'count':
            field = condition.get('field', '')
            count = source_data.get(field, 0)
            if isinstance(count, list):
                count = len(count)
            calculated_xp = count * xp_per_unit

        elif rule_type == 'boolean':
            field = condition.get('field', '')
            expected = condition.get('value')
            if source_data.get(field) == expected:
                calculated_xp = xp_per_unit

        elif rule_type == 'threshold':
            field = condition.get('field', '')
            threshold = condition.get('threshold', 0)
            if source_data.get(field, 0) >= threshold:
                calculated_xp = xp_per_unit

        # Apply max cap
        if max_xp and calculated_xp > max_xp:
            calculated_xp = max_xp

        if calculated_xp > 0:
            xp_awards.append({
                'rule': rule['code'],
                'area': rule['area_code'],
                'xp': calculated_xp,
                'source': source
            })
            total_xp += calculated_xp

    return jsonify({
        'status': Status.OK,
        'awards': xp_awards,
        'total_xp': total_xp
    })


# =============================================================================
# Email Automation API
# =============================================================================

# Lazy-loaded email automation components
_email_scheduler = None
_notification_router = None


def get_notification_router():
    """Get or create notification router."""
    global _notification_router
    if _notification_router is None:
        try:
            from email_automation.notifications import NotificationRouter
            notifications_config = config.get('notifications', {})
            _notification_router = NotificationRouter(
                notifications_config,
                db_callback=db.log_notification if DB_AVAILABLE else None
            )
        except ImportError as e:
            logger.warning(f"Email automation not available: {e}")
            return None
    return _notification_router


def get_email_scheduler():
    """Get or create email scheduler."""
    global _email_scheduler
    if _email_scheduler is None:
        try:
            from email_automation.scheduling import EmailScheduler, JobRegistry
            from email_automation.scheduling.jobs import JobDefinition
            from email_automation.inbox import InboxFetcher, InboxDigest
            from email_automation.school import SchoolAdapter
            from email_automation.notifications import Priority

            scheduling_config = config.get('scheduling', {})
            registry = JobRegistry()

            # Setup database callbacks for job tracking
            if DB_AVAILABLE:
                registry.set_db_callbacks(db.start_job_run, db.complete_job_run)

            router = get_notification_router()

            # Register inbox digest job
            def run_inbox_digest():
                email_config = config.get('email', {})
                fetcher = InboxFetcher(email_config)
                digest = InboxDigest(fetcher)
                title, body = digest.format_for_notification()
                if router:
                    router.send_digest(title, body, source='inbox')
                stats = digest.get_summary_stats()
                return {'success': True, **stats}

            registry.register(JobDefinition(
                job_id='inbox_digest',
                name='Inbox Digest',
                description='Generate and send inbox digest notification',
                func=run_inbox_digest
            ))

            # Register school email job
            def run_school_email():
                def notify(title, body, priority):
                    if router:
                        p = Priority.URGENT if priority == 'urgent' else Priority.INFO
                        router.send(title, body, p, source='school')
                adapter = SchoolAdapter(notify_callback=notify)
                if not adapter.is_available():
                    return {'success': False, 'error': 'SchoolAutomation not available'}
                return adapter.process_emails(days=1)

            registry.register(JobDefinition(
                job_id='school_email',
                name='School Email',
                description='Process school emails and create tasks/events',
                func=run_school_email
            ))

            # Register daily combined digest job
            def run_daily_combined():
                email_config = config.get('email', {})
                fetcher = InboxFetcher(email_config)
                inbox_digest = InboxDigest(fetcher)
                inbox_stats = inbox_digest.get_summary_stats()

                adapter = SchoolAdapter()
                school_status = adapter.get_status() if adapter.is_available() else None

                title = 'Daily Email Summary'
                lines = [
                    f"*Inbox*: {inbox_stats['total_unread']} unread, {inbox_stats['total_urgent']} urgent",
                ]
                if school_status and school_status.get('available'):
                    lines.append(f"*School*: {school_status.get('unresolved_errors', 0)} unresolved errors")
                body = '\n'.join(lines)

                if router:
                    router.send_digest(title, body, source='combined')
                return {'success': True, 'inbox': inbox_stats, 'school': school_status}

            registry.register(JobDefinition(
                job_id='daily_combined',
                name='Daily Combined Digest',
                description='Generate combined daily email digest',
                func=run_daily_combined
            ))

            _email_scheduler = EmailScheduler(scheduling_config, registry)

        except ImportError as e:
            logger.warning(f"Email scheduler not available: {e}")
            return None

    return _email_scheduler


@app.route('/api/email/process/school', methods=['POST'])
def process_school_email():
    """Trigger school email processing."""
    try:
        from email_automation.school import SchoolAdapter
        from email_automation.notifications import Priority

        router = get_notification_router()

        def notify(title, body, priority):
            if router:
                p = Priority.URGENT if priority == 'urgent' else Priority.INFO
                router.send(title, body, p, source='school')

        adapter = SchoolAdapter(notify_callback=notify)

        if not adapter.is_available():
            return jsonify({
                'status': Status.ERROR,
                'error': 'SchoolEmailAutomation not available'
            }), 503

        days = request.json.get('days', 1) if request.is_json else 1
        dry_run = request.json.get('dry_run', False) if request.is_json else False

        # Track job run
        run_id = None
        if DB_AVAILABLE:
            run_id = db.start_job_run('school_email', 'http')

        results = adapter.process_emails(days=days, dry_run=dry_run)

        if run_id and DB_AVAILABLE:
            status = 'success' if results.get('success') else 'failed'
            db.complete_job_run(run_id, status, results, results.get('error'))

        return jsonify({
            'status': Status.OK if results.get('success') else Status.ERROR,
            **results
        })

    except ImportError:
        return jsonify({
            'status': Status.ERROR,
            'error': 'email_automation module not available'
        }), 503
    except Exception as e:
        logger.error(f"School email processing failed: {e}")
        return jsonify({'status': Status.ERROR, 'error': str(e)}), 500


@app.route('/api/email/digest/inbox', methods=['POST'])
def trigger_inbox_digest():
    """Trigger inbox digest generation and notification."""
    try:
        from email_automation.inbox import InboxFetcher, InboxDigest

        email_config = config.get('email', {})

        # Setup database callbacks for detailed logging
        db_store = db.store_inbox_snapshot if DB_AVAILABLE else None
        db_log = db.log_email_fetch if DB_AVAILABLE else None
        db_cache = db.cache_inbox_message if DB_AVAILABLE else None

        fetcher = InboxFetcher(
            email_config,
            db_store_callback=db_store,
            db_log_callback=db_log
        )
        digest = InboxDigest(fetcher, db_cache_message=db_cache)

        # Track job run
        run_id = None
        if DB_AVAILABLE:
            run_id = db.start_job_run('inbox_digest', 'http')

        data = digest.generate()
        title, body = digest.format_for_notification()

        # Send notification
        router = get_notification_router()
        notification_results = []
        if router:
            results = router.send_digest(title, body, source='inbox')
            notification_results = [
                {'channel': r.channel, 'success': r.success, 'error': r.error}
                for r in results
            ]

        if run_id and DB_AVAILABLE:
            db.complete_job_run(run_id, 'success', data)

        return jsonify({
            'status': Status.OK,
            'digest': data,
            'notifications': notification_results
        })

    except ImportError:
        return jsonify({
            'status': Status.ERROR,
            'error': 'email_automation module not available'
        }), 503
    except Exception as e:
        logger.error(f"Inbox digest failed: {e}")
        return jsonify({'status': Status.ERROR, 'error': str(e)}), 500


@app.route('/api/email/digest/daily', methods=['POST'])
def trigger_daily_digest():
    """Trigger combined daily digest."""
    scheduler = get_email_scheduler()
    if scheduler is None:
        return jsonify({
            'status': Status.ERROR,
            'error': 'Email scheduler not available'
        }), 503

    result = scheduler.run_job_now('daily_combined')
    return jsonify({
        'status': Status.OK if result.get('success') else Status.ERROR,
        **result
    })


@app.route('/api/email/schedule/status')
def get_email_schedule_status():
    """Get email automation scheduler status."""
    scheduler = get_email_scheduler()

    if scheduler is None:
        return jsonify({
            'status': Status.UNAVAILABLE,
            'scheduler_available': False
        })

    status = scheduler.get_status()

    # Add recent job runs if database available
    if DB_AVAILABLE:
        status['recent_runs'] = db.get_job_runs(days=7, limit=20)

    return jsonify({
        'status': Status.OK,
        **status
    })


@app.route('/api/email/notifications/history')
def get_notification_history():
    """Get notification history."""
    if not DB_AVAILABLE:
        return jsonify({
            'status': Status.UNAVAILABLE,
            'error': 'Database not available'
        }), 503

    days = request.args.get('days', 7, type=int)
    channel = request.args.get('channel')
    source = request.args.get('source')

    history = db.get_notification_history(days=days, channel=channel, source=source)
    stats = db.get_notification_stats(days=days)

    return jsonify({
        'status': Status.OK,
        'history': history,
        'stats': stats
    })


@app.route('/api/email/notifications/test', methods=['POST'])
def test_notifications():
    """Test notification channels."""
    router = get_notification_router()

    if router is None:
        return jsonify({
            'status': Status.UNAVAILABLE,
            'error': 'Notification router not available'
        }), 503

    results = router.test_channels()
    return jsonify({
        'status': Status.OK,
        'results': {
            name: {'success': r.success, 'error': r.error}
            for name, r in results.items()
        }
    })


# =============================================================================
# Brave Search Integration
# =============================================================================

@app.route('/api/search')
def brave_search():
    """Perform a web search via Brave Search API."""
    query = request.args.get('q', '')
    count = request.args.get('count', 10, type=int)
    country = request.args.get('country', 'GB')
    
    if not query:
        return jsonify({'status': Status.ERROR, 'error': 'Query required'}), 400
    
    brave_config = config.get('brave_search', {})
    api_key = brave_config.get('api_key')
    
    if not api_key:
        return jsonify({'status': Status.NOT_CONFIGURED, 'error': 'Brave Search not configured'})
    
    try:
        import urllib.parse
        params = urllib.parse.urlencode({
            'q': query,
            'count': min(count, 20),
            'country': country,
            'search_lang': 'en',
            'text_decorations': 'false'
        })
        
        url = f"https://api.search.brave.com/res/v1/web/search?{params}"
        response = requests.get(url, headers={
            'Accept': 'application/json',
            'X-Subscription-Token': api_key
        }, timeout=Defaults.API_TIMEOUT_MEDIUM)
        
        if response.status_code != 200:
            return jsonify({'status': Status.ERROR, 'error': f'API error: {response.status_code}'})
        
        data = response.json()
        results = data.get('web', {}).get('results', [])
        
        return jsonify({
            'status': Status.OK,
            'query': query,
            'count': len(results),
            'results': [{
                'title': r.get('title'),
                'url': r.get('url'),
                'description': r.get('description', '')[:300]
            } for r in results]
        })
        
    except Exception as e:
        logger.error(f"Brave Search error: {e}")
        return jsonify({'status': Status.ERROR, 'error': str(e)}), 500


# =============================================================================
# RSS/Miniflux Integration
# =============================================================================

def get_miniflux_client():
    """Get Miniflux API configuration."""
    miniflux_config = config.get('miniflux', {})
    if not miniflux_config.get('url'):
        return None
    return {
        'url': miniflux_config['url'],
        'auth': (miniflux_config.get('username', ''), miniflux_config.get('password', ''))
    }


def miniflux_request(endpoint, method='GET', data=None):
    """Make a request to Miniflux API."""
    client = get_miniflux_client()
    if not client:
        return None, 'Miniflux not configured'

    try:
        url = f"{client['url']}/v1{endpoint}"
        if method == 'GET':
            response = requests.get(url, auth=client['auth'], timeout=Defaults.API_TIMEOUT_MEDIUM)
        elif method == 'POST':
            response = requests.post(url, auth=client['auth'], json=data, timeout=Defaults.API_TIMEOUT_MEDIUM)
        elif method == 'PUT':
            response = requests.put(url, auth=client['auth'], json=data, timeout=Defaults.API_TIMEOUT_MEDIUM)

        if response.status_code == 200 or response.status_code == 201:
            return response.json(), None
        else:
            return None, f"API error: {response.status_code}"
    except requests.exceptions.ConnectionError:
        return None, 'Miniflux not reachable'
    except Exception as e:
        return None, str(e)


@app.route('/api/rss/status')
def rss_status():
    """Check Miniflux connection status."""
    data, error = miniflux_request('/me')
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK, 'user': data.get('username')})


@app.route('/api/rss/categories')
def rss_categories():
    """Get all RSS categories."""
    data, error = miniflux_request('/categories')
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK, 'categories': data})


@app.route('/api/rss/feeds')
def rss_feeds():
    """Get all RSS feeds."""
    data, error = miniflux_request('/feeds')
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK, 'feeds': data})


@app.route('/api/rss/feeds', methods=['POST'])
def rss_add_feed():
    """Add a new RSS feed."""
    if not request.is_json:
        return jsonify({'status': Status.ERROR, 'error': 'JSON required'}), 400

    feed_url = request.json.get('feed_url')
    category_id = request.json.get('category_id', 1)

    if not feed_url:
        return jsonify({'status': Status.ERROR, 'error': 'feed_url required'}), 400

    data, error = miniflux_request('/feeds', method='POST', data={
        'feed_url': feed_url,
        'category_id': category_id
    })

    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK, 'feed': data})


@app.route('/api/rss/entries')
def rss_entries():
    """Get RSS entries with optional filters."""
    status_filter = request.args.get('status', 'unread')  # unread, read, or all
    limit = request.args.get('limit', 50, type=int)
    category_id = request.args.get('category_id', type=int)

    endpoint = f'/entries?status={status_filter}&limit={limit}&order=published_at&direction=desc'
    if category_id:
        endpoint += f'&category_id={category_id}'

    data, error = miniflux_request(endpoint)
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})

    entries = data.get('entries', [])

    # Group by category for display
    by_category = {}
    for entry in entries:
        cat_title = entry.get('feed', {}).get('category', {}).get('title', 'Uncategorized')
        if cat_title not in by_category:
            by_category[cat_title] = []
        by_category[cat_title].append({
            'id': entry.get('id'),
            'title': entry.get('title'),
            'url': entry.get('url'),
            'published_at': entry.get('published_at'),
            'reading_time': entry.get('reading_time', 0),
            'feed_title': entry.get('feed', {}).get('title', 'Unknown'),
            'status': entry.get('status'),
            'starred': entry.get('starred', False),
            'content': entry.get('content', '')[:500]  # First 500 chars for preview
        })

    return jsonify({
        'status': Status.OK,
        'total': data.get('total', len(entries)),
        'entries': entries,
        'by_category': by_category
    })


@app.route('/api/rss/entries/<int:entry_id>/read', methods=['PUT'])
def rss_mark_read(entry_id):
    """Mark an entry as read."""
    data, error = miniflux_request(f'/entries', method='PUT', data={
        'entry_ids': [entry_id],
        'status': 'read'
    })
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK})


@app.route('/api/rss/entries/<int:entry_id>/star', methods=['PUT'])
def rss_toggle_star(entry_id):
    """Toggle star on an entry."""
    data, error = miniflux_request(f'/entries/{entry_id}/bookmark', method='PUT')
    if error:
        return jsonify({'status': Status.ERROR, 'error': error})
    return jsonify({'status': Status.OK})


@app.route('/api/rss/summary')
def rss_summary():
    """Get RSS feed summary stats."""
    # Get feeds for counts
    feeds_data, feeds_error = miniflux_request('/feeds')
    if feeds_error:
        return jsonify({'status': Status.ERROR, 'error': feeds_error})

    # Get unread entries
    entries_data, entries_error = miniflux_request('/entries?status=unread&limit=1')
    if entries_error:
        return jsonify({'status': Status.ERROR, 'error': entries_error})

    # Get categories
    cats_data, cats_error = miniflux_request('/categories')

    feeds = feeds_data or []
    categories = cats_data or []

    # Calculate stats
    total_unread = entries_data.get('total', 0) if entries_data else 0

    # Unread by category
    by_category = {}
    for feed in feeds:
        cat_title = feed.get('category', {}).get('title', 'Uncategorized')
        if cat_title not in by_category:
            by_category[cat_title] = {'feeds': 0, 'unread': 0}
        by_category[cat_title]['feeds'] += 1
        by_category[cat_title]['unread'] += feed.get('unread_count', 0)

    return jsonify({
        'status': Status.OK,
        'total_feeds': len(feeds),
        'total_unread': total_unread,
        'categories': len(categories),
        'by_category': by_category
    })


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    port = app_config.server.port
    host = app_config.server.host

    logger.info(f"Starting Project Dashboard on {host}:{port}")
    logger.info(f"Config loaded from: {CONFIG_PATH}")

    # Initialize database connection pool
    if DB_AVAILABLE:
        if db.init_pool():
            logger.info("Database connection pool initialized")
        else:
            logger.warning("Failed to initialize database connection pool, using direct connections")

    # Start email scheduler if enabled
    scheduling = config.get('scheduling', {})
    if scheduling.get('enabled', False):
        scheduler = get_email_scheduler()
        if scheduler and scheduler.start():
            logger.info("Email scheduler started")
        else:
            logger.warning("Email scheduler not started (disabled or unavailable)")

    try:
        app.run(host=host, port=port, debug=os.environ.get('FLASK_DEBUG', False))
    finally:
        # Clean up connection pool on shutdown
        if DB_AVAILABLE:
            db.close_pool()
