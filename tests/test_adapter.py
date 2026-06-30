"""Testit: DomainRestrictedSocialAccountAdapter.

Kriittisin testi: GitHub-kirjautuminen ei saa estyä vaikka
GOOGLE_SSO_DOMAIN olisi asetettu (PR #8 -bugikorjauksen regressiotesti).
"""
import pytest
from unittest.mock import MagicMock, patch
from django.core.exceptions import PermissionDenied

from froide_scheduler.sso.adapter import DomainRestrictedSocialAccountAdapter


def make_sociallogin(provider, email):
    sociallogin = MagicMock()
    sociallogin.account.provider = provider
    sociallogin.account.extra_data = {'email': email}
    return sociallogin


@pytest.fixture
def adapter():
    return DomainRestrictedSocialAccountAdapter()


class TestDomainRestriction:
    def test_google_matching_domain_allowed(self, adapter):
        """Google + oikea domain → kirjautuminen sallittu."""
        sociallogin = make_sociallogin('google', 'user@domain.fi')
        with patch.dict('os.environ', {'GOOGLE_SSO_DOMAIN': 'domain.fi'}), \
             patch.object(adapter.__class__.__bases__[0], 'pre_social_login'):
            adapter.pre_social_login(MagicMock(), sociallogin)  # ei nosta

    def test_google_wrong_domain_blocked(self, adapter):
        """Google + väärä domain → PermissionDenied."""
        sociallogin = make_sociallogin('google', 'user@gmail.com')
        with patch.dict('os.environ', {'GOOGLE_SSO_DOMAIN': 'domain.fi'}):
            with pytest.raises(PermissionDenied):
                adapter.pre_social_login(MagicMock(), sociallogin)

    def test_github_bypasses_domain_restriction(self, adapter):
        """GitHub + GOOGLE_SSO_DOMAIN asetettu → EI PermissionDenied.

        Regressiotesti PR #8:n bugikorjaukselle: ennen korjausta tämä
        testi olisi epäonnistunut ja paljastanut bugin ennen mergettä.
        """
        sociallogin = make_sociallogin('github', 'user@gmail.com')
        with patch.dict('os.environ', {'GOOGLE_SSO_DOMAIN': 'domain.fi'}), \
             patch.object(adapter.__class__.__bases__[0], 'pre_social_login'):
            adapter.pre_social_login(MagicMock(), sociallogin)  # ei nosta

    def test_google_no_domain_restriction_allows_all(self, adapter):
        """Ilman GOOGLE_SSO_DOMAIN → kaikki Google-tilit sallittu."""
        sociallogin = make_sociallogin('google', 'anyone@gmail.com')
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(adapter.__class__.__bases__[0], 'pre_social_login'):
            adapter.pre_social_login(MagicMock(), sociallogin)  # ei nosta
