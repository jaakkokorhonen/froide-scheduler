# Changelog

Kaikki merkittävät muutokset dokumentoidaan tässä tiedostossa.

## [1.0.0] - 2026-06-30

Initial untested release.

### Tietoturva ja luotettavuus (PR #11)

- **fix:** XSS-haavoittuvuus `next_url`-injektiossa — korvattu `repr()` → `json.dumps()`
- **fix:** Säikeistörsyinen `_db_ready` globaali korvattu `threading.Event` + TTL-rakenteella
- **fix:** `OperationalError` DB-yhteyskatkon yhteydessä käsitellään siististi 503-vastaukseksi
- **fix:** `check_and_shutdown_db` käsittelee `OperationalError` session-kyselyssä (DB jo sammunut)
- **fix:** Sammutuksen jälkeen `_db_ready`-tila nollaantuu automaattisesti
- **refactor:** Jaettu Cloud SQL `set_activation_policy()`-helper (`froide_scheduler/cloud_sql.py`)
- **test:** Testit päivitetty Event-rakenteeseen + uudet testit XSS, TTL, OperationalError-poluille
- **build:** `pyproject.toml` lisätty (PEP 517/518), `setup.py` ohennettu shimiksi

### Testit ja CI (PR #10)

- **feat:** 16 yksikkötestiä `DBWakeupMiddleware`- ja `check_and_shutdown_db`-toiminnoille
- **feat:** GitHub Actions CI-pipeline — lint + test matrix Python 3.10–3.12

### Dokumentaatio (PR #9)

- **docs:** Lisätty lokaalikehityshuomio `ACCOUNT_DEFAULT_HTTP_PROTOCOL`-asetuksesta

### Korjaukset (PR #8)

- **fix:** Adapter provider-tarkistus — estetään domain-bypass
- **fix:** Health check docstring korjattu
- **fix:** Migration symmetria
- **fix:** `setup.py` siivottu

### Dokumentaatio (PR #7)

- **docs:** nginx-konfiguraatio-osio lisätty README:hen
- **docs:** `django.contrib.sites`-riippuvuus dokumentoitu
- **docs:** Cookie-aika ja polling-viive selitetty

### AppConfig ja dokumentaatio (PR #6)

- **fix:** Eksplisiittinen `AppConfig` SSO-pakkaukselle (`app_label='froide_scheduler_sso'`)
- **docs:** `AUTHENTICATION.md` lisätty
- **docs:** Dokumentaatioristiriidat korjattu (sammutusaika, API-versio, INSTALLED_APPS)
- **docs:** `_db_ready` per-instanssi -käyttäytyminen dokumentoitu `DECISIONS.md`:hen

### Sessiot ja ajastus (PR #4 + #5)

- **feat:** `check_and_shutdown_db` ajetaan joka tunnin :45 (aiemmin vain klo 16:00)
- **feat:** `SESSION_COOKIE_AGE=3h`, `SESSION_SAVE_EVERY_REQUEST=True`

### Google ja GitHub SSO (PR #3)

- **feat:** Google SSO `django-allauth`-pohjaisella konfiguraatiolla
- **feat:** GitHub SSO rinnakkaiseksi provideriksi (kansalaistaso)
- **feat:** Migraatiot `SocialApp`-objektien luontiin

### Dokumentaatio (PR #2)

- **docs:** README päivitetty vastaamaan repon todellista rakennetta
- **docs:** Google SSO -osio README:hen

### Perustoiminnallisuus (PR #1)

- **feat:** `DBWakeupMiddleware` — herättää Cloud SQL -instanssin automaattisesti kun käyttäjä pyytää kirjautumissivua tai kantaa tarvitsevaa URL:ia; palauttaa 503-odotussivun kunnes kanta on käynnissä
- **feat:** `check_and_shutdown_db` management command — sammuttaa Cloud SQL:n Cloud Scheduler -ajastetulla kutsulla jos aktiivisia sessioita ei ole
- **feat:** `/__health/`-endpoint DB-tilan tarkistukseen
- **feat:** `DECISIONS.md` arkkitehtuuripäätösten dokumentointiin
