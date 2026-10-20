"""Data transfer objects published by the ``operations`` module.

These are the types an operation handler receives and returns, plus the
declarations an extension publishes to describe its operation types. The engine
builds a request, hands it to a handler and applies the resulting plan. See
``docs/adr/0006-operations-extensibility-spi.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


class OperationKind:
    """Stable identifiers of the operation kinds (the direction of cash flow)."""

    INCOME = "income"
    EXPENSE = "expense"
    EXCHANGE = "exchange"
    INTERNAL = "internal"


@dataclass(frozen=True)
class OperationTypeDTO:
    """Immutable view of an operation type crossing the module boundary."""

    code: str
    name: str
    kind: str
    is_external: bool
    requires_client: bool


@dataclass(frozen=True)
class SlotValue:
    """A filled amount slot of an operation: one currency with an amount."""

    slot: str
    currency: str
    amount: Decimal
    rate: Decimal | None = None


@dataclass(frozen=True)
class OperationContext:
    """Execution context shared by every posting of an operation."""

    cash_desk_id: int
    shift_id: int
    cashier_id: int
    operation_type_code: str
    kind: str


@dataclass(frozen=True)
class OperationRequest:
    """Everything a handler needs to describe an operation's postings."""

    operation_type: OperationTypeDTO
    context: OperationContext
    lines: tuple[SlotValue, ...]


@dataclass(frozen=True)
class MovementSpec:
    """A register movement a handler asks the engine to apply.

    The movement always concerns the operation's cash desk. ``amount`` is
    signed: a positive value increases the register, a negative value decreases
    it.
    """

    register: str
    currency: str
    amount: Decimal


@dataclass(frozen=True)
class PostingPlan:
    """The set of register movements an operation produces."""

    movements: tuple[MovementSpec, ...]


@dataclass(frozen=True)
class SlotSpec:
    """Declaration of an amount slot an operation type expects.

    ``translations`` maps a language code to the slot name in that language;
    ``name`` stays the base-language value (see
    ``docs/adr/0016-translatable-reference-data.md``).
    """

    code: str
    name: str
    required: bool = True
    fixed_currency: str = ""
    order: int = 0
    translations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationTypeSpec:
    """Declaration of an operation type published by an extension module.

    An extension declares its operation types; the ``operations`` module
    materialises them into its own tables (see the ``sync_operation_types``
    command). Simple operations are fully described by ``slots`` and
    ``template``; non-trivial ones also register a handler.

    The client-data settings are seeded on creation only: an administrator may
    change them later, and synchronisation never overwrites them. ``requires_client``
    and ``client_id_threshold`` are kept for compatibility with existing
    extensions; new declarations should use ``client_data_policy``,
    ``threshold_type``, ``threshold_value`` and ``threshold_currency``. A legacy
    declaration with ``requires_client=True`` seeds the ``always`` policy.

    ``translations`` maps a language code to the type name in that language;
    ``name`` stays the base-language value (see
    ``docs/adr/0016-translatable-reference-data.md``).
    """

    code: str
    name: str
    kind: str
    slots: tuple[SlotSpec, ...] = ()
    template: dict[str, Any] = field(default_factory=dict)
    is_external: bool = False
    requires_client: bool = False
    client_id_threshold: Decimal | None = None
    client_data_policy: str = ""
    threshold_type: str = ""
    threshold_value: Decimal | None = None
    threshold_currency: str = ""
    permission_code: str = ""
    translations: dict[str, str] = field(default_factory=dict)
