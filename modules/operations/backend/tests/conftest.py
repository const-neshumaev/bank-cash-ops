"""Shared fixtures for the operations API tests.

The ``core`` contracts are replaced with fakes, so the module is exercised
through its own API without reaching into ``core``'s tables or models.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.contracts import (
    ORG_DIRECTORY,
    REFERENCE_DIRECTORY,
    CurrencyDTO,
    ShiftDTO,
)
from modules.operations.backend.models import OperationType, SlotDef
from modules.operations.contracts import OperationKind

User = get_user_model()

CASH_DESK = 7
OTHER_CASH_DESK = 99
SHIFT = 11

DEFAULT_CURRENCIES = (
    CurrencyDTO(code="BYN", name="Белорусский рубль", symbol="Br", minor_units=2),
    CurrencyDTO(code="USD", name="Доллар США", symbol="$", minor_units=2),
)


class FakeOrgDirectory:
    """Minimal ``OrgDirectory`` used instead of the real ``core`` service."""

    def __init__(self, *, shift=None, accessible=None):
        self.shift = shift
        self.accessible = accessible

    def get_open_shift(self, cashier_id):
        return self.shift

    def get_cash_desk(self, cash_desk_id):
        return None

    def accessible_cash_desk_ids(self, user_id):
        return self.accessible

    def user_can_access_cash_desk(self, user_id, cash_desk_id):
        return self.accessible is None or cash_desk_id in self.accessible


class FakeReferenceDirectory:
    """Minimal ``ReferenceDirectory``; ``allowed=None`` means unrestricted."""

    def __init__(self, allowed=None, rates=()):
        self.allowed = allowed
        self.rates = rates

    def currencies(self):
        return DEFAULT_CURRENCIES

    def get_currency(self, code):
        return next((currency for currency in DEFAULT_CURRENCIES if currency.code == code), None)

    def cash_desk_currency_codes(self, cash_desk_id):
        return self.allowed

    def rate(self, currency_code, rate_type, *, cash_desk_id=None, at=None):
        return None

    def cash_desk_rates(self, cash_desk_id):
        return self.rates


@pytest.fixture
def contracts(monkeypatch):
    """Replace the ``core`` contracts the operations API depends on."""
    org = FakeOrgDirectory(
        shift=ShiftDTO(id=SHIFT, cash_desk_id=CASH_DESK, cashier_id=1, status="open"),
        accessible=None,
    )
    references = FakeReferenceDirectory()
    original_get = registry.get

    def _get(name):
        if name == ORG_DIRECTORY:
            return org
        if name == REFERENCE_DIRECTORY:
            return references
        return original_get(name)

    monkeypatch.setattr(registry, "get", _get)
    return SimpleNamespace(org=org, references=references)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_superuser(email="cashier@example.com", password="secret-pass-123")


@pytest.fixture
def auth_client(client, user, contracts):
    client.force_authenticate(user)
    return client


@pytest.fixture
def income_type():
    operation_type = OperationType.objects.create(
        code="cash_receipt",
        name="Приход наличных",
        kind=OperationKind.INCOME,
        template={"movements": [{"register": "cash", "slot": "amount", "sign": 1}]},
    )
    SlotDef.objects.create(operation_type=operation_type, code="amount", name="Сумма")
    return operation_type
