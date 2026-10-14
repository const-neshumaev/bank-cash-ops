"""Concrete implementations of the ``core`` module's public contracts."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from modules.core.backend import scoping
from modules.core.backend.models import (
    CashDesk,
    CashDeskCurrency,
    Currency,
    CurrencyRate,
    Shift,
    User,
)
from modules.core.contracts.dto import CashDeskDTO, CurrencyDTO, CurrencyRateDTO, ShiftDTO, UserDTO


class UserDirectoryService:
    """In-process implementation of the ``UserDirectory`` contract."""

    def get_user(self, user_id: int) -> UserDTO | None:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return self._to_dto(user) if user is not None else None

    def is_admin(self, user_id: int) -> bool:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return bool(user and user.is_active and user.is_admin)

    def has_permission(self, user_id: int, permission: str) -> bool:
        user = User.objects.filter(pk=user_id).prefetch_related("roles").first()
        return bool(user and user.is_active and user.has_permission(permission))

    @staticmethod
    def _to_dto(user: User) -> UserDTO:
        return UserDTO(
            id=user.id,
            email=user.email,
            role_codes=tuple(sorted(role.code for role in user.roles.all())),
            is_active=user.is_active,
        )


class OrgDirectoryService:
    """In-process implementation of the ``OrgDirectory`` contract."""

    def get_open_shift(self, cashier_id: int) -> ShiftDTO | None:
        shift = Shift.objects.filter(cashier_id=cashier_id, status=Shift.Status.OPEN).first()
        return self._shift_to_dto(shift) if shift is not None else None

    def get_cash_desk(self, cash_desk_id: int) -> CashDeskDTO | None:
        cash_desk = CashDesk.objects.filter(pk=cash_desk_id).first()
        if cash_desk is None:
            return None
        return CashDeskDTO(
            id=cash_desk.id,
            branch_id=cash_desk.branch_id,
            is_active=cash_desk.is_active,
        )

    def accessible_cash_desk_ids(self, user_id: int) -> set[int] | None:
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return set()
        branch_ids = scoping.accessible_branch_ids(user)
        if branch_ids is None:
            return None
        return set(
            CashDesk.objects.filter(branch_id__in=branch_ids).values_list("id", flat=True)
        )

    def user_can_access_cash_desk(self, user_id: int, cash_desk_id: int) -> bool:
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return False
        branch_ids = scoping.accessible_branch_ids(user)
        if branch_ids is None:
            return True
        return CashDesk.objects.filter(pk=cash_desk_id, branch_id__in=branch_ids).exists()

    @staticmethod
    def _shift_to_dto(shift: Shift) -> ShiftDTO:
        return ShiftDTO(
            id=shift.id,
            cash_desk_id=shift.cash_desk_id,
            cashier_id=shift.cashier_id,
            status=shift.status,
        )


class ReferenceDirectoryService:
    """In-process implementation of the ``ReferenceDirectory`` contract."""

    def currencies(self) -> tuple[CurrencyDTO, ...]:
        queryset = Currency.objects.filter(is_active=True).order_by("code")
        return tuple(self._currency_to_dto(currency) for currency in queryset)

    def get_currency(self, code: str) -> CurrencyDTO | None:
        currency = Currency.objects.filter(code=(code or "").upper()).first()
        return self._currency_to_dto(currency) if currency is not None else None

    def cash_desk_currency_codes(self, cash_desk_id: int) -> set[str] | None:
        codes = set(
            CashDeskCurrency.objects.filter(cash_desk_id=cash_desk_id).values_list(
                "currency__code", flat=True
            )
        )
        return codes or None

    def rate(
        self,
        currency_code: str,
        rate_type: str,
        *,
        cash_desk_id: int | None = None,
        at=None,
    ):
        moment = at or timezone.now()
        rows = CurrencyRate.objects.filter(
            currency__code=(currency_code or "").upper(),
            rate_type=rate_type,
            effective_from__lte=moment,
        )
        if cash_desk_id is not None:
            scoped = rows.filter(cash_desk_id=cash_desk_id).order_by("-effective_from").first()
            if scoped is not None:
                return scoped.value
        bank = rows.filter(cash_desk__isnull=True).order_by("-effective_from").first()
        return bank.value if bank is not None else None

    def cash_desk_rates(self, cash_desk_id: int) -> tuple[CurrencyRateDTO, ...]:
        moment = timezone.now()
        rows = (
            CurrencyRate.objects.select_related("currency", "base_currency")
            .filter(effective_from__lte=moment)
            .filter(Q(cash_desk_id=cash_desk_id) | Q(cash_desk__isnull=True))
        )
        keys = sorted({(row.currency_id, row.base_currency_id, row.rate_type) for row in rows})
        resolved: list[CurrencyRateDTO] = []
        for currency_id, base_id, rate_type in keys:
            scoped = (
                rows.filter(
                    currency_id=currency_id,
                    base_currency_id=base_id,
                    rate_type=rate_type,
                    cash_desk_id=cash_desk_id,
                )
                .order_by("-effective_from")
                .first()
            )
            chosen = scoped or (
                rows.filter(
                    currency_id=currency_id,
                    base_currency_id=base_id,
                    rate_type=rate_type,
                    cash_desk__isnull=True,
                )
                .order_by("-effective_from")
                .first()
            )
            if chosen is not None:
                resolved.append(self._rate_to_dto(chosen))
        return tuple(resolved)

    @staticmethod
    def _currency_to_dto(currency: Currency) -> CurrencyDTO:
        return CurrencyDTO(
            code=currency.code,
            name=currency.name,
            symbol=currency.symbol,
            minor_units=currency.minor_units,
        )

    @staticmethod
    def _rate_to_dto(rate: CurrencyRate) -> CurrencyRateDTO:
        return CurrencyRateDTO(
            currency_code=rate.currency.code,
            base_currency_code=rate.base_currency.code,
            rate_type=rate.rate_type,
            value=rate.value,
            effective_from=rate.effective_from,
            cash_desk_id=rate.cash_desk_id,
        )
