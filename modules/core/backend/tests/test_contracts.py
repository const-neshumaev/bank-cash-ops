"""The ``core`` module publishes its user directory through the registry."""

import pytest
from django.contrib.auth import get_user_model

from modules.common.contracts import registry
from modules.core.contracts.dto import UserDTO

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_registry_resolves_the_core_user_directory():
    directory = registry.get("core.users")

    assert hasattr(directory, "get_user")


def test_get_user_returns_a_dto():
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")

    dto = registry.get("core.users").get_user(user.id)

    assert isinstance(dto, UserDTO)
    assert dto.email == "cashier@example.com"
    assert dto.role == User.Role.CASHIER


def test_get_user_returns_none_for_an_unknown_id():
    assert registry.get("core.users").get_user(999999) is None


def test_is_admin_reflects_administrator_status():
    admin = User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")
    cashier = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")
    directory = registry.get("core.users")

    assert directory.is_admin(admin.id) is True
    assert directory.is_admin(cashier.id) is False
