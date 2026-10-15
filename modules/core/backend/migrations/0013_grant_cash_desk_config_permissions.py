"""Grant the cash desk configuration permissions to the shipped system roles.

Data migration: adds the permissions introduced for cash desk configuration to the
``administrator`` and ``branch_manager`` roles. Roles are data, so the codes are
inlined here (see ``docs/adr/0012-permission-catalog-aggregation.md``); automatic
granting of new permissions to system roles is still deferred. Existing grants are
kept — the codes are only appended when missing.
"""

from django.db import migrations

ADDED = {
    "administrator": [
        "operations.view",
        "operations.config.manage",
        "operations.config.manage.branch",
        "core.currencies.config.manage",
        "core.currencies.config.manage.branch",
    ],
    "branch_manager": [
        "operations.view",
        "operations.config.manage.branch",
        "core.currencies.config.manage.branch",
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
        ("core", "0012_currencytemplate"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
