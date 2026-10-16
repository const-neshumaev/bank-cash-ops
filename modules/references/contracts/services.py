"""Service interfaces published by the ``references`` module.

Other modules depend on these abstractions, never on the concrete implementation
that lives in ``modules.references.backend``.
"""

from __future__ import annotations

from typing import Protocol

from modules.references.contracts.dto import CurrencyDTO, RateTypeDTO


class ReferenceDirectory(Protocol):
    """Read-only access to the system reference data (currencies, rate types)."""

    def currencies(self) -> tuple[CurrencyDTO, ...]:
        """Return the active currencies, ordered by code."""
        ...

    def get_currency(self, code: str) -> CurrencyDTO | None:
        """Return a currency by its code, or ``None`` when it is unknown."""
        ...

    def rate_types(self) -> tuple[RateTypeDTO, ...]:
        """Return the active rate types, ordered for presentation."""
        ...

    def get_rate_type(self, code: str) -> RateTypeDTO | None:
        """Return a rate type by its code, or ``None`` when it is unknown."""
        ...
