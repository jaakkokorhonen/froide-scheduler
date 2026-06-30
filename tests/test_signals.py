"""Testit: kirjautumissignaalit.

Varmistaa että user_logged_in/out -signaalit asettavat oikeat
liput middleware-cookiekäsittelyä varten.
"""
import pytest
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import RequestFactory

import froide_scheduler.signals  # noqa: F401 — rekisteröi signaalit


@pytest.fixture
def rf():
    return RequestFactory()


class TestSignals:
    def test_login_sets_db_cookie_flag(self, rf):
        """user_logged_in → request._set_db_cookie = True."""
        request = rf.get('/')
        user_logged_in.send(sender=object, request=request, user=object())
        assert getattr(request, '_set_db_cookie', False) is True

    def test_logout_sets_clear_cookie_flag(self, rf):
        """user_logged_out → request._clear_db_cookie = True."""
        request = rf.get('/')
        user_logged_out.send(sender=object, request=request, user=object())
        assert getattr(request, '_clear_db_cookie', False) is True
