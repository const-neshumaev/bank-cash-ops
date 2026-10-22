"""Public contract of the ``core`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.core.contracts.dto import (
    BankSettingsDTO,
    CashDeskDTO,
    CurrencyRateDTO,
    ShiftDTO,
    UserDTO,
)
from modules.core.contracts.services import (
    BankSettingsDirectory,
    CashDeskConfigDirectory,
    OrgDirectory,
    UserDirectory,
)

#: Names under which the ``core`` services are published in
#: ``modules.common.contracts.registry``.
USER_DIRECTORY = "core.users"
ORG_DIRECTORY = "core.org"
CASH_DESK_CONFIG = "core.cash_desk_config"
BANK_SETTINGS = "core.bank_settings"

__all__ = [
    "BANK_SETTINGS",
    "CASH_DESK_CONFIG",
    "ORG_DIRECTORY",
    "USER_DIRECTORY",
    "BankSettingsDTO",
    "BankSettingsDirectory",
    "CashDeskConfigDirectory",
    "CashDeskDTO",
    "CurrencyRateDTO",
    "OrgDirectory",
    "ShiftDTO",
    "UserDTO",
    "UserDirectory",
]
