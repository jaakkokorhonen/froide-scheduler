"""check_and_shutdown_db

Django management command joka sammuttaa Cloud SQL:n
jos ei ole aktiivisia sessioita.

Ajastettu Cloud Schedulerilla:
  - Käynnistys: klo 15:00 EET (UTC 12:00)  -> activationPolicy=ALWAYS
  - Tarkistus:  joka tunnin :45 (UTC :45)   -> sammutus jos ei sessioita
                cron: "45 * * * *"

Muutoshistoria:
  - OperationalError DB-kyselyssä käsitellään siististi (DB jo sammunut)
  - Käytetään yhteistä cloud_sql.set_activation_policy-helperiä
  - Sammutuksen jälkeen nollataan _mark_db_not_ready() jotta middleware-tila
    on ajan tasalla saman containerin säikeissä

Käyttö:
    python manage.py check_and_shutdown_db
"""
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.utils import timezone

from froide_scheduler.cloud_sql import set_activation_policy
from froide_scheduler.middleware.db_wakeup import _mark_db_not_ready


class Command(BaseCommand):
    help = "Sammuttaa Cloud SQL jos ei aktiivisia sessioita"

    def handle(self, *args, **kwargs):
        try:
            active = Session.objects.filter(
                expire_date__gt=timezone.now()
            ).count()
        except OperationalError:
            self.stdout.write(
                self.style.WARNING(
                    "DB ei vastaa \u2014 oletetaan jo sammuneeksi, ohitetaan sammutus."
                )
            )
            _mark_db_not_ready()
            return

        self.stdout.write(f"Aktiivisia sessioita: {active}")

        if active > 0:
            self.stdout.write("Sessioita käynnissä \u2014 DB pysyy päällä.")
            return

        self.stdout.write("Ei sessioita \u2014 sammutetaan Cloud SQL.")
        try:
            set_activation_policy("NEVER")
            _mark_db_not_ready()  # nollataan middleware-tila saman containerin säikeitä varten
            self.stdout.write(self.style.SUCCESS("Cloud SQL sammutettu."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Sammutus epäonnistui: {exc}"))
            raise
