"""Service interfaces published by the ``operations`` module.

``OperationHandler`` is the extension point. Modules that add operations
(``operations_standard``, bank specific extensions) implement it and register
their operation types through the operation type registry.
"""

from __future__ import annotations

from typing import Protocol

from modules.operations.contracts.dto import (
    OperationRequest,
    OperationTypeSpec,
    PostingPlan,
)


class OperationHandler(Protocol):
    """Describes how an operation affects the registers.

    A handler is a pure function over its request: it must **not** write to the
    database. It returns a posting plan that the engine applies atomically,
    together with the balance and overdraw checks.
    """

    def handle(self, request: OperationRequest) -> PostingPlan: ...


class OperationTypeRegistry(Protocol):
    """Registry of operation types and handlers, populated by extensions.

    An extension declares its operation types (metadata, slots and declarative
    template) and, when the posting needs computation, an ``OperationHandler``.
    The ``operations`` module reads the registry when it syncs its tables and
    when it posts an operation.
    """

    def register(
        self, spec: OperationTypeSpec, handler: OperationHandler | None = None
    ) -> None: ...

    def get_handler(self, operation_type_code: str) -> OperationHandler | None: ...

    def get_type(self, operation_type_code: str) -> OperationTypeSpec | None: ...

    def types(self) -> tuple[OperationTypeSpec, ...]: ...

    def has(self, operation_type_code: str) -> bool: ...
