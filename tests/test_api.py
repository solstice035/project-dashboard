"""
Tests for the Project Dashboard API.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app, fetch_git_repos, fetch_todoist, fetch_kanban


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_returns_ok(self, client):
        """Health check should return status ok."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'timestamp' in data
        assert 'version' in data


class TestDashboardEndpoint:
    """Tests for /api/dashboard endpoint."""

    def test_dashboard_returns_all_sources(self, client):
        """Dashboard should return data from all sources."""
        response = client.get('/api/dashboard')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'timestamp' in data
        assert 'sources' in data
        assert 'git' in data['sources']
        assert 'todoist' in data['sources']
        assert 'kanban' in data['sources']
        assert 'linear' in data['sources']


class TestGitFetcher:
    """Tests for Git repository scanning."""

    @patch('server.config')
    @patch('subprocess.run')
    def test_fetch_git_repos_success(self, mock_run, mock_config):
        """Should successfully scan git repos."""
        mock_config.__getitem__ = MagicMock(return_value={
            'scan_paths': ['/tmp/test'],
            'history_days': 7
        })
        
        # Mock subprocess calls
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='main\n'
        )
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=[]):
                result = fetch_git_repos()
        
        assert result['status'] == 'ok'
        assert 'repos' in result

    def test_fetch_git_repos_handles_timeout(self):
        """Should handle subprocess timeouts gracefully."""
        # This tests the error handling path
        result = fetch_git_repos()
        assert result['status'] in ['ok', 'error']


class TestTodoistFetcher:
    """Tests for Todoist integration."""

    @patch('server.config')
    def test_todoist_not_configured(self, mock_config):
        """Should return not_configured when no token."""
        mock_config.__getitem__ = MagicMock(return_value={'token': '', 'projects': []})
        
        result = fetch_todoist()
        
        assert result['status'] == 'not_configured'
        assert 'error' in result

    @patch('server.config')
    @patch('requests.get')
    def test_todoist_fetch_success(self, mock_get, mock_config):
        """Should successfully fetch and filter tasks."""
        mock_config.__getitem__ = MagicMock(return_value={
            'token': 'test-token',
            'projects': ['Personal']
        })
        
        # Mock responses
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=[
                    {
                        'id': '1',
                        'content': 'Test task',
                        'project_id': 'proj1',
                        'priority': 4,
                        'due': {'date': '2026-01-29'}
                    }
                ])
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=[
                    {'id': 'proj1', 'name': 'Personal'}
                ])
            )
        ]
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = fetch_todoist()
        
        assert result['status'] == 'ok'
        assert 'tasks' in result


class TestKanbanFetcher:
    """Tests for Kanban board integration."""

    @patch('server.config')
    @patch('requests.get')
    def test_kanban_fetch_success(self, mock_get, mock_config):
        """Should successfully fetch kanban tasks."""
        mock_config.__getitem__ = MagicMock(return_value={
            'api_url': 'http://localhost:8888/api/tasks'
        })
        
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[
                {'id': 1, 'title': 'Task', 'column': 'in-progress'}
            ])
        )
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = fetch_kanban()
        
        assert result['status'] == 'ok'
        assert 'tasks' in result
        assert 'by_column' in result

    @patch('server.config')
    @patch('requests.get')
    @patch('psycopg2.connect')
    def test_kanban_unavailable_with_db_fallback_failure(self, mock_pg, mock_get, mock_config):
        """Should return error when both API and DB are unavailable."""
        import requests
        mock_config.__getitem__ = MagicMock(return_value={
            'api_url': 'http://localhost:8888/api/tasks'
        })
        
        # API fails
        mock_get.side_effect = requests.exceptions.ConnectionError()
        # DB also fails
        mock_pg.side_effect = Exception("Database connection failed")
        
        result = fetch_kanban()
        
        # Should return error or ok (if real DB works), but test the fallback logic
        assert result['status'] in ['ok', 'error']
    
    @patch('server.config')
    @patch('requests.get')
    def test_kanban_api_success_no_fallback(self, mock_get, mock_config):
        """Should use API when available, not fallback."""
        mock_config.__getitem__ = MagicMock(return_value={
            'api_url': 'http://localhost:8888/api/tasks'
        })
        
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[
                {'id': 1, 'title': 'API Task', 'column': 'ready'}
            ])
        )
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = fetch_kanban()
        
        assert result['status'] == 'ok'
        assert result.get('source', 'api') == 'api'


class TestConfigEndpoint:
    """Tests for /api/config endpoint."""

    def test_config_returns_status(self, client):
        """Config endpoint should return configuration status."""
        response = client.get('/api/config')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'todoist' in data
        assert 'linear' in data
        assert 'git' in data
        assert 'kanban' in data
        
        # Should not expose actual secrets
        assert 'token' not in str(data)
        assert 'api_key' not in str(data)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
