"""Branch-scoped access rules for the ``core`` module.

Covers the :class:`BranchAccess` model, the ``scoping`` helpers and the way the
API applies the scope to branches, cash desks, shifts and user administration.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from modules.core.backend import scoping
from modules.core.backend.models import Branch, BranchAccess, CashDesk, Role, Shift

User = get_user_model()

pytestmark = pytest.mark.django_db

ADMIN_PASSWORD = "admin-pass-12345"
PASSWORD = "user-pass-12345"

BRANCHES_URL = "/api/branches/"
CASH_DESKS_URL = "/api/cash-desks/"
SHIFTS_URL = "/api/shifts/"
USERS_URL = "/api/users/"
LOGIN_URL = "/api/auth/login/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def head_office():
    return Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)


@pytest.fixture
def branch(head_office):
    return Branch.objects.create(code="B1", name="Отделение 1", parent=head_office)


@pytest.fixture
def child_branch(branch):
    return Branch.objects.create(code="B1-1", name="Подотделение", parent=branch)


@pytest.fixture
def other_branch(head_office):
    return Branch.objects.create(code="B2", name="Отделение 2", parent=head_office)


def make_user(email, *role_codes):
    user = User.objects.create_user(email=email, password=PASSWORD)
    if role_codes:
        user.roles.set(Role.objects.filter(code__in=role_codes))
    return user


def grant(user, branch, include_descendants=False):
    return BranchAccess.objects.create(
        user=user, branch=branch, include_descendants=include_descendants
    )


def login(client, email, password=PASSWORD):
    response = client.post(LOGIN_URL, {"email": email, "password": password}, format="json")
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return response


class TestBranchAccessModel:
    def test_access_is_unique_per_user_and_branch(self, branch):
        user = make_user("u@example.com")
        grant(user, branch)

        with pytest.raises(IntegrityError), transaction.atomic():
            grant(user, branch)


class TestAccessibleBranchIds:
    def test_superuser_sees_every_branch(self):
        admin = User.objects.create_superuser(email="admin@example.com", password=ADMIN_PASSWORD)

        assert scoping.accessible_branch_ids(admin) is None

    def test_no_records_means_no_access(self, branch):
        user = make_user("u@example.com")

        assert scoping.accessible_branch_ids(user) == set()

    def test_direct_access(self, branch, other_branch):
        user = make_user("u@example.com")
        grant(user, branch)

        assert scoping.accessible_branch_ids(user) == {branch.id}

    def test_descendants_are_included(self, branch, child_branch, other_branch):
        user = make_user("u@example.com")
        grant(user, branch, include_descendants=True)

        assert scoping.accessible_branch_ids(user) == {branch.id, child_branch.id}

    def test_records_are_merged(self, branch, child_branch, other_branch):
        user = make_user("u@example.com")
        grant(user, branch, include_descendants=True)
        grant(user, other_branch)

        assert scoping.accessible_branch_ids(user) == {
            branch.id,
            child_branch.id,
            other_branch.id,
        }

    def test_inactive_branch_stays_visible(self, branch):
        user = make_user("u@example.com")
        grant(user, branch)
        branch.is_active = False
        branch.save(update_fields=["is_active"])

        assert scoping.accessible_branch_ids(user) == {branch.id}

    def test_can_access_branch(self, branch, other_branch):
        user = make_user("u@example.com")
        grant(user, branch)

        assert scoping.can_access_branch(user, branch) is True
        assert scoping.can_access_branch(user, other_branch) is False


class TestUserBranchAccessAPI:
    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(email="admin@example.com", password=ADMIN_PASSWORD)

    def test_admin_creates_a_user_with_branch_access(self, client, admin_user, branch):
        login(client, admin_user.email, ADMIN_PASSWORD)

        payload = {
            "email": "operator@example.com",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "first_name": "Anna",
            "last_name": "Sidorova",
            "branch_access": [{"branch": branch.id, "include_descendants": True}],
        }
        response = client.post(USERS_URL, payload, format="json")

        assert response.status_code == 201, response.content
        assert response.data["branch_access"] == [
            {"branch": branch.id, "include_descendants": True}
        ]

    def test_admin_replaces_branch_access_on_update(
        self, client, admin_user, branch, other_branch
    ):
        target = make_user("operator@example.com")
        grant(target, branch)
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.patch(
            f"{USERS_URL}{target.id}/",
            {"branch_access": [{"branch": other_branch.id, "include_descendants": False}]},
            format="json",
        )

        assert response.status_code == 200, response.content
        assert [entry["branch"] for entry in response.data["branch_access"]] == [other_branch.id]

    def test_omitting_branch_access_keeps_it_untouched(self, client, admin_user, branch):
        target = make_user("operator@example.com")
        grant(target, branch)
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.patch(
            f"{USERS_URL}{target.id}/", {"first_name": "Pavel"}, format="json"
        )

        assert response.status_code == 200, response.content
        assert [entry["branch"] for entry in response.data["branch_access"]] == [branch.id]


class TestBranchScopingAPI:
    @pytest.fixture
    def manager_user(self, branch):
        user = make_user("manager@example.com", "branch_manager")
        grant(user, branch, include_descendants=True)
        return user

    def test_branch_list_is_scoped(self, client, manager_user, branch, other_branch):
        login(client, manager_user.email)

        response = client.get(BRANCHES_URL)

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [branch.id]

    def test_cash_desk_list_is_scoped(self, client, manager_user, branch, other_branch):
        own = CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        CashDesk.objects.create(branch=other_branch, code="C2", name="Касса 2")
        login(client, manager_user.email)

        response = client.get(CASH_DESKS_URL)

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [own.id]

    def test_shift_list_is_scoped(self, client, manager_user, branch, other_branch):
        first = make_user("first@example.com")
        second = make_user("second@example.com")
        own_desk = CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        other_desk = CashDesk.objects.create(branch=other_branch, code="C2", name="Касса 2")
        own = Shift.objects.create(cash_desk=own_desk, cashier=first)
        Shift.objects.create(cash_desk=other_desk, cashier=second)
        login(client, manager_user.email)

        response = client.get(SHIFTS_URL)

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [own.id]

    def test_selectable_branches_are_scoped(self, client, manager_user, branch, other_branch):
        CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        CashDesk.objects.create(branch=other_branch, code="C2", name="Касса 2")
        login(client, manager_user.email)

        response = client.get(f"{BRANCHES_URL}selectable/")

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [branch.id]

    def test_open_shift_rejects_an_inaccessible_branch(self, client, branch, other_branch):
        cashier = make_user("cashier@example.com", "cashier")
        grant(cashier, branch)
        other_desk = CashDesk.objects.create(branch=other_branch, code="C2", name="Касса 2")
        login(client, cashier.email)

        response = client.post(SHIFTS_URL, {"cash_desk": other_desk.id}, format="json")

        assert response.status_code == 400
        assert "cash_desk" in response.data

    def test_inactive_branch_stays_readable_but_cannot_host_a_shift(
        self, client, branch
    ):
        cashier = make_user("cashier@example.com", "cashier")
        grant(cashier, branch)
        desk = CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        existing = Shift.objects.create(cash_desk=desk, cashier=cashier)
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        login(client, cashier.email)

        listing = client.get(SHIFTS_URL)
        opening = client.post(SHIFTS_URL, {"cash_desk": desk.id}, format="json")

        assert listing.status_code == 200, listing.content
        assert [item["id"] for item in listing.data["results"]] == [existing.id]
        assert opening.status_code == 400

    def test_users_list_is_not_scoped(self, client, branch, other_branch):
        admin = make_user("admin@example.com", "administrator")
        grant(admin, branch)
        other = make_user("other@example.com", "cashier")
        grant(other, other_branch)
        login(client, admin.email)

        response = client.get(USERS_URL)

        assert response.status_code == 200, response.content
        emails = {item["email"] for item in response.data["results"]}
        assert {"admin@example.com", "other@example.com"} <= emails


class TestBranchCatalog:
    def test_catalog_lists_every_branch_for_user_managers(
        self, client, branch, other_branch
    ):
        admin = make_user("admin@example.com", "administrator")
        login(client, admin.email)

        response = client.get(f"{BRANCHES_URL}catalog/")

        assert response.status_code == 200, response.content
        ids = {item["id"] for item in response.data["results"]}
        assert {branch.id, other_branch.id} <= ids

    def test_catalog_requires_users_manage(self, client):
        cashier = make_user("cashier@example.com", "cashier")
        login(client, cashier.email)

        assert client.get(f"{BRANCHES_URL}catalog/").status_code == 403
