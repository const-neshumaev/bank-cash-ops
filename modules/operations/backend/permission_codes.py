"""Catalog of permission codes used by the ``operations`` module.

Permissions are code-defined capabilities: the code that *enforces* a
permission declares it here. Roles are data and reference these codes. The
module registers its catalog at startup; the administration UI renders the
aggregation of all modules' catalogs
(``modules.common.backend.permissions_catalog``).
"""

from __future__ import annotations

from dataclasses import dataclass


class PermissionCode:
    """Stable identifiers of the permissions the ``operations`` module understands."""

    VIEW = "operations.view"
    CREATE = "operations.create"
    REVERSE = "operations.reverse"
    TYPES_MANAGE = "operations.types.manage"
    CONFIG_MANAGE = "operations.config.manage"


@dataclass(frozen=True)
class Permission:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


CATALOG: tuple[Permission, ...] = (
    Permission(PermissionCode.VIEW, "Просмотр кассовых операций"),
    Permission(PermissionCode.CREATE, "Выполнение кассовых операций"),
    Permission(PermissionCode.REVERSE, "Сторнирование операций"),
    Permission(PermissionCode.TYPES_MANAGE, "Управление типами операций"),
    Permission(PermissionCode.CONFIG_MANAGE, "Настройка операций и касс"),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the module's permission catalog."""
    return code in _CODE_TO_NAME
