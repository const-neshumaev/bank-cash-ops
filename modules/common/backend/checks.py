"""Django system checks that keep the module boundaries enforced in code.

Django cannot express "this table lives in the module schema" at the type level,
so this check turns a forgotten schema qualification into a failed
``manage.py check`` — and therefore into a failed ``runserver`` and the
``makemigrations --check`` step in CI — instead of a table quietly created in
``public``. (``migrate`` does not run system checks, so it is not a guard by
itself.) See ``docs/adr/0013-postgresql-schemas-per-module.md``.
"""

from django.apps import apps
from django.core.checks import Error, register

from modules.common.backend.schemas import MODULE_APP_PREFIX, table_schema


@register()
def module_models_use_own_schema(app_configs, **kwargs):
    """Check that every model of a module is stored in its module's schema."""
    errors = []
    configs = app_configs if app_configs is not None else apps.get_app_configs()
    for config in configs:
        if not config.name.startswith(MODULE_APP_PREFIX):
            continue
        for model in config.get_models(include_auto_created=True):
            meta = model._meta
            if meta.abstract or meta.proxy:
                continue
            if table_schema(meta.db_table) == config.label:
                continue
            errors.append(
                Error(
                    f"{meta.label} is not stored in the '{config.label}' PostgreSQL schema.",
                    hint=(
                        "Set Meta.db_table with "
                        f'qualified_table("{config.label}", "{meta.db_table}").'
                    ),
                    obj=model,
                    id="modules.E001",
                )
            )
    return errors
