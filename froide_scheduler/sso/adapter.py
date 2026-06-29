"""Mukautettu allauth-adapteri domain-rajoitukselle.

Rajoittaa Google SSO:n tiettyyn sähköpostdomainiin kun
GOOGLE_SSO_DOMAIN-ympäristömuuttuja on asetettu.

Lisää settings_gcp.py:hin:

    SOCIALACCOUNT_ADAPTER = "froide_scheduler.sso.adapter.DomainRestrictedSocialAccountAdapter"
"""
import os

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import PermissionDenied


class DomainRestrictedSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Sallii kirjautumisen vain GOOGLE_SSO_DOMAIN-muuttujan domainista.

    Jos muuttujaa ei ole asetettu, kaikki Google-tilit sallitaan
    (kehitysympäristö / tarkoituksellinen julkinen käyttö).
    """

    def pre_social_login(self, request, sociallogin):
        allowed_domain = os.environ.get("GOOGLE_SSO_DOMAIN", "")
        if not allowed_domain:
            return  # Ei rajoitusta

        email = sociallogin.account.extra_data.get("email", "")
        if not email.endswith(f"@{allowed_domain}"):
            raise PermissionDenied(
                f"Kirjautuminen sallittu vain @{allowed_domain} -osoitteille."
            )

        super().pre_social_login(request, sociallogin)
