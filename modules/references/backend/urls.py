"""URL configuration of the ``references`` module.

The module is mounted under ``/api/references/`` (see ``config/urls.py``).
"""

from rest_framework.routers import SimpleRouter

from modules.references.backend.views import CurrencyRateTypeViewSet, CurrencyViewSet

router = SimpleRouter()
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("rate-types", CurrencyRateTypeViewSet, basename="rate-type")

urlpatterns = [*router.urls]
