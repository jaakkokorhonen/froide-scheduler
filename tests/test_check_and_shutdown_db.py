"""Testit: check_and_shutdown_db management command.

API-kutsut ja Session-queryt mockataan — ei oikeaa DB:tä tai GCP:tä.
"""
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from django.core.management import call_command


class TestCheckAndShutdownDb:
    def test_active_sessions_skips_api(self):
        """Aktiivisia sessioita → Cloud SQL API:ta ei kutsuta."""
        mock_service = MagicMock()
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.google.auth.default',
              return_value=(MagicMock(), None)), \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.googleapiclient.discovery.build',
              return_value=mock_service):
            mock_qs.filter.return_value.count.return_value = 2
            out = StringIO()
            call_command('check_and_shutdown_db', stdout=out)
        mock_service.instances.assert_not_called()
        assert 'pysyy päällä' in out.getvalue()

    def test_no_sessions_calls_api_with_never(self):
        """Ei sessioita → API kutsutaan activationPolicy=NEVER."""
        mock_service = MagicMock()
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.google.auth.default',
              return_value=(MagicMock(), None)), \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.googleapiclient.discovery.build',
              return_value=mock_service):
            mock_qs.filter.return_value.count.return_value = 0
            out = StringIO()
            call_command('check_and_shutdown_db', stdout=out)
        mock_service.instances().patch.assert_called_once()
        call_kwargs = mock_service.instances().patch.call_args
        assert call_kwargs.kwargs['body'] == {'settings': {'activationPolicy': 'NEVER'}}
        assert 'sammutettu' in out.getvalue()

    def test_api_failure_raises(self):
        """API-kutsu epäonnistuu → komento nostaa poikkeuksen.

        Cloud Scheduler näkee epäonnistumisen eikä sammutus jää
        hiljaa huomaamatta.
        """
        mock_service = MagicMock()
        mock_service.instances().patch().execute.side_effect = Exception('API error')
        with patch(
            'froide_scheduler.management.commands.check_and_shutdown_db.Session.objects'
        ) as mock_qs, \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.google.auth.default',
              return_value=(MagicMock(), None)), \
        patch('froide_scheduler.management.commands.check_and_shutdown_db.googleapiclient.discovery.build',
              return_value=mock_service):
            mock_qs.filter.return_value.count.return_value = 0
            with pytest.raises(Exception, match='API error'):
                call_command('check_and_shutdown_db', stdout=StringIO())
