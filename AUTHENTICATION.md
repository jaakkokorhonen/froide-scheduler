# Autentikointi

## Malli

Froide-portaaliin voi kirjautua Google SSO:lla (OAuth2 + PKCE).
Kirjautuminen on auki **kaikille Gmail-tileille** — käyttäjä on aina
tavallinen kansalainen, ei organisaation sisäinen käyttäjä.

SSO ei anna lisäoikeuksia. Se korvaa lomakerekisteröitymisen ja
sähköpostivahvistuksen, mutta käyttäjän oletuslupataso on
täsmälleen sama kuin itse rekisteröityneellä kansalaisella.

## Käyttäjän oletuslupataso (SSO-kirjautuminen)

| Kenttä | Arvo | Selitys |
|---|---|---|
| `is_active` | `True` | Google on vahvistanut tilin |
| `is_staff` | `False` | Django admin: myonnetään erikseen |
| `is_superuser` | `False` | Ei koskaan automaattisesti |
| `UserProfile.is_trusted` | `False` | Tuntematon käyttäjä — sama kuin uusi rekisteröityjä |
| `UserProfile.is_journalist` | `False` | Myonnetään erikseen |
| `UserProfile.private` | `False` | Froiden oletusarvo |

## Ero tavalliseen lomakerekisteröitymiseen

Ainoa merkityksellinen ero on **sähköpostivahvistus**: normaalissa
rekisteröitymisessä käyttäjä klikkaa vahvistuslinkin. SSO:ssa
Google on jo vahvistanut sähköpostin, joten vahvistusvaihetta ei
tarvita (`ACCOUNT_EMAIL_VERIFICATION = "none"`).

Muuten oikeudet, rajoitukset ja käyttäjäkokemus ovat identtiset.

## Domain-rajoitus

Oletuksena käyttö on auki kaikille Google-tileille.
Jos portaali halutaan rajoittaa tietyn organisaation jäsenille,
aseta ympäristömuuttuja:

```
GOOGLE_SSO_DOMAIN=yourdomain.fi
```

Tällöin `DomainRestrictedSocialAccountAdapter` hylkää kirjautumisyritykset
joiden sähköposti ei pääty `@yourdomain.fi`-domainiin.

## Admin-oikeuksien myöntäminen

`is_staff` ja `is_superuser` myönnetään aina manuaalisesti
Django adminissa tai management commandilla:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(email='admin@example.com')
u.is_staff = True
u.save()
"
```

## Kirjautumisvirta

```
Käyttäjä → /accounts/google/login/
    → Google OAuth2 (PKCE)
    → Google palauttaa: email, name, picture
    → DomainRestrictedSocialAccountAdapter.pre_social_login()
        → GOOGLE_SSO_DOMAIN asetettu? Tarkista domain. Muuten: läpimeno.
    → allauth: onko tämä email jo rekisteröity?
        Kyllä → yhdistä olemassa olevaan Django-käyttäjään
        Ei   → luo uusi käyttäjä oletusluvin
    → Kirjautuminen onnistui → ohjaus /
```

## Relevantit asetukset

```python
# froide_scheduler/sso/settings.py
ACCOUNT_EMAIL_VERIFICATION = "none"       # Google vahvistaa jo
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Yhdistä duplikaatit
```
