"""Per-cash-desk operation configuration API and its enforcement."""

import pytest

from modules.operations.backend.models import CashDeskOperation, Operation, OperationType
from modules.operations.contracts import OperationKind

pytestmark = pytest.mark.django_db

CASH_DESK = 7
CONFIG_URL = f"/api/operations/cash-desks/{CASH_DESK}/operations/"
OPERATIONS_URL = "/api/operations/operations/"


def _post_payload(operation_type, currency="USD", amount="100.00"):
    return {
        "operation_type": operation_type.code,
        "lines": [{"slot": "amount", "currency": currency, "amount": amount}],
    }


def test_a_desk_is_unrestricted_by_default(auth_client, income_type):
    response = auth_client.get(CONFIG_URL)

    assert response.status_code == 200
    assert response.data["configured"] is False
    assert income_type.code in [row["code"] for row in response.data["operations"]]


def test_configuring_a_desk_selects_the_operations(auth_client, income_type):
    response = auth_client.put(CONFIG_URL, {"operations": [income_type.code]}, format="json")

    assert response.status_code == 200
    assert response.data["configured"] is True
    assert [row["code"] for row in response.data["operations"]] == [income_type.code]
    assert CashDeskOperation.objects.filter(cash_desk_id=CASH_DESK).count() == 1


def test_an_unknown_operation_is_rejected(auth_client):
    response = auth_client.put(CONFIG_URL, {"operations": ["nope"]}, format="json")

    assert response.status_code == 400


def test_posting_an_operation_not_enabled_on_the_desk_is_rejected(auth_client, income_type):
    other = OperationType.objects.create(
        code="cash_handover",
        name="Сдача наличных",
        kind=OperationKind.EXPENSE,
        template={"movements": [{"register": "cash", "slot": "amount", "sign": -1}]},
    )
    auth_client.put(CONFIG_URL, {"operations": [other.code]}, format="json")

    response = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_posting_a_currency_not_enabled_on_the_desk_is_rejected(
    auth_client, contracts, income_type
):
    contracts.references.allowed = {"BYN"}

    response = auth_client.post(
        OPERATIONS_URL, _post_payload(income_type, currency="USD"), format="json"
    )

    assert response.status_code == 400
    assert Operation.objects.count() == 0
