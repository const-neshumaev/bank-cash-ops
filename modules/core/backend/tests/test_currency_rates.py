"""Currency rates: the API and the effective-rate contract."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.backend.models import Branch, CashDesk, Currency, CurrencyRate
from modules.core.contracts import REFERENCE_DIRECTORY

User = get_user_model()

pytestmark = pytest.mark.django_db

RATES_URL = "/api/currency-rates/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def auth_client(client, admin_user):
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def usd():
    return Currency.objects.get(code="USD")


@pytest.fixture
def byn():
    return Currency.objects.get(code="BYN")


@pytest.fixture
def cash_desk():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    branch = Branch.objects.create(code="B1", name="Отделение 1", parent=head)
    return CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")


def _directory():
    return registry.get(REFERENCE_DIRECTORY)


def test_a_rate_can_be_created_through_the_api(auth_client, usd):
    response = auth_client.post(
        RATES_URL,
        {
            "currency": "USD",
            "base_currency": "BYN",
            "rate_type": "buy",
            "value": "3.250000",
            "effective_from": timezone.now().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    assert CurrencyRate.objects.count() == 1


def test_the_base_currency_must_differ(auth_client):
    response = auth_client.post(
        RATES_URL,
        {
            "currency": "USD",
            "base_currency": "USD",
            "rate_type": "buy",
            "value": "1",
            "effective_from": timezone.now().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400


def test_the_effective_rate_prefers_the_cash_desk(usd, byn, cash_desk):
    now = timezone.now()
    CurrencyRate.objects.create(
        currency=usd, base_currency=byn, rate_type="buy", value=Decimal("3.2"), effective_from=now
    )
    CurrencyRate.objects.create(
        currency=usd,
        base_currency=byn,
        cash_desk=cash_desk,
        rate_type="buy",
        value=Decimal("3.3"),
        effective_from=now,
    )

    assert _directory().rate("USD", "buy") == Decimal("3.200000")
    assert _directory().rate("USD", "buy", cash_desk_id=cash_desk.id) == Decimal("3.300000")


def test_the_latest_rate_wins(usd, byn):
    CurrencyRate.objects.create(
        currency=usd,
        base_currency=byn,
        rate_type="buy",
        value=Decimal("3.1"),
        effective_from=timezone.now() - timedelta(days=1),
    )
    CurrencyRate.objects.create(
        currency=usd,
        base_currency=byn,
        rate_type="buy",
        value=Decimal("3.5"),
        effective_from=timezone.now(),
    )

    assert _directory().rate("USD", "buy") == Decimal("3.500000")


def test_a_future_rate_is_ignored(usd, byn):
    CurrencyRate.objects.create(
        currency=usd,
        base_currency=byn,
        rate_type="buy",
        value=Decimal("3.9"),
        effective_from=timezone.now() + timedelta(days=1),
    )

    assert _directory().rate("USD", "buy") is None


def test_cash_desk_rates_returns_the_effective_rates(usd, byn, cash_desk):
    CurrencyRate.objects.create(
        currency=usd,
        base_currency=byn,
        rate_type="buy",
        value=Decimal("3.2"),
        effective_from=timezone.now(),
    )

    rates = _directory().cash_desk_rates(cash_desk.id)

    assert len(rates) == 1
    assert rates[0].currency_code == "USD"
    assert rates[0].value == Decimal("3.200000")
