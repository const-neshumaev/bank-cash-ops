import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.core.backend.models import Branch, BranchAccess, CashDesk, Role

User = get_user_model()

pytestmark = pytest.mark.django_db

ADMIN_PASSWORD = "admin-pass-12345"
CASHIER_PASSWORD = "cashier-pass-123"

USERS_URL = "/api/users/"
ROLES_URL = "/api/roles/"
PERMISSIONS_URL = "/api/permissions/"
BRANCHES_URL = "/api/branches/"
CASH_DESKS_URL = "/api/cash-desks/"
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
    user = User.objects.create_user(
        email="cashier@example.com",
        password=CASHIER_PASSWORD,
        first_name="Petr",
        last_name="Petrov",
    )
    user.roles.add(Role.objects.get(code="cashier"))
    return user


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
        assert response.data["user"]["roles"] == ["cashier"]

    def test_login_rejects_wrong_password(self, client, cashier_user):
        response = client.post(
            LOGIN_URL,
            {"email": cashier_user.email, "password": "wrong-password"},
            format="json",
        )

        assert response.status_code == 401

    def test_me_exposes_permissions(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(ME_URL)

        assert response.status_code == 200
        assert "core.shifts.open" in response.data["permissions"]

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
            "roles": ["specialist"],
            "phone": "+7-900-000-00-00",
            "is_active": True,
        }
        response = client.post(USERS_URL, payload, format="json")

        assert response.status_code == 201, response.content
        assert response.data["email"] == "new.operator@example.com"
        assert response.data["full_name"] == "Sidorova Anna"
        assert response.data["roles"] == ["specialist"]
        assert "core.structure.view" in response.data["permissions"]

    def test_create_user_rejects_mismatched_passwords(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        payload = {
            "email": "bad@example.com",
            "password": "strong-pass-123",
            "password_confirm": "another-pass-123",
            "first_name": "Bad",
            "last_name": "User",
            "roles": ["cashier"],
        }
        response = client.post(USERS_URL, payload, format="json")

        assert response.status_code == 400
        assert "password_confirm" in response.data

    def test_admin_can_update_user_roles(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.patch(
            f"{USERS_URL}{cashier_user.id}/",
            {"roles": ["cashier", "specialist"], "first_name": "Pavel"},
            format="json",
        )

        assert response.status_code == 200, response.content
        cashier_user.refresh_from_db()
        assert sorted(cashier_user.roles.values_list("code", flat=True)) == [
            "cashier",
            "specialist",
        ]
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

    def test_search_filters_the_list(self, client, admin_user, cashier_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.get(USERS_URL, {"search": "Petrov"})

        assert response.status_code == 200
        emails = [item["email"] for item in response.data["results"]]
        assert cashier_user.email in emails


class TestRoles:
    def test_permission_catalog_is_available_to_administrators(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.get(PERMISSIONS_URL)

        assert response.status_code == 200
        codes = [item["code"] for item in response.data]
        assert "core.users.manage" in codes

    def test_cashier_cannot_read_the_permission_catalog(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        assert client.get(PERMISSIONS_URL).status_code == 403

    def test_admin_can_create_a_role(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            ROLES_URL,
            {
                "name": "Оператор кассы",
                "permissions": ["core.shifts.view", "core.shifts.open"],
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert Role.objects.filter(name="Оператор кассы").exists()

    def test_role_rejects_unknown_permission(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            ROLES_URL,
            {"name": "Bad role", "permissions": ["core.unknown.permission"]},
            format="json",
        )

        assert response.status_code == 400

    def test_system_role_cannot_be_deleted(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)
        role = Role.objects.get(code="cashier")

        response = client.delete(f"{ROLES_URL}{role.id}/")

        assert response.status_code == 400
        assert Role.objects.filter(id=role.id).exists()


class TestBranches:
    @pytest.fixture
    def head_office(self):
        return Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)

    def test_admin_can_create_a_branch(self, client, admin_user, head_office):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            BRANCHES_URL,
            {"code": "B1", "name": "Отделение 1", "parent": head_office.id},
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.data["parent"] == head_office.id

    def test_branch_without_parent_is_rejected(self, client, admin_user):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(BRANCHES_URL, {"code": "B1", "name": "Отделение"}, format="json")

        assert response.status_code == 400
        assert "parent" in response.data

    def test_branch_code_is_optional(self, client, admin_user, head_office):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            BRANCHES_URL,
            {"name": "Отделение без кода", "parent": head_office.id},
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.data["code"] is None

    def test_duplicate_branch_code_is_rejected(self, client, admin_user, head_office):
        login(client, admin_user.email, ADMIN_PASSWORD)
        Branch.objects.create(code="B1", name="Отделение 1", parent=head_office)

        response = client.post(
            BRANCHES_URL,
            {"code": "B1", "name": "Отделение два", "parent": head_office.id},
            format="json",
        )

        assert response.status_code == 400
        assert "code" in response.data

    def test_cashier_cannot_manage_branches(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        assert client.get(BRANCHES_URL).status_code == 403


class TestStructurePickers:
    @pytest.fixture
    def head_office(self):
        return Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)

    @pytest.fixture
    def branch(self, head_office):
        return Branch.objects.create(code="B1", name="Отделение 1", parent=head_office)

    def test_cashier_can_list_selectable_branches(self, client, cashier_user, branch):
        CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        BranchAccess.objects.create(user=cashier_user, branch=branch)
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(f"{BRANCHES_URL}selectable/")

        assert response.status_code == 200, response.content
        ids = [item["id"] for item in response.data["results"]]
        assert ids == [branch.id]

    def test_selectable_branches_skip_branches_without_cash_desks(
        self, client, cashier_user, branch, head_office
    ):
        BranchAccess.objects.create(user=cashier_user, branch=branch)
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(f"{BRANCHES_URL}selectable/")

        assert response.status_code == 200, response.content
        assert response.data["results"] == []

    def test_cashier_can_list_selectable_cash_desks_of_a_branch(
        self, client, cashier_user, branch, head_office
    ):
        desk = CashDesk.objects.create(branch=branch, code="C1", name="Касса 1")
        other_branch = Branch.objects.create(code="B2", name="Отделение 2", parent=head_office)
        CashDesk.objects.create(branch=other_branch, code="C2", name="Касса 2")
        BranchAccess.objects.create(user=cashier_user, branch=branch)
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(f"{CASH_DESKS_URL}selectable/", {"branch": branch.id})

        assert response.status_code == 200, response.content
        assert [item["id"] for item in response.data["results"]] == [desk.id]

    def test_selectable_cash_desks_reject_a_non_numeric_branch(self, client, cashier_user):
        login(client, cashier_user.email, CASHIER_PASSWORD)

        response = client.get(f"{CASH_DESKS_URL}selectable/", {"branch": "abc"})

        assert response.status_code == 400


class TestCashDesks:
    @pytest.fixture
    def branch(self):
        head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
        return Branch.objects.create(code="B1", name="Отделение 1", parent=head)

    def test_admin_can_create_a_cash_desk(self, client, admin_user, branch):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            CASH_DESKS_URL,
            {
                "branch": branch.id,
                "code": "C1",
                "name": "Касса 1",
                "mac_address": "aa:bb:cc:dd:ee:ff",
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.data["mac_address"] == "AA:BB:CC:DD:EE:FF"

    def test_cash_desk_code_is_optional(self, client, admin_user, branch):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            CASH_DESKS_URL,
            {"branch": branch.id, "name": "Касса без кода"},
            format="json",
        )

        assert response.status_code == 201, response.content
        assert response.data["code"] is None

    def test_invalid_mac_address_is_rejected(self, client, admin_user, branch):
        login(client, admin_user.email, ADMIN_PASSWORD)

        response = client.post(
            CASH_DESKS_URL,
            {"branch": branch.id, "code": "C1", "name": "Касса 1", "mac_address": "not-a-mac"},
            format="json",
        )

        assert response.status_code == 400
        assert "mac_address" in response.data
