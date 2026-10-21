"""Grant the currency rate permissions to the shipped system roles.

The codes are inlined so the migration keeps behaving the same way if the
application catalog changes later (see
``docs/adr/0012-permission-catalog-aggregation.md``). Only the bank administrator
may manage bank-wide rates and the national bank rate; a branch manager manages
the rates of accessible branches and their cash desks; a cashier manages the
rates of the cash desk of an open shift.
"""

from django.db import migrations

ADDED = {
    "administrator": [
        "core.currency_rates.view",
        "core.currency_rates.manage",
        "core.currency_rates.manage.branch",
        "core.currency_rates.manage.cash_desk",
        "core.currency_rates.manage.official",
    ],
    "branch_manager": [
        "core.currency_rates.view",
        "core.currency_rates.manage.branch",
    ],
    "specialist": [
        "core.currency_rates.view",
    ],
    "cashier": [
        "core.currency_rates.view",
        "core.currency_rates.manage.cash_desk",
    ],
}


def grant(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for code, permissions in ADDED.items():
        role = Role.objects.filter(code=code).first()
        if role is None:
            continue
        current = list(role.permissions or [])
        merged = current + [permission for permission in permissions if permission not in current]
        if merged != current:
            role.permissions = merged
            role.save(update_fields=["permissions"])


def revoke(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for code, permissions in ADDED.items():
        role = Role.objects.filter(code=code).first()
        if role is None:
            continue
        remaining = [
            permission for permission in (role.permissions or []) if permission not in permissions
        ]
        role.permissions = remaining
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_alter_currencyrate_options_and_more"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
