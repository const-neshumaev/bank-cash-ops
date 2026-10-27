"""Rendering, numbering and storage of printed documents."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest

from modules.printing.backend.models import PrintDocument, PrintNumberSequence
from modules.printing.backend.rendering import print_document_service
from modules.printing.contracts import (
    PrintBinding,
    PrintOperation,
    PrintOperationLine,
)

pytestmark = pytest.mark.django_db

CASH_DESK = 7


def _operation(operation_id: int = 1) -> PrintOperation:
    return PrintOperation(
        id=operation_id,
        number=operation_id,
        operation_type_code="currency_purchase",
        operation_type_name="Покупка валюты у клиента",
        operation_kind="exchange",
        cash_desk_id=CASH_DESK,
        cash_desk_name="Касса 7",
        cash_desk_code="K7",
        branch_name="Отделение 1",
        bank_name="Банк",
        cashier_id=1,
        posted_at=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
        client_name="Иванов И. И.",
        client_document="AB 1234567",
        base_currency="BYN",
        lines=(
            PrintOperationLine(
                slot="received",
                slot_name="Принято от клиента",
                currency="USD",
                currency_name="Доллар США",
                amount=Decimal("100.00"),
                rate=Decimal("3.25000000"),
                rate_type="buy",
            ),
            PrintOperationLine(
                slot="issued",
                slot_name="Выдано клиенту",
                currency="BYN",
                currency_name="Белорусский рубль",
                amount=Decimal("325.00"),
            ),
        ),
    )


def _binding() -> PrintBinding:
    return PrintBinding(
        document_type="cash_receipt",
        template="cash_receipt_currency_purchase",
    )


def test_rendering_stores_a_numbered_document(synced_templates):
    documents = print_document_service.render_operation(_operation(), [_binding()])

    assert len(documents) == 1
    document = documents[0]
    assert document.number == 1
    assert document.document_type == "cash_receipt"
    assert document.template_code == "cash_receipt_currency_purchase"
    assert PrintDocument.objects.count() == 1
    stored = PrintDocument.objects.get(pk=document.id)
    assert bytes(stored.content).startswith(b"PK")


def test_successive_documents_share_the_bank_wide_sequence(synced_templates):
    first = print_document_service.render_operation(_operation(1), [_binding()])
    second = print_document_service.render_operation(_operation(2), [_binding()])

    assert first[0].number == 1
    assert second[0].number == 2
    assert PrintNumberSequence.objects.get(document_type="cash_receipt").last_number == 2


def test_several_forms_of_one_document_type_are_rendered(synced_templates):
    bindings = [
        _binding(),
        PrintBinding(
            document_type="cash_receipt",
            template="cash_receipt_currency_sale",
        ),
    ]

    documents = print_document_service.render_operation(_operation(), bindings)

    assert len(documents) == 2
    assert {document.document_type for document in documents} == {"cash_receipt"}
    assert {document.template_code for document in documents} == {
        "cash_receipt_currency_purchase",
        "cash_receipt_currency_sale",
    }
    assert sorted(document.number for document in documents) == [1, 2]
    assert PrintDocument.objects.count() == 2

    stored = print_document_service.operation_documents(_operation().id)
    assert {document.template_code for document in stored} == {
        "cash_receipt_currency_purchase",
        "cash_receipt_currency_sale",
    }


def test_documents_of_different_types_are_rendered(synced_templates, second_document_type):
    bindings = [
        _binding(),
        PrintBinding(
            document_type="cash_order",
            template="cash_order_default",
        ),
    ]

    documents = print_document_service.render_operation(_operation(), bindings)

    assert len(documents) == 2
    assert {document.document_type for document in documents} == {"cash_receipt", "cash_order"}
    assert {document.template_code for document in documents} == {
        "cash_receipt_currency_purchase",
        "cash_order_default",
    }


def test_an_unnumbered_document_type_renders_without_numbers(
    synced_templates, unnumbered_document_type
):
    bindings = [
        PrintBinding(
            document_type="account_statement",
            template="account_statement_default",
        ),
        PrintBinding(
            document_type="account_statement",
            template="account_statement_detailed",
        ),
    ]

    documents = print_document_service.render_operation(_operation(), bindings)

    assert len(documents) == 2
    assert {document.number for document in documents} == {None}
    assert not PrintNumberSequence.objects.filter(document_type="account_statement").exists()


def test_the_same_operation_is_not_rendered_twice(synced_templates):
    first = print_document_service.render_operation(_operation(1), [_binding()])
    again = print_document_service.render_operation(_operation(1), [_binding()])

    assert len(first) == 1
    assert again == ()


def test_the_rendered_file_contains_the_substituted_values(synced_templates):
    documents = print_document_service.render_operation(_operation(), [_binding()])
    stored = PrintDocument.objects.get(pk=documents[0].id)

    with zipfile.ZipFile(BytesIO(bytes(stored.content))) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Банк" in xml
    assert "Покупка валюты у клиента" in xml
    assert "100.00" in xml
    assert "325.00" in xml
    assert "3.25" in xml
