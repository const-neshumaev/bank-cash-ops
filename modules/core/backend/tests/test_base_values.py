"""Bank settings and the effective-dated base value catalogue."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from modules.core.backend.models import BankSettings, BaseValue, CurrencyRate, Role

User = get_user_model()

pytestmark = pytest.mark.django_db

SETTINGS_URL = "/api/settings/"
BASE_VALUES_URL = "/api/base-values/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def cashier_user():
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")
    user.roles.add(Role.objects.get(code="cashier"))
    return user


def _future(days: int = 30) -> str:
    return (timezone.localdate() + timedelta(days=days)).isoformat()


class TestBankSettings:
    def test_the_public_response_includes_the_base_currency(self, client):
        response = client.get(SETTINGS_URL)

        assert response.status_code == 200
        assert response.data["base_currency"] == "BYN"

    def test_an_administrator_can_change_the_base_currency(self, client, admin_user):
        client.force_authenticate(admin_user)

        response = client.patch(SETTINGS_URL, {"base_currency": "usd"}, format="json")

        assert response.status_code == 200, response.content
        assert response.data["base_currency"] == "USD"
        assert BankSettings.load().base_currency == "USD"

    def test_a_user_without_permission_cannot_change_the_base_currency(self, client, cashier_user):
        client.force_authenticate(cashier_user)

        response = client.patch(SETTINGS_URL, {"base_currency": "USD"}, format="json")

        assert response.status_code == 403

    def test_an_unknown_currency_is_rejected(self, client, admin_user):
        client.force_authenticate(admin_user)

        response = client.patch(SETTINGS_URL, {"base_currency": "XXX"}, format="json")

        assert response.status_code == 400
        assert "base_currency" in response.data

    def test_the_base_currency_cannot_change_while_rates_use_another_base(self, client, admin_user):
        CurrencyRate.objects.create(
            currency="USD",
            base_currency="BYN",
            rate_type="official",
            value=Decimal("3.00000000"),
            effective_from=timezone.now(),
        )
        client.force_authenticate(admin_user)

        response = client.patch(SETTINGS_URL, {"base_currency": "EUR"}, format="json")

        assert response.status_code == 400
        assert "base_currency" in response.data


class TestBaseValues:
    def test_a_created_value_takes_the_bank_currency_snapshot(self, client, admin_user):
        client.force_authenticate(admin_user)

        response = client.post(
            BASE_VALUES_URL,
            {"effective_from": _future(), "amount": "40.00"},
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.data["currency_code"] == "BYN"
        assert BaseValue.objects.count() == 1

    def test_the_date_is_unique(self, client, admin_user):
        client.force_authenticate(admin_user)
        effective_from = _future()
        client.post(
            BASE_VALUES_URL,
            {"effective_from": effective_from, "amount": "40.00"},
            format="json",
        )

        response = client.post(
            BASE_VALUES_URL,
            {"effective_from": effective_from, "amount": "41.00"},
            format="json",
        )

        assert response.status_code == 400
        assert "effective_from" in response.data

    def test_a_future_value_can_be_edited_and_deleted(self, client, admin_user):
        client.force_authenticate(admin_user)
        created = client.post(
            BASE_VALUES_URL,
            {"effective_from": _future(), "amount": "40.00"},
            format="json",
        ).data

        updated = client.patch(
            f"{BASE_VALUES_URL}{created['id']}/", {"amount": "42.00"}, format="json"
        )

        assert updated.status_code == 200, updated.content
        assert updated.data["amount"] == "42.00"
        assert client.delete(f"{BASE_VALUES_URL}{created['id']}/").status_code == 204

    def test_an_effective_value_cannot_be_changed_or_deleted(self, client, admin_user):
        client.force_authenticate(admin_user)
        value = BaseValue.objects.create(effective_from=date(2020, 1, 1), amount=Decimal("40.00"))

        updated = client.patch(f"{BASE_VALUES_URL}{value.id}/", {"amount": "42.00"}, format="json")
        deleted = client.delete(f"{BASE_VALUES_URL}{value.id}/")

        assert updated.status_code == 400
        assert deleted.status_code == 400
        value.refresh_from_db()
        assert value.amount == Decimal("40.00")

    def test_a_cashier_may_read_but_not_change_the_catalogue(self, client, cashier_user):
        client.force_authenticate(cashier_user)

        assert client.get(BASE_VALUES_URL).status_code == 200
        assert (
            client.post(
                BASE_VALUES_URL,
                {"effective_from": _future(), "amount": "40.00"},
                format="json",
            ).status_code
            == 403
        )
