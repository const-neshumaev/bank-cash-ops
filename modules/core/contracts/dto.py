"""Data transfer objects published by the ``core`` module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class UserDTO:
    """Immutable view of a user crossing the module boundary."""

    id: int
    email: str
    role_codes: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True)
class CashDeskDTO:
    """Immutable view of a cashier workstation."""

    id: int
    branch_id: int
    is_active: bool


@dataclass(frozen=True)
class ShiftDTO:
    """Immutable view of a cashier shift."""

    id: int
    cash_desk_id: int
    cashier_id: int
    status: str


@dataclass(frozen=True)
class CurrencyDTO:
    """Immutable view of a currency."""

    code: str
    name: str
    symbol: str
    minor_units: int


@dataclass(frozen=True)
class CurrencyRateDTO:
    """Immutable view of a currency rate."""

    currency_code: str
    base_currency_code: str
    rate_type: str
    value: Decimal
    effective_from: datetime
    cash_desk_id: int | None
