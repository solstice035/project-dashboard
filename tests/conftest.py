"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    app.config['DEBUG'] = False
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db_available():
    """Mock database as available."""
    with patch('server.DB_AVAILABLE', True):
        yield


@pytest.fixture
def mock_db_unavailable():
    """Mock database as unavailable."""
    with patch('server.DB_AVAILABLE', False):
        yield


@pytest.fixture
def mock_db_connection():
    """Provide a mocked database connection."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {'id': 1, 'started_at': datetime.now()}
    mock_cursor.fetchall.return_value = []
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    
    with patch('psycopg2.connect', return_value=mock_conn):
        yield mock_cursor


@pytest.fixture
def mock_todoist_success():
    """Mock successful Todoist response."""
    with patch('server.fetch_todoist') as mock:
        mock.return_value = {
            'status': 'ok',
            'tasks': [
                {
                    'id': '1',
                    'content': 'Test task',
                    'project': 'Personal',
                    'priority': 4,
                    'is_overdue': False,
                    'is_today': True,
                    'due_date': datetime.now().strftime('%Y-%m-%d')
                }
            ]
        }
        yield mock


@pytest.fixture
def mock_kanban_success():
    """Mock successful Kanban response."""
    with patch('server.fetch_kanban') as mock:
        mock.return_value = {
            'status': 'ok',
            'tasks': [{'id': 1, 'title': 'Test task', 'column': 'in-progress'}],
            'by_column': {
                'in-progress': [{'id': 1, 'title': 'Test task'}],
                'ready': []
            }
        }
        yield mock


@pytest.fixture
def mock_git_success():
    """Mock successful Git response."""
    with patch('server.fetch_git_repos') as mock:
        mock.return_value = {
            'status': 'ok',
            'repos': [
                {
                    'name': 'test-repo',
                    'branch': 'main',
                    'commit_count': 5,
                    'commits': ['abc123 Test commit'],
                    'is_dirty': False,
                    'ahead': 0,
                    'behind': 0
                }
            ]
        }
        yield mock


@pytest.fixture
def mock_linear_success():
    """Mock successful Linear response."""
    with patch('server.fetch_linear') as mock:
        mock.return_value = {
            'status': 'ok',
            'issues': [
                {
                    'id': '1',
                    'identifier': 'TEST-1',
                    'title': 'Test issue',
                    'priority': 2,
                    'state': 'In Progress',
                    'state_type': 'started',
                    'project': 'Test Project'
                }
            ],
            'by_status': {
                'In Progress': [{'id': '1', 'title': 'Test issue'}]
            }
        }
        yield mock


@pytest.fixture
def mock_weather_success():
    """Mock successful weather response."""
    with patch('server.fetch_weather') as mock:
        mock.return_value = {
            'status': 'ok',
            'temp_c': '15',
            'condition': 'Partly cloudy',
            'humidity': '60',
            'wind_kph': '12'
        }
        yield mock


@pytest.fixture
def mock_all_sources_success(mock_git_success, mock_todoist_success, 
                              mock_kanban_success, mock_linear_success):
    """Mock all data sources as successful."""
    yield {
        'git': mock_git_success,
        'todoist': mock_todoist_success,
        'kanban': mock_kanban_success,
        'linear': mock_linear_success
    }


@pytest.fixture
def sample_planning_session():
    """Sample planning session data."""
    return {
        'id': 42,
        'started_at': datetime.now(),
        'ended_at': None,
        'duration_seconds': None,
        'messages_count': 0,
        'actions_count': 0
    }


@pytest.fixture
def sample_tasks():
    """Sample task data for testing."""
    today = datetime.now().strftime('%Y-%m-%d')
    return [
        {
            'id': '1',
            'content': 'Overdue task',
            'project': 'Work',
            'priority': 4,
            'is_overdue': True,
            'is_today': False,
            'due_date': '2026-01-28'
        },
        {
            'id': '2',
            'content': 'Today task',
            'project': 'Personal',
            'priority': 3,
            'is_overdue': False,
            'is_today': True,
            'due_date': today
        },
        {
            'id': '3',
            'content': 'Future task',
            'project': 'Personal',
            'priority': 1,
            'is_overdue': False,
            'is_today': False,
            'due_date': '2026-02-15'
        }
    ]


# Markers for categorizing tests
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "database: marks tests requiring database")
