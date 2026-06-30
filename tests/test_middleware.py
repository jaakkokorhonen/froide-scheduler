"""Testit: DBWakeupMiddleware.

Kaikki DB- ja GCP-kutsut mockataan — ei oikeaa yhteyttä tarvita.
"""
import pytest
from unittest.mock import patch
from django.http import HttpResponse

from froide_scheduler.middleware.db_wakeup import DBWakeupMiddleware
import froide_scheduler.middleware.db_wakeup as mw_module


@pytest.fixture(autouse=True)
def reset_globals():
    """Nollaa moduulitason globaalit ennen jokaista testiä."""
    mw_module._db_ready = False
    mw_module._wakeup_in_progress = False
    yield
    mw_module._db_ready = False
    mw_module._wakeup_in_progress = False


def make_middleware(get_response=None):
    if get_response is None:
        def get_response(req):  # noqa: E306
            return HttpResponse('ok')
    return DBWakeupMiddleware(get_response)


class TestBypassPaths:
    def test_health_endpoint_skips_db_check(self, rf):
        """/__health/ ei saa koskaan triggeröidä DB-tarkistusta."""
        middleware = make_middleware()
        request = rf.get('/__health/')
        with patch.object(middleware, '_check_db_alive') as mock_check:
            response = middleware(request)
        mock_check.assert_not_called()
        assert response.status_code == 200

    def test_static_path_skips_db_check(self, rf):
        middleware = make_middleware()
        request = rf.get('/static/app.css')
        with patch.object(middleware, '_check_db_alive') as mock_check:
            response = middleware(request)
        mock_check.assert_not_called()
        assert response.status_code == 200


class TestTriggerLogic:
    def test_trigger_path_with_db_down_returns_503(self, rf):
        """Kirjautumissivu + DB poikki → 503 odotussivu."""
        middleware = make_middleware()
        request = rf.get('/accounts/login/')
        with patch.object(middleware, '_check_db_alive', return_value=False), \
             patch.object(middleware, '_trigger_wakeup') as mock_wakeup:
            response = middleware(request)
        assert response.status_code == 503
        mock_wakeup.assert_called_once()

    def test_trigger_path_with_db_up_passes_through(self, rf):
        """Kirjautumissivu + DB käynnissä → normaali vastaus."""
        middleware = make_middleware()
        request = rf.get('/accounts/login/')
        with patch.object(middleware, '_check_db_alive', return_value=True):
            response = middleware(request)
        assert response.status_code == 200

    def test_cookie_triggers_wakeup_when_db_down(self, rf):
        """db_needed=1 cookie + DB poikki → 503."""
        middleware = make_middleware()
        request = rf.get('/some/page/')
        request.COOKIES['db_needed'] = '1'
        with patch.object(middleware, '_check_db_alive', return_value=False), \
             patch.object(middleware, '_trigger_wakeup'):
            response = middleware(request)
        assert response.status_code == 503

    def test_no_cookie_no_trigger_path_passes_through(self, rf):
        """Normaali pyyntö ilman cookieta → ei DB-tarkistusta."""
        middleware = make_middleware()
        request = rf.get('/some/page/')
        with patch.object(middleware, '_check_db_alive') as mock_check:
            response = middleware(request)
        mock_check.assert_not_called()
        assert response.status_code == 200


class TestCookieHandling:
    def test_sets_cookie_when_login_flag_present(self, rf):
        """_set_db_cookie=True → set_cookie kutsutaan vastaukseen."""
        def get_response(req):
            req._set_db_cookie = True
            return HttpResponse('ok')

        middleware = make_middleware(get_response)
        request = rf.get('/accounts/login/')
        with patch.object(middleware, '_check_db_alive', return_value=True):
            response = middleware(request)
        assert 'db_needed' in response.cookies
        assert response.cookies['db_needed'].value == '1'

    def test_deletes_cookie_when_logout_flag_present(self, rf):
        """_clear_db_cookie=True → delete_cookie kutsutaan."""
        def get_response(req):
            req._clear_db_cookie = True
            return HttpResponse('ok')

        middleware = make_middleware(get_response)
        request = rf.get('/accounts/logout/')
        request.COOKIES['db_needed'] = '1'
        with patch.object(middleware, '_check_db_alive', return_value=True):
            response = middleware(request)
        # delete_cookie asettaa max_age=0
        assert response.cookies['db_needed']['max-age'] == 0
