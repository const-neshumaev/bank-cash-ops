"""Catalog of permission codes used by the ``operations`` module.

Permissions are code-defined capabilities: the code that *enforces* a
permission declares it here. Roles are data and reference these codes. The
module registers its catalog at startup; the administration UI renders the
aggregation of all modules' catalogs
(``modules.common.backend.permissions_catalog``).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


class PermissionCode:
    """Stable identifiers of the permissions the ``operations`` module understands."""

    VIEW = "operations.view"
    CREATE = "operations.create"
    REVERSE = "operations.reverse"
    TYPES_MANAGE = "operations.types.manage"
    CONFIG_MANAGE = "operations.config.manage"
    CONFIG_MANAGE_BRANCH = "operations.config.manage.branch"


@dataclass(frozen=True)
class Permission:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


CATALOG: tuple[Permission, ...] = (
    Permission(PermissionCode.VIEW, _("View cash operations")),
    Permission(PermissionCode.CREATE, _("Perform cash operations")),
    Permission(PermissionCode.REVERSE, _("Reverse operations")),
    Permission(PermissionCode.TYPES_MANAGE, _("Manage operation types")),
    Permission(PermissionCode.CONFIG_MANAGE, _("Configure cash desk operations")),
    Permission(
        PermissionCode.CONFIG_MANAGE_BRANCH,
        _("Configure cash desk operations of own branch"),
    ),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the module's permission catalog."""
    return code in _CODE_TO_NAME
