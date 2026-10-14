"""Operation settings behave as a bank-wide singleton."""

from decimal import Decimal

import pytest

from modules.operations.backend.models import OperationsSettings

pytestmark = pytest.mark.django_db


def test_load_creates_the_singleton_from_the_environment(monkeypatch):
    monkeypatch.setenv("BCO_OPERATIONS_BASE_CURRENCY", "EUR")
    monkeypatch.setenv("BCO_OPERATIONS_CLIENT_ID_THRESHOLD", "1000")
    monkeypatch.setenv("BCO_OPERATIONS_REQUIRE_CLIENT", "true")

    settings = OperationsSettings.load()

    assert settings.pk == 1
    assert settings.base_currency == "EUR"
    assert settings.client_id_threshold == Decimal("1000")
    assert settings.require_client is True


def test_load_returns_the_same_row():
    assert OperationsSettings.load().pk == OperationsSettings.load().pk == 1


def test_editing_keeps_a_single_row():
    settings = OperationsSettings.load()

    settings.base_currency = "USD"
    settings.save()

    assert OperationsSettings.objects.count() == 1
    assert OperationsSettings.objects.get().base_currency == "USD"
