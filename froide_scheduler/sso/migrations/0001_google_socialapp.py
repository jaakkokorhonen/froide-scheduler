"""Datamigration: luo Google SocialApp -objekti automaattisesti.

Edellyttää ympäristömuuttujat:
    GOOGLE_OAUTH_CLIENT_ID      — Cloud Console OAuth2 client ID
    GOOGLE_OAUTH_CLIENT_SECRET  — Cloud Console OAuth2 client secret

GCP-suositus: tallenna Secret Manageriin ja injektoi Cloud Runiin
näin (Cloud Run -palvelun deploy-komennossa):

    --set-secrets=GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest,\
                  GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest

Migration on idempotentti: jos SocialApp on jo olemassa, sitä
päivitetään eikä luoda uutta.
"""
import os

from django.db import migrations


def create_google_socialapp(apps, schema_editor):
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print(
            "\n[froide-scheduler] VAROITUS: GOOGLE_OAUTH_CLIENT_ID tai "
            "GOOGLE_OAUTH_CLIENT_SECRET puuttuu — Google SocialApp "
            "jätetään luomatta. Aseta muuttujat ja aja migrate uudelleen."
        )
        return

    SocialApp = apps.get_model("socialaccount", "SocialApp")
    Site = apps.get_model("sites", "Site")

    app, created = SocialApp.objects.update_or_create(
        provider="google",
        defaults={
            "name": "Google",
            "client_id": client_id,
            "secret": client_secret,
        },
    )

    # Liitä kaikki Sites-objektit (tavallisesti vain yksi)
    for site in Site.objects.all():
        app.sites.add(site)

    action = "Luotu" if created else "Päivitetty"
    print(f"\n[froide-scheduler] {action} Google SocialApp (id={app.pk})")


def delete_google_socialapp(apps, schema_editor):
    """Reverse migration: poistaa Google SocialAppin."""
    SocialApp = apps.get_model("socialaccount", "SocialApp")
    SocialApp.objects.filter(provider="google").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("socialaccount", "0001_initial"),
        ("sites", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_google_socialapp,
            reverse_code=delete_google_socialapp,
        ),
    ]
