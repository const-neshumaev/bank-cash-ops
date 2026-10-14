"""URL configuration of the ``operations`` module.

The module is mounted under ``/api/operations/`` (see ``config/urls.py``).
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from modules.operations.backend.views import (
    CashBalanceViewSet,
    CashDeskOperationsView,
    OperationsSettingsView,
    OperationTypeViewSet,
    OperationViewSet,
    WorkplaceView,
)

router = SimpleRouter()
router.register("types", OperationTypeViewSet, basename="operation-type")
router.register("balances", CashBalanceViewSet, basename="cash-balance")
router.register("operations", OperationViewSet, basename="operation")

urlpatterns = [
    path("settings/", OperationsSettingsView.as_view(), name="operations-settings"),
    path("workplace/", WorkplaceView.as_view(), name="operations-workplace"),
    path(
        "cash-desks/<int:cash_desk_id>/operations/",
        CashDeskOperationsView.as_view(),
        name="cash-desk-operations",
    ),
    *router.urls,
]
