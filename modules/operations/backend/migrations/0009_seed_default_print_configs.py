"""Bind the baseline cash receipt templates to the shipped exchange operations.

New installations get the same defaults from ``sync_operation_types`` (the
operation type declarations carry them). This data migration covers databases
where the operation types were created before the printing feature existed. It
only adds a binding when the type has no printed documents configured, so an
administrator's choice is never overwritten.
"""

from django.db import migrations

DEFAULT_BINDINGS = {
    "currency_purchase": "cash_receipt_currency_purchase",
    "currency_sale": "cash_receipt_currency_sale",
    "currency_conversion": "cash_receipt_currency_conversion",
}

DOCUMENT_TYPE = "cash_receipt"


def seed(apps, schema_editor):
    OperationType = apps.get_model("operations", "OperationType")
    Config = apps.get_model("operations", "OperationPrintConfig")
    for operation_code, template_code in DEFAULT_BINDINGS.items():
        operation_type = OperationType.objects.filter(code=operation_code).first()
        if operation_type is None:
            continue
        if Config.objects.filter(operation_type=operation_type).exists():
            continue
        Config.objects.create(
            operation_type=operation_type,
            document_type=DOCUMENT_TYPE,
            template_code=template_code,
            is_active=True,
        )


def unseed(apps, schema_editor):
    Config = apps.get_model("operations", "OperationPrintConfig")
    Config.objects.filter(
        document_type=DOCUMENT_TYPE, template_code__in=set(DEFAULT_BINDINGS.values())
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0008_operationprintconfig"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
