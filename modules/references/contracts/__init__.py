"""Public contract of the ``references`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.references.contracts.dto import (
    CurrencyDTO,
    CurrencyRatePrinciple,
    RateTypeDTO,
    RateTypeValidity,
    SystemRateTypeCode,
)
from modules.references.contracts.services import RateTypeUsageGuard, ReferenceDirectory

#: Name under which the ``references`` service is published in
#: ``modules.common.contracts.registry``.
REFERENCE_DIRECTORY = "references.directory"

#: Optional guard implemented by the module that owns the rates, answering
#: whether a rate type can still change its storage semantics.
RATE_TYPE_USAGE_GUARD = "references.rate_type_usage_guard"

__all__ = [
    "RATE_TYPE_USAGE_GUARD",
    "REFERENCE_DIRECTORY",
    "CurrencyDTO",
    "CurrencyRatePrinciple",
    "RateTypeDTO",
    "RateTypeUsageGuard",
    "RateTypeValidity",
    "ReferenceDirectory",
    "SystemRateTypeCode",
]
