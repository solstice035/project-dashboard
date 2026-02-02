"""
Tests for Configuration API endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestActivityTypesEndpoint:
    """Tests for /api/config/activity-types endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_activity_types')
    def test_get_activity_types_success(self, mock_get, client):
        """Should return list of activity types."""
        mock_get.return_value = [
            {'code': 'workout', 'name': 'Workout', 'area_code': 'fitness', 'base_xp': 50},
            {'code': 'reading', 'name': 'Reading', 'area_code': 'learning', 'base_xp': 15}
        ]

        response = client.get('/api/config/activity-types')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'activity_types' in data
        assert data['count'] == 2
        assert data['activity_types'][0]['code'] == 'workout'

    @patch('server.DB_AVAILABLE', False)
    def test_get_activity_types_db_unavailable(self, client):
        """Should return 503 when database is unavailable."""
        response = client.get('/api/config/activity-types')
        assert response.status_code == 503

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_activity_type')
    def test_get_single_activity_type(self, mock_get, client):
        """Should return single activity type by code."""
        mock_get.return_value = {
            'code': 'workout', 'name': 'Workout', 'area_code': 'fitness', 'base_xp': 50
        }

        response = client.get('/api/config/activity-types/workout')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['code'] == 'workout'
        assert data['base_xp'] == 50

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_activity_type')
    def test_get_activity_type_not_found(self, mock_get, client):
        """Should return 404 for unknown activity type."""
        mock_get.return_value = None

        response = client.get('/api/config/activity-types/unknown')
        assert response.status_code == 404

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.upsert_activity_type')
    def test_create_activity_type(self, mock_upsert, client):
        """Should create new activity type."""
        mock_upsert.return_value = True

        response = client.put(
            '/api/config/activity-types/new_activity',
            json={'name': 'New Activity', 'area_code': 'work', 'base_xp': 25}
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'
        assert data['activity_type']['code'] == 'new_activity'

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.delete_activity_type')
    def test_delete_activity_type(self, mock_delete, client):
        """Should delete activity type."""
        mock_delete.return_value = True

        response = client.delete('/api/config/activity-types/workout')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'
        assert data['deleted'] == 'workout'


class TestGameConfigEndpoint:
    """Tests for /api/config/game endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_game_config')
    def test_get_all_config(self, mock_get, client):
        """Should return all game configuration values."""
        mock_get.return_value = {
            'DURATION_BONUS_PER_10MIN': 5,
            'DURATION_BONUS_MAX': 25
        }

        response = client.get('/api/config/game')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'config' in data
        assert data['config']['DURATION_BONUS_PER_10MIN'] == 5

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_game_config')
    def test_get_single_config_value(self, mock_get, client):
        """Should return single config value."""
        mock_get.return_value = 5

        response = client.get('/api/config/game/DURATION_BONUS_PER_10MIN')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['key'] == 'DURATION_BONUS_PER_10MIN'
        assert data['value'] == 5

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.set_game_config')
    def test_set_config_value(self, mock_set, client):
        """Should set config value."""
        mock_set.return_value = True

        response = client.put(
            '/api/config/game/NEW_CONFIG',
            json={'value': 100, 'data_type': 'integer', 'category': 'xp'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'
        assert data['value'] == 100


class TestKanbanColumnsEndpoint:
    """Tests for /api/config/kanban-columns endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_kanban_columns')
    def test_get_kanban_columns(self, mock_get, client):
        """Should return kanban column definitions."""
        mock_get.return_value = [
            {'code': 'backlog', 'title': 'Backlog', 'sort_order': 1},
            {'code': 'ready', 'title': 'Ready', 'sort_order': 2}
        ]

        response = client.get('/api/config/kanban-columns')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'columns' in data
        assert data['count'] == 2
        assert data['columns'][0]['code'] == 'backlog'

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.upsert_kanban_column')
    def test_update_kanban_column(self, mock_upsert, client):
        """Should update kanban column."""
        mock_upsert.return_value = True

        response = client.put(
            '/api/config/kanban-columns/blocked',
            json={'title': 'Blocked', 'label': 'Waiting on something', 'sort_order': 6}
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'
        assert data['column']['code'] == 'blocked'


class TestXpRulesEndpoint:
    """Tests for /api/config/xp-rules endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_get_xp_rules(self, mock_get, client):
        """Should return XP calculation rules."""
        mock_get.return_value = [
            {'code': 'commits_today', 'name': 'Daily Commits', 'source': 'git', 'xp_per_unit': 5}
        ]

        response = client.get('/api/config/xp-rules')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'rules' in data
        assert data['rules'][0]['code'] == 'commits_today'

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_get_xp_rules_by_source(self, mock_get, client):
        """Should filter XP rules by source."""
        mock_get.return_value = [
            {'code': 'commits_today', 'source': 'git'}
        ]

        response = client.get('/api/config/xp-rules?source=git')
        assert response.status_code == 200

        mock_get.assert_called_with(source='git', active_only=True)

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.upsert_xp_rule')
    def test_create_xp_rule(self, mock_upsert, client):
        """Should create XP rule."""
        mock_upsert.return_value = True

        response = client.put(
            '/api/config/xp-rules/new_rule',
            json={
                'name': 'New Rule',
                'source': 'custom',
                'area_code': 'work',
                'xp_per_unit': 10,
                'max_xp': 50
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'


class TestPriorityLevelsEndpoint:
    """Tests for /api/config/priority-levels endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_priority_levels')
    def test_get_priority_levels(self, mock_get, client):
        """Should return priority level definitions."""
        mock_get.return_value = [
            {'level': 4, 'code': 'p1', 'name': 'Urgent', 'color': '#ef4444'},
            {'level': 3, 'code': 'p2', 'name': 'High', 'color': '#f97316'}
        ]

        response = client.get('/api/config/priority-levels')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'levels' in data
        assert data['count'] == 2
        assert data['levels'][0]['name'] == 'Urgent'


class TestCalculateDashboardXp:
    """Tests for /api/life/calculate-dashboard-xp endpoint."""

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_calculate_xp_from_commits(self, mock_get_rules, client):
        """Should calculate XP from git commits."""
        mock_get_rules.return_value = [
            {
                'code': 'commits_today',
                'name': 'Daily Commits',
                'source': 'git',
                'area_code': 'work',
                'rule_type': 'count',
                'condition': {'field': 'commit_count'},
                'xp_per_unit': 5,
                'max_xp': 100
            }
        ]

        response = client.post(
            '/api/life/calculate-dashboard-xp',
            json={
                'dashboard': {
                    'git': {'commit_count': 10}
                }
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['status'] == 'ok'
        assert data['total_xp'] == 50  # 10 commits * 5 XP
        assert len(data['awards']) == 1
        assert data['awards'][0]['rule'] == 'commits_today'

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_calculate_xp_with_max_cap(self, mock_get_rules, client):
        """Should cap XP at max value."""
        mock_get_rules.return_value = [
            {
                'code': 'commits_today',
                'source': 'git',
                'area_code': 'work',
                'rule_type': 'count',
                'condition': {'field': 'commit_count'},
                'xp_per_unit': 5,
                'max_xp': 50
            }
        ]

        response = client.post(
            '/api/life/calculate-dashboard-xp',
            json={
                'dashboard': {
                    'git': {'commit_count': 100}  # Would be 500 XP without cap
                }
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['total_xp'] == 50  # Capped at 50

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_calculate_xp_boolean_rule(self, mock_get_rules, client):
        """Should calculate XP for boolean rules."""
        mock_get_rules.return_value = [
            {
                'code': 'sprint_complete',
                'source': 'sprint',
                'area_code': 'work',
                'rule_type': 'boolean',
                'condition': {'field': 'status', 'value': 'completed'},
                'xp_per_unit': 100,
                'max_xp': 100
            }
        ]

        response = client.post(
            '/api/life/calculate-dashboard-xp',
            json={
                'dashboard': {
                    'sprint': {'status': 'completed'}
                }
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['total_xp'] == 100

    @patch('server.DB_AVAILABLE', True)
    @patch('server.db.get_xp_rules')
    def test_calculate_xp_threshold_rule(self, mock_get_rules, client):
        """Should calculate XP for threshold rules."""
        mock_get_rules.return_value = [
            {
                'code': 'steps_goal',
                'source': 'health',
                'area_code': 'health',
                'rule_type': 'threshold',
                'condition': {'field': 'steps', 'threshold': 10000},
                'xp_per_unit': 25,
                'max_xp': 25
            }
        ]

        response = client.post(
            '/api/life/calculate-dashboard-xp',
            json={
                'dashboard': {
                    'health': {'steps': 12500}  # Above threshold
                }
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['total_xp'] == 25


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
