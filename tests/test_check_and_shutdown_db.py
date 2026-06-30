"""Testit: check_and_shutdown_db management command.

API-kutsut ja Session-queryt mockataan — ei oikeaa DB:tä tai GCP:tä.
"""
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from django.core.management import call_command
from django.db import OperationalError

import froide_scheduler.middleware.db_wakeup as mw_module


@pytest.fixture(autouse=True)
def reset_db_state():
    """Nollaa middleware-tila ennen jokaista testiä."""
    mw_module._db_ready_event.clear()
    mw_module._db_last_confirmed = 0.0
    yield
    mw_module._db_ready_event.clear()
    mw_module._db_last_confirmed = 0.0


class TestCheckAndShutdownDb:
    def test_active_sessions_skips_api(self):
        """Aktiivisia sessioita → Cloud SQL API:ta ei kutsuta."""
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.cloud_sql.set_activation_policy') as mock_policy:
            mock_qs.filter.return_value.count.return_value = 2
            out = StringIO()
            call_command('check_and_shutdown_db', stdout=out)
        mock_policy.assert_not_called()
        assert 'pysyy päällä' in out.getvalue()

    def test_no_sessions_calls_policy_never(self):
        """Ei sessioita → set_activation_policy('NEVER') kutsutaan."""
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.cloud_sql.set_activation_policy') as mock_policy:
            mock_qs.filter.return_value.count.return_value = 0
            out = StringIO()
            call_command('check_and_shutdown_db', stdout=out)
        mock_policy.assert_called_once_with('NEVER')
        assert 'sammutettu' in out.getvalue()

    def test_no_sessions_clears_db_state(self):
        """Sammutuksen jälkeen _db_ready_event pitää olla clear."""
        from froide_scheduler.middleware.db_wakeup import _mark_db_ready
        _mark_db_ready()  # simuloidaan että middleware luulee DB:n olevan päällä
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.cloud_sql.set_activation_policy'):
            mock_qs.filter.return_value.count.return_value = 0
            call_command('check_and_shutdown_db', stdout=StringIO())
        assert not mw_module._db_ready_event.is_set()

    def test_api_failure_raises(self):
        """API-kutsu epäonnistuu → komento nostaa poikkeuksen."""
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.cloud_sql.set_activation_policy',
              side_effect=Exception('API error')):
            mock_qs.filter.return_value.count.return_value = 0
            with pytest.raises(Exception, match='API error'):
                call_command('check_and_shutdown_db', stdout=StringIO())

    def test_operational_error_on_session_query_exits_gracefully(self):
        """DB ei vastaa session-kyselyssä → varoitus, ei poikkeusta."""
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.cloud_sql.set_activation_policy') as mock_policy:
            mock_qs.filter.side_effect = OperationalError('db down')
            out = StringIO()
            call_command('check_and_shutdown_db', stdout=out)
        mock_policy.assert_not_called()
        assert 'DB ei vastaa' in out.getvalue()
