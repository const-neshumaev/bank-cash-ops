"""Service interfaces published by the ``core`` module.

Other modules depend on these abstractions, never on the concrete
implementation that lives in ``modules.core.backend``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from modules.core.contracts.dto import CashDeskDTO, CurrencyDTO, CurrencyRateDTO, ShiftDTO, UserDTO


class UserDirectory(Protocol):
    """Read-only access to users and their permissions, offered to other modules."""

    def get_user(self, user_id: int) -> UserDTO | None: ...

    def is_admin(self, user_id: int) -> bool: ...

    def has_permission(self, user_id: int, permission: str) -> bool: ...


class OrgDirectory(Protocol):
    """Read-only access to the organisation structure and shifts.

    A module that works with cash desks (for example ``operations``) resolves
    the current shift and the caller's branch scope through this contract instead
    of reaching into ``core``'s tables.
    """

    def get_open_shift(self, cashier_id: int) -> ShiftDTO | None: ...

    def get_cash_desk(self, cash_desk_id: int) -> CashDeskDTO | None: ...

    def accessible_cash_desk_ids(self, user_id: int) -> set[int] | None:
        """Cash desks the user may see; ``None`` means every cash desk."""
        ...

    def user_can_access_cash_desk(self, user_id: int, cash_desk_id: int) -> bool: ...


class ReferenceDirectory(Protocol):
    """Read-only access to reference data: currencies and cash desk limits."""

    def currencies(self) -> tuple[CurrencyDTO, ...]: ...

    def get_currency(self, code: str) -> CurrencyDTO | None: ...

    def cash_desk_currency_codes(self, cash_desk_id: int) -> set[str] | None:
        """Currencies enabled on a cash desk; ``None`` means it is unrestricted."""
        ...

    def rate(
        self,
        currency_code: str,
        rate_type: str,
        *,
        cash_desk_id: int | None = None,
        at: datetime | None = None,
    ) -> Decimal | None:
        """Effective rate of ``currency_code``; a cash desk rate overrides the bank one."""
        ...

    def cash_desk_rates(self, cash_desk_id: int) -> tuple[CurrencyRateDTO, ...]:
        """Effective rates in force at a cash desk."""
        ...
