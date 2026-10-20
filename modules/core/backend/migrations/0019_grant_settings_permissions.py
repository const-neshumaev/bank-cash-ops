"""Grant the bank settings, base values and operation type settings permissions.

Data migration: the codes are inlined so the migration keeps behaving the same
way if the application catalogs change later (see
``docs/adr/0012-permission-catalog-aggregation.md``). Reading base values and the
currency dictionary is granted to every shipped role; managing them stays with
the administrator.
"""

from django.db import migrations

ADDED = {
    "administrator": [
        "core.bank_settings.manage",
        "core.base_values.view",
        "core.base_values.manage",
        "operations.types.manage",
        "references.view",
        "references.manage",
    ],
    "branch_manager": [
        "core.base_values.view",
        "references.view",
    ],
    "specialist": [
        "core.base_values.view",
        "references.view",
    ],
    "cashier": [
        "core.base_values.view",
        "references.view",
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
        ("core", "0018_basevalue"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
