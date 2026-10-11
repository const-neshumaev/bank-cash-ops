import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_create_user_hashes_the_password():
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")

    assert user.email == "cashier@example.com"
    assert user.password != "secret-pass-123"
    assert user.check_password("secret-pass-123")
    assert user.role == User.Role.CASHIER
    assert user.is_active is True
    assert user.is_admin is False


def test_create_superuser_is_an_administrator():
    user = User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")

    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.role == User.Role.ADMIN
    assert user.is_admin is True


def test_full_name_combines_available_parts():
    user = User.objects.create_user(
        email="ivanov@example.com",
        password="secret-pass-123",
        first_name="Ivan",
        last_name="Ivanov",
        middle_name="Ivanovich",
    )

    assert user.full_name == "Ivanov Ivan Ivanovich"


def test_email_must_be_unique():
    User.objects.create_user(email="dup@example.com", password="secret-pass-123")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="secret-pass-456")
