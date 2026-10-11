"""Public contract of the ``core`` module.

Only the types re-exported here may be used by other modules.
"""

from modules.core.contracts.dto import UserDTO
from modules.core.contracts.services import UserDirectory

__all__ = ["UserDTO", "UserDirectory"]
