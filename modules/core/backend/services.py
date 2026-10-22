"""Concrete implementations of the ``core`` module's public contracts."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from modules.core.backend import currency_config, rates, scoping
from modules.core.backend.models import (
    BankSettings,
    BaseValue,
    CashDesk,
    CurrencyRate,
    Shift,
    User,
)
from modules.core.contracts.dto import (
    BankSettingsDTO,
    CashDeskDTO,
    CurrencyRateDTO,
    ShiftDTO,
    UserDTO,
)


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
        return set(CashDesk.objects.filter(branch_id__in=branch_ids).values_list("id", flat=True))

    def accessible_branch_ids(self, user_id: int) -> set[int] | None:
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return set()
        return scoping.accessible_branch_ids(user)

    def branch_ancestor_ids(self, branch_id: int) -> tuple[int, ...]:
        return scoping.branch_ancestor_ids(branch_id)

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


class CashDeskConfigService:
    """In-process implementation of the ``CashDeskConfigDirectory`` contract."""

    def cash_desk_currency_codes(self, cash_desk_id: int) -> set[str]:
        return currency_config.effective_currency_codes(cash_desk_id)

    def rate(
        self,
        currency_code: str,
        rate_type: str,
        *,
        target_currency: str | None = None,
        cash_desk_id: int | None = None,
        at=None,
    ):
        row = rates.resolve_rate(
            currency_code,
            rate_type,
            target_currency=target_currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if row is None:
            return None
        return row.value / row.units if row.units else row.value

    def cash_desk_rates(self, cash_desk_id: int) -> tuple[CurrencyRateDTO, ...]:
        rows = rates.cash_desk_rates(cash_desk_id)
        return tuple(self._rate_to_dto(row) for row in rows)

    @staticmethod
    def _rate_to_dto(rate: CurrencyRate) -> CurrencyRateDTO:
        return CurrencyRateDTO(
            currency_code=rate.currency,
            base_currency_code=rate.base_currency,
            rate_type=rate.rate_type,
            value=rate.value,
            effective_from=rate.effective_from,
            cash_desk_id=rate.cash_desk_id,
            branch_id=rate.branch_id,
            scope=rate.scope,
            effective_date=rate.effective_date,
            units=rate.units,
        )


class BankSettingsService:
    """In-process implementation of the ``BankSettingsDirectory`` contract."""

    def get_settings(self, on: date | None = None) -> BankSettingsDTO:
        settings = BankSettings.load()
        moment = on or timezone.localdate()
        base_value = (
            BaseValue.objects.filter(effective_from__lte=moment)
            .order_by("-effective_from")
            .first()
        )
        return BankSettingsDTO(
            base_currency=settings.base_currency,
            conversion_mode=settings.conversion_mode,
            base_value=base_value.amount if base_value is not None else None,
            base_value_date=base_value.effective_from if base_value is not None else None,
        )


class RateTypeUsageGuardService:
    """Implementation of the ``references.rate_type_usage_guard`` callback."""

    def is_rate_type_used(self, code: str) -> bool:
        return CurrencyRate.objects.filter(rate_type=code).exists()
