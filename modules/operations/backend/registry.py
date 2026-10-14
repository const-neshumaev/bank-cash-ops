"""In-process implementation of the operation type registry (the SPI).

Extension modules declare their operation types (and, when needed, handlers)
here. The ``operations`` module reads the registry to sync its tables and to
resolve handlers when posting. The single instance is published to the shared
contract registry in :meth:`modules.operations.backend.apps.OperationsConfig.ready`.
"""

from __future__ import annotations

from modules.operations.contracts.dto import OperationTypeSpec
from modules.operations.contracts.services import OperationHandler


class OperationTypeRegistryService:
    """Stores the operation types and handlers declared by extension modules."""

    def __init__(self) -> None:
        self._types: dict[str, OperationTypeSpec] = {}
        self._handlers: dict[str, OperationHandler] = {}

    def register(self, spec: OperationTypeSpec, handler: OperationHandler | None = None) -> None:
        if spec.code in self._types:
            raise RuntimeError(f"Operation type '{spec.code}' is already registered")
        self._types[spec.code] = spec
        if handler is not None:
            self._handlers[spec.code] = handler

    def get_handler(self, operation_type_code: str) -> OperationHandler | None:
        return self._handlers.get(operation_type_code)

    def get_type(self, operation_type_code: str) -> OperationTypeSpec | None:
        return self._types.get(operation_type_code)

    def types(self) -> tuple[OperationTypeSpec, ...]:
        return tuple(self._types.values())

    def has(self, operation_type_code: str) -> bool:
        return operation_type_code in self._types

    def unregister(self, operation_type_code: str) -> None:
        """Forget an operation type (used by tests and extension teardown)."""
        self._types.pop(operation_type_code, None)
        self._handlers.pop(operation_type_code, None)


#: The single registry instance shared inside the process.
operation_type_registry = OperationTypeRegistryService()
