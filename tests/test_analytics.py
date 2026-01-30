"""
Tests for Analytics API endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
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


class TestTrendsEndpoint:
    """Tests for /api/analytics/trends endpoint."""

    def test_trends_default_period(self, client):
        """Should use default 30 day period."""
        response = client.get('/api/analytics/trends')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 30

    def test_trends_custom_period(self, client):
        """Should accept custom period parameter."""
        response = client.get('/api/analytics/trends?days=7')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 7

    def test_trends_period_clamped_min(self, client):
        """Should clamp period to minimum 1 day."""
        response = client.get('/api/analytics/trends?days=0')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] >= 1

    def test_trends_period_clamped_max(self, client):
        """Should clamp period to maximum 365 days."""
        response = client.get('/api/analytics/trends?days=1000')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] <= 365

    def test_trends_returns_all_sources(self, client):
        """Should return trends for all sources."""
        response = client.get('/api/analytics/trends')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'git' in data
            assert 'todoist' in data
            assert 'kanban' in data
            assert 'linear' in data

    @patch('server.DB_AVAILABLE', False)
    def test_trends_requires_database(self, client):
        """Should return 503 when database unavailable."""
        response = client.get('/api/analytics/trends')
        assert response.status_code == 503


class TestDailyEndpoint:
    """Tests for /api/analytics/daily endpoint."""

    def test_daily_default_period(self, client):
        """Should use default 7 day period."""
        response = client.get('/api/analytics/daily')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 7

    def test_daily_custom_period(self, client):
        """Should accept custom period parameter."""
        response = client.get('/api/analytics/daily?days=14')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 14

    def test_daily_period_clamped_max(self, client):
        """Should clamp period to maximum 90 days."""
        response = client.get('/api/analytics/daily?days=200')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] <= 90

    def test_daily_returns_stats(self, client):
        """Should return stats array."""
        response = client.get('/api/analytics/daily')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'stats' in data
            assert isinstance(data['stats'], list)

    @patch('server.DB_AVAILABLE', False)
    def test_daily_requires_database(self, client):
        """Should return 503 when database unavailable."""
        response = client.get('/api/analytics/daily')
        assert response.status_code == 503


class TestRepoAnalyticsEndpoint:
    """Tests for /api/analytics/repo/<repo_name> endpoint."""

    def test_repo_returns_history(self, client):
        """Should return repo history."""
        response = client.get('/api/analytics/repo/test-repo')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'repo' in data
            assert data['repo'] == 'test-repo'
            assert 'days' in data
            assert 'history' in data

    def test_repo_custom_period(self, client):
        """Should accept custom period parameter."""
        response = client.get('/api/analytics/repo/test-repo?days=14')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['days'] == 14

    @patch('server.DB_AVAILABLE', False)
    def test_repo_requires_database(self, client):
        """Should return 503 when database unavailable."""
        response = client.get('/api/analytics/repo/test-repo')
        assert response.status_code == 503


class TestAnalyticsWithMockedDB:
    """Tests with mocked database operations."""

    @patch('server.db.get_git_trends')
    @patch('server.db.get_todoist_trends')
    @patch('server.db.get_kanban_trends')
    @patch('server.db.get_linear_trends')
    @patch('server.DB_AVAILABLE', True)
    def test_trends_aggregates_all_sources(
        self, mock_linear, mock_kanban, mock_todoist, mock_git, client
    ):
        """Should aggregate trends from all sources."""
        mock_git.return_value = [{'date': '2026-01-30', 'total_commits': 5}]
        mock_todoist.return_value = [{'date': '2026-01-30', 'completed': 3}]
        mock_kanban.return_value = [{'date': '2026-01-30', 'done': 2}]
        mock_linear.return_value = [{'date': '2026-01-30', 'closed': 1}]
        
        response = client.get('/api/analytics/trends?days=7')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert len(data['git']) > 0
            assert len(data['todoist']) > 0
            assert len(data['kanban']) > 0
            assert len(data['linear']) > 0

    @patch('server.db.get_daily_summary')
    @patch('server.DB_AVAILABLE', True)
    def test_daily_returns_summary(self, mock_summary, client):
        """Should return daily summary."""
        mock_summary.return_value = [
            {'date': '2026-01-30', 'commits': 5, 'tasks_completed': 3}
        ]
        
        response = client.get('/api/analytics/daily?days=7')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'stats' in data

    @patch('server.db.get_repo_history')
    @patch('server.DB_AVAILABLE', True)
    def test_repo_returns_history(self, mock_history, client):
        """Should return repo history."""
        mock_history.return_value = [
            {'date': '2026-01-30', 'commits': 5, 'is_dirty': False}
        ]
        
        response = client.get('/api/analytics/repo/project-dashboard')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'history' in data


class TestAnalyticsDataIntegrity:
    """Tests for data integrity in analytics."""

    def test_trends_returns_arrays(self, client):
        """All trend data should be arrays."""
        response = client.get('/api/analytics/trends')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data.get('git', []), list)
            assert isinstance(data.get('todoist', []), list)
            assert isinstance(data.get('kanban', []), list)
            assert isinstance(data.get('linear', []), list)

    def test_daily_stats_are_dictionaries(self, client):
        """Daily stats should be list of dictionaries."""
        response = client.get('/api/analytics/daily')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            for stat in data.get('stats', []):
                assert isinstance(stat, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
