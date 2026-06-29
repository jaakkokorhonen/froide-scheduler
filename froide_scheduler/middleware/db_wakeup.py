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
"""
import threading
import time
import logging

import google.auth
import googleapiclient.discovery
from django.conf import settings
from django.db import connections, OperationalError
from django.http import HttpResponse

logger = logging.getLogger(__name__)

_wakeup_lock = threading.Lock()
_wakeup_in_progress = False
_db_ready = False  # In-memory — resetoituu containerin käynnistyessä


def _patch_sql_instance(policy: str):
    """Kutsuu Cloud SQL Admin API:a activationPolicy-muutokseen."""
    creds, _ = google.auth.default()
    service = googleapiclient.discovery.build(
        'sqladmin', 'v1beta4', credentials=creds,
        cache_discovery=False
    )
    service.instances().patch(
        project=settings.GCP_PROJECT_ID,
        instance=settings.CLOUD_SQL_INSTANCE_NAME,
        body={"settings": {"activationPolicy": policy}}
    ).execute()
    logger.info("Cloud SQL activationPolicy → %s", policy)


def _wakeup_worker():
    """Taustasäie: käynnistää Cloud SQL:n ja odottaa sen heräämistä."""
    global _wakeup_in_progress, _db_ready
    try:
        _patch_sql_instance("ALWAYS")
        # Odota max 3min kunnes DB vastaa (36 × 5s)
        for attempt in range(36):
            time.sleep(5)
            try:
                conn = connections['default']
                conn.ensure_connection()
                conn.close()
                _db_ready = True
                logger.info("Cloud SQL käynnistyi (%ds)", attempt * 5)
                return
            except OperationalError:
                logger.debug("DB ei vielä valmis, yritys %d/36", attempt + 1)
        logger.error("Cloud SQL ei käynnistynyt 3 minuutissa")
    except Exception:
        logger.exception("DB wakeup epäonnistui")
    finally:
        _wakeup_in_progress = False


class DBWakeupMiddleware:
    """Ks. moduulin docstring."""

    TRIGGER_PATHS = [
        '/accounts/login/',
        '/accounts/signup/',
        '/accounts/password_reset/',
    ]
    BYPASS_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/robots.txt',
        '/__health/',
    ]
    WAKEUP_COOKIE = 'db_needed'
    WAKEUP_COOKIE_MAX_AGE = 60 * 60 * 8  # 8h

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.BYPASS_PATHS):
            return self.get_response(request)

        needs_db = (
            any(request.path.startswith(p) for p in self.TRIGGER_PATHS)
            or request.COOKIES.get(self.WAKEUP_COOKIE) == '1'
        )

        if not needs_db:
            return self.get_response(request)

        global _db_ready
        if not _db_ready:
            _db_ready = self._check_db_alive()

        if not _db_ready:
            self._trigger_wakeup()
            return self._wakeup_page(request)

        response = self.get_response(request)

        if getattr(request, '_set_db_cookie', False):
            response.set_cookie(
                self.WAKEUP_COOKIE, '1',
                max_age=self.WAKEUP_COOKIE_MAX_AGE,
                httponly=True,
                samesite='Lax',
                secure=not settings.DEBUG,
            )
        if getattr(request, '_clear_db_cookie', False):
            response.delete_cookie(self.WAKEUP_COOKIE)

        return response

    def _check_db_alive(self) -> bool:
        try:
            conn = connections['default']
            conn.ensure_connection()
            conn.close()
            return True
        except Exception:
            return False

    def _trigger_wakeup(self):
        global _wakeup_in_progress
        with _wakeup_lock:
            if not _wakeup_in_progress:
                _wakeup_in_progress = True
                t = threading.Thread(target=_wakeup_worker, daemon=True)
                t.start()
                logger.info("DB wakeup käynnistetty taustasäikeessä")

    def _wakeup_page(self, request) -> HttpResponse:
        next_url = request.get_full_path()
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
    const nextUrl = {repr(next_url)};
    setInterval(() => {{
      document.getElementById('s').textContent =
        Math.round((Date.now() - start) / 1000);
    }}, 1000);
    async function poll() {{
      try {{
        const r = await fetch('/__health/', {{ cache: 'no-store' }});
        if (r.ok) {{ window.location.href = nextUrl; return; }}
      }} catch(e) {{}}
      setTimeout(poll, 5000);
    }}
    setTimeout(poll, 10000);
  </script>
</body>
</html>"""
        return HttpResponse(html, status=503, content_type='text/html; charset=utf-8')
