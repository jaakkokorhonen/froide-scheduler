"""Google- ja GitHub SSO -konfiguraatio Froide-asennukselle.

Lisää settings_gcp.py:hin:

    from froide_scheduler.sso.settings import *  # noqa

Tai kopioi muuttujat suoraan.
"""
import os

# ---------------------------------------------------------------------------
# Installed apps — lisätään Froiden olemassa olevan listan perään
# ---------------------------------------------------------------------------
INSTALLED_APPS = list(INSTALLED_APPS) + [  # noqa: F821
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
]

# ---------------------------------------------------------------------------
# Authentication backends
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = list(AUTHENTICATION_BACKENDS) + [  # noqa: F821
    "allauth.account.auth_backends.AuthenticationBackend",
]

# ---------------------------------------------------------------------------
# django-allauth: yleiset asetukset
# ---------------------------------------------------------------------------
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_VERIFICATION = "none"  # Google/GitHub vahvistaa sähköpostin jo
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# Kirjautumisen jälkeen ohjataan Froiden etusivulle
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------------------------
# Sessio: 3 tuntia, nollautuu aktiivisesta käytöstä
#
# SESSION_COOKIE_AGE: sessio vanhenee 3h viimeisestä aktiviteetista
# SESSION_SAVE_EVERY_REQUEST: pidentää kellon joka pyynnyllä, joten
#   aktiivisesti käyttävä ei joudu kirjautumaan uudelleen
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE = 10800  # 3 * 60 * 60 = 10 800 sekuntia
SESSION_SAVE_EVERY_REQUEST = True

# ---------------------------------------------------------------------------
# Google OAuth2 -provider
# ---------------------------------------------------------------------------
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
        # Rajoita kirjautuminen tiettyyn Google Workspace -domainiin.
        # Jätä tyhjäksi jos mitä tahansa Google-tiliä voi käyttää.
        # Aseta ympäristömuuttujalla GOOGLE_SSO_DOMAIN=yourdomain.fi
        "ALLOWED_DOMAINS": [
            d for d in [os.environ.get("GOOGLE_SSO_DOMAIN", "")] if d
        ],
    },
    "github": {
        "SCOPE": ["user:email"],
        # GitHub ei tue PKCE OAuth-flowssa, jätetään pois
    },
}

# Vaaditaan sähköposti jokaiselta social-tililtä
SOCIALACCOUNT_EMAIL_REQUIRED = True
# Älä luo duplikaatteja jos sama email on jo rekisteröity
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# ---------------------------------------------------------------------------
# Allauth middleware — lisätään automaattisesti jos ei jo mukana
# ---------------------------------------------------------------------------
_allauth_middleware = "allauth.account.middleware.AccountMiddleware"
if _allauth_middleware not in MIDDLEWARE:  # noqa: F821
    MIDDLEWARE = list(MIDDLEWARE) + [_allauth_middleware]  # noqa: F821
