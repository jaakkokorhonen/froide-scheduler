# Päätökset

## Cloud SQL sammutus/herätys -malli

**Päätös:** Cloud SQL db-f1-micro sammutetaan automaattisesti inaktiivina.

**Säästö:** ~$10/kk (730h → ~30h/kk laskutettu käyttöaika)

**Hyväksytty haitta:** Ensimmäinen käyttäjä inaktiivijakson jälkeen odottaa
kannan käynnistymistä **1–3 minuuttia**. Käyttäjälle näytetään odotussivu.
Tämä on tietoinen kompromissi.

**Laukaisuehdot (herätys):**
- Käyttäjä navigoi kirjautumissivulle (`/accounts/login/` jne.)
- Käyttäjällä on voimassa oleva `db_needed=1` -cookie (asetettu kirjautuessa)

**Sammutusehto:**
- Cloud Scheduler ajaa `check_and_shutdown_db` klo 16:00 EET
- Jos aktiivisia Django-sessioita ei ole → Cloud SQL sammutetaan

**Aikajana (EET):**
- 15:00 — Cloud Scheduler käynnistää Cloud SQL:n (activationPolicy=ALWAYS)
- 16:00 — `check_and_shutdown_db` tarkistaa sessiot
- 16:00 (jos ei käyttäjiä) — Cloud SQL sammutetaan (activationPolicy=NEVER)
- Milloin tahansa — Käyttäjä kirjautuu → DBWakeupMiddleware herättää DB:n

**Testattu:** [lisää päivämäärä käyttökokemustesteistä]
