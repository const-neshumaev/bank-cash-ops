"""Print documents configured on operation types and generated on posting."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from modules.core.contracts import BankSettingsDTO
from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationPrintConfig,
    OperationTemplate,
    OperationType,
    SlotDef,
)
from modules.operations.backend.permission_codes import PermissionCode
from modules.operations.contracts.dto import OperationKind, OperationRatePrinciple
from modules.printing.backend.sync import sync_print_templates

User = get_user_model()

pytestmark = pytest.mark.django_db

TYPES_URL = "/api/operations/types/"
OPERATIONS_URL = "/api/operations/operations/"

CASH_RECEIPT = "cash_receipt"
PURCHASE_TEMPLATE = "cash_receipt_currency_purchase"


def _exchange_type() -> OperationType:
    operation_type = OperationType.objects.create(
        code="currency_purchase",
        name="Покупка валюты у клиента",
        kind=OperationKind.EXCHANGE,
        form="exchange",
        rate_principle=OperationRatePrinciple.BUY,
        rate_type="buy",
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


def _post_purchase(client):
    return client.post(
        OPERATIONS_URL,
        {
            "operation_type": "currency_purchase",
            "lines": [
                {"slot": "received", "currency": "USD", "amount": "100.00"},
                {"slot": "issued", "currency": "BYN", "amount": "0.00"},
            ],
            "client_name": "Иванов И. И.",
            "client_document": "AB 1234567",
        },
        format="json",
    )


def test_print_configs_can_be_saved_and_read(auth_client):
    sync_print_templates()
    operation_type = _exchange_type()

    update = auth_client.put(
        f"{TYPES_URL}{operation_type.code}/print-configs/",
        {
            "configs": [
                {
                    "document_type": CASH_RECEIPT,
                    "template": PURCHASE_TEMPLATE,
                    "is_active": True,
                }
            ]
        },
        format="json",
    )

    assert update.status_code == 200, update.content
    assert update.data[0]["document_type"] == CASH_RECEIPT
    assert update.data[0]["document_type_name"] == "Кассовый чек"
    assert update.data[0]["template"] == PURCHASE_TEMPLATE
    assert update.data[0]["template_name"] == "Кассовый чек — покупка валюты у клиента"

    config = OperationPrintConfig.objects.get(operation_type=operation_type)
    assert config.template_code == PURCHASE_TEMPLATE

    read = auth_client.get(f"{TYPES_URL}{operation_type.code}/print-configs/")
    assert read.status_code == 200
    assert read.data[0]["template"] == PURCHASE_TEMPLATE


def test_an_unknown_template_is_rejected(auth_client):
    sync_print_templates()
    operation_type = _exchange_type()

    response = auth_client.put(
        f"{TYPES_URL}{operation_type.code}/print-configs/",
        {"configs": [{"document_type": CASH_RECEIPT, "template": "missing", "is_active": True}]},
        format="json",
    )

    assert response.status_code == 400
    assert "template" in response.data


def test_a_view_only_user_may_read_but_not_change_print_configs(
    client, contracts, income_type, monkeypatch
):
    viewer = User.objects.create_user(email="viewer@example.com", password="secret-pass-123")
    monkeypatch.setattr(
        viewer,
        "has_permission",
        lambda code: code == PermissionCode.VIEW,
        raising=False,
    )
    client.force_authenticate(viewer)

    read = client.get(f"{TYPES_URL}{income_type.code}/print-configs/")
    update = client.put(
        f"{TYPES_URL}{income_type.code}/print-configs/",
        {"configs": []},
        format="json",
    )

    assert read.status_code == 200
    assert update.status_code == 403


def test_posting_generates_the_configured_cash_receipt(auth_client, contracts):
    sync_print_templates()
    operation_type = _exchange_type()
    OperationPrintConfig.objects.create(
        operation_type=operation_type,
        document_type=CASH_RECEIPT,
        template_code=PURCHASE_TEMPLATE,
    )
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "buy", None): Decimal("3.25")}

    response = _post_purchase(auth_client)

    assert response.status_code == 201, response.content
    assert len(response.data["print_documents"]) == 1
    document = response.data["print_documents"][0]
    assert document["document_type"] == CASH_RECEIPT
    assert document["number"] == 1
    assert document["operation_id"] == response.data["id"]

    operation = Operation.objects.get(pk=response.data["id"])
    assert operation.number == 1


def test_the_journal_marks_operations_with_printed_documents(auth_client, contracts):
    sync_print_templates()
    operation_type = _exchange_type()
    OperationPrintConfig.objects.create(
        operation_type=operation_type,
        document_type=CASH_RECEIPT,
        template_code=PURCHASE_TEMPLATE,
    )
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "buy", None): Decimal("3.25")}

    posted = _post_purchase(auth_client)
    response = auth_client.get(OPERATIONS_URL)

    assert posted.status_code == 201, posted.content
    row = next(item for item in response.data["results"] if item["id"] == posted.data["id"])
    assert row["has_print_documents"] is True


def test_posting_without_a_print_config_does_not_print(auth_client, contracts):
    operation_type = _exchange_type()
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "buy", None): Decimal("3.25")}

    response = _post_purchase(auth_client)

    assert response.status_code == 201, response.content
    assert response.data["print_documents"] == []
    assert OperationPrintConfig.objects.count() == 0
    assert operation_type.print_configs.count() == 0


def test_the_available_print_document_types_are_exposed_for_configuration(auth_client):
    sync_print_templates()

    response = auth_client.get("/api/operations/print-templates/")

    assert response.status_code == 200, response.content
    document_type = next(row for row in response.data if row["code"] == CASH_RECEIPT)
    assert document_type["name"] == "Кассовый чек"
    assert {template["code"] for template in document_type["templates"]} == {
        PURCHASE_TEMPLATE,
        "cash_receipt_currency_sale",
        "cash_receipt_currency_conversion",
    }
    assert document_type["templates"][0]["variables"]


def test_bank_settings_are_not_needed_for_a_disabled_print_config(auth_client, contracts):
    sync_print_templates()
    operation_type = _exchange_type()
    OperationPrintConfig.objects.create(
        operation_type=operation_type,
        document_type=CASH_RECEIPT,
        template_code=PURCHASE_TEMPLATE,
        is_active=False,
    )
    CashBalance.objects.create(cash_desk_id=7, currency="BYN", amount=Decimal("1000.00"))
    contracts.cash_desk_config.currency_rates = {("USD", "buy", None): Decimal("3.25")}
    contracts.bank_settings.settings = BankSettingsDTO(
        base_currency="BYN", conversion_mode="via_base"
    )

    response = _post_purchase(auth_client)

    assert response.status_code == 201, response.content
    assert response.data["print_documents"] == []
