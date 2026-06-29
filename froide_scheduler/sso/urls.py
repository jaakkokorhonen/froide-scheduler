"""SSO URL-määritykset — sisällytä Froide-projektin urls.py:hin.

    from froide_scheduler.sso.urls import urlpatterns as sso_urlpatterns

    urlpatterns = [
        *sso_urlpatterns,
        # ...muut
    ]
"""
from django.urls import include, path

urlpatterns = [
    path("accounts/", include("allauth.urls")),
]
