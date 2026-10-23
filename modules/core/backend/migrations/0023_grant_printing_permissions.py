"""Grant the printing permissions to the shipped system roles.

The codes are inlined so the migration keeps behaving the same way if the
application catalog changes later (see
``docs/adr/0012-permission-catalog-aggregation.md``). Only the administrator
manages print templates; the roles that work with cash operations may print the
documents of the operations they can see.
"""

from django.db import migrations

ADDED = {
    "administrator": [
        "printing.templates.view",
        "printing.templates.manage",
        "printing.print",
    ],
    "branch_manager": ["printing.print"],
    "specialist": ["printing.print"],
    "cashier": ["printing.print"],
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
        ("core", "0022_banksettings_conversion_mode_currencyrate_units_and_more"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
