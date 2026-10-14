"""The permission catalog aggregates the codes of every installed module."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db

PERMISSIONS_URL = "/api/permissions/"
ROLES_URL = "/api/roles/"


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


def test_the_catalog_includes_operations_codes(auth_client):
    response = auth_client.get(PERMISSIONS_URL)

    assert response.status_code == 200
    codes = {row["code"] for row in response.data}
    assert {"core.users.view", "operations.create"} <= codes


def test_a_role_can_hold_an_operations_permission(auth_client):
    response = auth_client.post(
        ROLES_URL,
        {"name": "Операционист", "permissions": ["operations.view", "operations.create"]},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert set(response.data["permissions"]) == {"operations.view", "operations.create"}


def test_an_unknown_permission_code_is_rejected(auth_client):
    response = auth_client.post(
        ROLES_URL,
        {"name": "Пустая роль", "permissions": ["nope.nope"]},
        format="json",
    )

    assert response.status_code == 400
