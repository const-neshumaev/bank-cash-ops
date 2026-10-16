"""Bank rate types and the fixed principles they reference."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import translation
from rest_framework.test import APIClient

from modules.references.backend.models import CurrencyRateType
from modules.references.contracts import CurrencyRatePrinciple

User = get_user_model()

pytestmark = pytest.mark.django_db

RATE_TYPES_URL = "/api/references/rate-types/"


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


def test_the_system_rate_types_are_seeded_one_per_principle():
    principles = set(
        CurrencyRateType.objects.filter(is_system=True).values_list("principle", flat=True)
    )

    assert principles == set(CurrencyRatePrinciple.VALUES)


def test_the_api_lists_the_rate_types(auth_client):
    response = auth_client.get(RATE_TYPES_URL)

    assert response.status_code == 200
    assert {"official", "buy", "sell", "conversion"} <= {
        row["code"] for row in response.data["results"]
    }


def test_the_api_localizes_a_rate_type_name(auth_client):
    response = auth_client.get(RATE_TYPES_URL, HTTP_ACCEPT_LANGUAGE="en")

    by_code = {row["code"]: row for row in response.data["results"]}
    assert by_code["buy"]["name"] == "Buy rate"

    with translation.override("ru"):
        assert CurrencyRateType.objects.get(code="buy").localized_name() == "Курс покупки"


def test_a_bank_can_add_a_rate_type_for_an_existing_principle(auth_client):
    response = auth_client.post(
        RATE_TYPES_URL,
        {"code": "buy_cash", "name": "Курс покупки (наличные)", "principle": "buy", "order": 10},
        format="json",
    )

    assert response.status_code == 201, response.content
    rate_type = CurrencyRateType.objects.get(code="buy_cash")
    assert rate_type.principle == CurrencyRatePrinciple.BUY
    assert rate_type.is_system is False


def test_a_system_rate_type_cannot_be_deleted(auth_client):
    response = auth_client.delete(f"{RATE_TYPES_URL}{CurrencyRateType.objects.get(code='buy').id}/")

    assert response.status_code == 400
    assert CurrencyRateType.objects.filter(code="buy").exists()
