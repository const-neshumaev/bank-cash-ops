from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient

from modules.core.backend import shifts
from modules.core.backend.models import Branch, CashDesk, Role, Shift

User = get_user_model()

pytestmark = pytest.mark.django_db

CASHIER_PASSWORD = "cashier-pass-123"
ADMIN_PASSWORD = "admin-pass-12345"

SHIFTS_URL = "/api/shifts/"
LOGIN_URL = "/api/auth/login/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def branch():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    return Branch.objects.create(code="B1", name="Отделение 1", parent=head)


@pytest.fixture
def cash_desk(branch):
    return CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")


@pytest.fixture
def other_cash_desk(branch):
    return CashDesk.objects.create(branch=branch, code="C2", name="Касса 2")


@pytest.fixture
def other_branch_cash_desk(branch):
    other_branch = Branch.objects.create(code="B2", name="Отделение 2", parent=branch.parent)
    return CashDesk.objects.create(branch=other_branch, code="C3", name="Касса 3")


@pytest.fixture
def cashier_user():
    user = User.objects.create_user(email="cashier@example.com", password=CASHIER_PASSWORD)
    user.roles.add(Role.objects.get(code="cashier"))
    return user


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password=ADMIN_PASSWORD)


def login(client, email, password):
    response = client.post(LOGIN_URL, {"email": email, "password": password}, format="json")
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return response


class TestShiftService:
    def test_open_shift_binds_the_cash_desk(self, cashier_user, cash_desk):
        shift = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)

        assert shift.status == Shift.Status.OPEN
        assert shift.cashier == cashier_user
        assert shift.cash_desk == cash_desk

    def test_cashier_cannot_open_two_shifts(self, cashier_user, cash_desk, other_cash_desk):
        shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)

        with pytest.raises(DRFValidationError):
            shifts.open_shift(cashier=cashier_user, cash_desk=other_cash_desk)

    def test_cash_desk_cannot_host_two_shifts(self, cashier_user, cash_desk):
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)

        with pytest.raises(DRFValidationError):
            shifts.open_shift(cashier=other, cash_desk=cash_desk)

    def test_close_shift_records_who_closed_it(self, cashier_user, cash_desk):
        shift = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)

        closed = shifts.close_shift(shift=shift, closed_by=cashier_user)

        assert closed.status == Shift.Status.CLOSED
        assert closed.closed_at is not None
        assert closed.closed_by == cashier_user

    def test_closing_a_closed_shift_is_rejected(self, cashier_user, cash_desk):
        shift = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        shifts.close_shift(shift=shift, closed_by=cashier_user)

        with pytest.raises(DRFValidationError):
            shifts.close_shift(shift=shift, closed_by=cashier_user)

    def test_inactive_cash_desk_cannot_be_opened(self, cashier_user, cash_desk):
        cash_desk.is_active = False
        cash_desk.save(update_fields=["is_active"])

        with pytest.raises(DRFValidationError):
            shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)


