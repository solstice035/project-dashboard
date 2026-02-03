"""
Tests for Standup API endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app, fetch_weather


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestStandupEndpoint:
    """Tests for /api/standup endpoint."""

    def test_standup_returns_required_fields(self, client):
        """Standup should return all required fields."""
        response = client.get('/api/standup')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Required top-level fields
        assert 'generated_at' in data
        assert 'date' in data
        assert 'day_name' in data
        assert 'weather' in data
        assert 'tasks' in data
        assert 'kanban' in data
        assert 'summary' in data
        
    def test_standup_tasks_structure(self, client):
        """Standup tasks should have correct structure."""
        response = client.get('/api/standup')
        data = json.loads(response.data)
        
        tasks = data['tasks']
        assert 'overdue' in tasks
        assert 'today' in tasks
        assert 'upcoming' in tasks
        
        # All should be lists
        assert isinstance(tasks['overdue'], list)
        assert isinstance(tasks['today'], list)
        assert isinstance(tasks['upcoming'], list)

    def test_standup_kanban_structure(self, client):
        """Standup kanban should have correct structure."""
        response = client.get('/api/standup')
        data = json.loads(response.data)
        
        kanban = data['kanban']
        assert 'in_progress' in kanban
        assert 'ready' in kanban
        
        assert isinstance(kanban['in_progress'], list)
        assert isinstance(kanban['ready'], list)

    def test_standup_summary_counts(self, client):
        """Standup summary should have count fields."""
        response = client.get('/api/standup')
        data = json.loads(response.data)
        
        summary = data['summary']
        assert 'overdue_count' in summary
        assert 'today_count' in summary
        assert 'in_progress_count' in summary
        
        # Counts should be integers
        assert isinstance(summary['overdue_count'], int)
        assert isinstance(summary['today_count'], int)
        assert isinstance(summary['in_progress_count'], int)

    def test_standup_date_format(self, client):
        """Standup date should be in correct format."""
        response = client.get('/api/standup')
        data = json.loads(response.data)
        
        # Date should be YYYY-MM-DD
        date = data['date']
        assert len(date) == 10
        assert date[4] == '-'
        assert date[7] == '-'
        
        # day_name should be a weekday
        assert data['day_name'] in [
            'Monday', 'Tuesday', 'Wednesday', 
            'Thursday', 'Friday', 'Saturday', 'Sunday'
        ]


class TestWeatherFetcher:
    """Tests for weather fetching."""

    @patch('server._weather_api_get')
    def test_fetch_weather_success(self, mock_weather_api):
        """Should successfully fetch weather data."""
        mock_weather_api.return_value = {
            'current_condition': [{
                'temp_C': '12',
                'weatherDesc': [{'value': 'Partly cloudy'}],
                'humidity': '65',
                'windspeedKmph': '15'
            }]
        }

        result = fetch_weather()

        assert result['status'] == 'ok'
        assert result['temp_c'] == '12'
        assert result['condition'] == 'Partly cloudy'
        assert result['humidity'] == '65'
        assert result['wind_kph'] == '15'

    @patch('server._weather_api_get')
    def test_fetch_weather_timeout(self, mock_weather_api):
        """Should handle timeout gracefully."""
        import requests
        mock_weather_api.side_effect = requests.exceptions.Timeout()

        result = fetch_weather()

        assert result['status'] == 'error'
        assert 'error' in result

    @patch('server._weather_api_get')
    def test_fetch_weather_api_error(self, mock_weather_api):
        """Should handle API errors gracefully."""
        import requests
        mock_weather_api.side_effect = requests.exceptions.HTTPError("500 Server Error")

        result = fetch_weather()

        assert result['status'] == 'error'

    @patch('server._weather_api_get')
    def test_fetch_weather_malformed_response(self, mock_weather_api):
        """Should handle malformed responses."""
        mock_weather_api.return_value = {'invalid': 'data'}

        result = fetch_weather()
        
        # Should return error or handle gracefully
        assert 'status' in result


class TestStandupWithMockedData:
    """Tests with mocked external data."""

    @patch('server.fetch_todoist')
    @patch('server.fetch_kanban')
    @patch('server.fetch_weather')
    def test_standup_integrates_all_sources(self, mock_weather, mock_kanban, mock_todoist, client):
        """Standup should integrate data from all sources."""
        mock_weather.return_value = {
            'status': 'ok',
            'temp_c': '15',
            'condition': 'Sunny',
            'humidity': '50',
            'wind_kph': '10'
        }
        
        mock_todoist.return_value = {
            'status': 'ok',
            'tasks': [
                {'id': '1', 'content': 'Overdue task', 'is_overdue': True, 'is_today': False, 'due_date': '2026-01-29', 'project': 'Test', 'priority': 4},
                {'id': '2', 'content': 'Today task', 'is_overdue': False, 'is_today': True, 'due_date': '2026-01-30', 'project': 'Test', 'priority': 3},
            ]
        }
        
        mock_kanban.return_value = {
            'status': 'ok',
            'by_column': {
                'in-progress': [{'id': 1, 'title': 'Active task'}],
                'ready': [{'id': 2, 'title': 'Ready task'}]
            }
        }
        
        response = client.get('/api/standup')
        data = json.loads(response.data)
        
        # Check integration
        assert data['weather']['status'] == 'ok'
        assert data['summary']['overdue_count'] == 1
        assert data['summary']['today_count'] == 1
        assert data['summary']['in_progress_count'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
