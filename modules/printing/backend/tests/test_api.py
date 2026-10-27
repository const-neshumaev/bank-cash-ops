"""REST API of the printing module: templates, upload/download and reprints."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document

from modules.printing.backend.rendering import print_document_service
from modules.printing.contracts import PrintBinding, PrintOperation, PrintOperationLine

User = get_user_model()

pytestmark = pytest.mark.django_db

TEMPLATES_URL = "/api/printing/templates/"
DOCUMENTS_URL = "/api/printing/operations/1/documents/"

CASH_DESK = 7


def _docx() -> bytes:
    document = Document()
    document.add_paragraph("{{ bank_name }}")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


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
        base_currency="BYN",
        lines=(
            PrintOperationLine(
                slot="received",
                slot_name="Принято от клиента",
                currency="USD",
                currency_name="Доллар США",
                amount=Decimal("100.00"),
                rate=Decimal("3.25000000"),
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


def _rendered_document():
    return print_document_service.render_operation(
        _operation(),
        [
            PrintBinding(
                document_type="cash_receipt",
                template="cash_receipt_currency_purchase",
            )
        ],
    )[0]


def test_templates_require_authentication(client):
    assert client.get(TEMPLATES_URL).status_code == 401


def test_an_ordinary_user_cannot_read_templates(client):
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")
    client.force_authenticate(user)

    assert client.get(TEMPLATES_URL).status_code == 403


def test_the_administrator_lists_the_declared_templates(auth_client, synced_templates):
    response = auth_client.get(TEMPLATES_URL, {"page_size": 100})

    assert response.status_code == 200, response.content
    rows = response.data["results"]
    assert {row["code"] for row in rows} == {
        "cash_receipt_currency_purchase",
        "cash_receipt_currency_sale",
        "cash_receipt_currency_conversion",
    }
    purchase = next(row for row in rows if row["code"] == "cash_receipt_currency_purchase")
    assert purchase["has_file"] is True
    assert purchase["document_type_name"] == "Кассовый чек"
    assert {variable["code"] for variable in purchase["variables"]} >= {
        "bank_name",
        "operation_type",
        "received_amount",
        "document_number",
    }


def test_a_template_file_can_be_uploaded_and_downloaded(auth_client, synced_templates):
    content = _docx()

    upload = auth_client.post(
        f"{TEMPLATES_URL}cash_receipt_currency_purchase/file/",
        {"file": SimpleUploadedFile("receipt.docx", content)},
        format="multipart",
    )

    assert upload.status_code == 200, upload.content
    assert upload.data["has_file"] is True
    assert upload.data["file_name"] == "receipt.docx"

    download = auth_client.get(f"{TEMPLATES_URL}cash_receipt_currency_purchase/file/")

    assert download.status_code == 200
    assert download["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert download.content == content


def test_uploading_a_non_word_file_is_rejected(auth_client, synced_templates):
    response = auth_client.post(
        f"{TEMPLATES_URL}cash_receipt_currency_purchase/file/",
        {"file": SimpleUploadedFile("receipt.txt", b"not a document")},
        format="multipart",
    )

    assert response.status_code == 400
    assert "file" in response.data


def test_operation_documents_are_listed_for_an_accessible_cash_desk(
    auth_client, contracts, synced_templates
):
    document = _rendered_document()
    contracts.org.accessible = {CASH_DESK}

    response = auth_client.get(DOCUMENTS_URL)

    assert response.status_code == 200, response.content
    assert [row["id"] for row in response.data] == [document.id]
    assert response.data[0]["number"] == 1


def test_operation_documents_include_every_printed_form(
    auth_client, contracts, synced_templates, second_document_type
):
    print_document_service.render_operation(
        _operation(),
        [
            PrintBinding(
                document_type="cash_receipt",
                template="cash_receipt_currency_purchase",
            ),
            PrintBinding(
                document_type="cash_receipt",
                template="cash_receipt_currency_sale",
            ),
            PrintBinding(
                document_type="cash_order",
                template="cash_order_default",
            ),
        ],
    )
    contracts.org.accessible = {CASH_DESK}

    response = auth_client.get(DOCUMENTS_URL)

    assert response.status_code == 200, response.content
    assert {row["template_code"] for row in response.data} == {
        "cash_receipt_currency_purchase",
        "cash_receipt_currency_sale",
        "cash_order_default",
    }


def test_an_unnumbered_document_is_served_without_a_number(
    auth_client, contracts, synced_templates, unnumbered_document_type
):
    print_document_service.render_operation(
        _operation(),
        [
            PrintBinding(
                document_type="account_statement",
                template="account_statement_default",
            )
        ],
    )
    contracts.org.accessible = {CASH_DESK}

    response = auth_client.get(DOCUMENTS_URL)

    assert response.status_code == 200, response.content
    assert response.data[0]["number"] is None


def test_operation_documents_are_hidden_for_an_inaccessible_cash_desk(
    auth_client, contracts, synced_templates
):
    _rendered_document()
    contracts.org.accessible = {99}

    response = auth_client.get(DOCUMENTS_URL)

    assert response.status_code == 200
    assert response.data == []


def test_a_rendered_document_can_be_downloaded(auth_client, contracts, synced_templates):
    document = _rendered_document()
    contracts.org.accessible = {CASH_DESK}

    response = auth_client.get(f"/api/printing/documents/{document.id}/file/")

    assert response.status_code == 200
    assert response.content.startswith(b"PK")


def test_printing_documents_requires_the_print_permission(client, contracts, synced_templates):
    user = User.objects.create_user(email="viewer@example.com", password="secret-pass-123")
    client.force_authenticate(user)

    assert client.get(DOCUMENTS_URL).status_code == 403
