"""The baseline print forms are declared and well formed."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from modules.common.contracts import registry
from modules.printing.contracts import (
    PRINT_TEMPLATE_REGISTRY,
    PrintDocumentHeader,
    PrintOperation,
    PrintOperationLine,
)
from modules.printing_standard.backend.declarations import DOCUMENT_TYPES, TEMPLATES
from modules.printing_standard.backend.providers import CashReceiptProvider


def test_the_baseline_forms_are_registered_at_startup():
    registered = registry.get(PRINT_TEMPLATE_REGISTRY)

    assert {spec.code for spec in DOCUMENT_TYPES} <= {
        spec.code for spec in registered.document_type_specs()
    }
    assert {spec.code for spec in TEMPLATES} <= {spec.code for spec in registered.template_specs()}


def test_codes_are_unique():
    document_type_codes = [spec.code for spec in DOCUMENT_TYPES]
    template_codes = [spec.code for spec in TEMPLATES]

    assert len(document_type_codes) == len(set(document_type_codes))
    assert len(template_codes) == len(set(template_codes))


def test_templates_reference_a_declared_document_type():
    document_types = {spec.code for spec in DOCUMENT_TYPES}

    for spec in TEMPLATES:
        assert spec.document_type in document_types


def test_each_template_ships_a_sample_word_file():
    for spec in TEMPLATES:
        assert spec.default_file_path is not None
        assert Path(spec.default_file_path).is_file(), spec.code


def test_the_provider_derives_the_cash_receipt_values():
    provider = CashReceiptProvider()
    operation = PrintOperation(
        id=1,
        number=5,
        operation_type_code="currency_sale",
        operation_type_name="Продажа валюты клиенту",
        operation_kind="exchange",
        cash_desk_id=7,
        cash_desk_name="Касса 7",
        cash_desk_code="K7",
        branch_name="Отделение 1",
        bank_name="Банк",
        cashier_id=1,
        posted_at=datetime(2026, 10, 23, 12, 30, tzinfo=UTC),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
        base_currency="BYN",
        lines=(
            PrintOperationLine(
                slot="received",
                slot_name="Принято от клиента",
                currency="BYN",
                currency_name="Белорусский рубль",
                amount=Decimal("325.00"),
            ),
            PrintOperationLine(
                slot="issued",
                slot_name="Выдано клиенту",
                currency="USD",
                currency_name="Доллар США",
                amount=Decimal("100.00"),
                rate=Decimal("3.25000000"),
            ),
        ),
    )
    header = PrintDocumentHeader(
        number=1,
        document_type="cash_receipt",
        document_type_name="Кассовый чек",
        template_code="cash_receipt_currency_sale",
        template_name="Кассовый чек — продажа валюты клиенту",
    )

    context = provider.build(operation, header)

    assert context["bank_name"] == "Банк"
    assert context["cash_desk"] == "Касса 7 (K7)"
    assert context["operation_type"] == "Продажа валюты клиенту"
    assert context["received_amount"] == "325.00"
    assert context["received_currency"] == "Белорусский рубль"
    assert context["issued_amount"] == "100.00"
    assert context["issued_currency"] == "Доллар США"
    assert context["rate"] == "3.25"
    assert context["document_number"] == "1"
    assert context["operation_number"] == "5"
    assert context["client_name"] == "Иванов И. И."
