"""Shared fixtures for the printing module tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.common.contracts import registry
from modules.core.contracts import ORG_DIRECTORY
from modules.printing.backend.sync import sync_print_templates

User = get_user_model()

CASH_DESK = 7


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
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")


@pytest.fixture
def auth_client(client, admin_user, contracts):
    client.force_authenticate(admin_user)
    return client
