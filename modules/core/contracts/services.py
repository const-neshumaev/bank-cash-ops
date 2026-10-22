"""Service interfaces published by the ``core`` module.

Other modules depend on these abstractions, never on the concrete
implementation that lives in ``modules.core.backend``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from modules.core.contracts.dto import (
    BankSettingsDTO,
    CashDeskDTO,
    CurrencyRateDTO,
    ShiftDTO,
    UserDTO,
)


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

    def accessible_branch_ids(self, user_id: int) -> set[int] | None:
        """Branches the user may see; ``None`` means every branch."""
        ...

    def branch_ancestor_ids(self, branch_id: int) -> tuple[int, ...]:
        """Return ``branch_id`` and its ancestors, nearest first (up to the root)."""
        ...

    def user_can_access_cash_desk(self, user_id: int, cash_desk_id: int) -> bool: ...


class CashDeskConfigDirectory(Protocol):
    """Read-only access to a cash desk's currency configuration and rates.

    The currency and rate-type *dictionaries* live in the ``references`` module;
    this contract only exposes the cash desk specific configuration (which
    currencies are enabled and the effective rates). Currency and rate type
    values are addressed by their codes.
    """

    def cash_desk_currency_codes(self, cash_desk_id: int) -> set[str]:
        """Effective currencies enabled at a cash desk.

        An empty set means no currency is allowed: the cash desk has neither its
        own currencies nor an applicable template (deny by default).
        """
        ...

    def rate(
        self,
        currency_code: str,
        rate_type: str,
        *,
        target_currency: str | None = None,
        cash_desk_id: int | None = None,
        at: datetime | None = None,
    ) -> Decimal | None:
        """Effective rate of one unit of ``currency_code``.

        The scope is resolved from the cash desk upwards (cash desk, its branch,
        parent branches, bank), with ``uses_individual_rates`` cutting off the
        levels above. The national bank rate is always bank-wide. Rates are
        looked up against the bank's base currency; a ``conversion`` rate with
        the bank's direct conversion mode uses ``target_currency`` as the quote
        currency. The quoted value is normalized to one unit.
        """
        ...

    def cash_desk_rates(self, cash_desk_id: int) -> tuple[CurrencyRateDTO, ...]:
        """Effective rates in force at a cash desk."""
        ...


class BankSettingsDirectory(Protocol):
    """Read-only access to the bank-wide settings other modules rely on.

    The national currency, the conversion mode and the effective base value are
    owned by ``core``. Modules that evaluate client-data thresholds or convert
    amounts read them through this contract instead of ``core``'s tables.
    """

    def get_settings(self, on: date | None = None) -> BankSettingsDTO:
        """Return the settings and the base value in force on ``on``."""
        ...
