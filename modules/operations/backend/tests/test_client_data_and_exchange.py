"""Client-data control, exchange rates and multi-currency operations."""

from decimal import Decimal

import pytest

from modules.core.contracts import BankSettingsDTO
from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationLine,
    OperationTemplate,
    OperationType,
    SlotDef,
)
from modules.operations.contracts.dto import OperationKind, OperationRatePrinciple
from modules.references.contracts import CurrencyDTO, RateTypeDTO

pytestmark = pytest.mark.django_db

OPERATIONS_URL = "/api/operations/operations/"
PREVIEW_URL = "/api/operations/operations/preview/"


def _exchange_type(
    *,
    code="currency_purchase",
    principle=OperationRatePrinciple.BUY,
    rate_type="buy",
    form="exchange",
):
    operation_type = OperationType.objects.create(
        code=code,
        name=code,
        kind=OperationKind.EXCHANGE,
        form=form,
        rate_principle=principle,
        rate_type=rate_type,
        template={
            "movements": [
                {"register": "cash", "slot": "received", "sign": 1},
                {"register": "cash", "slot": "issued", "sign": -1},
            ]
        },
    )
    SlotDef.objects.create(
        operation_type=operation_type,
        code="received",
        name="Принято от клиента",
        currency_policy="foreign",
        stores_rate=True,
        threshold_basis=True,
    )
    SlotDef.objects.create(
        operation_type=operation_type,
        code="issued",
        name="Выдано клиенту",
        currency_policy="base",
        amount_mode="computed",
        computation="multiply",
        order=1,
    )
    OperationTemplate.objects.create(branch_id=None).operation_types.set([operation_type])
    return operation_type


def _post(client, operation_type, lines, **extra):
    payload = {
        "operation_type": operation_type.code,
        "lines": lines,
        **extra,
    }
    return client.post(OPERATIONS_URL, payload, format="json")


def _exchange_lines(received="100.00", currency="USD", issued="0.00", **extra):
    return [
        {"slot": "received", "currency": currency, "amount": received, **extra},
        {"slot": "issued", "currency": "BYN", "amount": issued},
    ]


