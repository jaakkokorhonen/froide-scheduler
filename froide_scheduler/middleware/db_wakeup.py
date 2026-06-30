"""DBWakeupMiddleware

Herättää Cloud SQL:n automaattisesti kun:
- Käyttäjä navigoi kirjautumissivulle
- Käyttäjällä on voimassa oleva kirjautumiscookie (db_needed=1)

Kun kanta on sammunut, palauttaa 503-sivun joka pollaa /__health/
kunnes kanta on käynnistynyt, jonka jälkeen selain ohjataan takaisin
alkuperäiseen osoitteeseen.

DOKUMENTOITU KÄYTTÄYTYMINEN:
  Kannan käynnistyminen kestää 1–3 minuuttia.
  Käyttäjälle näytetään odotussivu tänä aikana.
  Tämä on tietoinen kustannusoptimointipäätös (~$10/kk säästö).

Asennus: ks. README.md

Muutoshistoria:
  - next_url serialisoidaan json.dumps():lla repr():n sijaan (XSS)
  - _db_ready bool korvattu threading.Event + TTL -rakenteella
    jotta tila nollaantuu sammutuksen jälkeen
  - OperationalError varsinaisessa view-käsittelyssä napataan ja
    ohjataan wakeup-sivulle 500:n sijaan
  - _patch_sql_instance poistettu, käytetään cloud_sql.set_activation_policy
  - WAKEUP_COOKIE_MAX_AGE laskettu 8h -> 2h
"""
import json
import logging
import threading
import time

from django.conf import settings
from django.db import connections, OperationalError
from django.http import HttpResponse

from froide_scheduler.cloud_sql import set_activation_policy

logger = logging.getLogger(__name__)

_wakeup_lock = threading.Lock()
_wakeup_in_progress = False

# DB-tila: threading.Event + timestamp TTL
# threading.Event on säikeisteysturvallinen (set/clear/is_set ovat atomaarisia).
# TTL varmistaa että tila tarkistetaan uudelleen jos kanta sammutetaan
# ulkoa (Cloud Scheduler) containerin eläessä.
_db_ready_event = threading.Event()
_db_state_lock = threading.Lock()
_db_last_confirmed: float = 0.0
_DB_READY_TTL = 60  # sekuntia: kuinka kauan 'ready' on luotettava ilman uutta tarkistusta


def _mark_db_ready() -> None:
    """Merkitään DB käytättäväksi ja tallennetaan aika."""
    global _db_last_confirmed
    with _db_state_lock:
        _db_ready_event.set()
        _db_last_confirmed = time.monotonic()


def _mark_db_not_ready() -> None:
    """Nollataan DB-tila — kutsutaan sammutuksen tai virheen jälkeen."""
    global _db_last_confirmed
    with _db_state_lock:
        _db_ready_event.clear()
        _db_last_confirmed = 0.0


def _db_state_is_fresh() -> bool:
    """Palauttaa True jos DB on merkitty valmiiksi alle TTL sekuntia sitten."""
    with _db_state_lock:
        return (
            _db_ready_event.is_set()
            and (time.monotonic() - _db_last_confirmed) < _DB_READY_TTL
        )


def _wakeup_worker() -> None:
    """Taustasäie: käynnistää Cloud SQL:n ja odottaa sen heräämistä."""
    global _wakeup_in_progress
    try:
        set_activation_policy("ALWAYS")
        # Odota max 3min kunnes DB vastaa (36 x 5s)
        for attempt in range(36):
            time.sleep(5)
            try:
                conn = connections["default"]
                conn.ensure_connection()
                conn.close()
                _mark_db_ready()
                logger.info("Cloud SQL käynnistyi (%ds)", (attempt + 1) * 5)
                return
            except OperationalError:
                logger.debug("DB ei vielä valmis, yritys %d/36", attempt + 1)
        logger.error("Cloud SQL ei käynnistynyt 3 minuutissa")
        _mark_db_not_ready()
    except Exception:
        logger.exception("DB wakeup epäonnistui")
        _mark_db_not_ready()
    finally:
        _wakeup_in_progress = False


