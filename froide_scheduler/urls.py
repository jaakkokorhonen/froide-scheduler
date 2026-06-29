"""URL-määritykset — sisällytä Froide-projektin urls.py:hin:

    from froide_scheduler.urls import urlpatterns as scheduler_urls

    urlpatterns = [
        *scheduler_urls,
        # ...muut
    ]
"""
from django.urls import path
from froide_scheduler.views.health import health_check

urlpatterns = [
    path('__health/', health_check, name='health_check'),
]
