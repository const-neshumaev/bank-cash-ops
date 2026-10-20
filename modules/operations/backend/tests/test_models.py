"""Client-data policy and threshold configuration of operation types."""

from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from modules.operations.backend.admin import OperationTypeAdmin
from modules.operations.backend.models import OperationType
from modules.operations.backend.thresholds import ClientDataPolicy, ThresholdTypeCode
from modules.operations.contracts import OperationKind

pytestmark = pytest.mark.django_db

User = get_user_model()


def _operation_type(**kwargs):
    return OperationType.objects.create(
        code="cash_receipt",
        name="Приход наличных",
        kind=OperationKind.INCOME,
        **kwargs,
    )


def test_a_type_without_a_threshold_does_not_require_client_data():
    operation_type = _operation_type(client_data_policy=ClientDataPolicy.NEVER)

    assert operation_type.requires_client is False


def test_an_always_policy_requires_client_data():
    operation_type = _operation_type(client_data_policy=ClientDataPolicy.ALWAYS)

    assert operation_type.requires_client is True


def test_a_threshold_policy_requires_a_type_and_a_value():
    operation_type = _operation_type(
        client_data_policy=ClientDataPolicy.THRESHOLD,
        threshold_type=ThresholdTypeCode.CURRENCY,
        threshold_value=Decimal("1000"),
        threshold_currency="BYN",
    )

    operation_type.clean()


@pytest.mark.parametrize(
    "threshold_type,threshold_value,threshold_currency,field",
    [
        ("", Decimal("100"), "", "threshold_type"),
        (ThresholdTypeCode.CURRENCY, None, "BYN", "threshold_value"),
        (ThresholdTypeCode.CURRENCY, Decimal("100"), "", "threshold_currency"),
        (ThresholdTypeCode.BASE_VALUE, Decimal("100"), "BYN", "threshold_currency"),
    ],
)
def test_an_invalid_threshold_configuration_is_rejected(
    threshold_type, threshold_value, threshold_currency, field
):
    operation_type = _operation_type(
        client_data_policy=ClientDataPolicy.THRESHOLD,
        threshold_type=threshold_type,
        threshold_value=threshold_value,
        threshold_currency=threshold_currency,
    )

    with pytest.raises(ValidationError) as exc_info:
        operation_type.clean()

    assert field in exc_info.value.message_dict


def test_admin_changes_are_recorded_in_history():
    admin_user = User.objects.create_superuser(
        email="admin@example.com", password="secret-pass-123"
    )
    operation_type = _operation_type(client_data_policy=ClientDataPolicy.NEVER)
    request = RequestFactory().post("/admin/operations/operationtype/")
    request.user = admin_user
    model_admin = OperationTypeAdmin(OperationType, AdminSite())

    operation_type.client_data_policy = ClientDataPolicy.THRESHOLD
    operation_type.threshold_type = ThresholdTypeCode.BASE_VALUE
    operation_type.threshold_value = Decimal("100")
    model_admin.save_model(request, operation_type, None, change=True)

    change = operation_type.settings_changes.get()
    assert change.changed_by_email == "admin@example.com"
    assert change.changes["client_data_policy"] == {"before": "never", "after": "threshold"}
    assert change.changes["threshold_value"] == {"before": None, "after": "100.00"}
