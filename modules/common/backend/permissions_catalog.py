"""Registry of permission codes contributed by the installed modules.

Permissions are code-defined capabilities. Each module registers the catalog it
owns; the administration UI and role validation read the aggregation instead of
a single fixed list. This keeps the module boundaries: a module declares its
codes, the consumer reads the union.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class _CatalogEntry(Protocol):
    code: str
    name: str


@dataclass(frozen=True)
class PermissionEntry:
    """A permission catalog entry: its code and the human readable label."""

    code: str
    name: str


_catalog: dict[str, PermissionEntry] = {}


def register(entries: Iterable[_CatalogEntry]) -> None:
    """Add the catalog entries contributed by a module (idempotent by code)."""
    for entry in entries:
        _catalog[entry.code] = PermissionEntry(code=entry.code, name=entry.name)


def all_entries() -> list[PermissionEntry]:
    """Every registered entry, ordered by code."""
    return sorted(_catalog.values(), key=lambda entry: entry.code)


def all_codes() -> list[str]:
    """Every registered permission code."""
    return [entry.code for entry in all_entries()]


def is_known_code(code: str) -> bool:
    """Return whether ``code`` is registered by any module."""
    return code in _catalog
