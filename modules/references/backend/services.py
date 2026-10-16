"""Concrete implementation of the ``references`` module's public contract."""

from __future__ import annotations

from modules.references.backend.models import Currency, CurrencyRateType
from modules.references.contracts.dto import CurrencyDTO, RateTypeDTO


class ReferenceDirectoryService:
    """In-process implementation of the ``ReferenceDirectory`` contract."""

    def currencies(self) -> tuple[CurrencyDTO, ...]:
        queryset = (
            Currency.objects.filter(is_active=True)
            .prefetch_related("translations")
            .order_by("code")
        )
        return tuple(self._currency_to_dto(currency) for currency in queryset)

    def get_currency(self, code: str) -> CurrencyDTO | None:
        currency = (
            Currency.objects.filter(code=(code or "").strip().upper())
            .prefetch_related("translations")
            .first()
        )
        return self._currency_to_dto(currency) if currency is not None else None

    def rate_types(self) -> tuple[RateTypeDTO, ...]:
        queryset = (
            CurrencyRateType.objects.filter(is_active=True)
            .prefetch_related("translations")
            .order_by("order", "code")
        )
        return tuple(self._rate_type_to_dto(rate_type) for rate_type in queryset)

    def get_rate_type(self, code: str) -> RateTypeDTO | None:
        rate_type = (
            CurrencyRateType.objects.filter(code=code).prefetch_related("translations").first()
        )
        return self._rate_type_to_dto(rate_type) if rate_type is not None else None

    @staticmethod
    def _currency_to_dto(currency: Currency) -> CurrencyDTO:
        return CurrencyDTO(
            code=currency.code,
            name=currency.localized_name(),
            symbol=currency.symbol,
            minor_units=currency.minor_units,
        )

    @staticmethod
    def _rate_type_to_dto(rate_type: CurrencyRateType) -> RateTypeDTO:
        return RateTypeDTO(
            code=rate_type.code,
            name=rate_type.localized_name(),
            principle=rate_type.principle,
            is_active=rate_type.is_active,
        )
