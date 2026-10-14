"""Currency reference data and per-cash-desk currency configuration."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.backend.models import Branch, CashDesk, CashDeskCurrency, Currency
from modules.core.contracts import REFERENCE_DIRECTORY

User = get_user_model()

pytestmark = pytest.mark.django_db

CURRENCIES_URL = "/api/currencies/"


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


def test_common_currencies_are_seeded():
    codes = set(Currency.objects.values_list("code", flat=True))

    assert {"BYN", "USD", "EUR", "RUB"} <= codes


def test_listing_currencies(auth_client):
    response = auth_client.get(CURRENCIES_URL)

    assert response.status_code == 200
    assert "USD" in {row["code"] for row in response.data["results"]}


def test_a_cash_desk_is_unrestricted_without_configuration(auth_client, cash_desk):
    response = auth_client.get(f"/api/cash-desks/{cash_desk.id}/currencies/")

    assert response.status_code == 200
    assert response.data["configured"] is False
    assert "USD" in {row["code"] for row in response.data["currencies"]}


def test_setting_cash_desk_currencies(auth_client, cash_desk):
    response = auth_client.put(
        f"/api/cash-desks/{cash_desk.id}/currencies/",
        {"currencies": ["USD", "BYN"]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["configured"] is True
    assert {row["code"] for row in response.data["currencies"]} == {"USD", "BYN"}
    assert CashDeskCurrency.objects.filter(cash_desk=cash_desk).count() == 2


def test_an_unknown_currency_is_rejected(auth_client, cash_desk):
    response = auth_client.put(
        f"/api/cash-desks/{cash_desk.id}/currencies/",
        {"currencies": ["XXX"]},
        format="json",
    )

    assert response.status_code == 400


def test_reference_directory_contract_reports_the_enabled_currencies(cash_desk):
    directory = registry.get(REFERENCE_DIRECTORY)

    assert directory.cash_desk_currency_codes(cash_desk.id) is None

    CashDeskCurrency.objects.create(
        cash_desk=cash_desk, currency=Currency.objects.get(code="USD")
    )

    assert directory.cash_desk_currency_codes(cash_desk.id) == {"USD"}
