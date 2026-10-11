"""Service interfaces published by the ``core`` module.

Other modules depend on these abstractions, never on the concrete
implementation that lives in ``modules.core.backend``.
"""

from __future__ import annotations

from typing import Protocol

from modules.core.contracts.dto import UserDTO


class UserDirectory(Protocol):
    """Read-only access to users, offered to other modules."""

    def get_user(self, user_id: int) -> UserDTO | None: ...

    def is_admin(self, user_id: int) -> bool: ...
