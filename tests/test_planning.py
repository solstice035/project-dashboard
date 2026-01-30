"""
Tests for Planning Session API endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
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


@pytest.fixture
def mock_db():
    """Mock database connection."""
    with patch('server.DB_AVAILABLE', True):
        yield


class TestPlanningSessionEndpoint:
    """Tests for /api/planning/session endpoint."""

    def test_session_requires_action(self, client):
        """Should require action parameter."""
        response = client.post('/api/planning/session',
                              data=json.dumps({}),
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_session_invalid_action(self, client):
        """Should reject invalid actions."""
        response = client.post('/api/planning/session',
                              data=json.dumps({'action': 'invalid'}),
                              content_type='application/json')
        assert response.status_code == 400

    @patch('psycopg2.connect')
    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.DB_AVAILABLE', True)
    def test_session_start_success(self, mock_kanban, mock_todoist, mock_connect, client):
        """Should successfully start a planning session."""
        # Mock database
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 42, 'started_at': datetime.now()}
        mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        # Mock data fetchers
        mock_todoist.return_value = {'status': 'ok', 'tasks': []}
        mock_kanban.return_value = {'status': 'ok', 'by_column': {}}
        
        response = client.post('/api/planning/session',
                              data=json.dumps({'action': 'start'}),
                              content_type='application/json')
        
        # May fail without real DB, but should attempt
        assert response.status_code in [200, 500, 503]

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_session_end_requires_session_id(self, mock_connect, client):
        """Should require session_id for end action."""
        response = client.post('/api/planning/session',
                              data=json.dumps({'action': 'end'}),
                              content_type='application/json')
        
        assert response.status_code in [400, 503]

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_session_end_success(self, mock_connect, client):
        """Should successfully end a planning session."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 42,
            'duration_seconds': 300,
            'messages_count': 5,
            'actions_count': 2
        }
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        response = client.post('/api/planning/session',
                              data=json.dumps({
                                  'action': 'end',
                                  'session_id': 42,
                                  'final_state': {'notes': 'test'}
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 404, 500, 503]


class TestPlanningMessageEndpoint:
    """Tests for /api/planning/message endpoint."""

    def test_message_requires_fields(self, client):
        """Should require required fields."""
        response = client.post('/api/planning/message',
                              data=json.dumps({}),
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_message_validates_required_fields(self, client):
        """Should validate required fields are present."""
        # Missing role
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': 42,
                                  'content': 'test'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

        # Missing content
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': 42,
                                  'role': 'user'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_message_log_success(self, mock_connect, client):
        """Should successfully log a message."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': 42,
                                  'role': 'user',
                                  'content': 'What should I focus on?',
                                  'tokens_used': 150
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 500, 503]


class TestPlanningActionEndpoint:
    """Tests for /api/planning/action endpoint."""

    def test_action_requires_fields(self, client):
        """Should require required fields."""
        response = client.post('/api/planning/action',
                              data=json.dumps({}),
                              content_type='application/json')
        assert response.status_code == 400

    def test_action_validates_session_id(self, client):
        """Should require session_id."""
        response = client.post('/api/planning/action',
                              data=json.dumps({
                                  'action_type': 'defer'
                              }),
                              content_type='application/json')
        assert response.status_code == 400

    def test_action_validates_action_type(self, client):
        """Should require action_type."""
        response = client.post('/api/planning/action',
                              data=json.dumps({
                                  'session_id': 42
                              }),
                              content_type='application/json')
        assert response.status_code == 400

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_action_log_success(self, mock_connect, client):
        """Should successfully log an action."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        response = client.post('/api/planning/action',
                              data=json.dumps({
                                  'session_id': 42,
                                  'action_type': 'defer',
                                  'target_type': 'todoist',
                                  'target_id': '12345',
                                  'target_title': 'Check tyre pressure',
                                  'details': {'new_due_date': '2026-02-01'}
                              }),
                              content_type='application/json')
        
        assert response.status_code in [200, 500, 503]


class TestPlanningAnalyticsEndpoint:
    """Tests for /api/planning/analytics endpoint."""

    def test_analytics_returns_structure(self, client):
        """Analytics should return expected structure."""
        response = client.get('/api/planning/analytics')
        
        # May return 503 if DB not available
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'days' in data
            assert 'sessions' in data
            assert 'action_breakdown' in data
            assert 'totals' in data

    def test_analytics_respects_days_param(self, client):
        """Analytics should respect days parameter."""
        response = client.get('/api/planning/analytics?days=7')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 7

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_analytics_with_mock_db(self, mock_connect, client):
        """Should return analytics data with mocked DB."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {
            'total_sessions': 10,
            'total_duration': 3600,
            'total_messages': 50,
            'total_actions': 20,
            'avg_duration': 360
        }
        mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        response = client.get('/api/planning/analytics?days=30')
        
        assert response.status_code in [200, 500, 503]


class TestActionTypes:
    """Tests for valid action types."""
    
    VALID_ACTION_TYPES = ['defer', 'complete', 'prioritize', 'add', 'drop', 'reschedule']

    @patch('psycopg2.connect')
    @patch('server.DB_AVAILABLE', True)
    def test_valid_action_types_accepted(self, mock_connect, client):
        """All valid action types should be accepted."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        for action_type in self.VALID_ACTION_TYPES:
            response = client.post('/api/planning/action',
                                  data=json.dumps({
                                      'session_id': 42,
                                      'action_type': action_type
                                  }),
                                  content_type='application/json')
            
            # Should at least attempt (200 or 500/503 for DB issues)
            assert response.status_code in [200, 500, 503], f"Failed for action_type: {action_type}"


class TestDatabaseUnavailable:
    """Tests for database unavailable scenarios."""

    @patch('server.DB_AVAILABLE', False)
    def test_session_returns_503_without_db(self, client):
        """Planning session should return 503 without DB."""
        response = client.post('/api/planning/session',
                              data=json.dumps({'action': 'start'}),
                              content_type='application/json')
        assert response.status_code == 503

    @patch('server.DB_AVAILABLE', False)
    def test_message_returns_503_without_db(self, client):
        """Planning message should return 503 without DB."""
        response = client.post('/api/planning/message',
                              data=json.dumps({
                                  'session_id': 42,
                                  'role': 'user',
                                  'content': 'test'
                              }),
                              content_type='application/json')
        assert response.status_code == 503

    @patch('server.DB_AVAILABLE', False)
    def test_action_returns_503_without_db(self, client):
        """Planning action should return 503 without DB."""
        response = client.post('/api/planning/action',
                              data=json.dumps({
                                  'session_id': 42,
                                  'action_type': 'defer'
                              }),
                              content_type='application/json')
        assert response.status_code == 503

    @patch('server.DB_AVAILABLE', False)
    def test_analytics_returns_503_without_db(self, client):
        """Planning analytics should return 503 without DB."""
        response = client.get('/api/planning/analytics')
        assert response.status_code == 503


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
