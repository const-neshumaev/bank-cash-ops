"""Currency rate resolution and setting.

A rate is stored at one of three scopes: bank, branch or cash desk. Resolution
walks from the cash desk upwards (cash desk -> its branch -> parent branches ->
bank), unless an ``uses_individual_rates`` flag cuts off the levels above it.
The national bank rate is always bank-wide and ignores the flags.

The rate type (owned by ``references``) decides how a rate is stored:

* ``calendar_day`` — one active rate per local date and scope; a correction
  creates a new version and marks the previous one as superseded;
* ``since_set`` — a rate takes effect at an explicit date and time; the latest
  rate not in the future wins.

See ``docs/architecture-module-core.md`` and
``docs/adr/0019-currency-rate-setting.md``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from modules.common.contracts import registry
from modules.core.backend import scoping
from modules.core.backend.models import BankSettings, Branch, CashDesk, CurrencyRate, Shift
from modules.core.backend.permission_codes import PermissionCode
from modules.references.contracts import (
    REFERENCE_DIRECTORY,
    CurrencyRatePrinciple,
    RateTypeDTO,
    RateTypeValidity,
    SystemRateTypeCode,
)

BANK = "bank"
BRANCH = "branch"
CASH_DESK = "cash_desk"

MANAGE_PERMISSIONS = (
    PermissionCode.CURRENCY_RATES_MANAGE,
    PermissionCode.CURRENCY_RATES_MANAGE_BRANCH,
    PermissionCode.CURRENCY_RATES_MANAGE_CASH_DESK,
    PermissionCode.CURRENCY_RATES_MANAGE_OFFICIAL,
)


def rate_type(code: str) -> RateTypeDTO | None:
    """Return the bank rate type by its code."""
    return registry.get(REFERENCE_DIRECTORY).get_rate_type((code or "").strip())


def _normalise_currency(code: str) -> str:
    return (code or "").strip().upper()


def _scope_filter(branch_id: int | None = None, cash_desk_id: int | None = None) -> dict:
    """Return the ORM filter for a rate scope."""
    if cash_desk_id is not None:
        return {"cash_desk_id": cash_desk_id, "branch__isnull": True}
    if branch_id is not None:
        return {"branch_id": branch_id, "cash_desk__isnull": True}
    return {"branch__isnull": True, "cash_desk__isnull": True}


def local_day_start(moment: datetime) -> datetime:
    """Return the start of the local day containing ``moment``."""
    return timezone.localtime(moment).replace(hour=0, minute=0, second=0, microsecond=0)


def _latest_at_scope(
    currency: str,
    base_currency: str,
    rate_type_dto: RateTypeDTO,
    moment: datetime,
    *,
    branch_id: int | None = None,
    cash_desk_id: int | None = None,
) -> CurrencyRate | None:
    """Return the active rate of a scope effective at ``moment``.

    ``daily_required`` decides whether a rate of the operation date is mandatory
    or the latest value in force is enough; ``validity`` decides how the rate is
    stored (by date or by an explicit moment).
    """
    queryset = CurrencyRate.objects.filter(
        superseded_at__isnull=True,
        currency=currency,
        base_currency=base_currency,
        rate_type=rate_type_dto.code,
        **_scope_filter(branch_id, cash_desk_id),
    )
    if rate_type_dto.validity == RateTypeValidity.CALENDAR_DAY:
        if rate_type_dto.daily_required:
            queryset = queryset.filter(effective_date=timezone.localdate(moment))
        else:
            queryset = queryset.filter(effective_date__lte=timezone.localdate(moment))
        return queryset.order_by("-effective_date", "-effective_from", "-id").first()

    queryset = queryset.filter(effective_date__isnull=True, effective_from__lte=moment)
    if rate_type_dto.daily_required:
        queryset = queryset.filter(effective_from__gte=local_day_start(moment))
    return queryset.order_by("-effective_from", "-id").first()


def _resolve_branch_chain(
    currency: str,
    base_currency: str,
    rate_type_dto: RateTypeDTO,
    moment: datetime,
    branch_id: int | None,
) -> CurrencyRate | None:
    """Walk the branch chain and return the first applicable rate."""
    current_id = branch_id
    while current_id is not None:
        branch = (
            Branch.objects.filter(pk=current_id)
            .only("id", "parent_id", "uses_individual_rates")
            .first()
        )
        if branch is None:
            break
        scoped = _latest_at_scope(
            currency, base_currency, rate_type_dto, moment, branch_id=branch.id
        )
        if scoped is not None:
            return scoped
        if branch.uses_individual_rates:
            return None
        current_id = branch.parent_id
    return _latest_at_scope(currency, base_currency, rate_type_dto, moment)


def resolve_rate(
    currency_code: str,
    rate_type_code: str,
    *,
    target_currency: str | None = None,
    cash_desk_id: int | None = None,
    at: datetime | None = None,
) -> CurrencyRate | None:
    """Return the effective rate row for a currency and rate type.

    Without ``cash_desk_id`` only the bank scope is consulted. The national bank
    rate is always bank-wide, regardless of the flags on branches and cash desks.

    ``target_currency`` selects the quote currency of a direct conversion rate
    (for example EUR/USD). It is only used when the bank's conversion mode is
    ``direct``; otherwise the rate is looked up against the bank's base currency.
    """
    rate_type_dto = rate_type(rate_type_code)
    if rate_type_dto is None or not rate_type_dto.is_active:
        return None
    moment = at or timezone.now()
    currency = _normalise_currency(currency_code)
    bank_settings = BankSettings.load()
    base_currency = bank_settings.base_currency
    if rate_type_dto.principle == CurrencyRatePrinciple.CONVERSION:
        if bank_settings.conversion_mode == BankSettings.ConversionMode.DIRECT:
            base_currency = _normalise_currency(target_currency) or base_currency
        elif target_currency and _normalise_currency(target_currency) != base_currency:
            # Direct pairs are not used while the bank converts via its base.
            return None

    if rate_type_dto.principle == CurrencyRatePrinciple.OFFICIAL:
        return _latest_at_scope(currency, base_currency, rate_type_dto, moment)

    if cash_desk_id is None:
        return _latest_at_scope(currency, base_currency, rate_type_dto, moment)

    cash_desk = CashDesk.objects.select_related("branch").filter(pk=cash_desk_id).first()
    if cash_desk is None:
        return None

    scoped = _latest_at_scope(
        currency, base_currency, rate_type_dto, moment, cash_desk_id=cash_desk.id
    )
    if scoped is not None:
        return scoped
    if cash_desk.uses_individual_rates:
        return None
    return _resolve_branch_chain(
        currency, base_currency, rate_type_dto, moment, cash_desk.branch_id
    )


def cash_desk_rates(cash_desk_id: int, at: datetime | None = None) -> list[CurrencyRate]:
    """Return every effective rate at a cash desk, honouring the scope flags."""
    cash_desk = CashDesk.objects.select_related("branch").filter(pk=cash_desk_id).first()
    if cash_desk is None:
        return []
    moment = at or timezone.now()
    branch_ids = scoping.branch_ancestor_ids(cash_desk.branch_id)
    candidate_rates = CurrencyRate.objects.filter(superseded_at__isnull=True).filter(
        Q(branch__isnull=True, cash_desk__isnull=True)
        | Q(branch_id__in=branch_ids, cash_desk__isnull=True)
        | Q(cash_desk_id=cash_desk.id)
    )
    keys = {(rate.currency, rate.base_currency, rate.rate_type) for rate in candidate_rates}
    resolved: list[CurrencyRate] = []
    for currency, base_currency, rate_type_code in sorted(keys):
        row = resolve_rate(
            currency,
            rate_type_code,
            target_currency=base_currency,
            cash_desk_id=cash_desk.id,
            at=moment,
        )
        if row is not None:
            resolved.append(row)
    return resolved


def visible_rates(queryset, user):
    """Narrow a rate queryset to what ``user`` may see.

    Bank rates are visible to every user with the view permission; branch and
    cash desk rates are visible only within the user's branch scope.
    """
    if user.is_superuser or user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE):
        return queryset
    branch_ids = scoping.accessible_branch_ids(user)
    if branch_ids is None:
        return queryset
    return queryset.filter(
        Q(branch__isnull=True, cash_desk__isnull=True)
        | Q(branch_id__in=branch_ids)
        | Q(cash_desk__branch_id__in=branch_ids)
    )


def _check_backdating(
    user,
    rate_type_dto: RateTypeDTO,
    *,
    effective_date: date | None,
    effective_from: datetime | None,
) -> None:
    """Only the bank administrator may set a rate retroactively."""
    if user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE):
        return
    if rate_type_dto.validity == RateTypeValidity.CALENDAR_DAY:
        if effective_date is not None and effective_date < timezone.localdate():
            raise ValidationError(
                {"effective_date": _("A past rate can only be set by a bank administrator.")}
            )
    elif effective_from is not None and effective_from < timezone.now() - timedelta(minutes=1):
        # The editor sends minutes, so a rate set for the current minute is a
        # normal "now" rather than backdating.
        raise ValidationError(
            {"effective_from": _("A past rate can only be set by a bank administrator.")}
        )


def check_can_set_rate(
    user,
    rate_type_dto: RateTypeDTO,
    *,
    branch: Branch | None = None,
    cash_desk: CashDesk | None = None,
) -> None:
    """Raise when ``user`` may not set a rate at the requested scope."""
    if branch is not None and cash_desk is not None:
        raise ValidationError(_("A rate belongs to one scope: bank, branch or cash desk."))

    if rate_type_dto.principle == CurrencyRatePrinciple.OFFICIAL:
        if branch is not None or cash_desk is not None:
            raise ValidationError(
                {"rate_type": _("The national bank rate is set for the whole bank.")}
            )
        if not user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE_OFFICIAL):
            raise PermissionDenied(_("You do not have permission to set the national bank rate."))
        return

    if branch is None and cash_desk is None:
        if not user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE):
            raise PermissionDenied(_("You do not have permission to perform this action."))
        return

    if cash_desk is not None:
        if user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE_BRANCH) and (
            scoping.can_access_branch(user, cash_desk.branch)
        ):
            return
        if user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE_CASH_DESK):
            shift = Shift.objects.filter(cashier=user, status=Shift.Status.OPEN).first()
            if shift is not None and shift.cash_desk_id == cash_desk.id:
                return
        raise PermissionDenied(_("You do not have permission to perform this action."))

    if not user.has_permission(PermissionCode.CURRENCY_RATES_MANAGE_BRANCH) or not (
        scoping.can_access_branch(user, branch)
    ):
        raise PermissionDenied(_("You do not have permission to perform this action."))


def _validate_scope(
    rate_type_dto: RateTypeDTO,
    branch: Branch | None,
    cash_desk: CashDesk | None,
) -> None:
    """Validate the combination of scope and rate type before writing."""
    if branch is None and cash_desk is None:
        return
    if branch is not None and cash_desk is not None:
        raise ValidationError(_("A rate belongs to one scope: bank, branch or cash desk."))
    if rate_type_dto.principle == CurrencyRatePrinciple.OFFICIAL:
        raise ValidationError({"rate_type": _("The national bank rate is set for the whole bank.")})


def _validate_currency(currency: str, base_currency: str, rate_type_dto: RateTypeDTO) -> None:
    directory = registry.get(REFERENCE_DIRECTORY)
    if directory.get_currency(currency) is None:
        raise ValidationError({"currency": _("Unknown currency.")})
    if directory.get_currency(base_currency) is None:
        raise ValidationError({"base_currency": _("Unknown currency.")})
    if currency == base_currency:
        raise ValidationError(
            {"base_currency": _("The base currency must differ from the currency.")}
        )
    if not rate_type_dto.is_active:
        raise ValidationError({"rate_type": _("The rate type is inactive.")})

    bank_settings = BankSettings.load()
    if rate_type_dto.principle == CurrencyRatePrinciple.CONVERSION:
        if (
            bank_settings.conversion_mode == BankSettings.ConversionMode.VIA_BASE
            and base_currency != bank_settings.base_currency
        ):
            raise ValidationError(
                {
                    "base_currency": _(
                        "Conversion through the base currency requires the bank's "
                        "base currency as the quote currency."
                    )
                }
            )
    elif base_currency != bank_settings.base_currency:
        raise ValidationError(
            {
                "base_currency": _(
                    "Only the bank's base currency can be used as the quote currency "
                    "for this rate type."
                )
            }
        )


def _validate_units(units: int | None) -> int:
    """Return a valid unit count or raise a field error."""
    if units is None or units < 1:
        raise ValidationError({"units": _("The number of units must be at least one.")})
    return units


def create_rate(
    user,
    *,
    rate_type: str,
    currency: str,
    base_currency: str,
    value,
    units: int = 1,
    effective_from: datetime | None = None,
    effective_date: date | None = None,
    branch: Branch | None = None,
    cash_desk: CashDesk | None = None,
) -> CurrencyRate:
    """Create a single rate; a second calendar-day rate for the date is refused."""
    rate_type_dto = registry.get(REFERENCE_DIRECTORY).get_rate_type(rate_type)
    if rate_type_dto is None:
        raise ValidationError({"rate_type": _("Unknown rate type.")})
    currency = _normalise_currency(currency)
    base_currency = _normalise_currency(base_currency)
    units = _validate_units(units)
    if value is not None and value <= 0:
        raise ValidationError({"value": _("The rate value must be greater than zero.")})
    _validate_currency(currency, base_currency, rate_type_dto)
    _validate_scope(rate_type_dto, branch, cash_desk)
    check_can_set_rate(user, rate_type_dto, branch=branch, cash_desk=cash_desk)
    _check_backdating(
        user,
        rate_type_dto,
        effective_date=effective_date,
        effective_from=effective_from,
    )

    if rate_type_dto.validity == RateTypeValidity.CALENDAR_DAY:
        if effective_date is None:
            raise ValidationError({"effective_date": _("A calendar-day rate requires a date.")})
        if CurrencyRate.objects.filter(
            superseded_at__isnull=True,
            currency=currency,
            base_currency=base_currency,
            rate_type=rate_type_dto.code,
            effective_date=effective_date,
            **_scope_filter(branch.id if branch else None, cash_desk.id if cash_desk else None),
        ).exists():
            raise ValidationError(
                {"effective_date": _("A rate of this type is already set for this date and scope.")}
            )

    try:
        with transaction.atomic():
            return CurrencyRate.objects.create(
                currency=currency,
                base_currency=base_currency,
                rate_type=rate_type_dto.code,
                units=units,
                value=value,
                effective_from=effective_from,
                effective_date=effective_date,
                branch=branch,
                cash_desk=cash_desk,
                created_by=user,
            )
    except IntegrityError:
        raise ValidationError(
            _("A rate with the same scope and effective time already exists.")
        ) from None
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from None


def bulk_set_conversion_pairs(
    user,
    *,
    pairs: list[dict],
    effective_from: datetime | None = None,
    effective_date: date | None = None,
    branch: Branch | None = None,
    cash_desk: CashDesk | None = None,
) -> list[CurrencyRate]:
    """Set both sides of direct conversion pairs atomically.

    The bank must use the direct conversion mode. Each pair is stored as the
    ``conversion_buy`` and ``conversion_sell`` rates with ``currency = source``
    and ``base_currency = target`` (for example EUR/USD).
    """
    bank_settings = BankSettings.load()
    if bank_settings.conversion_mode != BankSettings.ConversionMode.DIRECT:
        raise ValidationError(
            _("Direct conversion is not enabled for the bank.")
        )
    if not pairs:
        raise ValidationError({"pairs": _("At least one conversion pair is required.")})

    buy_type = rate_type(SystemRateTypeCode.CONVERSION_BUY)
    sell_type = rate_type(SystemRateTypeCode.CONVERSION_SELL)
    if buy_type is None or sell_type is None or not buy_type.is_active or not sell_type.is_active:
        raise ValidationError(
            _("The conversion rate types are not available.")
        )

    normalized: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        source = _normalise_currency(pair["currency"])
        target = _normalise_currency(pair["base_currency"])
        if source == target:
            raise ValidationError({"pairs": _("The conversion pair currencies must differ.")})
        if (source, target) in seen:
            raise ValidationError({"pairs": _("Each conversion pair can appear only once.")})
        units = _validate_units(pair.get("units", 1))
        if pair["buy"] <= 0 or pair["sell"] <= 0:
            raise ValidationError({"pairs": _("The rate value must be greater than zero.")})
        _validate_currency(source, target, buy_type)
        seen.add((source, target))
        normalized.append(
            {
                "currency": source,
                "base_currency": target,
                "units": units,
                "buy": pair["buy"],
                "sell": pair["sell"],
            }
        )

    _validate_scope(buy_type, branch, cash_desk)
    check_can_set_rate(user, buy_type, branch=branch, cash_desk=cash_desk)
    _check_backdating(
        user,
        buy_type,
        effective_date=effective_date,
        effective_from=effective_from,
    )

    created: list[CurrencyRate] = []
    with transaction.atomic():
        for pair in normalized:
            for rate_type_dto, value in (
                (buy_type, pair["buy"]),
                (sell_type, pair["sell"]),
            ):
                created.extend(
                    bulk_set_rates(
                        user,
                        rate_type=rate_type_dto.code,
                        items=[
                            {
                                "currency": pair["currency"],
                                "units": pair["units"],
                                "value": value,
                            }
                        ],
                        base_currency=pair["base_currency"],
                        effective_from=effective_from,
                        effective_date=effective_date,
                        branch=branch,
                        cash_desk=cash_desk,
                    )
                )
    return created


def bulk_set_rates(
    user,
    *,
    rate_type: str,
    items: list[dict],
    base_currency: str,
    effective_from: datetime | None = None,
    effective_date: date | None = None,
    branch: Branch | None = None,
    cash_desk: CashDesk | None = None,
) -> list[CurrencyRate]:
    """Set several rates of one type and scope atomically.

    For a ``calendar_day`` rate type an existing active rate of the same date and
    scope is replaced by a new version. For ``since_set`` a duplicate effective
    time is an error.
    """
    rate_type_dto = registry.get(REFERENCE_DIRECTORY).get_rate_type(rate_type)
    if rate_type_dto is None:
        raise ValidationError({"rate_type": _("Unknown rate type.")})
    _validate_scope(rate_type_dto, branch, cash_desk)
    check_can_set_rate(user, rate_type_dto, branch=branch, cash_desk=cash_desk)
    _check_backdating(
        user,
        rate_type_dto,
        effective_date=effective_date,
        effective_from=effective_from,
    )
    if not items:
        raise ValidationError({"items": _("At least one rate is required.")})

    if rate_type_dto.validity == RateTypeValidity.CALENDAR_DAY and effective_date is None:
        raise ValidationError({"effective_date": _("A calendar-day rate requires a date.")})
    if rate_type_dto.validity == RateTypeValidity.SINCE_SET and effective_from is None:
        raise ValidationError({"effective_from": _("A since-set rate requires a date and time.")})

    branch_id = branch.id if branch is not None else None
    cash_desk_id = cash_desk.id if cash_desk is not None else None
    base_currency = _normalise_currency(base_currency)
    created: list[CurrencyRate] = []

    try:
        with transaction.atomic():
            for item in items:
                currency = _normalise_currency(item["currency"])
                units = _validate_units(item.get("units", 1))
                if item["value"] <= 0:
                    raise ValidationError({"items": _("The rate value must be greater than zero.")})
                _validate_currency(currency, base_currency, rate_type_dto)
                existing = CurrencyRate.objects.filter(
                    superseded_at__isnull=True,
                    currency=currency,
                    base_currency=base_currency,
                    rate_type=rate_type_dto.code,
                    effective_date=effective_date,
                    **_scope_filter(branch_id, cash_desk_id),
                )
                if rate_type_dto.validity == RateTypeValidity.CALENDAR_DAY:
                    for previous in existing:
                        previous.superseded_at = timezone.now()
                        previous.save(update_fields=["superseded_at", "updated_at"])
                else:
                    if existing.filter(effective_from=effective_from).exists():
                        raise ValidationError(
                            {
                                "effective_from": _(
                                    "A rate with the same scope and effective time already exists."
                                )
                            }
                        )

                row = CurrencyRate.objects.create(
                    currency=currency,
                    base_currency=base_currency,
                    rate_type=rate_type_dto.code,
                    units=units,
                    value=item["value"],
                    effective_from=effective_from,
                    effective_date=effective_date,
                    branch=branch,
                    cash_desk=cash_desk,
                    created_by=user,
                )
                created.append(row)
    except IntegrityError:
        raise ValidationError(
            _("A rate with the same scope and effective time already exists.")
        ) from None
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from None
    return created