def test_purchase_resolves_the_buy_rate_and_computes_the_issued_amount(auth_client, contracts):
    operation_type = _exchange_type()
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "buy", None): Decimal("3.25")}

    response = _post(
        auth_client,
        operation_type,
        _exchange_lines(),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content
    lines = {line["slot"]: line for line in response.data["lines"]}
    assert lines["issued"]["amount"] == "325.00"
    assert lines["received"]["rate"] == "3.25000000"
    assert lines["received"]["rate_type"] == "buy"
    assert lines["received"]["rate_is_individual"] is False
    assert CashBalance.objects.get(cash_desk_id=7, currency="BYN").amount == Decimal("675.00")
    assert CashBalance.objects.get(cash_desk_id=7, currency="USD").amount == Decimal("100.00")


def test_an_individual_rate_is_used_and_kept_in_the_journal(auth_client, contracts):
    operation_type = _exchange_type()
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))

    response = _post(
        auth_client,
        operation_type,
        _exchange_lines(rate="3.50", rate_is_individual=True),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content
    line = OperationLine.objects.get(operation_id=response.data["id"], slot="received")
    assert line.rate == Decimal("3.50000000")
    assert line.rate_is_individual is True
    assert line.rate_type == "buy"
    assert OperationLine.objects.get(
        operation_id=response.data["id"], slot="issued"
    ).amount == Decimal("350.00")


def test_a_missing_rate_blocks_the_operation(auth_client, contracts):
    operation_type = _exchange_type()

    response = _post(
        auth_client,
        operation_type,
        _exchange_lines(),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_an_unconfigured_rate_type_blocks_the_operation(auth_client, contracts):
    operation_type = _exchange_type(rate_type="")

    response = _post(
        auth_client,
        operation_type,
        _exchange_lines(),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_sale_divides_the_received_national_amount_by_the_sell_rate(auth_client, contracts):
    operation_type = _exchange_type(
        code="currency_sale", principle=OperationRatePrinciple.SELL, rate_type="sell"
    )
    operation_type.slots.filter(code="received").update(
        currency_policy="base", stores_rate=False
    )
    operation_type.slots.filter(code="issued").update(
        currency_policy="foreign", stores_rate=True, computation="divide"
    )
    CashBalance.objects.create(cash_desk_id=7, currency="USD", amount=Decimal("100.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "sell", None): Decimal("4.00")}

    response = _post(
        auth_client,
        operation_type,
        [
            {"slot": "received", "currency": "BYN", "amount": "400.00"},
            {"slot": "issued", "currency": "USD", "amount": "0.00"},
        ],
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content
    issued = next(line for line in response.data["lines"] if line["slot"] == "issued")
    assert issued["amount"] == "100.00"
    assert CashBalance.objects.get(cash_desk_id=7, currency="USD").amount == Decimal("0.00")


def test_conversion_uses_the_cross_rate_via_the_base_currency(auth_client, contracts):
    operation_type = _exchange_type(
        code="currency_conversion",
        principle=OperationRatePrinciple.CONVERSION,
        rate_type="conversion",
    )
    operation_type.slots.filter(code="issued").update(currency_policy="foreign")
    contracts.cash_desk_config.allowed = {"BYN", "USD", "EUR"}
    contracts.references._currencies = (
        *contracts.references.currencies(),
        CurrencyDTO(code="EUR", name="Евро", symbol="€", minor_units=2),
    )
    contracts.cash_desk_config.currency_rates = {
        ("USD", "conversion", None): Decimal("3.00"),
        ("EUR", "conversion", None): Decimal("4.00"),
    }
    CashBalance.objects.create(cash_desk_id=7, currency="EUR", amount=Decimal("100.00"))

    response = _post(
        auth_client,
        operation_type,
        [
            {"slot": "received", "currency": "USD", "amount": "100.00"},
            {"slot": "issued", "currency": "EUR", "amount": "0.00"},
        ],
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content
    issued = next(line for line in response.data["lines"] if line["slot"] == "issued")
    assert issued["amount"] == "75.00"


def test_direct_conversion_uses_the_direction_correct_pair_side(auth_client, contracts):
    operation_type = _exchange_type(
        code="currency_conversion",
        principle=OperationRatePrinciple.CONVERSION,
        rate_type="conversion",
    )
    operation_type.slots.filter(code="issued").update(currency_policy="foreign")
    contracts.cash_desk_config.allowed = {"BYN", "USD", "EUR"}
    contracts.references._currencies = (
        *contracts.references.currencies(),
        CurrencyDTO(code="EUR", name="Евро", symbol="€", minor_units=2),
    )
    contracts.bank_settings.settings = BankSettingsDTO(
        base_currency="BYN",
        conversion_mode="direct",
    )
    contracts.cash_desk_config.currency_rates = {
        ("EUR", "conversion_buy", "USD"): Decimal("1.105"),
        ("EUR", "conversion_sell", "USD"): Decimal("1.140"),
        ("USD", "conversion_buy", "EUR"): Decimal("1.500"),
        ("USD", "conversion_sell", "EUR"): Decimal("0.900"),
    }
    CashBalance.objects.create(cash_desk_id=7, currency="EUR", amount=Decimal("100.00"))
    CashBalance.objects.create(cash_desk_id=7, currency="USD", amount=Decimal("1000.00"))

    response = _post(
        auth_client,
        operation_type,
        [
            {"slot": "received", "currency": "EUR", "amount": "100.00"},
            {"slot": "issued", "currency": "USD", "amount": "0.00"},
        ],
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content
    issued = next(line for line in response.data["lines"] if line["slot"] == "issued")
    assert issued["amount"] == "110.50"


def _income_type(code="cash_receipt", *, threshold=False):
    operation_type = OperationType.objects.create(
        code=code,
        name=code,
        kind=OperationKind.INCOME,
        form="amount",
        client_data_policy="threshold" if threshold else "always",
        threshold_type="currency" if threshold else "",
        threshold_value=Decimal("1000.00") if threshold else None,
        threshold_currency="BYN" if threshold else "",
        template={"movements": [{"register": "cash", "slot": "amount", "sign": 1}]},
    )
    SlotDef.objects.create(
        operation_type=operation_type, code="amount", name="Сумма", threshold_basis=True
    )
    OperationTemplate.objects.create(branch_id=None).operation_types.set([operation_type])
    return operation_type


def test_always_requires_both_client_fields(auth_client):
    operation_type = _income_type()

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "BYN", "amount": "10.00"}],
        client_name="Иванов И. И.",
    )

    assert response.status_code == 400
    assert "client_document" in response.data
    assert Operation.objects.count() == 0


def test_a_threshold_converts_the_amount_at_the_official_rate(auth_client, contracts):
    operation_type = _income_type(threshold=True)
    contracts.cash_desk_config.currency_rates = {("USD", "official", None): Decimal("3.00")}

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "USD", "amount": "400.00"}],
        client_name="Иванов И. И.",
        client_document="AB 1234567",
    )

    assert response.status_code == 201, response.content


def test_a_threshold_without_client_data_is_rejected(auth_client, contracts):
    operation_type = _income_type(threshold=True)
    contracts.cash_desk_config.currency_rates = {("USD", "official", None): Decimal("3.00")}

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "USD", "amount": "400.00"}],
    )

    assert response.status_code == 400
    assert set(response.data) == {"client_name", "client_document"}
    assert Operation.objects.count() == 0


def test_an_amount_equal_to_the_threshold_does_not_require_client_data(auth_client, contracts):
    operation_type = _income_type(threshold=True)

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "BYN", "amount": "1000.00"}],
    )

    assert response.status_code == 201, response.content


