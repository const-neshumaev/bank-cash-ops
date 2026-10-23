"""Root URL configuration of the BankCashOps backend."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from modules.common.backend.views import health_check

api_patterns = [
    path("auth/", include("modules.core.backend.auth_urls")),
    path("references/", include("modules.references.backend.urls")),
    path("", include("modules.core.backend.urls")),
    path("printing/", include("modules.printing.backend.urls")),
    path("operations/", include("modules.operations.backend.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
    path("api/health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
