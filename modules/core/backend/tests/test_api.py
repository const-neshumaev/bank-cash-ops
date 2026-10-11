import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db

ADMIN_PASSWORD = "admin-pass-12345"
CASHIER_PASSWORD = "cashier-pass-123"

USERS_URL = "/api/users/"
LOGIN_URL = "/api/auth/login/"
ME_URL = "/api/auth/me/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password=ADMIN_PASSWORD)


@pytest.fixture
def cashier_user():
    return User.objects.create_user(
        email="cashier@example.com",
        password=CASHIER_PASSWORD,
        first_name="Petr",
        last_name="Petrov",
        role=User.Role.CASHIER,
    )


def login(client, email, password):
    response = client.post(LOGIN_URL, {"email": email, "password": password}, format="json")
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return response


class TestAuthentication:
    def test_login_returns_tokens_and_user(self, client, cashier_user):
        response = login(client, cashier_user.email, CASHIER_PASSWORD)

        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == cashier_user.email

    def test_login_rejects_wrong_password(self, client, cashier_user):
        response = client.post(
            LOGIN_URL,
            {"email": cashier_user.email, "password": "wrong-password"},
            format="json",
        )

        assert response.status_code == 401

    def test_me_requires_authentication(self, client):
        assert client.get(ME_URL).status_code == 401

    def test_me_returns_the_current_user(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(ME_URL)

        assert response.status_code == 200
        assert response.data["email"] == cashier_user.email

    def test_logout_blacklists_the_refresh_token(self, client, cashier_user):
        tokens = login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.post(
            "/api/auth/logout/", {"refresh": tokens.data["refresh"]}, format="json"
        )

        assert response.status_code == 205


class TestUserPermissions:
    def test_listing_users_requires_authentication(self, client):
        assert client.get(USERS_URL).status_code == 401

    def test_non_admin_cannot_list_users(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        assert client.get(USERS_URL).status_code == 403


class TestUserAdministration:
    def test_admin_can_create_a_user(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        payload = {
            "email": "new.operator@example.com",
            "password": "strong-pass-123",
            "password_confirm": "strong-pass-123",
            "first_name": "Anna",
            "last_name": "Sidorova",
            "role": User.Role.OPERATOR,
            "phone": "+7-900-000-00-00",
            "is_active": True,
        }
        response = client.post(USERS_URL, payload, format="json")

        assert response.status_code == 201, response.content
        assert response.data["email"] == "new.operator@example.com"
        assert response.data["full_name"] == "Sidorova Anna"
        assert User.objects.filter(email="new.operator@example.com").exists()

    def test_create_user_rejects_mismatched_passwords(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        payload = {
            "email": "bad@example.com",
            "password": "strong-pass-123",
            "password_confirm": "another-pass-123",
            "first_name": "Bad",
            "last_name": "User",
            "role": User.Role.CASHIER,
        }
        response = client.post(USERS_URL, payload, format="json")

        assert response.status_code == 400
        assert "password_confirm" in response.data

    def test_admin_can_update_a_user(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.patch(
            f"{USERS_URL}{cashier_user.id}/",
            {"role": User.Role.MANAGER, "first_name": "Pavel"},
            format="json",
        )

        assert response.status_code == 200, response.content
        cashier_user.refresh_from_db()
        assert cashier_user.role == User.Role.MANAGER
        assert cashier_user.first_name == "Pavel"

    def test_delete_deactivates_the_user_by_default(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.delete(f"{USERS_URL}{cashier_user.id}/")

        assert response.status_code == 204
        assert User.objects.filter(id=cashier_user.id).exists()
        cashier_user.refresh_from_db()
        assert cashier_user.is_active is False

    def test_delete_permanently_when_requested(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.delete(f"{USERS_URL}{cashier_user.id}/?permanent=true")

        assert response.status_code == 204
        assert not User.objects.filter(id=cashier_user.id).exists()

    def test_admin_cannot_delete_their_own_account(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.delete(f"{USERS_URL}{admin_user.id}/")

        assert response.status_code == 400

    def test_activate_endpoint_restores_the_user(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)
        cashier_user.is_active = False
        cashier_user.save(update_fields=["is_active"])

        response = client.post(f"{USERS_URL}{cashier_user.id}/activate/")

        assert response.status_code == 200
        cashier_user.refresh_from_db()
        assert cashier_user.is_active is True

    def test_search_filters_the_list(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.get(USERS_URL, {"search": "Petrov"})

        assert response.status_code == 200
        emails = [item["email"] for item in response.data["results"]]
        assert cashier_user.email in emails


class TestPasswordChange:
    def test_user_can_change_their_password(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.post(
            "/api/auth/change-password/",
            {
                "old_password": CASHIER_PASSWORD,
                "new_password": "brand-new-pass-123",
                "new_password_confirm": "brand-new-pass-123",
            },
            format="json",
        )

        assert response.status_code == 200, response.content
        cashier_user.refresh_from_db()
        assert cashier_user.check_password("brand-new-pass-123")

    def test_wrong_current_password_is_rejected(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.post(
            "/api/auth/change-password/",
            {
                "old_password": "not-the-password",
                "new_password": "brand-new-pass-123",
                "new_password_confirm": "brand-new-pass-123",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "old_password" in response.data
