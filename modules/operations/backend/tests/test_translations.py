"""Localised operation type and slot names (ADR 0016).

The base (Russian) value stays on the model; the declared translations are
materialised into the module's own tables and handed out in the request
language, falling back to the base value.
"""

import pytest

from modules.operations.backend.models import (
    OperationTemplate,
    OperationType,
    OperationTypeTranslation,
    SlotDefTranslation,
)
from modules.operations.backend.sync import sync_operation_types
from modules.operations_standard.backend.declarations import OPERATION_TYPES

pytestmark = pytest.mark.django_db

TYPES_URL = "/api/operations/types/"
OPERATIONS_URL = "/api/operations/operations/"


@pytest.fixture
def translated_type(income_type):
    """The ``cash_receipt`` type with an English name for it and its slot."""
    OperationTypeTranslation.objects.create(
        operation_type=income_type, language="en", name="Cash receipt from client"
    )
    slot = income_type.slots.get(code="amount")
    SlotDefTranslation.objects.create(slot=slot, language="en", name="Amount")
    return income_type


def test_sync_materialises_the_declared_translations():
    sync_operation_types()

    for spec in OPERATION_TYPES:
        operation_type = OperationType.objects.get(code=spec.code)
        assert operation_type.name == spec.name
        assert {
            row.language: row.name for row in operation_type.translations.all()
        } == spec.translations

        for slot in spec.slots:
            slot_def = operation_type.slots.get(code=slot.code)
            assert slot_def.name == slot.name
            assert {
                row.language: row.name for row in slot_def.translations.all()
            } == slot.translations


def test_the_types_endpoint_returns_english_names(auth_client, translated_type):
    response = auth_client.get(TYPES_URL, HTTP_ACCEPT_LANGUAGE="en")

    row = response.data["results"][0]
    assert row["code"] == "cash_receipt"
    assert row["name"] == "Cash receipt from client"
    assert row["slots"][0]["name"] == "Amount"


def test_the_types_endpoint_falls_back_to_the_base_name(auth_client, translated_type):
    response = auth_client.get(TYPES_URL, HTTP_ACCEPT_LANGUAGE="ru")

    row = response.data["results"][0]
    assert row["name"] == "Приход наличных"
    assert row["slots"][0]["name"] == "Сумма"


def test_an_unknown_language_falls_back_to_the_base_name(auth_client, translated_type):
    response = auth_client.get(TYPES_URL, HTTP_ACCEPT_LANGUAGE="de")

    row = response.data["results"][0]
    assert row["name"] == "Приход наличных"


def test_the_journal_localises_the_operation_type_name(auth_client, translated_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([translated_type])

    response = auth_client.post(
        OPERATIONS_URL,
        {
            "operation_type": translated_type.code,
            "lines": [{"slot": "amount", "currency": "USD", "amount": "10.00"}],
        },
        format="json",
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.status_code == 201, response.content
    assert response.data["operation_type_name"] == "Cash receipt from client"
