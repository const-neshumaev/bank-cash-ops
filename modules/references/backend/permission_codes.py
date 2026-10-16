"""Catalog of the permission codes owned by the ``references`` module."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


class PermissionCode:
    """Stable identifiers of the permissions the application understands."""

    REFERENCES_VIEW = "references.view"
    REFERENCES_MANAGE = "references.manage"


@dataclass(frozen=True)
class Permission:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


CATALOG: tuple[Permission, ...] = (
    Permission(PermissionCode.REFERENCES_VIEW, _("View reference data")),
    Permission(PermissionCode.REFERENCES_MANAGE, _("Manage reference data")),
)

ALL_CODES: tuple[str, ...] = tuple(permission.code for permission in CATALOG)

_CODE_TO_NAME: dict[str, str] = {permission.code: permission.name for permission in CATALOG}


def is_known_code(code: str) -> bool:
    """Return whether ``code`` belongs to the permission catalog."""
    return code in _CODE_TO_NAME
