"""Baseline print forms shipped with the product.

The module declares one printed document type (a cash receipt) and three forms
for the baseline exchange operations. The Word files under ``templates/`` are
sample layouts; a bank downloads, edits and uploads them through the
administration UI. A bank-specific extension declares additional forms through
the same SPI.
"""

from __future__ import annotations

from pathlib import Path

from modules.printing.contracts import PrintDocumentTypeSpec, PrintTemplateSpec

CASH_RECEIPT = "cash_receipt"
CASH_RECEIPT_PROVIDER = "cash_receipt_exchange"

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

#: Printed document types declared by the module.
DOCUMENT_TYPES: tuple[PrintDocumentTypeSpec, ...] = (
    PrintDocumentTypeSpec(
        code=CASH_RECEIPT,
        name="Кассовый чек",
        description="Документ, подтверждающий кассовую операцию с клиентом.",
        translations={"en": "Cash receipt"},
        numbering_scope="bank",
    ),
)

#: Print forms declared by the module.
TEMPLATES: tuple[PrintTemplateSpec, ...] = (
    PrintTemplateSpec(
        code="cash_receipt_currency_purchase",
        name="Кассовый чек — покупка валюты у клиента",
        document_type=CASH_RECEIPT,
        provider=CASH_RECEIPT_PROVIDER,
        description="Чек по операции «Покупка валюты у клиента».",
        translations={"en": "Cash receipt — currency purchase from client"},
        default_file_path=str(_TEMPLATES_DIR / "cash_receipt_currency_purchase.docx"),
    ),
    PrintTemplateSpec(
        code="cash_receipt_currency_sale",
        name="Кассовый чек — продажа валюты клиенту",
        document_type=CASH_RECEIPT,
        provider=CASH_RECEIPT_PROVIDER,
        description="Чек по операции «Продажа валюты клиенту».",
        translations={"en": "Cash receipt — currency sale to client"},
        default_file_path=str(_TEMPLATES_DIR / "cash_receipt_currency_sale.docx"),
    ),
    PrintTemplateSpec(
        code="cash_receipt_currency_conversion",
        name="Кассовый чек — конвертация валюты",
        document_type=CASH_RECEIPT,
        provider=CASH_RECEIPT_PROVIDER,
        description="Чек по операции «Конвертация валюты».",
        translations={"en": "Cash receipt — currency conversion"},
        default_file_path=str(_TEMPLATES_DIR / "cash_receipt_currency_conversion.docx"),
    ),
)