def test_a_base_value_threshold_uses_the_value_in_force(auth_client, contracts):
    operation_type = _income_type(threshold=True)
    operation_type.threshold_type = "base_value"
    operation_type.threshold_value = Decimal("10.00")
    operation_type.threshold_currency = ""
    operation_type.save(
        update_fields=[
            "threshold_type",
            "threshold_value",
            "threshold_currency",
            "updated_at",
        ]
    )
    contracts.bank_settings.settings = BankSettingsDTO(
        base_currency="BYN",
        conversion_mode="via_base",
        base_value=Decimal("40.00"),
    )

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "BYN", "amount": "500.00"}],
    )

    assert response.status_code == 400
    assert "client_name" in response.data


def test_a_missing_base_value_blocks_the_threshold_check(auth_client, contracts):
    operation_type = _income_type(threshold=True)
    operation_type.threshold_type = "base_value"
    operation_type.threshold_value = Decimal("10.00")
    operation_type.save(update_fields=["threshold_type", "threshold_value", "updated_at"])

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "BYN", "amount": "500.00"}],
    )

    assert response.status_code == 400
    assert "amount" not in response.data


def test_a_missing_official_rate_blocks_the_threshold_check(auth_client, contracts):
    operation_type = _income_type(threshold=True)

    response = _post(
        auth_client,
        operation_type,
        [{"slot": "amount", "currency": "USD", "amount": "10.00"}],
    )

    assert response.status_code == 400


def test_preview_returns_the_prepared_lines_and_client_requirement(auth_client, contracts):
    operation_type = _income_type(threshold=True)
    contracts.cash_desk_config.currency_rates = {("USD", "official", None): Decimal("3.00")}

    response = auth_client.post(
        PREVIEW_URL,
        {
            "operation_type": operation_type.code,
            "lines": [{"slot": "amount", "currency": "USD", "amount": "400.00"}],
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["client_data"]["required"] is True
    assert response.data["client_data"]["reason"] == "threshold"
    assert response.data["client_data"]["amount"] == "1200.0000"
    assert response.data["client_data"]["threshold"] == "1000.00"
    assert response.data["lines"][0]["amount"] == "400.00"


def _multi_currency_type():
    operation_type = OperationType.objects.create(
        code="cash_replenishment",
        name="Подкрепление кассы",
        kind=OperationKind.INCOME,
        form="multi_currency",
        template={
            "movements": [
                {"register": "cash", "slot": "amount", "sign": 1},
                {"register": "turnover", "slot": "amount", "sign": 1},
            ]
        },
    )
    SlotDef.objects.create(
        operation_type=operation_type,
        code="amount",
        name="Сумма",
        multiple=True,
        threshold_basis=True,
    )
    OperationTemplate.objects.create(branch_id=None).operation_types.set([operation_type])
    return operation_type


def test_one_multi_currency_operation_moves_every_currency(auth_client):
    operation_type = _multi_currency_type()

    response = _post(
        auth_client,
        operation_type,
        [
            {"slot": "amount", "currency": "USD", "amount": "100.00"},
            {"slot": "amount", "currency": "BYN", "amount": "200.00"},
        ],
    )

    assert response.status_code == 201, response.content
    assert len(response.data["lines"]) == 2
    assert Operation.objects.count() == 1
    assert CashBalance.objects.get(cash_desk_id=7, currency="USD").amount == Decimal("100.00")
    assert CashBalance.objects.get(cash_desk_id=7, currency="BYN").amount == Decimal("200.00")


def test_a_multi_currency_slot_rejects_a_duplicate_currency(auth_client):
    operation_type = _multi_currency_type()

    response = _post(
        auth_client,
        operation_type,
        [
            {"slot": "amount", "currency": "USD", "amount": "100.00"},
            {"slot": "amount", "currency": "USD", "amount": "50.00"},
        ],
    )

    assert response.status_code == 400


def test_an_exchange_type_requires_a_rate_type(auth_client, contracts):
    operation_type = _exchange_type()
    contracts.references._rate_types = (
        RateTypeDTO(code="buy", name="Buy", principle="buy", is_active=True),
    )

    response = auth_client.patch(
        f"/api/operations/types/{operation_type.code}/",
        {"rate_type": ""},
        format="json",
    )

    assert response.status_code == 400
    assert "rate_type" in response.data


def test_an_exchange_type_accepts_a_matching_rate_type(auth_client, contracts):
    operation_type = _exchange_type(rate_type="")
    contracts.references._rate_types = (
        RateTypeDTO(code="buy", name="Buy", principle="buy", is_active=True),
    )

    response = auth_client.patch(
        f"/api/operations/types/{operation_type.code}/",
        {"rate_type": "buy"},
        format="json",
    )

    assert response.status_code == 200, response.content
    operation_type.refresh_from_db()
    assert operation_type.rate_type == "buy"
