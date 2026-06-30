"""Testit: /__health/ -endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.db import OperationalError

from froide_scheduler.views.health import health_check


@pytest.fixture
def rf():
    return RequestFactory()


class TestHealthCheck:
    def test_returns_200_when_db_ok(self, rf):
        """DB vastaa → HTTP 200, body 'ok'."""
        request = rf.get('/__health/')
        mock_conn = MagicMock()
        with patch('froide_scheduler.views.health.connections') as mock_conns:
            mock_conns.__getitem__.return_value = mock_conn
            response = health_check(request)
        assert response.status_code == 200
        assert response.content == b'ok'

    def test_returns_503_when_db_down(self, rf):
        """DB ei vastaa → HTTP 503, body 'db_unavailable'."""
        request = rf.get('/__health/')
        mock_conn = MagicMock()
        mock_conn.ensure_connection.side_effect = OperationalError('connection refused')
        with patch('froide_scheduler.views.health.connections') as mock_conns:
            mock_conns.__getitem__.return_value = mock_conn
            response = health_check(request)
        assert response.status_code == 503
        assert response.content == b'db_unavailable'
