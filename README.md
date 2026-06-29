# froide-scheduler

Cloud SQL:n automaattinen sammutus ja herätys Froide-asennuksille (Google Cloud Platform).

Ajetaan Froide-asennuksen päälle patchina — ei muokkaa Froide-ydintä.

## Miksi
Cloud SQL:n automaattinen sammutus/herätys ja Google SSO Froide-asennuksille (Google Cloud Platform).

Ajetaan Froide-asennuksen päälle patchina — ei muokkaa Froide-ydintä.

## Ominaisuudet

- **DBWakeupMiddleware** — herättää Cloud SQL:n automaattisesti kun kirjautunut käyttäjä tai kirjautumissivu havaitaan
- **`check_and_shutdown_db`** — sammuttaa Cloud SQL:n jos ei aktiivisia sessioita
- **`/__health/`** — sisäinen endpoint jonka selain pollaa odotussivulla kunnes DB on valmis
- **Google SSO** — django-allauth-pohjainen OAuth2-kirjautuminen, domain-rajoituksella

Cloud SQL `db-f1-micro` maksaa ~$12/kk pyöriessään jatkuvasti. Suurin osa tästä ajasta kanta on tyhjäkäynnillä. Tämä paketti sammuttaa kannan automaattisesti inaktiivin aikana ja herättää sen tarvittaessa.

**Säästö: ~$10/kk** (730h → ~30h/kk laskutettava käyttöaika)

## Hyväksytty haitta

Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa kannan käynnistymistä **1–3 minuuttia**. Käyttäjälle näytetään odotussivu automaattisesti. Tämä on tietoinen kompromissi, dokumentoitu [`DECISIONS.md`](DECISIONS.md):ssä.
Cloud SQL `db-f1-micro`: ~$12/kk → ~$2/kk kun sammutettuna inaktiivina. **Säästö ~$10/kk.**

## Hyväksytty haitta

Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa **1–3 minuuttia** kannan käynnistymistä. Käyttäjälle näytetään odotussivu automaattisesti. Dokumentoitu [`DECISIONS.md`](DECISIONS.md):ssä.

## Repon rakenne

```
froide-scheduler/
├── froide_scheduler/
│   ├── __init__.py
│   ├── signals.py                        # user_logged_in/out → db_needed-cookie
│   ├── urls.py                           # /__health/ -reitti
│   ├── middleware/
│   │   └── db_wakeup.py                  # Päälogiikka: havaitsee tarpeen, herättää DB:n
│   ├── views/
│   │   └── health.py                     # /__health/ — selain pollaa tätä odotussivulta
│   └── management/
│       └── commands/
│           └── check_and_shutdown_db.py  # Sammuttaa jos ei sessioita
│   ├── signals.py                             # user_logged_in/out → db_needed-cookie
│   ├── urls.py                                # /__health/ -reitti
│   ├── middleware/
│   │   └── db_wakeup.py                       # Päälogiikka: havaitsee tarpeen, herättää DB:n
│   ├── views/
│   │   └── health.py                          # /__health/ — selain pollaa tätä odotussivulta
│   ├── management/
│   │   └── commands/
│   │       └── check_and_shutdown_db.py       # Sammuttaa jos ei sessioita
│   └── sso/
│       ├── settings.py                        # INSTALLED_APPS, SOCIALACCOUNT_PROVIDERS jne.
│       ├── urls.py                            # allauth.urls -sisällytys
│       ├── adapter.py                         # Domain-rajoitus (GOOGLE_SSO_DOMAIN)
│       └── migrations/
│           └── 0001_google_socialapp.py       # Datamigration: luo SocialApp env-muuttujista
├── setup.py
├── DECISIONS.md
└── README.md
```

## Miten toimii

### Cloud SQL -herätys

```
Käyttäjä → Django (Cloud Run)
              ↓
         DBWakeupMiddleware
              ↓ onko db_needed-cookie tai kirjautumissivu?
         Kyllä → onko DB käynnissä?
              ↓ Ei
         → Kutsu Cloud SQL Admin API: activationPolicy=ALWAYS
         → Cloud SQL Admin API: activationPolicy=ALWAYS
         → Palauta 503 + odotussivu (pollaa /__health/ 5s välein)
              ↓ DB herää (1–3 min)
         → Selain ohjataan takaisin alkuperäiseen osoitteeseen
```

Kannan sammutus:
```
Cloud Scheduler klo 16:00
### Cloud SQL -sammutus

```
Cloud Scheduler klo 16:00 EET
    → python manage.py check_and_shutdown_db
    → Aktiivisia sessioita? Ei → activationPolicy=NEVER
```

### Google SSO

```
Käyttäjä → /accounts/google/login/
    → Google OAuth2 (PKCE)
    → Paluu /accounts/google/login/callback/
    → DomainRestrictedSocialAccountAdapter tarkistaa @domain.fi
    → allauth luo tai yhdistää Django-käyttäjään
    → Ohjaus LOGIN_REDIRECT_URL:iin (/)
```

## Aikajana (EET)

| Aika | Tapahtuma |
|------|-----------|
| 15:00 | Cloud Scheduler käynnistää Cloud SQL:n (`activationPolicy=ALWAYS`) |
| 15:00–15:03 | DB herää, Froide vastaa normaalisti |
| 16:00 | `check_and_shutdown_db` tarkistaa sessiot |
| 16:00 (ei käyttäjiä) | Cloud SQL sammutetaan (`activationPolicy=NEVER`) |
| Milloin tahansa | Käyttäjä kirjautuu → DBWakeupMiddleware herättää DB:n |

---

## Asennus

### 1. Asenna paketti

```bash
pip install git+https://github.com/jaakkokorhonen/froide-scheduler.git
```

### 2. Lisää `settings_gcp.py`

```python
GCP_PROJECT_ID = env('GCP_PROJECT_ID')           # esim. 'froide-prod'
### 2. Cloud SQL -herätys: `settings_gcp.py`

