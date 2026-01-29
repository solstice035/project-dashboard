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
    """Fetch tasks from Kanban board."""
    result = {'status': 'ok', 'tasks': [], 'by_column': {}, 'error': None}
    
    api_url = config['kanban'].get('api_url', 'http://localhost:8888/api/tasks')
    
    try:
        resp = requests.get(api_url, timeout=5)
        resp.raise_for_status()
        tasks = resp.json()
        
        result['tasks'] = tasks
        
        # Group by column
        for task in tasks:
            col = task.get('column', 'unknown')
            if col not in result['by_column']:
                result['by_column'][col] = []
            result['by_column'][col].append(task)
        
    except requests.exceptions.ConnectionError:
        result['status'] = 'unavailable'
        result['error'] = 'Kanban board not running'
    except requests.exceptions.RequestException as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Kanban fetch error: {e}")
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f"Kanban processing error: {e}")
    
    return result


def fetch_linear() -> dict[str, Any]:
    """Fetch issues from Linear (placeholder for future implementation)."""
    result = {'status': 'not_configured', 'issues': [], 'error': None}
    
    api_key = config['linear'].get('api_key', '')
    if not api_key:
        result['error'] = 'Linear API key not configured'
        return result
    
    # TODO: Implement Linear API integration
    # GraphQL endpoint: https://api.linear.app/graphql
    
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
        'kanban': db.get_kanban_trends(days)
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
# Main
# =============================================================================

if __name__ == '__main__':
    port = config['server'].get('port', 8889)
    host = config['server'].get('host', '0.0.0.0')
    
    logger.info(f"Starting Project Dashboard on {host}:{port}")
    logger.info(f"Config loaded from: {CONFIG_PATH}")
    
    app.run(host=host, port=port, debug=os.environ.get('FLASK_DEBUG', False))
