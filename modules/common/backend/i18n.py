"""Helpers for translating reference data with per-module translation tables.

Reference data (currencies, operation types, their slots) keeps the base-language
value in its main column and stores translations in a dedicated table owned by the
module that owns the data. The value handed to a client is the translation for the
active request language, falling back to the base value. See
``docs/adr/0016-translatable-reference-data.md``.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.utils.translation import get_language


def active_language() -> str:
    """Return the base code of the language activated for the current request."""
    return (get_language() or "").split("-")[0]


def pick_translation(
    base: str,
    translations: Iterable[tuple[str, str]],
    language: str | None = None,
) -> str:
    """Return the translation for ``language`` (the active one when omitted).

    ``translations`` is an iterable of ``(language, value)`` pairs. A blank value
    does not override the base value, so an empty translation simply falls back.
    """
    target = language or active_language()
    for code, value in translations:
        if code == target and value:
            return value
    return base
