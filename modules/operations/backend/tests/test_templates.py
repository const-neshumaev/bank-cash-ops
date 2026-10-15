"""The operation template API: the bank default and per-branch overrides."""

import pytest
from django.contrib.auth import get_user_model

from modules.operations.backend.models import OperationTemplate
from modules.operations.backend.permission_codes import PermissionCode
from modules.operations.backend.tests.conftest import CASH_DESK_BRANCH

User = get_user_model()

pytestmark = pytest.mark.django_db

BANK_URL = "/api/operations/operation-templates/bank/"
BRANCH_URL = f"/api/operations/operation-templates/branches/{CASH_DESK_BRANCH}/"
LIST_URL = "/api/operations/operation-templates/"


def _put(client, url, code):
    return client.put(url, {"operations": [code]}, format="json")


def test_the_bank_template_is_undefined_by_default(auth_client):
    response = auth_client.get(BANK_URL)

    assert response.status_code == 200
    assert response.data["branch_id"] is None
    assert response.data["defined"] is False
    assert response.data["operations"] == []


def test_setting_and_clearing_the_bank_template(auth_client, income_type):
    response = auth_client.put(BANK_URL, {"operations": [income_type.code]}, format="json")

    assert response.status_code == 200
    assert response.data["defined"] is True
    assert [row["code"] for row in response.data["operations"]] == [income_type.code]

    response = auth_client.delete(BANK_URL)

    assert response.status_code == 204
    assert OperationTemplate.objects.filter(branch_id__isnull=True).count() == 0


def test_setting_a_branch_template(auth_client, income_type):
    response = auth_client.put(BRANCH_URL, {"operations": [income_type.code]}, format="json")

    assert response.status_code == 200
    assert response.data["branch_id"] == CASH_DESK_BRANCH
    assert [row["code"] for row in response.data["operations"]] == [income_type.code]


def test_the_list_includes_every_defined_template(auth_client, income_type):
    auth_client.put(BANK_URL, {"operations": [income_type.code]}, format="json")
    auth_client.put(BRANCH_URL, {"operations": [income_type.code]}, format="json")

    response = auth_client.get(LIST_URL)

    assert response.status_code == 200
    assert {row["branch_id"] for row in response.data["results"]} == {None, CASH_DESK_BRANCH}


def test_templates_cannot_be_changed_without_a_permission(client, income_type):
    plain = User.objects.create_user(email="plain@example.com", password="secret-pass-123")
    client.force_authenticate(plain)

    assert _put(client, BRANCH_URL, income_type.code).status_code == 403
    assert _put(client, BANK_URL, income_type.code).status_code == 403


def test_the_branch_permission_is_limited_to_accessible_branches(
    client, contracts, user, income_type, monkeypatch
):
    monkeypatch.setattr(
        user,
        "has_permission",
        lambda code: code == PermissionCode.CONFIG_MANAGE_BRANCH,
        raising=False,
    )
    contracts.org.accessible_branches = {CASH_DESK_BRANCH}
    client.force_authenticate(user)

    # An accessible branch: allowed.
    assert _put(client, BRANCH_URL, income_type.code).status_code == 200

    # The bank-wide template stays out of reach.
    assert _put(client, BANK_URL, income_type.code).status_code == 403

    # A branch outside the scope: denied as well.
    other_branch_url = "/api/operations/operation-templates/branches/999/"
    assert _put(client, other_branch_url, income_type.code).status_code == 403
