"""Signaalit kirjautumiscookien asettamiseen.

Liitä Froide-projektin AppConfig.ready():

    from froide_scheduler import signals  # noqa: F401
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


@receiver(user_logged_in)
def mark_db_needed(sender, request, user, **kwargs):
    """Merkitään pyyntöön lippu jotta middleware asettaa db_needed-cookien."""
    request._set_db_cookie = True


@receiver(user_logged_out)
def clear_db_needed(sender, request, user, **kwargs):
    """Poistetaan db_needed-cookie uloskirjautuessa."""
    request._clear_db_cookie = True
