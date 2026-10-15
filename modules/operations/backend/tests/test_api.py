"""REST API of the operations module: posting, journal, balances, settings."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from modules.operations.backend.models import (
    CashBalance,
    Operation,
    OperationsSettings,
    OperationTemplate,
)
from modules.operations.backend.permission_codes import PermissionCode

User = get_user_model()

pytestmark = pytest.mark.django_db

TYPES_URL = "/api/operations/types/"
BALANCES_URL = "/api/operations/balances/"
OPERATIONS_URL = "/api/operations/operations/"
SETTINGS_URL = "/api/operations/settings/"

CASH_DESK = 7
OTHER_CASH_DESK = 99


def _post_payload(operation_type, amount="500.00", currency="USD"):
    return {
        "operation_type": operation_type.code,
        "lines": [{"slot": "amount", "currency": currency, "amount": amount}],
    }


def test_listing_operations_requires_authentication(client):
    assert client.get(OPERATIONS_URL).status_code == 401


def test_types_endpoint_lists_the_catalogue(auth_client, income_type):
    response = auth_client.get(TYPES_URL)

    assert response.status_code == 200
    assert response.data["results"][0]["code"] == "cash_receipt"
    assert response.data["results"][0]["slots"][0]["code"] == "amount"


def test_posting_an_operation_updates_the_balance(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])

    response = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 201, response.content
    assert response.data["cash_desk_id"] == CASH_DESK
    assert response.data["number"] == 1
    balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert balance.amount == Decimal("500.00")


def test_posting_without_an_open_shift_is_rejected(auth_client, contracts, income_type):
    contracts.org.shift = None

    response = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 400
    assert Operation.objects.count() == 0


def test_reversing_an_operation_closes_it(auth_client, income_type):
    OperationTemplate.objects.create(branch_id=None).operation_types.set([income_type])
    posted = auth_client.post(OPERATIONS_URL, _post_payload(income_type), format="json").data

    response = auth_client.post(f"{OPERATIONS_URL}{posted['id']}/reverse/", {}, format="json")

    assert response.status_code == 201, response.content
    original = Operation.objects.get(pk=posted["id"])
    assert original.status == Operation.Status.REVERSED
    assert CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD").amount == Decimal("0.00")


def test_balances_are_narrowed_to_the_callers_cash_desks(auth_client, contracts):
    CashBalance.objects.create(cash_desk_id=CASH_DESK, currency="USD", amount=Decimal("100"))
    CashBalance.objects.create(cash_desk_id=OTHER_CASH_DESK, currency="USD", amount=Decimal("50"))
    contracts.org.accessible = {CASH_DESK}

    response = auth_client.get(BALANCES_URL)

    assert response.status_code == 200
    cash_desks = [row["cash_desk_id"] for row in response.data["results"]]
    assert cash_desks == [CASH_DESK]


def test_settings_can_be_read_and_updated(auth_client):
    assert auth_client.get(SETTINGS_URL).status_code == 200

    response = auth_client.patch(SETTINGS_URL, {"base_currency": "USD"}, format="json")

    assert response.status_code == 200
    assert response.data["base_currency"] == "USD"
    assert OperationsSettings.load().base_currency == "USD"


def test_a_user_without_permissions_is_rejected(client, contracts, income_type):
    plain = User.objects.create_user(email="plain@example.com", password="secret-pass-123")
    client.force_authenticate(plain)

    response = client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 403


def test_a_type_specific_permission_is_enforced(client, user, contracts, income_type, monkeypatch):
    income_type.permission_code = "operations.supervised"
    income_type.save(update_fields=["permission_code"])
    # The user may post in general, but not the type-specific permission.
    monkeypatch.setattr(
        user, "has_permission", lambda code: code == PermissionCode.CREATE, raising=False
    )
    client.force_authenticate(user)

    response = client.post(OPERATIONS_URL, _post_payload(income_type), format="json")

    assert response.status_code == 403
