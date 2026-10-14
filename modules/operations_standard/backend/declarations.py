"""Baseline catalogue of cash operation types.

Every operation is fully described by its slots and declarative posting
template, so the module declares data only — no handlers. Bank specific and
computed operations are added by extension modules, which also register a
handler through the same SPI.

Templates refer to the registers published by the engine: ``cash`` for the cash
balance and ``turnover`` for the analytical turnover.
"""

from __future__ import annotations

from modules.operations.contracts import (
    OperationKind,
    OperationTypeSpec,
    RegisterCode,
    SlotSpec,
)

#: Permission a user needs to perform the baseline operations.
PERMISSION = "operations.create"

#: Currency of the operations that are defined for the national currency only.
BASE_CURRENCY = "BYN"


def _amount_slots(currency: str = "") -> tuple[SlotSpec, ...]:
    return (SlotSpec(code="amount", name="Сумма", fixed_currency=currency),)


def _amount_template(sign: int) -> dict:
    return {
        "movements": [
            {"register": RegisterCode.CASH, "slot": "amount", "sign": sign},
            {"register": RegisterCode.TURNOVER, "slot": "amount", "sign": sign},
        ]
    }


def _exchange_slots() -> tuple[SlotSpec, ...]:
    return (
        SlotSpec(code="received", name="Принято от клиента", order=0),
        SlotSpec(code="issued", name="Выдано клиенту", order=1),
    )


def _exchange_template() -> dict:
    return {
        "movements": [
            {"register": RegisterCode.CASH, "slot": "received", "sign": 1},
            {"register": RegisterCode.CASH, "slot": "issued", "sign": -1},
            {"register": RegisterCode.TURNOVER, "slot": "received", "sign": 1},
            {"register": RegisterCode.TURNOVER, "slot": "issued", "sign": -1},
        ]
    }


def _income(code: str, name: str, *, currency: str = "", requires_client: bool = False):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.INCOME,
        slots=_amount_slots(currency),
        template=_amount_template(1),
        requires_client=requires_client,
        permission_code=PERMISSION,
    )


def _expense(code: str, name: str, *, currency: str = "", requires_client: bool = False):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXPENSE,
        slots=_amount_slots(currency),
        template=_amount_template(-1),
        requires_client=requires_client,
        permission_code=PERMISSION,
    )


def _exchange(code: str, name: str):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXCHANGE,
        slots=_exchange_slots(),
        template=_exchange_template(),
        requires_client=True,
        permission_code=PERMISSION,
    )


#: The baseline operation types declared to the operations engine.
OPERATION_TYPES: tuple[OperationTypeSpec, ...] = (
    # Income
    _income("cash_replenishment", "Подкрепление кассы"),
    _income("cash_receipt", "Приход наличных от клиента", requires_client=True),
    _income(
        "utility_payment",
        "Приём коммунальных платежей",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income(
        "loan_repayment",
        "Погашение кредита наличными",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income(
        "deposit_topup",
        "Пополнение вклада наличными",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income("fee_income", "Приём комиссии", requires_client=True),
    # Expense
    _expense("cash_disbursement", "Выдача наличных клиенту", requires_client=True),
    _expense(
        "deposit_withdrawal",
        "Снятие вклада наличными",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "loan_issuance",
        "Выдача кредита наличными",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "salary_payment",
        "Выплата заработной платы",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "pension_payment",
        "Выплата пенсии и пособий",
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense("cash_handover", "Сдача наличных в кассу банка"),
    # Exchange
    _exchange("currency_sale", "Продажа валюты клиенту"),
    _exchange("currency_purchase", "Покупка валюты у клиента"),
    _exchange("currency_conversion", "Конвертация валюты"),
    _exchange("fractional_currency_purchase", "Покупка дробной части валюты"),
)
