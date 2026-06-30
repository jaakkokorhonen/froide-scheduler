"""Minimiasetukset pytest-django-testejä varten.

Ei oikeaa DB:tä eikä GCP-yhteyttä — kaikki ulkoiset riippuvuudet
mockataan testeissä.
"""
SECRET_KEY = 'test-secret-key-not-used-in-production'
DEBUG = True

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'froide_scheduler.sso',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SITE_ID = 1

GCP_PROJECT_ID = 'test-project'
CLOUD_SQL_INSTANCE_NAME = 'test-instance'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
