# froide-scheduler

Cloud SQL:n automaattinen sammutus ja herätys Froide-asennuksille (Google Cloud Platform).

Ajetaan Froide-asennuksen päälle patchina — ei muokkaa Froide-ydintä.

## Miksi

Cloud SQL `db-f1-micro` maksaa ~$12/kk pyöriessään jatkuvasti. Suurin osa tästä ajasta kanta on tyhjäkäynnillä. Tämä paketti sammuttaa kannan automaattisesti inaktiivin aikana ja herättää sen tarvittaessa.

**Säästö: ~$10/kk** (730h → ~30h/kk laskutettava käyttöaika)

## Hyväksytty haitta

Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa kannan käynnistymistä **1–3 minuuttia**. Käyttäjälle näytetään odotussivu automaattisesti. Tämä on tietoinen kompromissi, dokumentoitu [`DECISIONS.md`](DECISIONS.md):ssä.

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
├── setup.py
├── DECISIONS.md
└── README.md
```

## Miten toimii

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

Kannan sammutus:
```
Cloud Scheduler klo 16:00
    → python manage.py check_and_shutdown_db
    → Aktiivisia sessioita? Ei → activationPolicy=NEVER
```

## Aikajana (EET)

| Aika | Tapahtuma |
|------|-----------|
| 15:00 | Cloud Scheduler käynnistää Cloud SQL:n (`activationPolicy=ALWAYS`) |
| 15:00–15:03 | DB herää, Froide vastaa normaalisti |
| 16:00 | `check_and_shutdown_db` tarkistaa sessiot |
| 16:00 (ei käyttäjiä) | Cloud SQL sammutetaan (`activationPolicy=NEVER`) |
| Milloin tahansa | Käyttäjä kirjautuu → DBWakeupMiddleware herättää DB:n |

## Asennus

### 1. Asenna paketti

```bash
pip install git+https://github.com/jaakkokorhonen/froide-scheduler.git
```

### 2. Lisää `settings_gcp.py`

```python
GCP_PROJECT_ID = env('GCP_PROJECT_ID')           # esim. 'froide-prod'
CLOUD_SQL_INSTANCE_NAME = env('CLOUD_SQL_INSTANCE')  # esim. 'froide-db'

MIDDLEWARE = [
    'froide_scheduler.middleware.db_wakeup.DBWakeupMiddleware',  # TÄYTYY OLLA ENSIMMÄINEN
    'django.middleware.security.SecurityMiddleware',
    # ...muut middlewaret
]
```

### 3. Lisää `urls.py`

```python
from froide_scheduler.urls import urlpatterns as scheduler_urls

urlpatterns = [
    *scheduler_urls,
    # ...muut
]
```

### 4. Rekisteröi signaalit `AppConfig.ready()`-metodissa

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
```

## Riippuvuudet

- Django >= 4.2
- google-auth >= 2.0
- google-api-python-client >= 2.0

## Lisenssi

MIT
