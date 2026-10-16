"""Per-cash-desk operation configuration, templates and enforcement."""

import pytest

from modules.operations.backend.models import (
    CashDeskOperation,
    Operation,
    OperationTemplate,
    OperationType,
)
from modules.operations.backend.tests.conftest import CASH_DESK, CASH_DESK_BRANCH
from modules.operations.contracts import OperationKind

pytestmark = pytest.mark.django_db

CONFIG_URL = f"/api/operations/cash-desks/{CASH_DESK}/operations/"
OPERATIONS_URL = "/api/operations/operations/"


def _post_payload(operation_type, currency="USD", amount="100.00"):
    return {
        "operation_type": operation_type.code,
        "lines": [{"slot": "amount", "currency": currency, "amount": amount}],
    }


def _other_type(code="cash_handover", name="Сдача наличных"):
    operation_type = OperationType.objects.create(
        code=code,
        name=name,
        kind=OperationKind.EXPENSE,
        template={"movements": [{"register": "cash", "slot": "amount", "sign": -1}]},
    )
    return operation_type


def test_a_desk_without_configuration_denies_operations(auth_client, income_type):
    response = auth_client.get(CONFIG_URL)

    assert response.status_code == 200
    assert response.data["configured"] is False
    assert response.data["source"] == "none"
    assert response.data["template_branch_id"] is None
    assert response.data["operations"] == []


def test_a_bank_template_sets_the_default(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])

    response = auth_client.get(CONFIG_URL)

    assert response.data["configured"] is False
    assert response.data["source"] == "bank"
    assert response.data["template_branch_id"] is None
    assert [row["code"] for row in response.data["operations"]] == [income_type.code]


def test_an_empty_bank_template_denies_operations(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None)

    response = auth_client.get(CONFIG_URL)

    assert response.data["source"] == "bank"
    assert response.data["operations"] == []


def test_a_branch_template_overrides_the_bank_template(auth_client, income_type):
    other = _other_type()
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])
    OperationTemplate.objects.create(branch_id=CASH_DESK_BRANCH).operation_types.set([other])

    response = auth_client.get(CONFIG_URL)

    assert response.data["source"] == "branch"
    assert response.data["template_branch_id"] == CASH_DESK_BRANCH
    assert [row["code"] for row in response.data["operations"]] == [other.code]


def test_own_configuration_overrides_the_template(auth_client, income_type):
    other = _other_type()
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])

    response = auth_client.put(CONFIG_URL, {"operations": [other.code]}, format="json")

    assert response.status_code == 200
    assert response.data["configured"] is True
    assert response.data["source"] == "own"
    assert [row["code"] for row in response.data["operations"]] == [other.code]
    assert CashDeskOperation.objects.filter(cash_desk_id=CASH_DESK).count() == 1


def test_an_empty_own_configuration_falls_back_to_the_template(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])
    auth_client.put(CONFIG_URL, {"operations": [income_type.code]}, format="json")

    response = auth_client.put(CONFIG_URL, {"operations": []}, format="json")

    assert response.data["configured"] is False
    assert response.data["source"] == "bank"
    assert CashDeskOperation.objects.filter(cash_desk_id=CASH_DESK).count() == 0


def test_an_unknown_operation_is_rejected(auth_client):
    response = auth_client.put(CONFIG_URL, {"operations": ["nope"]}, format="json")

    assert response.status_code == 400


def test_posting_an_operation_without_configuration_is_rejected(auth_client, income_type):
    response = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_posting_an_operation_not_enabled_on_the_desk_is_rejected(auth_client, income_type):
    other = _other_type()
    auth_client.put(CONFIG_URL, {"operations": [other.code]}, format="json")

    response = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_posting_a_currency_not_enabled_on_the_desk_is_rejected(
    auth_client, contracts, income_type
):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])
    contracts.cash_desk_config.allowed = {"BYN"}

    response = auth_client.post(
        OPERATIONS_URL, _post_payload(income_type, currency="USD"), format="json"
    )

    assert response.status_code == 400
    assert Operation.objects.count() == 0