```python
GCP_PROJECT_ID = env('GCP_PROJECT_ID')               # esim. 'froide-prod'
CLOUD_SQL_INSTANCE_NAME = env('CLOUD_SQL_INSTANCE')  # esim. 'froide-db'

MIDDLEWARE = [
    'froide_scheduler.middleware.db_wakeup.DBWakeupMiddleware',  # TÄYTYY OLLA ENSIMMÄINEN
    'django.middleware.security.SecurityMiddleware',
    # ...muut middlewaret
]
```

### 3. Lisää `urls.py`
### 3. Cloud SQL -herätys: `urls.py`

```python
from froide_scheduler.urls import urlpatterns as scheduler_urls

urlpatterns = [
    *scheduler_urls,
    # ...muut
]
```

### 4. Rekisteröi signaalit `AppConfig.ready()`-metodissa
### 4. Cloud SQL -herätys: signaalit

```python
# myapp/apps.py
class MyAppConfig(AppConfig):
    def ready(self):
        from froide_scheduler import signals  # noqa: F401
```

### 5. Ympäristömuuttujat

```
GCP_PROJECT_ID=froide-prod
CLOUD_SQL_INSTANCE=froide-db
```

Cloud Run -palvelutilillä täytyy olla `cloudsql.instances.update` -oikeus (rooli: `Cloud SQL Editor`).

### 6. Cloud Scheduler -ajastimet

```bash
### 5. Google SSO: `settings_gcp.py`

```python
from froide_scheduler.sso.settings import *  # noqa

# Valinnainen: rajoita kirjautuminen yhteen domainiin
# (vaihtoehtoisesti aseta ympäristömuuttujalla GOOGLE_SSO_DOMAIN)
SOCIALACCOUNT_ADAPTER = "froide_scheduler.sso.adapter.DomainRestrictedSocialAccountAdapter"
```

### 6. Google SSO: `urls.py`

```python
from froide_scheduler.sso.urls import urlpatterns as sso_urlpatterns

urlpatterns = [
    *sso_urlpatterns,   # /accounts/... allauth-reitit
    *scheduler_urls,    # /__health/
    # ...muut
]
```

### 7. Aja migraatiot

```bash
python manage.py migrate
# Luo Google SocialApp automaattisesti jos GOOGLE_OAUTH_CLIENT_ID ja
# GOOGLE_OAUTH_CLIENT_SECRET on asetettu ympäristömuuttujiin.
```

### 8. Ympäristömuuttujat

```
# Cloud SQL
GCP_PROJECT_ID=froide-prod
CLOUD_SQL_INSTANCE=froide-db

# Google SSO — hae GCP Console → APIs & Services → Credentials
GOOGLE_OAUTH_CLIENT_ID=123456789-xxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxx

# Valinnainen: rajoita kirjautuminen yhteen domainiin
GOOGLE_SSO_DOMAIN=yourdomain.fi
```

**GCP-suositus:** tallenna secrets Secret Manageriin ja injektoi Cloud Runiin:

```bash
gcloud run services update froide \
  --set-secrets=GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest,\
GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest \
  --region=europe-north1
```

### 9. Cloud Scheduler -ajastimet

```bash
# Käynnistä DB klo 15:00 EET (UTC 12:00)
gcloud scheduler jobs create http froide-db-start \
  --schedule="0 12 * * *" \
  --uri="https://sqladmin.googleapis.com/v1/projects/${PROJECT_ID}/instances/${INSTANCE}" \
  --message-body='{"settings":{"activationPolicy":"ALWAYS"}}' \
  --http-method=PATCH \
  --oauth-service-account-email=${SA_EMAIL} \
  --location=europe-north1

# Tarkista sessiot ja sammuta tarvittaessa klo 16:00 EET (UTC 13:00)
# Aja Cloud Run Job -muodossa:
gcloud scheduler jobs create http froide-db-shutdown-check \
  --schedule="0 13 * * *" \
  --uri="https://${CLOUD_RUN_JOB_URL}" \
  --location=europe-north1
```

Tai aja `check_and_shutdown_db` suoraan Cloud Run Jobina:

```bash
gcloud run jobs create froide-shutdown-check \
  --image=${IMAGE} \
  --command="python" \
  --args="manage.py,check_and_shutdown_db" \
  --region=europe-north1
# Sammuta klo 16:00 EET (UTC 13:00) — Cloud Run Job
gcloud run jobs create froide-shutdown-check \
  --image=${IMAGE} \
  --command=python \
  --args="manage.py,check_and_shutdown_db" \
  --region=europe-north1

gcloud scheduler jobs create http froide-db-shutdown-check \
  --schedule="0 13 * * *" \
  --uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/europe-north1/jobs/froide-shutdown-check:run" \
  --http-method=POST \
  --oauth-service-account-email=${SA_EMAIL} \
  --location=europe-north1
```

### 10. IAM-oikeudet

Cloud Run -palvelutilillä täytyy olla:

| Rooli | Miksi |
|---|---|
| `roles/cloudsql.editor` | Cloud SQL käynnistys/sammutus |
| `roles/run.invoker` | Cloud Scheduler → Cloud Run Job |

```bash
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member=serviceAccount:${SA_EMAIL} \
  --role=roles/cloudsql.editor
```

## Riippuvuudet

- Django >= 4.2
- google-auth >= 2.0
- google-api-python-client >= 2.0
- django-allauth >= 0.63

## Lisenssi

MIT
