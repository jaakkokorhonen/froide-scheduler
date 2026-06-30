# Päätökset

## Cloud SQL sammutus/herätys -malli

**Päätös:** Cloud SQL `db-f1-micro` sammutetaan automaattisesti inaktiivina.

**Säästö:** ~$10/kk (730h → ~30h/kk laskutettu käyttöaika)

**Hyväksytty haitta:** Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa
kannan käynnistymistä **1–3 minuuttia**. Käyttäjälle näytetään odotussivu.
Tämä on tietoinen kompromissi. Käyttökokemustesteissä voidaan tarvittaessa
lisätä lataussivu jos odotusaika koetaan liian pitkäksi.

**Laukaisuehdot (herätys):**
- Käyttäjä navigoi kirjautumissivulle (`/accounts/login/` jne.)
- Käyttäjällä on voimassa oleva `db_needed=1` -cookie (asetettu kirjautuessa)

**Sammutusehto:**
- Cloud Scheduler ajaa `check_and_shutdown_db` joka tunnin :45 (cron: `45 * * * *`)
- Jos aktiivisia Django-sessioita ei ole → Cloud SQL sammutetaan

**Aikajana (EET):**
- 15:00 — Cloud Scheduler käynnistää Cloud SQL:n (`activationPolicy=ALWAYS`)
- Joka tunti :45 — `check_and_shutdown_db` tarkistaa sessiot
- :45 (jos ei käyttäjiä) — Cloud SQL sammutetaan (`activationPolicy=NEVER`)
- Milloin tahansa — Käyttäjä kirjautuu → `DBWakeupMiddleware` herättää DB:n

**Odotussivun polling-käyttäytyminen:**
Selain odottaa ensin 10 sekuntia ennen ensimmäistä `/__health/`-kyselyä
(DB:n käynnistyminen vie aina vähintään useita sekunteja), sen jälkeen
pollataan 5 sekunnin välein kunnes DB vastaa 200.

**Huomio — cookie-aikataulutus:**
`db_needed`-cookie elää 8 tuntia (`WAKEUP_COOKIE_MAX_AGE = 8h`), mutta
Django-sessio vanhenee 3 tunnin inaktiivin jälkeen (`SESSION_COOKIE_AGE = 3h`).
Tämä tarkoittaa, että DB voidaan herättää cookien perusteella vaikka
käyttäjän sessio olisi jo vanhentunut. Tämä on hyväksytty käyttäytyminen:
herätys on nopea eikä aiheuta haittaa, ja `check_and_shutdown_db` sammuttaa
DB:n heti kun aktiivisia sessioita ei ole.

**Huomio — multi-instanssi -käyttäytyminen:**
`_db_ready`-muuttuja on in-memory per Cloud Run -instanssi. Jokainen uusi
instanssi tekee ensimmäisellä pyynnöllä yhden DB-yhteyskokeilun (`_check_db_alive`)
asettaakseen oman tilansa. Tämä on normaali ja hyväksytty käyttäytyminen —
ylimääräinen kokeilukytkentä on nopea eikä aiheuta herätystä jos DB on
jo käynnissä.

**Toteutus:** [`froide_scheduler/middleware/db_wakeup.py`](froide_scheduler/middleware/db_wakeup.py)

**Testattu:** [lisää päivämäärä käyttökokemustesteistä]

---

## SSO-autentikointi

**Päätös:** Google ja GitHub SSO [django-allauth](https://docs.allauth.org/)-paketilla.

**Lupataso:** SSO-kirjautuminen ei anna lisäoikeuksia — sama kuin
tavallinen lomakerekisteröityminen. `is_staff` myönnetään manuaalisesti.

**Perustelu:** Kansalaiskäyttäjien tunnistaminen Google/GitHub-tilillä
poistaa sähköpostivahvistusvaiheen ja vähentää käyttäjätukea.
Admin-oikeuksien manuaalinen myöntäminen on tietoinen
turvallisuuspäätös.

**Toteutus:** [`froide_scheduler/sso/`](froide_scheduler/sso/)

Ks. tarkempi kuvaus: [`AUTHENTICATION.md`](AUTHENTICATION.md)
