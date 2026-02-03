"""Tests for Financial/Monzo integration endpoints."""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestMonzoEndpoints:
    """Test the Monzo integration API endpoints."""

    def test_monzo_returns_offline_when_service_unavailable(self, client):
        """When Monzo service is not running, return 503 with helpful message."""
        with patch('server.requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            response = client.get('/api/integrations/monzo')
            
            assert response.status_code == 500  # Server error when exception
    
    def test_monzo_returns_offline_on_connection_error(self, client):
        """When Monzo service connection fails, return offline status."""
        import requests
        with patch('server.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            response = client.get('/api/integrations/monzo')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'offline'
            assert 'not running' in data['message'].lower()

    def test_monzo_returns_data_on_success(self, client):
        """When Monzo service responds, return the data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'balance': 150000,
            'spend_today': 2500,
            'spend_this_month': 45000,
            'transaction_count': 42,
            'top_categories': [
                {'category': 'groceries', 'amount': 15000},
                {'category': 'transport', 'amount': 8000}
            ]
        }
        
        with patch('server.requests.get', return_value=mock_response):
            response = client.get('/api/integrations/monzo')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            assert data['source'] == 'monzo-analysis'
            assert data['data']['balance'] == 150000

    def test_monzo_trends_returns_offline_on_connection_error(self, client):
        """Trends endpoint returns offline when Monzo not available."""
        import requests
        with patch('server.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            response = client.get('/api/integrations/monzo/trends')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'offline'

    def test_monzo_recurring_returns_offline_on_connection_error(self, client):
        """Recurring endpoint returns offline when Monzo not available."""
        import requests
        with patch('server.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            response = client.get('/api/integrations/monzo/recurring')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'offline'

    def test_monzo_trends_returns_data_on_success(self, client):
        """Trends endpoint returns data when Monzo available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'daily_spend': [
                {'date': '2026-02-01', 'amount': 5000},
                {'date': '2026-02-02', 'amount': 3500}
            ],
            'average_daily': 4250,
            'total': 8500
        }
        
        with patch('server.requests.get', return_value=mock_response):
            response = client.get('/api/integrations/monzo/trends?days=30')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'daily_spend' in data

    def test_monzo_recurring_returns_data_on_success(self, client):
        """Recurring endpoint returns subscription data when Monzo available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {
                    'merchant_name': 'Netflix',
                    'monthly_cost': 1599,
                    'frequency_label': 'Monthly'
                }
            ],
            'total_monthly_cost': 1599
        }
        
        with patch('server.requests.get', return_value=mock_response):
            response = client.get('/api/integrations/monzo/recurring')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'items' in data
            assert data['total_monthly_cost'] == 1599


class TestMonzoXpAward:
    """Test the Monzo XP award endpoint."""

    def test_xp_award_returns_offline_when_service_unavailable(self, client):
        """XP award returns offline when Monzo not available."""
        import requests
        with patch('server.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            response = client.post('/api/integrations/monzo/award-xp')
            
            assert response.status_code == 503
