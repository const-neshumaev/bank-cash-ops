"""The ``core`` module publishes its user directory through the registry."""

import pytest
from django.contrib.auth import get_user_model

from modules.common.contracts import registry
from modules.core.backend.models import Role
from modules.core.backend.permission_codes import PermissionCode
from modules.core.contracts.dto import UserDTO

User = get_user_model()

pytestmark = pytest.mark.django_db


def _user_with_roles(email, *codes):
    user = User.objects.create_user(email=email, password="secret-pass-123")
    user.roles.set(Role.objects.filter(code__in=codes))
    return user


def test_registry_resolves_the_core_user_directory():
    directory = registry.get("core.users")

    assert hasattr(directory, "get_user")


def test_get_user_returns_a_dto():
    user = _user_with_roles("cashier@example.com", "cashier")

    dto = registry.get("core.users").get_user(user.id)

    assert isinstance(dto, UserDTO)
    assert dto.email == "cashier@example.com"
    assert dto.role_codes == ("cashier",)


def test_get_user_returns_none_for_an_unknown_id():
    assert registry.get("core.users").get_user(999999) is None


def test_is_admin_reflects_administrator_status():
    admin = User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")
    cashier = _user_with_roles("cashier@example.com", "cashier")
    directory = registry.get("core.users")

    assert directory.is_admin(admin.id) is True
    assert directory.is_admin(cashier.id) is False


def test_has_permission_reflects_the_granted_roles():
    cashier = _user_with_roles("cashier@example.com", "cashier")
    directory = registry.get("core.users")

    assert directory.has_permission(cashier.id, PermissionCode.SHIFTS_OPEN) is True
    assert directory.has_permission(cashier.id, PermissionCode.USERS_MANAGE) is False
