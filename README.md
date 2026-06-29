# froide-scheduler

Froide-asennuksen päälle ajettava patch joka lisää Cloud SQL:n automaattisen sammutuksen ja herätyksen.

## Mitä tämä tekee

- **DBWakeupMiddleware** — herättää Cloud SQL:n automaattisesti kun kirjautunut käyttäjä tai kirjautumissivu havaitaan
- **`check_and_shutdown_db`** — Django management command joka sammuttaa Cloud SQL:n jos ei aktiivisia sessioita
- **`/__health/`** — sisäinen endpoint jonka selain pollaa odotussivulla kunnes DB on valmis

## Säästö

Cloud SQL db-f1-micro: ~$12/kk → ~$2/kk kun sammutettuna inaktiivina.

## Hyväksytty haitta

Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa **1–3 minuuttia** kannan käynnistymistä.
Käyttäjälle näytetään odotussivu automaattisesti. Tämä on tietoinen päätös.

## Asennus

### 1. Kopioi tiedostot Froide-projektin päälle

```bash
cp -r froide_scheduler/middleware/ <froide-project>/froide/middleware/
cp froide_scheduler/views/health.py <froide-project>/froide/views/health.py
cp froide_scheduler/management/commands/check_and_shutdown_db.py \
   <froide-project>/froide/management/commands/check_and_shutdown_db.py
```

### 2. Lisää settings_gcp.py:hin

```python
GCP_PROJECT_ID = env('GCP_PROJECT_ID')
CLOUD_SQL_INSTANCE_NAME = env('CLOUD_SQL_INSTANCE')

MIDDLEWARE = [
    'froide.middleware.db_wakeup.DBWakeupMiddleware',  # TÄYTYY OLLA ENSIMMÄINEN
    'django.middleware.security.SecurityMiddleware',
    # ...muut middlewaret
]
```

### 3. Lisää urls.py:hin

```python
from froide.views.health import health_check

urlpatterns = [
    path('__health/', health_check),
    # ...muut
]
```

### 4. Luo Cloud Scheduler -ajastimet

```bash
# Käynnistä DB klo 15:00 (EET = UTC+3, eli UTC 12:00)
gcloud scheduler jobs create http froide-db-start \
  --schedule="0 12 * * *" \
  --uri="https://sqladmin.googleapis.com/v1/projects/${PROJECT_ID}/instances/${INSTANCE}/patch" \
  --message-body='{"settings":{"activationPolicy":"ALWAYS"}}' \
  --http-method=PATCH \
  --oauth-service-account-email=${SA_EMAIL} \
  --location=europe-north1

# Tarkista sessiot ja sammuta tarvittaessa klo 16:00 (UTC 13:00)
gcloud scheduler jobs create http froide-db-shutdown-check \
  --schedule="0 13 * * *" \
  --uri="https://${CLOUD_RUN_URL}/run-management-command" \
  --message-body='{"command":"check_and_shutdown_db"}' \
  --http-method=POST \
  --location=europe-north1
```

Vaihtoehtoisesti aja `check_and_shutdown_db` Cloud Run Jobin kautta.

### 5. Ympäristömuuttujat

```
GCP_PROJECT_ID=froide-prod
CLOUD_SQL_INSTANCE=froide-db
```

## Aikajana (EET)

| Aika | Tapahtuma |
|------|-----------|
| 15:00 | Cloud Scheduler käynnistää Cloud SQL:n (activationPolicy=ALWAYS) |
| 15:00–15:03 | DB herää, Froide alkaa vastata normaalisti |
| 16:00 | `check_and_shutdown_db` tarkistaa sessiot |
| 16:00 (jos ei käyttäjiä) | Cloud SQL sammutetaan (activationPolicy=NEVER) |
| Milloin tahansa | Käyttäjä menee kirjautumissivulle → DBWakeupMiddleware herättää DB:n |
