"""Catalog of permission codes used by the ``printing`` module."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


class PermissionCode:
    """Stable identifiers of the permissions the ``printing`` module understands."""

    TEMPLATES_VIEW = "printing.templates.view"
    TEMPLATES_MANAGE = "printing.templates.manage"
    PRINT = "printing.print"


@dataclass(frozen=True)
class Permission:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


CATALOG: tuple[Permission, ...] = (
    Permission(PermissionCode.TEMPLATES_VIEW, _("View print templates")),
    Permission(PermissionCode.TEMPLATES_MANAGE, _("Manage print templates")),
    Permission(PermissionCode.PRINT, _("Print documents")),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the module's permission catalog."""
    return code in _CODE_TO_NAME
