"""Syncing declared operation types into the operations tables."""

from decimal import Decimal

import pytest

from modules.operations.backend.models import (
    OperationPrintConfig,
    OperationType,
    SlotDef,
)
from modules.operations.backend.registry import operation_type_registry
from modules.operations.backend.sync import sync_operation_types
from modules.operations.contracts import (
    OperationKind,
    OperationTypeSpec,
    PrintBindingSpec,
    SlotSpec,
)

pytestmark = pytest.mark.django_db

CODE = "bank.sync_test"


@pytest.fixture
def declared_type():
    spec = OperationTypeSpec(
        code=CODE,
        name="Sync test",
        kind=OperationKind.INCOME,
        slots=(SlotSpec(code="amount", name="Сумма", fixed_currency="USD"),),
        template={"movements": [{"register": "cash", "slot": "amount", "sign": 1}]},
        permission_code="operations.create",
    )
    operation_type_registry.register(spec)
    yield spec
    operation_type_registry.unregister(CODE)


def test_sync_creates_the_type_and_its_slots(declared_type):
    sync_operation_types()

    operation_type = OperationType.objects.get(code=CODE)
    assert operation_type.kind == OperationKind.INCOME
    assert operation_type.template == declared_type.template
    slot = operation_type.slots.get(code="amount")
    assert slot.fixed_currency == "USD"


def test_sync_is_idempotent(declared_type):
    sync_operation_types()
    sync_operation_types()

    assert OperationType.objects.filter(code=CODE).count() == 1
    assert SlotDef.objects.filter(operation_type__code=CODE).count() == 1


def test_sync_seeds_the_declared_print_binding_only_on_creation():
    spec = OperationTypeSpec(
        code=CODE,
        name="Sync print test",
        kind=OperationKind.EXCHANGE,
        slots=(
            SlotSpec(code="received", name="Принято", currency_policy="foreign"),
            SlotSpec(
                code="issued",
                name="Выдано",
                currency_policy="base",
                amount_mode="computed",
                computation="multiply",
                order=1,
            ),
        ),
        template={"movements": [{"register": "cash", "slot": "received", "sign": 1}]},
        print_configs=(
            PrintBindingSpec(
                document_type="cash_receipt",
                template="cash_receipt_currency_purchase",
            ),
        ),
    )
    operation_type_registry.register(spec)
    try:
        sync_operation_types()
        assert OperationPrintConfig.objects.filter(
            operation_type__code=CODE, template_code="cash_receipt_currency_purchase"
        ).exists()

        OperationPrintConfig.objects.filter(operation_type__code=CODE).delete()
        sync_operation_types()

        assert not OperationPrintConfig.objects.filter(operation_type__code=CODE).exists()
    finally:
        operation_type_registry.unregister(CODE)


def test_sync_does_not_overwrite_administrator_settings(declared_type):
    sync_operation_types()
    operation_type = OperationType.objects.get(code=CODE)
    operation_type.client_data_policy = "threshold"
    operation_type.threshold_type = "currency"
    operation_type.threshold_value = Decimal("1000")
    operation_type.threshold_currency = "BYN"
    operation_type.is_active = False
    operation_type.save()

    sync_operation_types()

    operation_type.refresh_from_db()
    assert operation_type.client_data_policy == "threshold"
    assert operation_type.threshold_type == "currency"
    assert operation_type.threshold_value == Decimal("1000")
    assert operation_type.threshold_currency == "BYN"
    assert operation_type.is_active is False
