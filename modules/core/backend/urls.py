from django.urls import path
from rest_framework.routers import SimpleRouter

from modules.core.backend.views import (
    BankCurrencyTemplateView,
    BranchCurrencyTemplateView,
    BranchViewSet,
    CashDeskViewSet,
    CurrencyRateViewSet,
    CurrencyTemplateListView,
    CurrencyViewSet,
    PermissionCatalogView,
    RoleViewSet,
    ShiftViewSet,
    UserViewSet,
)

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("branches", BranchViewSet, basename="branch")
router.register("cash-desks", CashDeskViewSet, basename="cash-desk")
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("currency-rates", CurrencyRateViewSet, basename="currency-rate")
router.register("shifts", ShiftViewSet, basename="shift")

urlpatterns = [
    path("permissions/", PermissionCatalogView.as_view(), name="permission-catalog"),
    path(
        "currency-templates/",
        CurrencyTemplateListView.as_view(),
        name="currency-template-list",
    ),
    path(
        "currency-templates/bank/",
        BankCurrencyTemplateView.as_view(),
        name="currency-template-bank",
    ),
    path(
        "currency-templates/branches/<int:branch_id>/",
        BranchCurrencyTemplateView.as_view(),
        name="currency-template-branch",
    ),
    *router.urls,
]
