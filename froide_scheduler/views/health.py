"""Sisäinen health check -endpoint DB wakeup -pollauksia varten.

Palauttaa 200 kun PostgreSQL vastaa, muuten 503.
Selain pollaa tätä odotussivulta 5s välein.

Ei kirjata access-logeihin — lisää nginx-konfiguraatioon:
    location = /__health/ { access_log off; proxy_pass ... }
"""
from django.db import connections, OperationalError
from django.http import HttpResponse, HttpResponseServiceUnavailable


def health_check(request):
    try:
        conn = connections['default']
        conn.ensure_connection()
        conn.close()
        return HttpResponse('ok', content_type='text/plain')
    except OperationalError:
        return HttpResponseServiceUnavailable('db_unavailable', content_type='text/plain')
