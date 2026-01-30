#!/usr/bin/env python3
"""
Project Intelligence Dashboard - Flask Backend

Aggregates data from multiple sources:
- Git repositories (commits, branch status, dirty state)
- Todoist (tasks filtered by project)
- Kanban board (localhost:8888)
- Linear (future)
"""

import json
import os
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
import requests
from flask import Flask, jsonify, send_from_directory, request

# Import database module
try:
    import database as db
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
DEFAULT_CONFIG = {
    'todoist': {'token': '', 'projects': []},
    'linear': {'api_key': '', 'team_id': ''},
    'git': {'scan_paths': ['~/clawd/projects'], 'history_days': 7},
    'kanban': {'api_url': 'http://localhost:8888/api/tasks'},
    'server': {'port': 8889, 'host': '0.0.0.0', 'refresh_interval': 300}
}


def load_config() -> dict:
    """Load configuration from YAML file."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                config = yaml.safe_load(f)
                # Merge with defaults
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if subkey not in config[key]:
                                config[key][subkey] = subvalue
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return DEFAULT_CONFIG


config = load_config()


# =============================================================================
# Data Fetchers
# =============================================================================

def fetch_git_repos() -> dict[str, Any]:
    """Scan git repositories for status."""
    result = {'status': 'ok', 'repos': [], 'error': None}
    
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
                        capture_output=True, text=True, timeout=5
                    )
                    if branch_result.returncode == 0:
                        repo_info['branch'] = branch_result.stdout.strip() or 'HEAD'
                    
                    # Get recent commits
                    log_result = subprocess.run(
                        ['git', '-C', str(repo_dir), 'log', '--oneline', '-10', f'--since={since_date}'],
                        capture_output=True, text=True, timeout=5
                    )
                    if log_result.returncode == 0 and log_result.stdout.strip():
                        commits = log_result.stdout.strip().split('\n')
                        repo_info['commits'] = commits[:5]
                        repo_info['commit_count'] = len(commits)
                    
                    # Check if dirty
                    status_result = subprocess.run(
                        ['git', '-C', str(repo_dir), 'status', '--porcelain'],
                        capture_output=True, text=True, timeout=5
                    )
                    if status_result.returncode == 0:
                        repo_info['is_dirty'] = bool(status_result.stdout.strip())
                    
                    # Get ahead/behind (if tracking remote)
                    try:
                        rev_result = subprocess.run(
                            ['git', '-C', str(repo_dir), 'rev-list', '--left-right', '--count', '@{u}...HEAD'],
                            capture_output=True, text=True, timeout=5
                        )
                        if rev_result.returncode == 0:
                            parts = rev_result.stdout.strip().split()
                            if len(parts) == 2:
                                repo_info['behind'] = int(parts[0])
                                repo_info['ahead'] = int(parts[1])
                    except Exception:
                        pass  # No upstream tracking
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"Timeout scanning repo: {repo_dir}")
                except Exception as e:
                    logger.warning(f"Error scanning repo {repo_dir}: {e}")
                
                result['repos'].append(repo_info)
        
        # Sort by activity (commit count + dirty)
        result['repos'].sort(key=lambda x: (x['is_dirty'], x['commit_count']), reverse=True)
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Git fetch error: {e}")
    
    return result


def fetch_todoist() -> dict[str, Any]:
    """Fetch tasks from Todoist."""
    result = {'status': 'ok', 'tasks': [], 'error': None}
    
    token = config['todoist'].get('token', '')
    if not token:
        result['status'] = 'not_configured'
        result['error'] = 'Todoist token not configured'
        return result
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(
            'https://api.todoist.com/rest/v2/tasks',
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        all_tasks = resp.json()
        
        # Get project names for filtering
        projects_resp = requests.get(
            'https://api.todoist.com/rest/v2/projects',
            headers=headers,
            timeout=10
        )
        projects_resp.raise_for_status()
        projects = {p['id']: p['name'] for p in projects_resp.json()}
        
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
        
    except requests.exceptions.RequestException as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Todoist fetch error: {e}")
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Todoist processing error: {e}")
    
    return result


def fetch_kanban() -> dict[str, Any]:
    """Fetch tasks from Kanban board API, with PostgreSQL fallback."""
    result = {'status': 'ok', 'tasks': [], 'by_column': {}, 'error': None, 'source': 'api'}
    
    api_url = config['kanban'].get('api_url', 'http://localhost:8888/api/tasks')
    
    # Try API first
    try:
        resp = requests.get(api_url, timeout=3)
        resp.raise_for_status()
        tasks = resp.json()
        
        result['tasks'] = tasks
        
        # Group by column
        for task in tasks:
            col = task.get('column', 'unknown')
            if col not in result['by_column']:
                result['by_column'][col] = []
            result['by_column'][col].append(task)
        
        return result
        
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.info("Kanban API unavailable, falling back to PostgreSQL")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Kanban API error, trying PostgreSQL: {e}")
    
    # Fallback to PostgreSQL
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(dbname='nick', host='localhost', cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, description, column_name as column, tags, 
                   priority, position, created_at, updated_at
            FROM kanban_tasks 
            ORDER BY column_name, position
        """)
        tasks = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        result['tasks'] = tasks
        result['source'] = 'database'
        
        # Group by column
        for task in tasks:
            col = task.get('column', 'unknown')
            if col not in result['by_column']:
                result['by_column'][col] = []
            result['by_column'][col].append(task)
        
        logger.info(f"Loaded {len(tasks)} tasks from PostgreSQL")
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = f'Both API and database unavailable: {e}'
        logger.error(f"Kanban PostgreSQL fallback error: {e}")
    
    return result


