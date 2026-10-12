import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from modules.core.backend.models import Branch, CashDesk, Role
from modules.core.backend.permission_codes import PermissionCode

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def cashier_role():
    return Role.objects.get(code="cashier")


@pytest.fixture
def branch():
    head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
    return Branch.objects.create(code="B1", name="Отделение 1", parent=head)


def test_create_user_hashes_the_password():
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")

    assert user.email == "cashier@example.com"
    assert user.password != "secret-pass-123"
    assert user.check_password("secret-pass-123")
    assert user.is_active is True
    assert user.is_admin is False
    assert user.roles.count() == 0


def test_create_superuser_is_an_administrator():
    user = User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")

    assert user.is_superuser is True
    assert user.is_staff is True
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

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email="dup@example.com", password="secret-pass-456")


def test_role_grants_its_permissions(cashier_role):
    user = User.objects.create_user(email="cashier@example.com", password="secret-pass-123")
    user.roles.add(cashier_role)

    assert user.has_permission(PermissionCode.SHIFTS_OPEN) is True
    assert user.has_permission(PermissionCode.USERS_MANAGE) is False


def test_permissions_of_several_roles_are_merged():
    user = User.objects.create_user(email="multi@example.com", password="secret-pass-123")
    user.roles.add(Role.objects.get(code="cashier"), Role.objects.get(code="specialist"))

    assert user.has_permission(PermissionCode.SHIFTS_OPEN) is True
    assert user.has_permission(PermissionCode.STRUCTURE_VIEW) is True


def test_administrator_role_is_an_admin():
    user = User.objects.create_user(email="admin@example.com", password="secret-pass-123")
    user.roles.add(Role.objects.get(code="administrator"))

    assert user.has_permission(PermissionCode.ROLES_MANAGE) is True
    assert user.is_admin is True


class TestBranchHierarchy:
    def test_head_office_cannot_have_a_parent(self):
        head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
        child = Branch.objects.create(code="B1", name="Отделение 1", parent=head)

        head.parent = child
        with pytest.raises(ValidationError):
            head.save()

    def test_non_head_office_requires_a_parent(self):
        with pytest.raises(ValidationError):
            Branch.objects.create(code="ORPHAN", name="Без родителя")

    def test_branch_cannot_be_its_own_ancestor(self):
        head = Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)
        a = Branch.objects.create(code="A", name="A", parent=head)
        b = Branch.objects.create(code="B", name="B", parent=a)

        b.parent = b
        with pytest.raises(ValidationError):
            b.save()

    def test_only_one_head_office_is_allowed(self):
        Branch.objects.create(code="HQ", name="Головной офис", is_head_office=True)

        with pytest.raises(IntegrityError), transaction.atomic():
            Branch.objects.create(code="HQ2", name="Второй офис", is_head_office=True)


class TestCashDesk:
    def test_mac_address_is_upper_cased(self, branch):
        desk = CashDesk.objects.create(
            branch=branch,
            code="C1",
            name="Касса 1",
            mac_address="aa:bb:cc:dd:ee:ff",
        )

        assert desk.mac_address == "AA:BB:CC:DD:EE:FF"

    def test_mac_address_is_unique(self, branch):
        CashDesk.objects.create(
            branch=branch, code="C1", name="Касса 1", mac_address="AA:BB:CC:DD:EE:FF"
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CashDesk.objects.create(
                branch=branch, code="C2", name="Касса 2", mac_address="AA:BB:CC:DD:EE:FF"
            )
