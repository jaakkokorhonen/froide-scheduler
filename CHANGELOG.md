# Changelog

Kaikki merkittävät muutokset dokumentoidaan tässä tiedostossa.

## [1.0.0] - 2026-06-30

Initial untested release.

### Sisältö

- `DBWakeupMiddleware` — herättää Cloud SQL -instanssin automaattisesti kun käyttäjä pyytää kirjautumissivua tai kantaa tarvitsevaa URL:ia
- `check_and_shutdown_db` management command — sammuttaa Cloud SQL:n Cloud Scheduler -ajastetulla kutsulla jos aktiivisia sessioita ei ole
- Google SSO -integraatio (`django-allauth`) migraatioineen
- `pyproject.toml`-paketointi (PEP 517/518)
