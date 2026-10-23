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
    BANK_SETTINGS,
    CASH_DESK_CONFIG,
    ORG_DIRECTORY,
    BankSettingsDTO,
    CashDeskDTO,
    ShiftDTO,
)
from modules.operations.backend.models import OperationType, SlotDef
from modules.operations.contracts import OperationKind
from modules.references.contracts import (
    REFERENCE_DIRECTORY,
    CurrencyDTO,
)

User = get_user_model()

CASH_DESK = 7
OTHER_CASH_DESK = 99
CASH_DESK_BRANCH = 3
SHIFT = 11

DEFAULT_CURRENCIES = (
    CurrencyDTO(code="BYN", name="Белорусский рубль", symbol="Br", minor_units=2),
    CurrencyDTO(code="USD", name="Доллар США", symbol="$", minor_units=2),
)


class FakeOrgDirectory:
    """Minimal ``OrgDirectory`` used instead of the real ``core`` service."""

    def __init__(self, *, shift=None, accessible=None, branch_id=CASH_DESK_BRANCH, ancestors=None):
        self.shift = shift
        self.accessible = accessible
        self.branch_id = branch_id
        self.ancestors = ancestors if ancestors is not None else ((branch_id,) if branch_id else ())
        self.accessible_branches = None

    def get_open_shift(self, cashier_id):
        return self.shift

    def get_cash_desk(self, cash_desk_id):
        if cash_desk_id != CASH_DESK or self.branch_id is None:
            return None
        return CashDeskDTO(
            id=cash_desk_id,
            branch_id=self.branch_id,
            is_active=True,
            name="Касса 7",
            code="K7",
            branch_name="Отделение 1",
            bank_name="Банк",
        )

    def accessible_cash_desk_ids(self, user_id):
        return self.accessible

    def accessible_branch_ids(self, user_id):
        return self.accessible_branches

    def branch_ancestor_ids(self, branch_id):
        return self.ancestors

    def user_can_access_cash_desk(self, user_id, cash_desk_id):
        return self.accessible is None or cash_desk_id in self.accessible


class FakeReferenceDirectory:
    """Minimal ``references`` directory: the currency dictionary and rate types."""

    def __init__(self, rate_types=(), currencies=DEFAULT_CURRENCIES):
        self._rate_types = tuple(rate_types)
        self._currencies = tuple(currencies)

    def currencies(self):
        return self._currencies

    def get_currency(self, code):
        return next((currency for currency in self._currencies if currency.code == code), None)

    def rate_types(self):
        return self._rate_types

    def get_rate_type(self, code):
        return next((item for item in self._rate_types if item.code == code), None)


class FakeCashDeskConfig:
    """Minimal ``core`` cash desk configuration; by default every currency is allowed."""

    def __init__(self, allowed=None, rates=(), currency_rates=None):
        self.allowed = allowed if allowed is not None else {c.code for c in DEFAULT_CURRENCIES}
        self.rates = rates
        self.currency_rates = currency_rates or {}

    def cash_desk_currency_codes(self, cash_desk_id):
        return self.allowed

    def rate(self, currency_code, rate_type, *, target_currency=None, cash_desk_id=None, at=None):
        return self.currency_rates.get((currency_code, rate_type, target_currency))

    def cash_desk_rates(self, cash_desk_id):
        return self.rates


class FakeBankSettings:
    """Minimal ``core`` bank settings directory used by threshold and exchange rules."""

    def __init__(self, base_currency="BYN", conversion_mode="via_base", base_value=None):
        self.settings = BankSettingsDTO(
            base_currency=base_currency,
            conversion_mode=conversion_mode,
            base_value=base_value,
        )

    def get_settings(self, on=None):
        return self.settings


@pytest.fixture
def contracts(monkeypatch):
    """Replace the ``core`` and ``references`` contracts the operations API depends on."""
    org = FakeOrgDirectory(
        shift=ShiftDTO(id=SHIFT, cash_desk_id=CASH_DESK, cashier_id=1, status="open"),
        accessible=None,
    )
    references = FakeReferenceDirectory()
    cash_desk_config = FakeCashDeskConfig()
    bank_settings = FakeBankSettings()
    original_get = registry.get

    def _get(name):
        if name == ORG_DIRECTORY:
            return org
        if name == REFERENCE_DIRECTORY:
            return references
        if name == CASH_DESK_CONFIG:
            return cash_desk_config
        if name == BANK_SETTINGS:
            return bank_settings
        return original_get(name)

    monkeypatch.setattr(registry, "get", _get)
    return SimpleNamespace(
        org=org,
        references=references,
        cash_desk_config=cash_desk_config,
        bank_settings=bank_settings,
    )


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
        form="amount",
        template={"movements": [{"register": "cash", "slot": "amount", "sign": 1}]},
    )
    SlotDef.objects.create(
        operation_type=operation_type, code="amount", name="Сумма", threshold_basis=True
    )
    return operation_type
