from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OperationsStandardConfig(AppConfig):
    """Baseline cash operations declared as data for the operations engine.

    This module owns no tables: it declares its operation types through the
    ``operations`` SPI, and the ``operations`` module persists them (see the
    ``sync_operation_types`` command).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.operations_standard.backend"
    label = "operations_standard"
    verbose_name = _("Standard operations")

    def ready(self):
        """Declare the baseline operation types to the operations engine."""
        from modules.common.contracts import registry
        from modules.operations.contracts import OPERATION_TYPES_REGISTRY
        from modules.operations_standard.backend.declarations import OPERATION_TYPES

        operation_types = registry.get(OPERATION_TYPES_REGISTRY)
        for spec in OPERATION_TYPES:
            if operation_types.has(spec.code):
                continue
            operation_types.register(spec)
