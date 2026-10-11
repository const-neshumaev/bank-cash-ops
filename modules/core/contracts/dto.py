"""Data transfer objects published by the ``core`` module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserDTO:
    """Immutable view of a user crossing the module boundary."""

    id: int
    email: str
    role: str
    is_active: bool
