"""Localized currency names backed by per-currency translation rows."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import translation
from rest_framework.test import APIClient

from modules.core.backend.models import Currency, CurrencyTranslation

User = get_user_model()

pytestmark = pytest.mark.django_db

CURRENCIES_URL = "/api/currencies/"

SEEDED_ENGLISH = {
    "BYN": "Belarusian ruble",
    "USD": "US dollar",
    "EUR": "Euro",
    "RUB": "Russian ruble",
}


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


def _names_by_code(payload):
    return {row["code"]: row["name"] for row in payload["results"]}


def test_localized_name_falls_back_to_the_base_value():
    currency = Currency.objects.create(code="GBP", name="Фунт стерлингов")

    assert currency.localized_name("en") == "Фунт стерлингов"
    assert currency.localized_name("ru") == "Фунт стерлингов"


def test_localized_name_returns_the_translation_when_present():
    currency = Currency.objects.create(code="GBP", name="Фунт стерлингов")
    CurrencyTranslation.objects.create(currency=currency, language="en", name="Pound sterling")

    assert currency.localized_name("en") == "Pound sterling"
    assert currency.localized_name("ru") == "Фунт стерлингов"


def test_localized_name_uses_the_active_language():
    currency = Currency.objects.create(code="GBP", name="Фунт стерлингов")
    CurrencyTranslation.objects.create(currency=currency, language="en", name="Pound sterling")

    with translation.override("en"):
        assert currency.localized_name() == "Pound sterling"
    with translation.override("ru"):
        assert currency.localized_name() == "Фунт стерлингов"


def test_a_blank_translation_falls_back_to_the_base_value():
    currency = Currency.objects.create(code="GBP", name="Фунт стерлингов")
    CurrencyTranslation.objects.create(currency=currency, language="en", name="")

    assert currency.localized_name("en") == "Фунт стерлингов"


def test_the_seeded_currencies_have_english_translations():
    translations = {
        row.currency.code: row.name
        for row in CurrencyTranslation.objects.filter(language="en")
    }

    for code, name in SEEDED_ENGLISH.items():
        assert translations[code] == name

    # The base value stays the Russian name seeded with the currency.
    assert Currency.objects.get(code="USD").name == "Доллар США"


def test_the_api_returns_the_english_name_for_accept_language_en(auth_client):
    response = auth_client.get(CURRENCIES_URL, HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert _names_by_code(response.data)["USD"] == "US dollar"


def test_the_api_returns_the_base_name_for_accept_language_ru(auth_client):
    response = auth_client.get(CURRENCIES_URL, HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    assert _names_by_code(response.data)["USD"] == "Доллар США"


def test_the_api_localizes_names_in_a_currency_template(auth_client):
    auth_client.put(
        "/api/currency-templates/bank/",
        {"currencies": ["USD"]},
        format="json",
    )

    response = auth_client.get("/api/currency-templates/bank/", HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.data["currencies"][0]["name"] == "US dollar"


def test_creating_a_currency_sets_the_base_name(auth_client):
    response = auth_client.post(
        CURRENCIES_URL,
        {
            "code": "gbp",
            "name": "Фунт стерлингов",
            "symbol": "£",
            "minor_units": 2,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert Currency.objects.get(code="GBP").name == "Фунт стерлингов"


def test_updating_a_currency_sets_the_base_name(auth_client):
    Currency.objects.create(code="GBP", name="Фунт")

    response = auth_client.patch(
        f"{CURRENCIES_URL}GBP/",
        {"name": "Фунт стерлингов"},
        format="json",
    )

    assert response.status_code == 200
    assert Currency.objects.get(code="GBP").name == "Фунт стерлингов"
