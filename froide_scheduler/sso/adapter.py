"""Mukautettu allauth-adapteri Google SSO:lle.

Oletuksena kirjautuminen on auki kaikille Google-tileille.
SSO-käyttäjä saa täsmälleen saman lupatason kuin tavallisella
lomakkeella rekisteröitynyt kansalainen — ei lisäoikeuksia.

Domain-rajoitus aktivoituu asettamalla ympäristömuuttuja:
    GOOGLE_SSO_DOMAIN=yourdomain.fi

Rajoitus koskee VAIN Google-providerilla kirjautuvia. GitHub-
kirjautumiseen ei koskaan sovelleta domain-rajoitusta.

Ks. AUTHENTICATION.md tarkempi selitys.
"""
import os

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import PermissionDenied


class DomainRestrictedSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google SSO -adapteri Froide-portaalille.

    Toiminta:
    - Ilman GOOGLE_SSO_DOMAIN: kaikki Google-tilit sallittu (kansalaiskäyttö)
    - GOOGLE_SSO_DOMAIN asetettu: vain kyseisen domainin tilit sallittu

    Domain-rajoitus koskee VAIN Google-providerilla kirjautuvia.
    GitHub-kirjautuminen ei koskaan rajoitu tässä adapterissa.

    save_user()-ylikirjoitusta ei tarvita: alloauthin oletustoteutus
    luo käyttäjän is_active=True, is_staff=False, is_superuser=False —
    täsmälleen oikea lupataso kansalaiskäyttäjälle.
    """

    def pre_social_login(self, request, sociallogin):
        if sociallogin.account.provider == 'google':
            allowed_domain = os.environ.get("GOOGLE_SSO_DOMAIN", "")
            if allowed_domain:
                email = sociallogin.account.extra_data.get("email", "")
                if not email.endswith(f"@{allowed_domain}"):
                    raise PermissionDenied(
                        f"Kirjautuminen sallittu vain @{allowed_domain} -osoitteille."
                    )
        super().pre_social_login(request, sociallogin)
