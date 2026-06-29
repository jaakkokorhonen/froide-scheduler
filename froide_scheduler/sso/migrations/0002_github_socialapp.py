"""Datamigration: luo tai päivittää GitHub OAuth2 SocialApp-objektin.

Lukee tunnukset ympäristömuuttujista:
    GITHUB_OAUTH_CLIENT_ID
    GITHUB_OAUTH_CLIENT_SECRET

Jos muuttujat puuttuvat, migraatio ohitetaan varoituksella.
SocialApp voidaan luoda myös käsin Django adminissa.
"""
from django.db import migrations


def create_github_socialapp(apps, schema_editor):
    import os
    import sys

    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print(
            "\n  [0002_github_socialapp] GITHUB_OAUTH_CLIENT_ID tai "
            "GITHUB_OAUTH_CLIENT_SECRET puuttuu — ohitetaan.",
            file=sys.stderr,
        )
        return

    SocialApp = apps.get_model("socialaccount", "SocialApp")
    Site = apps.get_model("sites", "Site")

    app, created = SocialApp.objects.update_or_create(
        provider="github",
        defaults={
            "name": "GitHub",
            "client_id": client_id,
            "secret": client_secret,
        },
    )

    site = Site.objects.get_current()
    app.sites.add(site)

    action = "luotu" if created else "päivitetty"
    print(f"\n  [0002_github_socialapp] GitHub SocialApp {action} (site: {site.domain}).")


def remove_github_socialapp(apps, schema_editor):
    SocialApp = apps.get_model("socialaccount", "SocialApp")
    SocialApp.objects.filter(provider="github").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("froide_scheduler_sso", "0001_google_socialapp"),
    ]

    operations = [
        migrations.RunPython(
            create_github_socialapp,
            reverse_code=remove_github_socialapp,
        ),
    ]
