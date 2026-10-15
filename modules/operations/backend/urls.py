"""URL configuration of the ``operations`` module.

The module is mounted under ``/api/operations/`` (see ``config/urls.py``).
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from modules.operations.backend.views import (
    BankOperationTemplateView,
    BranchOperationTemplateView,
    CashBalanceViewSet,
    CashDeskOperationsView,
    OperationsSettingsView,
    OperationTemplateListView,
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
        "operation-templates/",
        OperationTemplateListView.as_view(),
        name="operation-template-list",
    ),
    path(
        "operation-templates/bank/",
        BankOperationTemplateView.as_view(),
        name="operation-template-bank",
    ),
    path(
        "operation-templates/branches/<int:branch_id>/",
        BranchOperationTemplateView.as_view(),
        name="operation-template-branch",
    ),
    path(
        "cash-desks/<int:cash_desk_id>/operations/",
        CashDeskOperationsView.as_view(),
        name="cash-desk-operations",
    ),
    *router.urls,
]
