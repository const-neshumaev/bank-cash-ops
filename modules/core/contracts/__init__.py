"""Public contract of the ``core`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.core.contracts.dto import CashDeskDTO, CurrencyDTO, CurrencyRateDTO, ShiftDTO, UserDTO
from modules.core.contracts.services import OrgDirectory, ReferenceDirectory, UserDirectory

#: Names under which the ``core`` services are published in
#: ``modules.common.contracts.registry``.
USER_DIRECTORY = "core.users"
ORG_DIRECTORY = "core.org"
REFERENCE_DIRECTORY = "core.references"

__all__ = [
    "ORG_DIRECTORY",
    "REFERENCE_DIRECTORY",
    "USER_DIRECTORY",
    "CashDeskDTO",
    "CurrencyDTO",
    "CurrencyRateDTO",
    "OrgDirectory",
    "ReferenceDirectory",
    "ShiftDTO",
    "UserDTO",
    "UserDirectory",
]