class TestShiftAPI:
    def test_cashier_opens_a_shift(self, client, cashier_user, cash_desk):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.post(SHIFTS_URL, {"cash_desk": cash_desk.id}, format="json")

        assert response.status_code == 201, response.content
        assert response.data["cash_desk"] == cash_desk.id
        assert response.data["cashier"] == cashier_user.id

    def test_current_returns_the_open_shift(self, client, cashier_user, cash_desk):
        login(client, cashier_user.email, CASHIER_PASSWORD)
        client.post(SHIFTS_URL, {"cash_desk": cash_desk.id}, format="json")

        response = client.get(f"{SHIFTS_URL}current/")

        assert response.status_code == 200
        assert response.data["cash_desk"] == cash_desk.id

    def test_current_is_null_without_a_shift(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(f"{SHIFTS_URL}current/")

        assert response.status_code == 200
        assert response.data is None

    def test_cashier_closes_their_own_shift(self, client, cashier_user, cash_desk):
        login(client, cashier_user.email, CASHIER_PASSWORD)
        shift_id = client.post(SHIFTS_URL, {"cash_desk": cash_desk.id}, format="json").data["id"]

        response = client.post(f"{SHIFTS_URL}{shift_id}/close/")

        assert response.status_code == 200, response.content
        assert response.data["status"] == "closed"

    def test_cashier_cannot_close_someone_elses_shift(self, client, cashier_user, cash_desk):
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        other.roles.add(Role.objects.get(code="cashier"))
        shift = shifts.open_shift(cashier=other, cash_desk=cash_desk)

        login(client, cashier_user.email, CASHIER_PASSWORD)
        response = client.post(f"{SHIFTS_URL}{shift.id}/close/")

        assert response.status_code == 403

    def test_admin_force_closes_a_shift(self, client, admin_user, cashier_user, cash_desk):
        shift = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(f"{SHIFTS_URL}{shift.id}/force-close/")

        assert response.status_code == 200, response.content
        shift.refresh_from_db()
        assert shift.status == Shift.Status.CLOSED
        assert shift.closed_by == admin_user


class TestShiftVisibility:
    def test_cashier_sees_only_their_own_shifts(
        self, client, cashier_user, cash_desk, other_cash_desk
    ):
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        own = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        shifts.open_shift(cashier=other, cash_desk=other_cash_desk)

        login(client, cashier_user.email, CASHIER_PASSWORD)
        response = client.get(SHIFTS_URL)

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [own.id]

    def test_admin_sees_every_shift(
        self, client, admin_user, cashier_user, cash_desk, other_cash_desk
    ):
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        shifts.open_shift(cashier=other, cash_desk=other_cash_desk)

        login(client, admin_user.email, ADMIN_PASSWORD)
        response = client.get(SHIFTS_URL)

        assert response.status_code == 200, response.content
        assert response.data["count"] == 2

    def test_cashier_cannot_retrieve_someone_elses_shift(
        self, client, cashier_user, other_cash_desk
    ):
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        stranger_shift = shifts.open_shift(cashier=other, cash_desk=other_cash_desk)

        login(client, cashier_user.email, CASHIER_PASSWORD)
        response = client.get(f"{SHIFTS_URL}{stranger_shift.id}/")

        assert response.status_code == 404


class TestShiftFilters:
    def test_filter_by_branch(
        self, client, admin_user, cashier_user, cash_desk, other_branch_cash_desk
    ):
        shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        other = User.objects.create_user(email="other@example.com", password=CASHIER_PASSWORD)
        shift = shifts.open_shift(cashier=other, cash_desk=other_branch_cash_desk)

        login(client, admin_user.email, ADMIN_PASSWORD)
        response = client.get(SHIFTS_URL, {"branch": other_branch_cash_desk.branch_id})

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [shift.id]

    def test_filter_by_cash_desk(
        self, client, admin_user, cashier_user, cash_desk, other_cash_desk
    ):
        shift = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        shifts.close_shift(shift=shift, closed_by=cashier_user)
        shifts.open_shift(cashier=cashier_user, cash_desk=other_cash_desk)

        login(client, admin_user.email, ADMIN_PASSWORD)
        response = client.get(SHIFTS_URL, {"cash_desk": cash_desk.id})

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [shift.id]

    def test_filter_by_opening_period(self, client, admin_user, cashier_user, cash_desk):
        old = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        Shift.objects.filter(pk=old.pk).update(opened_at=timezone.now() - timedelta(days=10))
        shifts.close_shift(shift=old, closed_by=cashier_user)

        recent = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)

        login(client, admin_user.email, ADMIN_PASSWORD)
        cutoff = (timezone.now() - timedelta(days=5)).isoformat()

        response = client.get(SHIFTS_URL, {"opened_from": cutoff})

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [recent.id]

    def test_filter_by_branch_and_status(
        self, client, admin_user, cashier_user, cash_desk, other_branch_cash_desk
    ):
        first = shifts.open_shift(cashier=cashier_user, cash_desk=cash_desk)
        shifts.close_shift(shift=first, closed_by=cashier_user)

        login(client, admin_user.email, ADMIN_PASSWORD)
        response = client.get(
            SHIFTS_URL,
            {"branch": cash_desk.branch_id, "status": "open"},
        )

        assert response.status_code == 200, response.content
        assert response.data["results"] == []
