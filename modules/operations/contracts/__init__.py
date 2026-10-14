"""Public contract of the ``operations`` module.

Only the types re-exported here may be used by other modules and by operation
extensions.
"""

from modules.operations.contracts.dto import (
    MovementSpec,
    OperationContext,
    OperationKind,
    OperationRequest,
    OperationTypeDTO,
    OperationTypeSpec,
    PostingPlan,
    SlotSpec,
    SlotValue,
)
from modules.operations.contracts.registers import RegisterCode
from modules.operations.contracts.services import OperationHandler, OperationTypeRegistry

#: Name under which the operation type registry is published in
#: ``modules.common.contracts.registry``. Extensions resolve it to declare their
#: operation types and register their handlers::
#:
#:     from modules.common.contracts import registry
#:     registry.get(OPERATION_TYPES_REGISTRY).register(spec, MyHandler())
OPERATION_TYPES_REGISTRY = "operations.types"

__all__ = [
    "OPERATION_TYPES_REGISTRY",
    "MovementSpec",
    "OperationContext",
    "OperationHandler",
    "OperationKind",
    "OperationRequest",
    "OperationTypeDTO",
    "OperationTypeRegistry",
    "OperationTypeSpec",
    "PostingPlan",
    "RegisterCode",
    "SlotSpec",
    "SlotValue",
]