class DBWakeupMiddleware:
    """Ks. moduulin docstring."""

    TRIGGER_PATHS = [
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/password_reset/",
    ]
    BYPASS_PATHS = [
        "/static/",
        "/media/",
        "/favicon.ico",
        "/robots.txt",
        "/__health/",
    ]
    WAKEUP_COOKIE = "db_needed"
    WAKEUP_COOKIE_MAX_AGE = 60 * 60 * 2  # 2h (oli 8h — lyhennetty turhan herättelytä välttämään)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.BYPASS_PATHS):
            return self.get_response(request)

        needs_db = (
            any(request.path.startswith(p) for p in self.TRIGGER_PATHS)
            or request.COOKIES.get(self.WAKEUP_COOKIE) == "1"
        )

        if not needs_db:
            return self.get_response(request)

        if not self._db_is_available():
            self._trigger_wakeup()
            return self._wakeup_page(request)

        try:
            response = self.get_response(request)
        except OperationalError:
            # DB sammui käsittelyn aikana (esim. Cloud Scheduler sammutti)
            # -> nollataan tila ja näytetään odotussivu 500:n sijaan
            logger.warning("OperationalError view-käsittelyssä — nollataan DB-tila")
            _mark_db_not_ready()
            self._trigger_wakeup()
            return self._wakeup_page(request)

        if getattr(request, "_set_db_cookie", False):
            response.set_cookie(
                self.WAKEUP_COOKIE,
                "1",
                max_age=self.WAKEUP_COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=not settings.DEBUG,
            )
        if getattr(request, "_clear_db_cookie", False):
            response.delete_cookie(self.WAKEUP_COOKIE)

        return response

    def _check_db_alive(self) -> bool:
        try:
            conn = connections["default"]
            conn.ensure_connection()
            conn.close()
            return True
        except Exception:
            return False

    def _db_is_available(self) -> bool:
        """Palauttaa True jos DB on käytettävissä.

        Tuore tila (< TTL) palautetaan suoraan ilman verkkokyäntiä.
        Vanhentuneen tilan tapauksessa tehdään oikea yhteystesti.
        """
        if _db_state_is_fresh():
            return True
        alive = self._check_db_alive()
        if alive:
            _mark_db_ready()
        else:
            _mark_db_not_ready()
        return alive

    def _trigger_wakeup(self) -> None:
        global _wakeup_in_progress
        with _wakeup_lock:
            if not _wakeup_in_progress:
                _wakeup_in_progress = True
                t = threading.Thread(target=_wakeup_worker, daemon=True)
                t.start()
                logger.info("DB wakeup käynnistetty taustasäikeessä")

    def _wakeup_page(self, request) -> HttpResponse:
        # json.dumps() takaa turvallisen JavaScipt-merkkijonon
        # (vanha repr() ei ollut XSS-turvallinen)
        next_url = json.dumps(request.get_full_path())
        html = f"""<!DOCTYPE html>
<html lang="fi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palvelu käynnistyy...</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0;
      background: #f5f5f5; color: #333;
    }}
    .box {{
      text-align: center; max-width: 420px;
      padding: 2rem; background: white;
      border-radius: 12px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }}
    .spinner {{
      width: 48px; height: 48px;
      border: 4px solid #e0e0e0;
      border-top-color: #01696f;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 1.5rem;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    h2 {{ margin: 0 0 0.5rem; font-size: 1.3rem; }}
    p {{ color: #666; margin: 0.4rem 0; font-size: 0.9rem; }}
    .timer {{ font-size: 0.8rem; color: #999; margin-top: 1rem; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <h2>Palvelu käynnistyy</h2>
    <p>Tietokanta herää lepotilasta.</p>
    <p>Tämä kestää noin 1&#8202;–&#8202;3 minuuttia.</p>
    <p class="timer">Odotettu: <span id="s">0</span>s</p>
  </div>
  <script>
    const start = Date.now();
    const nextUrl = {next_url};
    setInterval(() => {{
      document.getElementById('s').textContent =
        Math.round((Date.now() - start) / 1000);
    }}, 1000);
    async function poll() {{
      try {{
        const r = await fetch('/__health/', {{ cache: 'no-store' }});
        if (r.ok) {{ window.location.href = nextUrl; return; }}
      }} catch (e) {{}}
      setTimeout(poll, 5000);
    }}
    setTimeout(poll, 10000);
  </script>
</body>
</html>"""
        return HttpResponse(html, status=503, content_type="text/html; charset=utf-8")
