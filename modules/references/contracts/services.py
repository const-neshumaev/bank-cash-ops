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


class RateTypeUsageGuard(Protocol):
    """Answers whether a bank rate type already has rates stored by another module.

    The ``references`` module owns the rate types, while the rates themselves
    belong to ``core``. The check cannot query ``core`` tables directly, so the
    owner of the rates implements this small callback contract and registers it
    in the service registry. When no implementation is registered, the guard is
    considered absent and the change is allowed.
    """

    def is_rate_type_used(self, code: str) -> bool:
        """Return whether at least one rate of this type exists."""
        ...
