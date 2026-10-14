"""Register codes published by the ``operations`` module.

Handlers and declarative posting templates refer to registers by these codes.
Registers are code-defined structural concepts (unlike operation types, which
are data).
"""

from __future__ import annotations


class RegisterCode:
    """Stable identifiers of the registers the engine understands."""

    #: Cash on hand at a cash desk, per currency. Carries a balance.
    CASH = "cash"

    #: Operation turnover, per cash desk, currency and operation type.
    TURNOVER = "turnover"
