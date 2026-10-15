"""PostgreSQL schemas: every module owns the tables it declares.

Django has no built-in support for database schemas, so a module qualifies each
of its tables with the module schema in ``Meta.db_table`` (use
:func:`qualified_table` for that) and the schema itself is created right before
migrations run. Creating the schemas from the pre-migrate hook keeps fresh
databases, the development stack and the test database in sync without hand-run
SQL, and needs no change to the already applied migrations.

See ``docs/adr/0013-postgresql-schemas-per-module.md`` and ``docs/modules.md``
for the rationale.
"""

from __future__ import annotations

from django.apps import apps
from django.db import connections
from django.db.backends.utils import split_identifier
from django.db.models.signals import pre_migrate
from django.dispatch import receiver

# App paths that belong to the product's own modules. Technical Django
# applications (contenttypes, auth, admin, sessions, ...) keep their tables in
# the default ``public`` schema.
MODULE_APP_PREFIX = "modules."

# Schemas already ensured in this process, keyed by (alias, database name), so
# the hook stays cheap while still covering a freshly created test database.
_ensured: set[tuple[str, str]] = set()


def qualified_table(schema: str, table: str) -> str:
    """Return a schema-qualified table name for use in ``Meta.db_table``.

    The value is pre-quoted so Django passes it through unchanged. Django also
    derives the auto-created many-to-many tables from this value, so those land
    in the same schema automatically.
    """
    return f'"{schema}"."{table}"'


def table_schema(table: str) -> str:
    """Return the schema of a (possibly qualified) table name.

    An unqualified name yields an empty string. Understands both the
    ``"schema"."table"`` form written in models and the ``schema"."table`` form
    Django derives for auto-created many-to-many tables.
    """
    return split_identifier(table)[0]


def module_schemas() -> list[str]:
    """Return the schemas owned by the installed modules, sorted and unique.

    A module's schema is its app label; applications without models (for
    example ``operations_standard``) own no schema.
    """
    return sorted(
        {
            config.label
            for config in apps.get_app_configs()
            if config.name.startswith(MODULE_APP_PREFIX) and config.models
        }
    )


def create_module_schemas(using: str = "default") -> None:
    """Create every module schema of the given connection if it does not exist."""
    connection = connections[using]
    key = (using, connection.settings_dict["NAME"])
    if key in _ensured:
        return
    with connection.cursor() as cursor:
        for schema in module_schemas():
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    _ensured.add(key)


@receiver(pre_migrate, dispatch_uid="modules.common.backend.schemas.create_module_schemas")
def _create_module_schemas(sender, using, **kwargs):
    """Ensure the module schemas exist before any migration creates tables."""
    create_module_schemas(using)
