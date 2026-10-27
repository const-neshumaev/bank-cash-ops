"""Shared fixtures for the printing module tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.contracts import ORG_DIRECTORY
from modules.printing.backend.registry import print_template_registry
from modules.printing.backend.sync import sync_print_templates
from modules.printing.contracts import PrintDocumentTypeSpec, PrintTemplateSpec

User = get_user_model()

CASH_DESK = 7
PURCHASE_TEMPLATE = "cash_receipt_currency_purchase"
CASH_ORDER = "cash_order"
CASH_ORDER_TEMPLATE = "cash_order_default"
STATEMENT = "account_statement"
STATEMENT_TEMPLATE = "account_statement_default"
STATEMENT_DETAILED_TEMPLATE = "account_statement_detailed"


class FakeOrgDirectory:
    """Minimal ``OrgDirectory``: controls the visible cash desks."""

    def __init__(self, accessible=None):
        self.accessible = accessible

    def accessible_cash_desk_ids(self, user_id):
        return self.accessible


@pytest.fixture
def contracts(monkeypatch):
    org = FakeOrgDirectory()
    original_get = registry.get

    def _get(name):
        if name == ORG_DIRECTORY:
            return org
        return original_get(name)

    monkeypatch.setattr(registry, "get", _get)
    return SimpleNamespace(org=org)


@pytest.fixture
def synced_templates():
    """Materialise the baseline forms declared by ``printing_standard``."""
    return sync_print_templates()


@pytest.fixture
def second_document_type(synced_templates):
    """Declare an extra printed document type for the duration of a test."""
    purchase = print_template_registry.get_template_spec(PURCHASE_TEMPLATE)
    assert purchase is not None
    print_template_registry.register_document_type(
        PrintDocumentTypeSpec(code=CASH_ORDER, name="Приходный кассовый ордер")
    )
    print_template_registry.register_template(
        PrintTemplateSpec(
            code=CASH_ORDER_TEMPLATE,
            name="Приходный кассовый ордер",
            document_type=CASH_ORDER,
            provider="cash_receipt_exchange",
            default_file_path=purchase.default_file_path,
        )
    )
    try:
        sync_print_templates()
        yield
    finally:
        print_template_registry.unregister_template(CASH_ORDER_TEMPLATE)
        print_template_registry.unregister_document_type(CASH_ORDER)


@pytest.fixture
def unnumbered_document_type(synced_templates):
    """Declare a document type without numbering and two of its forms."""
    purchase = print_template_registry.get_template_spec(PURCHASE_TEMPLATE)
    assert purchase is not None
    print_template_registry.register_document_type(
        PrintDocumentTypeSpec(
            code=STATEMENT,
            name="Выписка по счёту",
            numbering_scope="none",
        )
    )
    for code, name in (
        (STATEMENT_TEMPLATE, "Выписка по счёту"),
        (STATEMENT_DETAILED_TEMPLATE, "Выписка по счёту (подробная)"),
    ):
        print_template_registry.register_template(
            PrintTemplateSpec(
                code=code,
                name=name,
                document_type=STATEMENT,
                provider="cash_receipt_exchange",
                default_file_path=purchase.default_file_path,
            )
        )
    try:
        sync_print_templates()
        yield
    finally:
        print_template_registry.unregister_template(STATEMENT_DETAILED_TEMPLATE)
        print_template_registry.unregister_template(STATEMENT_TEMPLATE)
        print_template_registry.unregister_document_type(STATEMENT)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def auth_client(client, admin_user, contracts):
    client.force_authenticate(admin_user)
    return client