def fetch_linear() -> dict[str, Any]:
    """Fetch issues from Linear."""
    result = {'status': 'ok', 'issues': [], 'by_status': {}, 'error': None}
    
    api_key = config['linear'].get('api_key', '')
    if not api_key:
        result['status'] = 'not_configured'
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
        
        headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }
        
        resp = requests.post(
            'https://api.linear.app/graphql',
            headers=headers,
            json={'query': query},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        if 'errors' in data:
            result['status'] = 'error'
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
        
    except requests.exceptions.RequestException as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Linear fetch error: {e}")
    except Exception as e:
        result['status'] = 'error'
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
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


@app.route('/api/dashboard')
def get_dashboard():
    """Fetch all dashboard data in parallel."""
    start_time = datetime.now()
    store_snapshot = request.args.get('store', 'true').lower() == 'true'
    
    # Fetch all sources in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
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
                results[source] = {'status': 'error', 'error': str(e)}
    
    # Store snapshots to database (for analytics)
    if DB_AVAILABLE and store_snapshot:
        try:
            if results['git'].get('status') == 'ok':
                db.store_git_snapshot(results['git'].get('repos', []))
            if results['todoist'].get('status') == 'ok':
                db.store_todoist_snapshot(results['todoist'].get('tasks', []))
            if results['kanban'].get('status') == 'ok':
                db.store_kanban_snapshot(results['kanban'].get('by_column', {}))
            if results['linear'].get('status') == 'ok':
                db.store_linear_snapshot(
                    results['linear'].get('issues', []),
                    results['linear'].get('by_status', {})
                )
            # Update daily aggregates
            db.update_daily_stats(results['git'], results['todoist'], results['kanban'])
        except Exception as e:
            logger.error(f"Failed to store snapshots: {e}")
    
    # Build response
    elapsed = (datetime.now() - start_time).total_seconds()
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'fetch_time_seconds': round(elapsed, 2),
        'refresh_interval': config['server'].get('refresh_interval', 300),
        'db_available': DB_AVAILABLE,
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
            'api_url': config['kanban'].get('api_url')
        },
        'server': {
            'refresh_interval': config['server'].get('refresh_interval', 300)
        }
    })


# =============================================================================
# Standup & Planning API
# =============================================================================

def fetch_weather() -> dict:
    """Fetch current weather."""
    try:
        resp = requests.get('https://wttr.in/London?format=j1', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            return {
                'status': 'ok',
                'temp_c': current.get('temp_C'),
                'condition': current.get('weatherDesc', [{}])[0].get('value'),
                'humidity': current.get('humidity'),
                'wind_kph': current.get('windspeedKmph')
            }
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")
    return {'status': 'error', 'error': 'Failed to fetch weather'}


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
            'upcoming': upcoming[:5]  # Next 5 upcoming
        },
        'kanban': {
            'in_progress': in_progress,
            'ready': ready[:5]  # Top 5 ready
        },
        'summary': {
            'overdue_count': len(overdue),
            'today_count': len(today_tasks),
            'in_progress_count': len(in_progress)
        }
    })


