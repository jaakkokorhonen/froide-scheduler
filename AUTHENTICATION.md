# Autentikointi

## Malli

Froide-portaaliin voi kirjautua kahdella SSO-providerilla:

| Provider | Käyttäjätyyppi | Rajoitus |
|---|---|---|
| **Google** | Kansalainen | Ei rajoitusta (kaikki Gmail-tilit) |
| **GitHub** | Kansalainen | Ei rajoitusta (kaikki GitHub-tilit) |

Kumpikaan provider ei anna lisäoikeuksia. Molemmat korvaavat
lomakerekisteröitymisen ja sähköpostivahvistuksen, mutta
käyttäjän oletuslupataso on täsmälleen sama kuin itse
rekisteröityneellä kansalaisella.

## Käyttäjän oletuslupataso (SSO-kirjautuminen)

| Kenttä | Arvo | Selitys |
|---|---|---|
| `is_active` | `True` | Provider on vahvistanut tilin |
| `is_staff` | `False` | Django admin: myönnetään erikseen |
| `is_superuser` | `False` | Ei koskaan automaattisesti |
| `UserProfile.is_trusted` | `False` | Tuntematon käyttäjä — sama kuin uusi rekisteröityjä |
| `UserProfile.is_journalist` | `False` | Myönnetään erikseen |
| `UserProfile.private` | `False` | Froiden oletusarvo |

## Ero tavalliseen lomakerekisteröitymiseen

Ainoa merkityksellinen ero on **sähköpostivahvistus**: normaalissa
rekisteröitymisessä käyttäjä klikkaa vahvistuslinkin. SSO:ssa
provider on jo vahvistanut sähköpostin, joten vahvistusvaihetta
ei tarvita (`ACCOUNT_EMAIL_VERIFICATION = "none"`).

Muuten oikeudet, rajoitukset ja käyttäjäkokemus ovat identtiset.

## Domain-rajoitus (valinnainen)

Google-kirjautuminen voidaan rajoittaa tiettyyn Google Workspace
-domainiin asettamalla ympäristömuuttuja:

```
GOOGLE_SSO_DOMAIN=yourdomain.fi
```

Tällöin `DomainRestrictedSocialAccountAdapter` hylkää muut tilit.
GitHub-kirjautumisessa vastaavaa rajoitusta ei ole —
lisätään tarvittaessa org/tiimi-tarkistuksella.

## Admin-oikeuksien myöntäminen

`is_staff` ja `is_superuser` myönnetään aina manuaalisesti
Django adminissa tai management commandilla — riippumatta
käytetystä SSO-providerista:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(email='admin@example.com')
u.is_staff = True
u.save()
"
```

## Kirjautumisvirrat

```
Google:
Käyttäjä → /accounts/google/login/
    → Google OAuth2 (PKCE)
    → DomainRestrictedSocialAccountAdapter.pre_social_login()
        → GOOGLE_SSO_DOMAIN asetettu? Tarkista domain. Muuten: läpimeno.
    → allauth: onko tämä email jo rekisteröity?
        Kyllä → yhdistä olemassa olevaan käyttäjään
        Ei   → luo uusi käyttäjä oletusluvin
    → Kirjautuminen onnistui → ohjaus /

GitHub:
Käyttäjä → /accounts/github/login/
    → GitHub OAuth2 (scope: user:email)
    → DomainRestrictedSocialAccountAdapter.pre_social_login()
        → GitHub-providerille ei rajoitusta — läpimeno
    → allauth: onko tämä email jo rekisteröity?
        Kyllä → yhdistä olemassa olevaan käyttäjään
        Ei   → luo uusi käyttäjä oletusluvin
    → Kirjautuminen onnistui → ohjaus /
```

## Ympäristömuuttujat

| Muuttuja | Pakollinen | Selitys |
|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | Kyllä | Google OAuth2 Client ID. [Ohje](https://developers.google.com/identity/protocols/oauth2) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Kyllä | Google OAuth2 Client Secret |
| `GITHUB_OAUTH_CLIENT_ID` | Kyllä | GitHub OAuth App Client ID. [Ohje](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) |
| `GITHUB_OAUTH_CLIENT_SECRET` | Kyllä | GitHub OAuth App Client Secret |
| `GOOGLE_SSO_DOMAIN` | Ei | Google-kirjautumisen domain-rajoitus |

## Relevantit asetukset

```python
# froide_scheduler/sso/settings.py
ACCOUNT_EMAIL_VERIFICATION = "none"                    # Provider vahvistaa jo
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Yhdistää duplikaatit
```

Ks. [django-allauth SocialAccount -dokumentaatio](https://docs.allauth.org/en/latest/socialaccount/configuration.html).
