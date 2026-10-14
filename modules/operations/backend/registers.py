"""Internal register helpers for the operation engine.

The register codes themselves are part of the module contract
(``modules.operations.contracts.registers``); they are re-exported here so the
engine and its tests keep a single import site.
"""

from __future__ import annotations

from modules.operations.contracts.registers import RegisterCode

#: Registers whose balance is materialised in the ``CashBalance`` table.
BALANCED_REGISTERS: frozenset[str] = frozenset({RegisterCode.CASH})

__all__ = ["BALANCED_REGISTERS", "RegisterCode"]
