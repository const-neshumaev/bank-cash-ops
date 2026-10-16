"""Data transfer objects and stable constants of the ``references`` module."""

from __future__ import annotations

from dataclasses import dataclass


class CurrencyRatePrinciple:
    """Stable identifiers of the principled rate kinds.

    A *principle* is what operation code branches on: it says which rate of a
    currency the engine should apply (the official accounting rate, the bank's
    buying or selling rate, or the cross rate used in a conversion). It is fixed
    in code, on purpose — the code that reasons about rates must not depend on
    rows an administrator can rename or delete. Concrete, bank-managed rate types
    reference one of these principles (see ``docs/adr/0017-references-module.md``).
    """

    OFFICIAL = "official"
    BUY = "buy"
    SELL = "sell"
    CONVERSION = "conversion"

    VALUES = (OFFICIAL, BUY, SELL, CONVERSION)


@dataclass(frozen=True)
class CurrencyDTO:
    """Immutable view of a currency crossing the module boundary."""

    code: str
    name: str
    symbol: str
    minor_units: int


@dataclass(frozen=True)
class RateTypeDTO:
    """Immutable view of a bank rate type crossing the module boundary."""

    code: str
    name: str
    principle: str
    is_active: bool
