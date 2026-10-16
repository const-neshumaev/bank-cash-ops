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


def _en(name: str) -> dict[str, str]:
    """Return a translations mapping holding only the English name."""
    return {"en": name}


def _amount_slots(currency: str = "") -> tuple[SlotSpec, ...]:
    return (
        SlotSpec(
            code="amount",
            name="Сумма",
            fixed_currency=currency,
            translations=_en("Amount"),
        ),
    )


def _amount_template(sign: int) -> dict:
    return {
        "movements": [
            {"register": RegisterCode.CASH, "slot": "amount", "sign": sign},
            {"register": RegisterCode.TURNOVER, "slot": "amount", "sign": sign},
        ]
    }


def _exchange_slots() -> tuple[SlotSpec, ...]:
    return (
        SlotSpec(
            code="received",
            name="Принято от клиента",
            order=0,
            translations=_en("Received from client"),
        ),
        SlotSpec(
            code="issued",
            name="Выдано клиенту",
            order=1,
            translations=_en("Issued to client"),
        ),
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


def _income(
    code: str,
    name: str,
    *,
    translations: dict[str, str],
    currency: str = "",
    requires_client: bool = False,
):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.INCOME,
        slots=_amount_slots(currency),
        template=_amount_template(1),
        requires_client=requires_client,
        permission_code=PERMISSION,
        translations=translations,
    )


def _expense(
    code: str,
    name: str,
    *,
    translations: dict[str, str],
    currency: str = "",
    requires_client: bool = False,
):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXPENSE,
        slots=_amount_slots(currency),
        template=_amount_template(-1),
        requires_client=requires_client,
        permission_code=PERMISSION,
        translations=translations,
    )


def _exchange(code: str, name: str, *, translations: dict[str, str]):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXCHANGE,
        slots=_exchange_slots(),
        template=_exchange_template(),
        requires_client=True,
        permission_code=PERMISSION,
        translations=translations,
    )


#: The baseline operation types declared to the operations engine.
OPERATION_TYPES: tuple[OperationTypeSpec, ...] = (
    # Income
    _income(
        "cash_replenishment",
        "Подкрепление кассы",
        translations=_en("Cash desk replenishment"),
    ),
    _income(
        "cash_receipt",
        "Приход наличных от клиента",
        translations=_en("Cash receipt from client"),
        requires_client=True,
    ),
    _income(
        "utility_payment",
        "Приём коммунальных платежей",
        translations=_en("Utility payments acceptance"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income(
        "loan_repayment",
        "Погашение кредита наличными",
        translations=_en("Loan repayment in cash"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income(
        "deposit_topup",
        "Пополнение вклада наличными",
        translations=_en("Deposit top-up in cash"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _income(
        "fee_income",
        "Приём комиссии",
        translations=_en("Fee collection"),
        requires_client=True,
    ),
    # Expense
    _expense(
        "cash_disbursement",
        "Выдача наличных клиенту",
        translations=_en("Cash disbursement to client"),
        requires_client=True,
    ),
    _expense(
        "deposit_withdrawal",
        "Снятие вклада наличными",
        translations=_en("Deposit withdrawal in cash"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "loan_issuance",
        "Выдача кредита наличными",
        translations=_en("Loan issuance in cash"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "salary_payment",
        "Выплата заработной платы",
        translations=_en("Salary payment"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "pension_payment",
        "Выплата пенсии и пособий",
        translations=_en("Pension and benefit payment"),
        currency=BASE_CURRENCY,
        requires_client=True,
    ),
    _expense(
        "cash_handover",
        "Сдача наличных в кассу банка",
        translations=_en("Cash handover to the bank"),
    ),
    # Exchange
    _exchange(
        "currency_sale",
        "Продажа валюты клиенту",
        translations=_en("Currency sale to client"),
    ),
    _exchange(
        "currency_purchase",
        "Покупка валюты у клиента",
        translations=_en("Currency purchase from client"),
    ),
    _exchange(
        "currency_conversion",
        "Конвертация валюты",
        translations=_en("Currency conversion"),
    ),
    _exchange(
        "fractional_currency_purchase",
        "Покупка дробной части валюты",
        translations=_en("Fractional currency purchase"),
    ),
)
