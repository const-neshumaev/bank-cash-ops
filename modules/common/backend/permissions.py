"""Shared DRF permission classes reused by every module."""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allow access only to authenticated users with the administrator role."""

    message = "Administrator privileges are required to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


class PermissionRequired(BasePermission):
    """Grant access when the user holds the permission required by the view.

    The class is generic: it only relies on the user exposing a
    ``has_permission(code)`` method, so every module can use it.

    A view declares either a single ``required_permission`` or a ``permission_map``
    that resolves the code per DRF action (``list``, ``create``, ``partial_update``
    and so on). When neither is set the view is left to the default authentication
    requirement.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        code = getattr(view, "required_permission", None)
        permission_map = getattr(view, "permission_map", None)
        if permission_map:
            code = permission_map.get(getattr(view, "action", None), code)

        if code is None:
            return True
        return user.has_permission(code)
