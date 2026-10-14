"""Syncing declared operation types into the operations tables."""

import pytest

from modules.operations.backend.models import OperationType, SlotDef
from modules.operations.backend.registry import operation_type_registry
from modules.operations.backend.sync import sync_operation_types
from modules.operations.contracts import OperationKind, OperationTypeSpec, SlotSpec

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
