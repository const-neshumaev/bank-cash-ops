"""Catalog of the permission codes owned by the ``core`` module.

Permissions are code-defined capabilities: the code that *enforces* a
permission declares it here. Roles are data (administrators create and edit
them) and reference these codes. Each module declares the codes it owns; the
administration UI renders the aggregation of all modules' catalogs
(``modules.common.backend.permissions_catalog``).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


class PermissionCode:
    """Stable identifiers of the permissions the application understands."""

    USERS_VIEW = "core.users.view"
    USERS_MANAGE = "core.users.manage"

    ROLES_VIEW = "core.roles.view"
    ROLES_MANAGE = "core.roles.manage"

    STRUCTURE_VIEW = "core.structure.view"
    STRUCTURE_MANAGE = "core.structure.manage"

    CURRENCIES_CONFIG_MANAGE = "core.currencies.config.manage"
    CURRENCIES_CONFIG_MANAGE_BRANCH = "core.currencies.config.manage.branch"

    BANK_SETTINGS_MANAGE = "core.bank_settings.manage"
    BASE_VALUES_VIEW = "core.base_values.view"
    BASE_VALUES_MANAGE = "core.base_values.manage"

    SHIFTS_VIEW = "core.shifts.view"
    SHIFTS_OPEN = "core.shifts.open"
    SHIFTS_CLOSE = "core.shifts.close"
    SHIFTS_MANAGE = "core.shifts.manage"


@dataclass(frozen=True)
class Permission:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


CATALOG: tuple[Permission, ...] = (
    Permission(PermissionCode.USERS_VIEW, _("View users")),
    Permission(PermissionCode.USERS_MANAGE, _("Manage users")),
    Permission(PermissionCode.ROLES_VIEW, _("View roles")),
    Permission(PermissionCode.ROLES_MANAGE, _("Manage roles")),
    Permission(PermissionCode.STRUCTURE_VIEW, _("View bank structure")),
    Permission(PermissionCode.STRUCTURE_MANAGE, _("Manage bank structure")),
    Permission(PermissionCode.CURRENCIES_CONFIG_MANAGE, _("Configure cash desk currencies")),
    Permission(
        PermissionCode.CURRENCIES_CONFIG_MANAGE_BRANCH,
        _("Configure cash desk currencies of own branch"),
    ),
    Permission(PermissionCode.BANK_SETTINGS_MANAGE, _("Manage bank settings")),
    Permission(PermissionCode.BASE_VALUES_VIEW, _("View base values")),
    Permission(PermissionCode.BASE_VALUES_MANAGE, _("Manage base values")),
    Permission(PermissionCode.SHIFTS_VIEW, _("View cash shifts")),
    Permission(PermissionCode.SHIFTS_OPEN, _("Open a cash shift")),
    Permission(PermissionCode.SHIFTS_CLOSE, _("Close own shift")),
    Permission(PermissionCode.SHIFTS_MANAGE, _("Manage cash shifts")),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the permission catalog."""
    return code in _CODE_TO_NAME
