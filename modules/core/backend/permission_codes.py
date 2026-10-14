"""Catalog of the permission codes owned by the ``core`` module.

Permissions are code-defined capabilities: the code that *enforces* a
permission declares it here. Roles are data (administrators create and edit
them) and reference these codes. Each module declares the codes it owns; the
administration UI renders the aggregation of all modules' catalogs
(``modules.common.backend.permissions_catalog``).
"""

from __future__ import annotations

from dataclasses import dataclass


class PermissionCode:
    """Stable identifiers of the permissions the application understands."""

    USERS_VIEW = "core.users.view"
    USERS_MANAGE = "core.users.manage"

    ROLES_VIEW = "core.roles.view"
    ROLES_MANAGE = "core.roles.manage"

    STRUCTURE_VIEW = "core.structure.view"
    STRUCTURE_MANAGE = "core.structure.manage"

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
    Permission(PermissionCode.USERS_VIEW, "Просмотр пользователей"),
    Permission(PermissionCode.USERS_MANAGE, "Управление пользователями"),
    Permission(PermissionCode.ROLES_VIEW, "Просмотр ролей"),
    Permission(PermissionCode.ROLES_MANAGE, "Управление ролями"),
    Permission(PermissionCode.STRUCTURE_VIEW, "Просмотр структуры банка"),
    Permission(PermissionCode.STRUCTURE_MANAGE, "Управление структурой банка"),
    Permission(PermissionCode.SHIFTS_VIEW, "Просмотр кассовых смен"),
    Permission(PermissionCode.SHIFTS_OPEN, "Открытие кассовой смены"),
    Permission(PermissionCode.SHIFTS_CLOSE, "Закрытие своей смены"),
    Permission(PermissionCode.SHIFTS_MANAGE, "Управление кассовыми сменами"),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the permission catalog."""
    return code in _CODE_TO_NAME
