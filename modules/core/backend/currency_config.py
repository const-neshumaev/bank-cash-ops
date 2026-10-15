"""Effective currency configuration of a cash desk.

The currencies allowed at a cash desk are resolved dynamically (see
``docs/adr/0014-cash-desk-configuration-templates.md``):

1. the cash desk's own currencies, when it has any (an override);
2. otherwise the nearest defined template on the branch path — the cash desk's
   branch, its ancestors and finally the bank-wide template;
3. with neither, no currency is allowed (deny by default).

A template that exists but lists no currencies is a defined, empty template and
therefore also denies every currency.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.core.backend import scoping
from modules.core.backend.models import CashDesk, CashDeskCurrency, Currency, CurrencyTemplate

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
            "currency__code", flat=True
        )
    )
    return codes or None


def template_currency_codes(branch_id: int | None) -> set[str] | None:
    """Return the currencies of a template, or ``None`` when it is not defined."""
    template = CurrencyTemplate.objects.filter(branch_id=branch_id).first()
    if template is None:
        return None
    return set(template.currencies.values_list("code", flat=True))


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


def _resolve_currencies(codes) -> list[Currency]:
    """Validate currency codes and return the matching instances, de-duplicated."""
    normalised = [code.strip().upper() for code in codes]
    found = Currency.objects.filter(code__in=normalised)
    currencies = {currency.code: currency for currency in found}
    unknown = sorted(set(normalised) - set(currencies))
    if unknown:
        raise ValidationError(
            {"currencies": _("Unknown currencies: %(codes)s.") % {"codes": ", ".join(unknown)}}
        )
    return [currencies[code] for code in dict.fromkeys(normalised)]


def set_cash_desk_currencies(cash_desk: CashDesk, codes) -> None:
    """Replace the currencies of a cash desk; an empty list removes the override."""
    currencies = _resolve_currencies(codes)
    with transaction.atomic():
        CashDeskCurrency.objects.filter(cash_desk=cash_desk).delete()
        for currency in currencies:
            CashDeskCurrency.objects.create(cash_desk=cash_desk, currency=currency)


def set_template_currencies(branch_id: int | None, codes) -> CurrencyTemplate:
    """Create or replace a currency template for the bank or a single branch."""
    currencies = _resolve_currencies(codes)
    with transaction.atomic():
        template, _ = CurrencyTemplate.objects.get_or_create(branch_id=branch_id)
        template.currencies.set(currencies)
    return template


def delete_template(branch_id: int | None) -> None:
    """Remove the currency template for the bank or a branch, if it exists."""
    CurrencyTemplate.objects.filter(branch_id=branch_id).delete()
