"""Currency reference data, cash desk currencies and currency templates."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.backend.models import (
    Branch,
    BranchAccess,
    CashDesk,
    CashDeskCurrency,
    Currency,
    CurrencyTemplate,
    Role,
)
from modules.core.contracts import REFERENCE_DIRECTORY

User = get_user_model()

pytestmark = pytest.mark.django_db

CURRENCIES_URL = "/api/currencies/"
BANK_TEMPLATE_URL = "/api/currency-templates/bank/"
LIST_TEMPLATES_URL = "/api/currency-templates/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def cash_desk():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    branch = Branch.objects.create(code="B1", name="Отделение 1", parent=head)
    return CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")


@pytest.fixture
def auth_client(client, admin_user):
    client.force_authenticate(admin_user)
    return client


def _currencies_url(cash_desk):
    return f"/api/cash-desks/{cash_desk.id}/currencies/"


def _branch_template_url(branch_id):
    return f"/api/currency-templates/branches/{branch_id}/"


def _codes(payload):
    return {row["code"] for row in payload["currencies"]}


def test_common_currencies_are_seeded():
    codes = set(Currency.objects.values_list("code", flat=True))

    assert {"BYN", "USD", "EUR", "RUB"} <= codes


def test_listing_currencies(auth_client):
    response = auth_client.get(CURRENCIES_URL)

    assert response.status_code == 200
    assert "USD" in {row["code"] for row in response.data["results"]}


def test_a_cash_desk_without_configuration_denies_every_currency(auth_client, cash_desk):
    response = auth_client.get(_currencies_url(cash_desk))

    assert response.status_code == 200
    assert response.data["configured"] is False
    assert response.data["source"] == "none"
    assert response.data["currencies"] == []


def test_the_bank_template_sets_the_default(auth_client, cash_desk):
    template = CurrencyTemplate.objects.create(branch=None)
    template.currencies.set([Currency.objects.get(code="USD")])

    response = auth_client.get(_currencies_url(cash_desk))

    assert response.data["configured"] is False
    assert response.data["source"] == "bank"
    assert response.data["template_branch_id"] is None
    assert _codes(response.data) == {"USD"}


def test_a_branch_template_overrides_the_bank_template(auth_client, cash_desk):
    bank = CurrencyTemplate.objects.create(branch=None)
    bank.currencies.set([Currency.objects.get(code="USD")])
    branch = CurrencyTemplate.objects.create(branch=cash_desk.branch)
    branch.currencies.set([Currency.objects.get(code="BYN")])

    response = auth_client.get(_currencies_url(cash_desk))

    assert response.data["source"] == "branch"
    assert response.data["template_branch_id"] == cash_desk.branch_id
    assert _codes(response.data) == {"BYN"}


def test_setting_cash_desk_currencies(auth_client, cash_desk):
    response = auth_client.put(
        _currencies_url(cash_desk),
        {"currencies": ["USD", "BYN"]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["configured"] is True
    assert response.data["source"] == "own"
    assert _codes(response.data) == {"USD", "BYN"}
    assert CashDeskCurrency.objects.filter(cash_desk=cash_desk).count() == 2


def test_an_empty_own_configuration_falls_back_to_the_template(auth_client, cash_desk):
    template = CurrencyTemplate.objects.create(branch=None)
    template.currencies.set([Currency.objects.get(code="USD")])
    auth_client.put(_currencies_url(cash_desk), {"currencies": ["BYN"]}, format="json")

    response = auth_client.put(_currencies_url(cash_desk), {"currencies": []}, format="json")

    assert response.data["configured"] is False
    assert response.data["source"] == "bank"
    assert CashDeskCurrency.objects.filter(cash_desk=cash_desk).count() == 0


def test_an_unknown_currency_is_rejected(auth_client, cash_desk):
    response = auth_client.put(
        _currencies_url(cash_desk),
        {"currencies": ["XXX"]},
        format="json",
    )

    assert response.status_code == 400


def test_reference_directory_contract_reports_the_effective_currencies(cash_desk):
    directory = registry.get(REFERENCE_DIRECTORY)

    assert directory.cash_desk_currency_codes(cash_desk.id) == set()

    CashDeskCurrency.objects.create(cash_desk=cash_desk, currency=Currency.objects.get(code="USD"))

    assert directory.cash_desk_currency_codes(cash_desk.id) == {"USD"}


def test_setting_and_clearing_the_bank_currency_template(auth_client):
    response = auth_client.put(BANK_TEMPLATE_URL, {"currencies": ["USD", "BYN"]}, format="json")

    assert response.status_code == 200
    assert response.data["defined"] is True
    assert response.data["branch_id"] is None
    assert _codes(response.data) == {"USD", "BYN"}

    assert auth_client.delete(BANK_TEMPLATE_URL).status_code == 204
    assert CurrencyTemplate.objects.filter(branch__isnull=True).count() == 0


def test_setting_a_branch_currency_template(auth_client, cash_desk):
    response = auth_client.put(
        _branch_template_url(cash_desk.branch_id), {"currencies": ["USD"]}, format="json"
    )

    assert response.status_code == 200
    assert response.data["branch_id"] == cash_desk.branch_id
    assert _codes(response.data) == {"USD"}


def test_the_template_list_contains_the_bank_and_branch_templates(auth_client, cash_desk):
    auth_client.put(BANK_TEMPLATE_URL, {"currencies": ["USD"]}, format="json")
    auth_client.put(
        _branch_template_url(cash_desk.branch_id), {"currencies": ["BYN"]}, format="json"
    )

    response = auth_client.get(LIST_TEMPLATES_URL)

    assert response.status_code == 200
    assert {row["branch_id"] for row in response.data["results"]} == {None, cash_desk.branch_id}


def test_the_branch_permission_is_scoped_to_accessible_branches(client, cash_desk):
    manager = User.objects.create_user(email="mgr@example.com", password="secret-pass-123")
    manager.roles.set(Role.objects.filter(code="branch_manager"))
    client.force_authenticate(manager)

    url = _branch_template_url(cash_desk.branch_id)

    # Without branch access the bank-wide and branch templates are out of reach.
    assert client.put(url, {"currencies": ["USD"]}, format="json").status_code == 403
    assert client.put(BANK_TEMPLATE_URL, {"currencies": ["USD"]}, format="json").status_code == 403

    # Granting access to the branch enables its template, but never the bank one.
    BranchAccess.objects.create(user=manager, branch=cash_desk.branch, include_descendants=False)
    assert client.put(url, {"currencies": ["USD"]}, format="json").status_code == 200
    assert client.put(BANK_TEMPLATE_URL, {"currencies": ["USD"]}, format="json").status_code == 403
