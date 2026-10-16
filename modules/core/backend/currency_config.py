"""Effective currency configuration of a cash desk.

The currencies allowed at a cash desk are resolved dynamically (see
``docs/adr/0014-cash-desk-configuration-templates.md``):

1. the cash desk's own currencies, when it has any (an override);
2. otherwise the nearest defined template on the branch path — the cash desk's
   branch, its ancestors and finally the bank-wide template;
3. with neither, no currency is allowed (deny by default).

A template that exists but lists no currencies is a defined, empty template and
therefore also denies every currency.

A currency is stored (and referenced) by its ISO code; the code catalogue lives
in the ``references`` module and is consulted through its contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.common.contracts import registry
from modules.core.backend import scoping
from modules.core.backend.models import (
    CashDesk,
    CashDeskCurrency,
    CurrencyTemplate,
    CurrencyTemplateItem,
)
from modules.references.contracts import REFERENCE_DIRECTORY

#: Sources of an effective configuration.
OWN = "own"
BRANCH = "branch"
BANK = "bank"
NONE = "none"


@dataclass(frozen=True)
class EffectiveCurrencyConfig:
    """The currencies in force at a cash desk and where they come from."""

    codes: tuple[str, ...]
    source: str
    template_branch_id: int | None = None


def configured_currency_codes(cash_desk_id: int) -> list[str] | None:
    """Return the currencies set on a cash desk, or ``None`` when not overridden."""
    codes = list(
        CashDeskCurrency.objects.filter(cash_desk_id=cash_desk_id).values_list(
            "currency_code", flat=True
        )
    )
    return codes or None


def template_currency_codes(branch_id: int | None) -> set[str] | None:
    """Return the currencies of a template, or ``None`` when it is not defined."""
    template = CurrencyTemplate.objects.filter(branch_id=branch_id).first()
    if template is None:
        return None
    return set(template.items.values_list("currency_code", flat=True))


def effective_currency_config(cash_desk_id: int) -> EffectiveCurrencyConfig:
    """Resolve the effective currencies of a cash desk and their source."""
    own = configured_currency_codes(cash_desk_id)
    if own is not None:
        return EffectiveCurrencyConfig(codes=tuple(sorted(own)), source=OWN)

    branch_id = CashDesk.objects.filter(pk=cash_desk_id).values_list("branch_id", flat=True).first()
    if branch_id is not None:
        for ancestor_id in scoping.branch_ancestor_ids(branch_id):
            codes = template_currency_codes(ancestor_id)
            if codes is not None:
                return EffectiveCurrencyConfig(
                    codes=tuple(sorted(codes)),
                    source=BRANCH,
                    template_branch_id=ancestor_id,
                )

    bank = template_currency_codes(None)
    if bank is not None:
        return EffectiveCurrencyConfig(codes=tuple(sorted(bank)), source=BANK)

    return EffectiveCurrencyConfig(codes=(), source=NONE)


def effective_currency_codes(cash_desk_id: int) -> set[str]:
    """Return the effective currencies of a cash desk (empty means none)."""
    return set(effective_currency_config(cash_desk_id).codes)


def _resolve_currency_codes(codes) -> list[str]:
    """Validate currency codes against the catalogue, de-duplicated and ordered."""
    directory = registry.get(REFERENCE_DIRECTORY)
    normalised = [code.strip().upper() for code in codes]
    unknown = sorted({code for code in normalised if directory.get_currency(code) is None})
    if unknown:
        raise ValidationError(
            {"currencies": _("Unknown currencies: %(codes)s.") % {"codes": ", ".join(unknown)}}
        )
    return list(dict.fromkeys(normalised))


def set_cash_desk_currencies(cash_desk: CashDesk, codes) -> None:
    """Replace the currencies of a cash desk; an empty list removes the override."""
    resolved = _resolve_currency_codes(codes)
    with transaction.atomic():
        CashDeskCurrency.objects.filter(cash_desk=cash_desk).delete()
        for code in resolved:
            CashDeskCurrency.objects.create(cash_desk=cash_desk, currency_code=code)


def set_template_currencies(branch_id: int | None, codes) -> CurrencyTemplate:
    """Create or replace a currency template for the bank or a single branch."""
    resolved = _resolve_currency_codes(codes)
    with transaction.atomic():
        template, _ = CurrencyTemplate.objects.get_or_create(branch_id=branch_id)
        CurrencyTemplateItem.objects.filter(template=template).delete()
        for code in resolved:
            CurrencyTemplateItem.objects.create(template=template, currency_code=code)
    return template


def delete_template(branch_id: int | None) -> None:
    """Remove the currency template for the bank or a branch, if it exists."""
    CurrencyTemplate.objects.filter(branch_id=branch_id).delete()
