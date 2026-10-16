"""Bank-wide language settings and the per-user language choice."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from modules.core.backend.models import BankSettings

User = get_user_model()

pytestmark = pytest.mark.django_db

SETTINGS_URL = "/api/settings/"
ME_URL = "/api/auth/me/"
LOGIN_URL = "/api/auth/login/"

PASSWORD = "user-pass-12345"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(email="user@example.com", password=PASSWORD)


def authenticate(client, user):
    response = client.post(LOGIN_URL, {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class TestBankSettings:
    def test_load_creates_singleton_from_defaults(self):
        settings_obj = BankSettings.load()

        assert settings_obj.pk == 1
        assert settings_obj.default_language == "ru"
        assert settings_obj.enabled_languages == ["ru", "en"]

        # A second call returns the same row, never a duplicate.
        assert BankSettings.load().pk == 1
        assert BankSettings.objects.count() == 1

    def test_settings_endpoint_is_public(self, client):
        response = client.get(SETTINGS_URL)

        assert response.status_code == 200
        assert response.data["default_language"] == "ru"
        assert response.data["enabled_languages"] == ["ru", "en"]

    def test_clean_rejects_unsupported_language(self):
        settings_obj = BankSettings(default_language="ru", enabled_languages=["ru", "de"])

        with pytest.raises(ValidationError):
            settings_obj.clean()

    def test_clean_rejects_default_not_enabled(self):
        settings_obj = BankSettings(default_language="en", enabled_languages=["ru"])

        with pytest.raises(ValidationError):
            settings_obj.clean()


class TestUserLanguage:
    def test_me_exposes_language(self, client, user):
        authenticate(client, user)

        response = client.get(ME_URL)

        assert response.status_code == 200
        assert response.data["language"] == ""

    def test_user_can_change_own_language(self, client, user):
        authenticate(client, user)

        response = client.patch(ME_URL, {"language": "en"}, format="json")

        assert response.status_code == 200, response.content
        user.refresh_from_db()
        assert user.language == "en"

    def test_user_cannot_set_unsupported_language(self, client, user):
        authenticate(client, user)

        response = client.patch(ME_URL, {"language": "de"}, format="json")

        assert response.status_code == 400
        assert "language" in response.data
        user.refresh_from_db()
        assert user.language == ""
