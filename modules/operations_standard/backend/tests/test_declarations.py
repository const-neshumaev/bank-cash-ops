"""The baseline catalogue is declared and well formed.

The tests only touch the published ``operations`` contract (never its internals,
per the module boundary rules in ``docs/modules.md``). Posting behaviour is
covered by the ``operations`` engine tests.
"""

from modules.common.contracts import registry as contract_registry
from modules.operations.contracts import (
    OPERATION_TYPES_REGISTRY,
    OperationKind,
    RegisterCode,
)
from modules.operations_standard.backend.declarations import OPERATION_TYPES

KNOWN_REGISTERS = {RegisterCode.CASH, RegisterCode.TURNOVER}


def _registry():
    return contract_registry.get(OPERATION_TYPES_REGISTRY)


def test_the_baseline_types_are_registered_at_startup():
    assert {spec.code for spec in OPERATION_TYPES} <= {spec.code for spec in _registry().types()}


def test_codes_are_unique():
    codes = [spec.code for spec in OPERATION_TYPES]

    assert len(codes) == len(set(codes))


def test_templates_reference_declared_slots_and_known_registers():
    for spec in OPERATION_TYPES:
        slot_codes = {slot.code for slot in spec.slots}
        movements = spec.template["movements"]

        assert movements, f"{spec.code} has no movements"
        for movement in movements:
            assert movement["register"] in KNOWN_REGISTERS
            assert movement["slot"] in slot_codes
            assert movement["sign"] in (1, -1)


def test_income_increases_and_expense_decreases_cash():
    for spec in OPERATION_TYPES:
        cash_signs = {
            movement["sign"]
            for movement in spec.template["movements"]
            if movement["register"] == RegisterCode.CASH
        }
        if spec.kind == OperationKind.INCOME:
            assert cash_signs == {1}, spec.code
        elif spec.kind == OperationKind.EXPENSE:
            assert cash_signs == {-1}, spec.code


def test_exchange_operations_declare_their_cash_receipt_templates():
    expected = {
        "currency_purchase": "cash_receipt_currency_purchase",
        "currency_sale": "cash_receipt_currency_sale",
        "currency_conversion": "cash_receipt_currency_conversion",
    }
    by_code = {spec.code: spec for spec in OPERATION_TYPES}

    for operation_code, template_code in expected.items():
        configs = by_code[operation_code].print_configs
        assert len(configs) == 1
        assert configs[0].document_type == "cash_receipt"
        assert configs[0].template == template_code


def test_exchange_moves_cash_in_two_directions():
    for spec in OPERATION_TYPES:
        if spec.kind != OperationKind.EXCHANGE:
            continue
        cash_signs = {
            movement["sign"]
            for movement in spec.template["movements"]
            if movement["register"] == RegisterCode.CASH
        }

        assert cash_signs == {1, -1}, spec.code
