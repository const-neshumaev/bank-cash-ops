"""Public contract of the ``references`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.references.contracts.dto import (
    CurrencyDTO,
    CurrencyRatePrinciple,
    RateTypeDTO,
)
from modules.references.contracts.services import ReferenceDirectory

#: Name under which the ``references`` service is published in
#: ``modules.common.contracts.registry``.
REFERENCE_DIRECTORY = "references.directory"

__all__ = [
    "REFERENCE_DIRECTORY",
    "CurrencyDTO",
    "CurrencyRatePrinciple",
    "RateTypeDTO",
    "ReferenceDirectory",
]