@app.route('/api/planning/session', methods=['POST'])
def manage_planning_session():
    """Start or end a planning session."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    data = request.get_json() or {}
    action = data.get('action')
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(dbname='nick', host='localhost', cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        if action == 'start':
            # Get current context
            context = {
                'tasks': fetch_todoist().get('tasks', [])[:20],
                'kanban': fetch_kanban().get('by_column', {})
            }
            
            cur.execute("""
                INSERT INTO planning_sessions (initial_context)
                VALUES (%s)
                RETURNING id, started_at
            """, (json.dumps(context),))
            
            result = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'status': 'ok',
                'session_id': result['id'],
                'started_at': result['started_at'].isoformat(),
                'context': context
            })
            
        elif action == 'end':
            session_id = data.get('session_id')
            if not session_id:
                return jsonify({'error': 'session_id required'}), 400
            
            # Calculate duration and update
            cur.execute("""
                UPDATE planning_sessions
                SET ended_at = NOW(),
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER,
                    final_state = %s,
                    messages_count = (SELECT COUNT(*) FROM planning_messages WHERE session_id = %s),
                    actions_count = (SELECT COUNT(*) FROM planning_actions WHERE session_id = %s)
                WHERE id = %s
                RETURNING id, duration_seconds, messages_count, actions_count
            """, (json.dumps(data.get('final_state', {})), session_id, session_id, session_id))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                return jsonify({
                    'status': 'ok',
                    'session_id': result['id'],
                    'duration_seconds': result['duration_seconds'],
                    'messages_count': result['messages_count'],
                    'actions_count': result['actions_count']
                })
            else:
                return jsonify({'error': 'Session not found'}), 404
        
        else:
            return jsonify({'error': 'Invalid action. Use start or end'}), 400
            
    except Exception as e:
        logger.error(f"Planning session error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/api/planning/action', methods=['POST'])
def log_planning_action():
    """Log a planning action (task change)."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    data = request.get_json() or {}
    required = ['session_id', 'action_type']
    
    if not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {required}'}), 400
    
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='nick', host='localhost')
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO planning_actions 
            (session_id, action_type, target_type, target_id, target_title, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['session_id'],
            data['action_type'],
            data.get('target_type'),
            data.get('target_id'),
            data.get('target_title'),
            json.dumps(data.get('details', {}))
        ))
        
        action_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({'status': 'ok', 'action_id': action_id})
        
    except Exception as e:
        logger.error(f"Planning action error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/api/planning/message', methods=['POST'])
def log_planning_message():
    """Log a chat message in the planning session."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    data = request.get_json() or {}
    required = ['session_id', 'role', 'content']
    
    if not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {required}'}), 400
    
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='nick', host='localhost')
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO planning_messages 
            (session_id, role, content, tokens_used)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            data['session_id'],
            data['role'],
            data['content'],
            data.get('tokens_used')
        ))
        
        msg_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({'status': 'ok', 'message_id': msg_id})
        
    except Exception as e:
        logger.error(f"Planning message error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/api/planning/analytics')
def get_planning_analytics():
    """Get planning analytics and trends."""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.args.get('days', 30, type=int)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(dbname='nick', host='localhost', cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # Recent sessions
        cur.execute("""
            SELECT id, started_at, ended_at, duration_seconds, 
                   messages_count, actions_count
            FROM planning_sessions
            WHERE started_at > NOW() - INTERVAL '%s days'
            ORDER BY started_at DESC
            LIMIT 20
        """, (days,))
        sessions = [dict(row) for row in cur.fetchall()]
        
        # Action type breakdown
        cur.execute("""
            SELECT action_type, COUNT(*) as count
            FROM planning_actions
            WHERE action_at > NOW() - INTERVAL '%s days'
            GROUP BY action_type
            ORDER BY count DESC
        """, (days,))
        action_breakdown = [dict(row) for row in cur.fetchall()]
        
        # Totals
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
        totals = dict(cur.fetchone())
        
        conn.close()
        
        return jsonify({
            'days': days,
            'sessions': sessions,
            'action_breakdown': action_breakdown,
            'totals': totals
        })
        
    except Exception as e:
        logger.error(f"Planning analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    port = config['server'].get('port', 8889)
    host = config['server'].get('host', '0.0.0.0')
    
    logger.info(f"Starting Project Dashboard on {host}:{port}")
    logger.info(f"Config loaded from: {CONFIG_PATH}")
    
    app.run(host=host, port=port, debug=os.environ.get('FLASK_DEBUG', False))
