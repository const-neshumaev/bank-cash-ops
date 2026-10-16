"""Public contract of the ``core`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.core.contracts.dto import (
    CashDeskDTO,
    CurrencyRateDTO,
    ShiftDTO,
    UserDTO,
)
from modules.core.contracts.services import (
    CashDeskConfigDirectory,
    OrgDirectory,
    UserDirectory,
)

#: Names under which the ``core`` services are published in
#: ``modules.common.contracts.registry``.
USER_DIRECTORY = "core.users"
ORG_DIRECTORY = "core.org"
CASH_DESK_CONFIG = "core.cash_desk_config"

__all__ = [
    "CASH_DESK_CONFIG",
    "ORG_DIRECTORY",
    "USER_DIRECTORY",
    "CashDeskConfigDirectory",
    "CashDeskDTO",
    "CurrencyRateDTO",
    "OrgDirectory",
    "ShiftDTO",
    "UserDTO",
    "UserDirectory",
]
