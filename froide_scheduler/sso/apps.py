"""AppConfig froide_scheduler.sso -sovellukselle.

Määrittelee eksplisiittisen app_label:in jotta Django löytää
migraatiot oikein riippumatta siitä miten paketti on lisätty
INSTALLED_APPS-listaan.
"""
from django.apps import AppConfig


class FroideSchedulerSsoConfig(AppConfig):
    name = "froide_scheduler.sso"
    label = "froide_scheduler_sso"
    verbose_name = "Froide Scheduler SSO"
