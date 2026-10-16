"""The cashier workplace context endpoint."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from modules.core.contracts import CurrencyRateDTO
from modules.operations.backend.models import CashBalance, OperationTemplate

pytestmark = pytest.mark.django_db

WORKPLACE_URL = "/api/operations/workplace/"
CASH_DESK = 7


def test_workplace_without_a_shift_returns_an_empty_context(auth_client, contracts):
    contracts.org.shift = None

    response = auth_client.get(WORKPLACE_URL)

    assert response.status_code == 200
    assert response.data["shift_id"] is None
    assert response.data["cash_desk_id"] is None
    assert response.data["operations"] == []
    assert response.data["balances"] == []


def test_workplace_returns_the_desk_context(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])
    CashBalance.objects.create(cash_desk_id=CASH_DESK, currency="USD", amount=Decimal("500"))

    response = auth_client.get(WORKPLACE_URL)

    assert response.status_code == 200
    assert response.data["cash_desk_id"] == CASH_DESK
    assert [row["code"] for row in response.data["operations"]] == [income_type.code]
    assert response.data["balances"][0]["currency"] == "USD"
    assert {row["code"] for row in response.data["currencies"]} == {"BYN", "USD"}


def test_workplace_currencies_respect_the_cash_desk_configuration(auth_client, contracts):
    contracts.cash_desk_config.allowed = {"USD"}

    response = auth_client.get(WORKPLACE_URL)

    assert {row["code"] for row in response.data["currencies"]} == {"USD"}


def test_workplace_exposes_the_effective_rates(auth_client, contracts):
    contracts.cash_desk_config.rates = (
        CurrencyRateDTO(
            currency_code="USD",
            base_currency_code="BYN",
            rate_type="buy",
            value=Decimal("3.25"),
            effective_from=datetime(2026, 10, 14, tzinfo=UTC),
            cash_desk_id=None,
        ),
    )

    response = auth_client.get(WORKPLACE_URL)

    assert response.data["rates"][0]["currency"] == "USD"
    assert response.data["rates"][0]["rate_type"] == "buy"
    assert response.data["rates"][0]["value"] == "3.25"
