# froide-scheduler

Cloud SQL:n automaattinen sammutus/herätys ja Google/GitHub SSO Froide-asennuksille (Google Cloud Platform).

Ajetaan Froide-asennuksen päälle patchina — ei muokkaa Froide-ydintä.

## Miksi

Cloud SQL `db-f1-micro` maksaa ~$12/kk pyöriessään jatkuvasti. Suurin osa tästä ajasta kanta on tyhjäkäynnillä. Tämä paketti sammuttaa kannan automaattisesti inaktiivin aikana ja herättää sen tarvittaessa.

**Säästö: ~$10/kk** (730h → ~30h/kk laskutettava käyttöaika)

## Hyväksytty haitta

Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa kannan käynnistymistä **1–3 minuuttia**. Käyttäjälle näytetään odotussivu automaattisesti. Tämä on tietoinen kompromissi — katso [`DECISIONS.md`](DECISIONS.md).

## Ominaisuudet

- **DBWakeupMiddleware** — herättää Cloud SQL:n automaattisesti kun kirjautunut käyttäjä tai kirjautumissivu havaitaan
- **`check_and_shutdown_db`** — sammuttaa Cloud SQL:n jos ei aktiivisia sessioita
- **`/__health/`** — sisäinen endpoint jonka selain pollaa odotussivulla kunnes DB on valmis
- **Google SSO** — kaikille Gmail-tileille, domain-rajoitus valinnaisella `GOOGLE_SSO_DOMAIN`-muuttujalla
- **GitHub SSO** — kaikille GitHub-tileille, admin-oikeudet myönnetään erikseen

## Repon rakenne

```
froide-scheduler/
├── froide_scheduler/
│   ├── signals.py                        # user_logged_in/out → db_needed-cookie
│   ├── urls.py                           # /__health/ -reitti
│   ├── middleware/
│   │   └── db_wakeup.py                  # Päälogiikka: havaitsee tarpeen, herättää DB:n
│   ├── views/
│   │   └── health.py                     # /__health/ — selain pollaa tätä odotussivulta
│   ├── management/
│   │   └── commands/
│   │       └── check_and_shutdown_db.py  # Sammuttaa jos ei sessioita
│   └── sso/
│       ├── settings.py                   # INSTALLED_APPS, SOCIALACCOUNT_PROVIDERS jne.
│       ├── urls.py                       # allauth.urls -sisällytys
│       ├── adapter.py                    # Domain-rajoitus (GOOGLE_SSO_DOMAIN)
│       └── migrations/
│           ├── 0001_google_socialapp.py  # Luo Google SocialApp env-muuttujista
│           └── 0002_github_socialapp.py  # Luo GitHub SocialApp env-muuttujista
├── AUTHENTICATION.md
├── DECISIONS.md
├── setup.py
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
         → Palauta 503 + odotussivu (pollaa /__health/ 5s välein)
              ↓ DB herää (1–3 min)
         → Selain ohjataan takaisin alkuperäiseen osoitteeseen
```

### Cloud SQL -sammutus

```
Cloud Scheduler (päivittäin klo 16:00 EET)
    → python manage.py check_and_shutdown_db
    → Aktiivisia sessioita? Ei → activationPolicy=NEVER
```

### Google/GitHub SSO

Ks. [`AUTHENTICATION.md`](AUTHENTICATION.md) — kirjautumisvirrat, lupataso, domain-rajoitus ja admin-oikeuksien myöntäminen.

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

### 3. Cloud SQL -herätys: `urls.py`

```python
from froide_scheduler.urls import urlpatterns as scheduler_urls

urlpatterns = [
    *scheduler_urls,  # /__health/
    # ...muut
]
```

### 4. Rekisteröi signaalit

```python
# myapp/apps.py
class MyAppConfig(AppConfig):
    def ready(self):
        from froide_scheduler import signals  # noqa: F401
```

### 5. Google/GitHub SSO: `settings_gcp.py`

```python
from froide_scheduler.sso.settings import *  # noqa

# Valinnainen: rajoita Google-kirjautuminen yhteen domainiin
# (vaihtoehtoisesti aseta ympäristömuuttujalla GOOGLE_SSO_DOMAIN)
SOCIALACCOUNT_ADAPTER = "froide_scheduler.sso.adapter.DomainRestrictedSocialAccountAdapter"
```

### 6. Google/GitHub SSO: `urls.py`

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
# Luo Google ja GitHub SocialApp-objektit automaattisesti
# jos OAuth-ympäristömuuttujat on asetettu.
```

### 8. Ympäristömuuttujat

```
# Cloud SQL
GCP_PROJECT_ID=froide-prod
CLOUD_SQL_INSTANCE=froide-db

# Google SSO — hae: GCP Console → APIs & Services → Credentials
# Ohje: https://developers.google.com/identity/protocols/oauth2
GOOGLE_OAUTH_CLIENT_ID=123456789-xxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxx

# GitHub SSO — hae: github.com → Settings → Developer settings → OAuth Apps
# Ohje: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app
GITHUB_OAUTH_CLIENT_ID=Iv1.xxx
GITHUB_OAUTH_CLIENT_SECRET=xxx

# Valinnainen: rajoita Google-kirjautuminen yhteen domainiin
GOOGLE_SSO_DOMAIN=yourdomain.fi
```

**GCP-suositus:** tallenna secrets Secret Manageriin ja injektoi Cloud Runiin:

```bash
gcloud run services update froide \
  --set-secrets=GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest,\
GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest,\
GITHUB_OAUTH_CLIENT_ID=github-oauth-client-id:latest,\
GITHUB_OAUTH_CLIENT_SECRET=github-oauth-client-secret:latest \
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

Ks. [Cloud SQL IAM -dokumentaatio](https://cloud.google.com/sql/docs/mysql/iam-roles) ja [Cloud Run IAM](https://cloud.google.com/run/docs/securing/managing-access).

## Riippuvuudet

| Paketti | Versio | Käyttö |
|---|---|---|
| Django | >= 4.2 | Perusta |
| google-auth | >= 2.0 | Cloud SQL Admin API -autentikointi |
| google-api-python-client | >= 2.0 | Cloud SQL Admin API -kutsut |
| django-allauth | >= 0.63 | Google ja GitHub SSO |

Ks. [django-allauth -dokumentaatio](https://docs.allauth.org/) ja [google-api-python-client](https://googleapis.github.io/google-api-python-client/docs/).

## Lisätietoja

- [`AUTHENTICATION.md`](AUTHENTICATION.md) — SSO-malli, lupataso, kirjautumisvirrat
- [`DECISIONS.md`](DECISIONS.md) — arkkitehtuuripäätökset perusteluineen

## Lisenssi

MIT
