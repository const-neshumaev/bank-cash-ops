"""Rate resolution and amount computation for exchange operations.

The concrete bank rate type is configured by an administrator on the operation
type. This module knows only the *direction* declared by the operation
(``buy``, ``sell`` or ``conversion``) and asks ``core`` for the effective rate.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.common.contracts import registry
from modules.core.contracts import BANK_SETTINGS, CASH_DESK_CONFIG
from modules.operations.backend.models import OperationType
from modules.operations.contracts.dto import OperationRatePrinciple
from modules.references.contracts import REFERENCE_DIRECTORY, SystemRateTypeCode

RATE_QUANT = Decimal("0.00000001")


def _settings():
    return registry.get(BANK_SETTINGS)


def _cash_desk_config():
    return registry.get(CASH_DESK_CONFIG)


def base_currency() -> str:
    """Return the bank's national currency."""
    return _settings().get_settings().base_currency


def conversion_mode() -> str:
    """Return the bank's conversion mode (``via_base`` or ``direct``)."""
    return _settings().get_settings().conversion_mode


def resolve_exchange_rate(
    operation_type: OperationType,
    *,
    source_currency: str,
    target_currency: str,
    cash_desk_id: int,
    at: datetime,
) -> Decimal | None:
    """Resolve the rate of one source unit expressed in the target currency.

    ``buy`` is the rate at which the bank buys the foreign currency, ``sell`` is
    the rate at which it sells it, and ``conversion`` is the cross rate between
    two foreign currencies.
    """
    rate_type = (operation_type.rate_type or "").strip()
    if not rate_type:
        raise ValidationError(
            _("The rate type is not configured for the operation type '%(code)s'.")
            % {"code": operation_type.code}
        )

    config = _cash_desk_config()
    principle = operation_type.rate_principle

    if principle == OperationRatePrinciple.BUY:
        return config.rate(source_currency, rate_type, cash_desk_id=cash_desk_id, at=at)
    if principle == OperationRatePrinciple.SELL:
        return config.rate(target_currency, rate_type, cash_desk_id=cash_desk_id, at=at)
    if principle == OperationRatePrinciple.CONVERSION:
        return _conversion_rate(
            rate_type,
            source_currency=source_currency,
            target_currency=target_currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
    return None


def _conversion_rate(
    rate_type: str,
    *,
    source_currency: str,
    target_currency: str,
    cash_desk_id: int,
    at: datetime,
) -> Decimal | None:
    """Resolve a conversion rate, direct or through the national currency."""
    config = _cash_desk_config()
    if conversion_mode() == "direct":
        # Direct pairs are stored under the two system side types. The bank
        # buys the currency it receives, so ``conversion_buy`` of the
        # source/target pair is the rate of this operation; when only the
        # reverse pair exists, the opposite side is used and inverted.
        direct = _direct_pair_rate(
            source_currency=source_currency,
            target_currency=target_currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if direct is not None:
            return direct

        direct = config.rate(
            source_currency,
            rate_type,
            target_currency=target_currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if direct is not None:
            return direct
        reverse = config.rate(
            target_currency,
            rate_type,
            target_currency=source_currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if reverse is not None and reverse != 0:
            return Decimal("1") / reverse

    source_rate = config.rate(source_currency, rate_type, cash_desk_id=cash_desk_id, at=at)
    target_rate = config.rate(target_currency, rate_type, cash_desk_id=cash_desk_id, at=at)
    if source_rate is None or target_rate is None or target_rate == 0:
        return None
    return source_rate / target_rate


def _direct_pair_rate(
    *,
    source_currency: str,
    target_currency: str,
    cash_desk_id: int,
    at: datetime,
) -> Decimal | None:
    """Return the rate of receiving ``source`` and issuing ``target``.

    The bank buys the received currency and sells the issued one. A direct
    pair is stored in both directions independently, so the operation takes the
    buying side of the source/target pair or, when only the reverse pair is
    configured, the selling side of the target/source pair inverted.
    """
    config = _cash_desk_config()
    buying = config.rate(
        source_currency,
        SystemRateTypeCode.CONVERSION_BUY,
        target_currency=target_currency,
        cash_desk_id=cash_desk_id,
        at=at,
    )
    if buying is not None:
        return buying

    selling = config.rate(
        target_currency,
        SystemRateTypeCode.CONVERSION_SELL,
        target_currency=source_currency,
        cash_desk_id=cash_desk_id,
        at=at,
    )
    if selling is not None and selling != 0:
        return Decimal("1") / selling
    return None


def quantize_rate(value: Decimal) -> Decimal:
    """Normalise a computed rate to the journal's precision."""
    return value.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def quantize_amount(value: Decimal, currency: str) -> Decimal:
    """Round an amount to the currency's minor units."""
    directory = registry.get(REFERENCE_DIRECTORY)
    currency_dto = directory.get_currency(currency)
    minor_units = currency_dto.minor_units if currency_dto is not None else 2
    return value.quantize(Decimal(1).scaleb(-minor_units), rounding=ROUND_HALF_UP)
