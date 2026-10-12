from django.urls import path
from rest_framework.routers import SimpleRouter

from modules.core.backend.views import (
    BranchViewSet,
    CashDeskViewSet,
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
router.register("shifts", ShiftViewSet, basename="shift")

urlpatterns = [
    path("permissions/", PermissionCatalogView.as_view(), name="permission-catalog"),
    *router.urls,
]
