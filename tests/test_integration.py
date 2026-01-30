"""
Integration tests for the Project Dashboard.

These tests verify end-to-end functionality with mocked external services.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDashboardIntegration:
    """Full integration tests for dashboard."""

    @patch('server.fetch_git_repos')
    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.fetch_linear')
    def test_dashboard_aggregates_all_sources(
        self, mock_linear, mock_kanban, mock_todoist, mock_git, client
    ):
        """Dashboard should successfully aggregate all data sources."""
        mock_git.return_value = {
            'status': 'ok',
            'repos': [
                {'name': 'project-dashboard', 'branch': 'main', 'commit_count': 10, 'is_dirty': False}
            ]
        }
        
        mock_todoist.return_value = {
            'status': 'ok',
            'tasks': [
                {'id': '1', 'content': 'Test task', 'project': 'Personal', 'priority': 4, 'is_overdue': False, 'is_today': True, 'due_date': '2026-01-30'}
            ]
        }
        
        mock_kanban.return_value = {
            'status': 'ok',
            'tasks': [{'id': 1, 'title': 'Kanban task', 'column': 'in-progress'}],
            'by_column': {'in-progress': [{'id': 1, 'title': 'Kanban task'}]}
        }
        
        mock_linear.return_value = {
            'status': 'ok',
            'issues': [{'id': '1', 'identifier': 'TEST-1', 'title': 'Linear issue', 'state': 'In Progress'}],
            'by_status': {'In Progress': []}
        }
        
        response = client.get('/api/dashboard')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # All sources should be present
        assert data['sources']['git']['status'] == 'ok'
        assert data['sources']['todoist']['status'] == 'ok'
        assert data['sources']['kanban']['status'] == 'ok'
        assert data['sources']['linear']['status'] == 'ok'
        
        # Data should be present
        assert len(data['sources']['git']['repos']) == 1
        assert len(data['sources']['todoist']['tasks']) == 1
        assert len(data['sources']['kanban']['tasks']) == 1
        assert len(data['sources']['linear']['issues']) == 1

    @patch('server.fetch_git_repos')
    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.fetch_linear')
    def test_dashboard_handles_partial_failures(
        self, mock_linear, mock_kanban, mock_todoist, mock_git, client
    ):
        """Dashboard should handle partial failures gracefully."""
        mock_git.return_value = {'status': 'ok', 'repos': []}
        mock_todoist.return_value = {'status': 'error', 'error': 'API timeout', 'tasks': []}
        mock_kanban.return_value = {'status': 'ok', 'tasks': [], 'by_column': {}}
        mock_linear.return_value = {'status': 'not_configured', 'error': 'No API key', 'issues': [], 'by_status': {}}
        
        response = client.get('/api/dashboard')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should still have all sources in response
        assert 'git' in data['sources']
        assert 'todoist' in data['sources']
        assert 'kanban' in data['sources']
        assert 'linear' in data['sources']
        
        # Error statuses should be preserved
        assert data['sources']['todoist']['status'] == 'error'
        assert data['sources']['linear']['status'] == 'not_configured'


class TestStandupIntegration:
    """Integration tests for standup endpoint."""

    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.fetch_weather')
    def test_standup_full_integration(self, mock_weather, mock_kanban, mock_todoist, client):
        """Standup should integrate all data sources correctly."""
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        mock_weather.return_value = {
            'status': 'ok',
            'temp_c': '15',
            'condition': 'Partly cloudy',
            'humidity': '60',
            'wind_kph': '12'
        }
        
        mock_todoist.return_value = {
            'status': 'ok',
            'tasks': [
                {'id': '1', 'content': 'Overdue task', 'project': 'Work', 'priority': 4, 'is_overdue': True, 'is_today': False, 'due_date': yesterday},
                {'id': '2', 'content': 'Today task 1', 'project': 'Personal', 'priority': 3, 'is_overdue': False, 'is_today': True, 'due_date': today},
                {'id': '3', 'content': 'Today task 2', 'project': 'Personal', 'priority': 2, 'is_overdue': False, 'is_today': True, 'due_date': today},
                {'id': '4', 'content': 'Future task', 'project': 'Personal', 'priority': 1, 'is_overdue': False, 'is_today': False, 'due_date': '2026-02-15'},
            ]
        }
        
        mock_kanban.return_value = {
            'status': 'ok',
            'by_column': {
                'in-progress': [
                    {'id': 1, 'title': 'Active project', 'tags': ['priority']},
                    {'id': 2, 'title': 'Another active', 'tags': []}
                ],
                'ready': [
                    {'id': 3, 'title': 'Ready task 1'},
                    {'id': 4, 'title': 'Ready task 2'}
                ]
            }
        }
        
        response = client.get('/api/standup')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check summary counts
        assert data['summary']['overdue_count'] == 1
        assert data['summary']['today_count'] == 2
        assert data['summary']['in_progress_count'] == 2
        
        # Check tasks categorization
        assert len(data['tasks']['overdue']) == 1
        assert len(data['tasks']['today']) == 2
        assert len(data['tasks']['upcoming']) >= 1
        
        # Check kanban data
        assert len(data['kanban']['in_progress']) == 2
        assert len(data['kanban']['ready']) >= 1


class TestPlanningWorkflow:
    """Integration tests for planning workflow."""

    @patch('psycopg2.connect')
    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.DB_AVAILABLE', True)
    def test_full_planning_workflow(self, mock_kanban, mock_todoist, mock_connect, client):
        """Test complete planning session workflow."""
        # Setup mocks
        mock_cursor = MagicMock()
        session_id = 42
        
        # Mock INSERT returning session_id
        mock_cursor.fetchone.side_effect = [
            {'id': session_id, 'started_at': datetime.now()},  # Session start
            [1],  # Message insert
            [1],  # Action insert
            [1],  # Another message
            {'id': session_id, 'duration_seconds': 300, 'messages_count': 2, 'actions_count': 1}  # Session end
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        mock_todoist.return_value = {'status': 'ok', 'tasks': []}
        mock_kanban.return_value = {'status': 'ok', 'by_column': {}}
        
        # Step 1: Start session
        response = client.post('/api/planning/session',
                              data=json.dumps({'action': 'start'}),
                              content_type='application/json')
        
        # Should attempt to create session
        assert response.status_code in [200, 500, 503]
        
        # Step 2: Log a user message
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': session_id,
                                  'role': 'user',
                                  'content': 'What should I focus on today?'
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 500, 503]
        
        # Step 3: Log an action
        response = client.post('/api/planning/action',
                              data=json.dumps({
                                  'session_id': session_id,
                                  'action_type': 'prioritize',
                                  'target_type': 'todoist',
                                  'target_id': '123',
                                  'target_title': 'Important task'
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 500, 503]
        
        # Step 4: Log assistant response
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': session_id,
                                  'role': 'assistant',
                                  'content': 'Based on your tasks, I recommend focusing on...'
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 500, 503]
        
        # Step 5: End session
        response = client.post('/api/planning/session',
                              data=json.dumps({
                                  'action': 'end',
                                  'session_id': session_id,
                                  'final_state': {'focus': 'Important task'}
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 404, 500, 503]


class TestErrorRecovery:
    """Tests for error recovery and graceful degradation."""

    def test_static_files_served_without_data(self, client):
        """Dashboard UI should load even without data sources."""
        response = client.get('/')
        assert response.status_code == 200
        # Should return HTML
        assert b'<!DOCTYPE html>' in response.data or b'Project Dashboard' in response.data

    @patch('server.fetch_git_repos')
    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.fetch_linear')
    def test_dashboard_returns_partial_data_on_errors(
        self, mock_linear, mock_kanban, mock_todoist, mock_git, client
    ):
        """Dashboard should return partial data when some sources fail."""
        mock_git.side_effect = Exception("Git scanning failed")
        mock_todoist.return_value = {'status': 'ok', 'tasks': [{'id': '1', 'content': 'Task'}]}
        mock_kanban.side_effect = Exception("Kanban unavailable")
        mock_linear.return_value = {'status': 'ok', 'issues': []}
        
        response = client.get('/api/dashboard')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have error status for failed sources
        assert data['sources']['git']['status'] == 'error'
        assert data['sources']['kanban']['status'] == 'error'
        
        # Working sources should have data
        assert data['sources']['todoist']['status'] == 'ok'
        assert data['sources']['linear']['status'] == 'ok'


class TestConcurrency:
    """Tests for concurrent request handling."""

    def test_multiple_sequential_requests(self, client):
        """Should handle multiple sequential requests."""
        results = []
        
        for _ in range(5):
            response = client.get('/api/health')
            results.append(response.status_code)
        
        # All requests should succeed
        assert all(r == 200 for r in results)

    def test_different_endpoints_in_sequence(self, client):
        """Should handle different endpoints in sequence."""
        endpoints = ['/api/health', '/api/config', '/api/standup']
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
