"""check_and_shutdown_db

Django management command joka sammuttaa Cloud SQL:n
jos ei ole aktiivisia sessioita.

Ajastettu Cloud Schedulerilla:
  - Käynnistys: klo 15:00 EET (UTC 12:00)  → activationPolicy=ALWAYS
  - Tarkistus:  joka tunnin :45 (UTC :45)   → sammutus jos ei sessioita
                cron: "45 * * * *"

Käyttö:
    python manage.py check_and_shutdown_db
"""
import google.auth
import googleapiclient.discovery

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sammuttaa Cloud SQL jos ei aktiivisia sessioita'

    def handle(self, *args, **kwargs):
        active = Session.objects.filter(
            expire_date__gt=timezone.now()
        ).count()

        self.stdout.write(f'Aktiivisia sessioita: {active}')

        if active > 0:
            self.stdout.write('Sessioita käynnissä — DB pysyy päällä.')
            return

        self.stdout.write('Ei sessioita — sammutetaan Cloud SQL.')
        try:
            creds, _ = google.auth.default()
            service = googleapiclient.discovery.build(
                'sqladmin', 'v1beta4', credentials=creds,
                cache_discovery=False
            )
            service.instances().patch(
                project=settings.GCP_PROJECT_ID,
                instance=settings.CLOUD_SQL_INSTANCE_NAME,
                body={'settings': {'activationPolicy': 'NEVER'}}
            ).execute()
            self.stdout.write(self.style.SUCCESS('Cloud SQL sammutettu.'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Sammutus epäonnistui: {exc}'))
            raise
