"""In-process registry that resolves module contracts by name.

Modules never import each other's internals: a consumer asks the registry for
the implementation of a published contract. This is the single seam that later
allows the same contract to be backed by a remote (HTTP) client without touching
the consumer code.
"""

from __future__ import annotations

from typing import Any

_registry: dict[str, Any] = {}


def register(name: str, implementation: Any) -> None:
    """Bind a contract name to an implementation (called by the provider)."""
    if name in _registry:
        raise RuntimeError(f"Contract '{name}' is already registered")
    _registry[name] = implementation


def get(name: str) -> Any:
    """Return the implementation registered for a contract name."""
    try:
        return _registry[name]
    except KeyError as exc:
        raise LookupError(f"Contract '{name}' is not registered") from exc
