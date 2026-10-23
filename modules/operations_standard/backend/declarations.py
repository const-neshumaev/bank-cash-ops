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
    OperationForm,
    OperationKind,
    OperationRatePrinciple,
    OperationTypeSpec,
    PrintBindingSpec,
    RegisterCode,
    SlotAmountMode,
    SlotComputation,
    SlotCurrencyPolicy,
    SlotSpec,
)

#: Permission a user needs to perform the baseline operations.
PERMISSION = "operations.create"

#: Currency of the operations that are defined for the national currency only.
BASE_CURRENCY = "BYN"


def _en(name: str) -> dict[str, str]:
    """Return a translations mapping holding only the English name."""
    return {"en": name}


def _amount_slots(currency: str = "", *, multiple: bool = False) -> tuple[SlotSpec, ...]:
    return (
        SlotSpec(
            code="amount",
            name="Сумма",
            fixed_currency=currency,
            multiple=multiple,
            threshold_basis=True,
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


def _purchase_slots() -> tuple[SlotSpec, ...]:
    """The bank buys foreign cash and pays the national currency."""
    return (
        SlotSpec(
            code="received",
            name="Принято от клиента",
            order=0,
            currency_policy=SlotCurrencyPolicy.FOREIGN,
            stores_rate=True,
            threshold_basis=True,
            translations=_en("Received from client"),
        ),
        SlotSpec(
            code="issued",
            name="Выдано клиенту",
            order=1,
            currency_policy=SlotCurrencyPolicy.BASE,
            amount_mode=SlotAmountMode.COMPUTED,
            computation=SlotComputation.MULTIPLY,
            translations=_en("Issued to client"),
        ),
    )


def _sale_slots() -> tuple[SlotSpec, ...]:
    """The bank sells foreign cash for the national currency."""
    return (
        SlotSpec(
            code="received",
            name="Принято от клиента",
            order=0,
            currency_policy=SlotCurrencyPolicy.BASE,
            threshold_basis=True,
            translations=_en("Received from client"),
        ),
        SlotSpec(
            code="issued",
            name="Выдано клиенту",
            order=1,
            currency_policy=SlotCurrencyPolicy.FOREIGN,
            amount_mode=SlotAmountMode.COMPUTED,
            computation=SlotComputation.DIVIDE,
            stores_rate=True,
            translations=_en("Issued to client"),
        ),
    )


def _conversion_slots() -> tuple[SlotSpec, ...]:
    """The bank exchanges one foreign currency for another."""
    return (
        SlotSpec(
            code="received",
            name="Принято от клиента",
            order=0,
            currency_policy=SlotCurrencyPolicy.FOREIGN,
            threshold_basis=True,
            translations=_en("Received from client"),
        ),
        SlotSpec(
            code="issued",
            name="Выдано клиенту",
            order=1,
            currency_policy=SlotCurrencyPolicy.FOREIGN,
            amount_mode=SlotAmountMode.COMPUTED,
            computation=SlotComputation.MULTIPLY,
            stores_rate=True,
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
    form: str = OperationForm.AMOUNT,
    multiple: bool = False,
):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.INCOME,
        form=form,
        slots=_amount_slots(currency, multiple=multiple),
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
    form: str = OperationForm.AMOUNT,
    multiple: bool = False,
):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXPENSE,
        form=form,
        slots=_amount_slots(currency, multiple=multiple),
        template=_amount_template(-1),
        requires_client=requires_client,
        permission_code=PERMISSION,
        translations=translations,
    )


def _exchange(
    code: str,
    name: str,
    *,
    translations: dict[str, str],
    slots: tuple[SlotSpec, ...],
    rate_principle: str,
    print_configs: tuple[PrintBindingSpec, ...] = (),
):
    return OperationTypeSpec(
        code=code,
        name=name,
        kind=OperationKind.EXCHANGE,
        form=OperationForm.EXCHANGE,
        rate_principle=rate_principle,
        slots=slots,
        template=_exchange_template(),
        requires_client=True,
        permission_code=PERMISSION,
        translations=translations,
        print_configs=print_configs,
    )


def _cash_receipt(template: str) -> tuple[PrintBindingSpec, ...]:
    """The cash receipt template declared by ``printing_standard``."""
    return (PrintBindingSpec(document_type="cash_receipt", template=template),)


#: The baseline operation types declared to the operations engine.
OPERATION_TYPES: tuple[OperationTypeSpec, ...] = (
    # Income
    _income(
        "cash_replenishment",
        "Подкрепление кассы",
        translations=_en("Cash desk replenishment"),
        form=OperationForm.MULTI_CURRENCY,
        multiple=True,
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
        "Инкассация кассы",
        translations=_en("Cash collection"),
        form=OperationForm.MULTI_CURRENCY,
        multiple=True,
    ),
    # Exchange
    _exchange(
        "currency_sale",
        "Продажа валюты клиенту",
        translations=_en("Currency sale to client"),
        slots=_sale_slots(),
        rate_principle=OperationRatePrinciple.SELL,
        print_configs=_cash_receipt("cash_receipt_currency_sale"),
    ),
    _exchange(
        "currency_purchase",
        "Покупка валюты у клиента",
        translations=_en("Currency purchase from client"),
        slots=_purchase_slots(),
        rate_principle=OperationRatePrinciple.BUY,
        print_configs=_cash_receipt("cash_receipt_currency_purchase"),
    ),
    _exchange(
        "currency_conversion",
        "Конвертация валюты",
        translations=_en("Currency conversion"),
        slots=_conversion_slots(),
        rate_principle=OperationRatePrinciple.CONVERSION,
        print_configs=_cash_receipt("cash_receipt_currency_conversion"),
    ),
    _exchange(
        "fractional_currency_purchase",
        "Покупка дробной части валюты",
        translations=_en("Fractional currency purchase"),
        slots=_purchase_slots(),
        rate_principle=OperationRatePrinciple.BUY,
    ),
)
