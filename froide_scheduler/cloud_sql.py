"""Yhteinen Cloud SQL Admin API -helper.

Käytetään sekä DBWakeupMiddlewaren _wakeup_workerissa
että check_and_shutdown_db -komennossa.

Perustelu: ei duplikoida google.auth + googleapiclient -alustusta
kahdessa paikassa.
"""
import logging

import google.auth
import googleapiclient.discovery
from django.conf import settings

logger = logging.getLogger(__name__)


def set_activation_policy(policy: str) -> None:
    """Asettaa Cloud SQL -instanssin activationPolicy-arvon.

    Args:
        policy: 'ALWAYS' (käynnistä) tai 'NEVER' (sammuta).
    """
    creds, _ = google.auth.default()
    service = googleapiclient.discovery.build(
        "sqladmin",
        "v1beta4",
        credentials=creds,
        cache_discovery=False,
    )
    service.instances().patch(
        project=settings.GCP_PROJECT_ID,
        instance=settings.CLOUD_SQL_INSTANCE_NAME,
        body={"settings": {"activationPolicy": policy}},
    ).execute()
    logger.info("Cloud SQL activationPolicy -> %s", policy)
