from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OperationsConfig(AppConfig):
    """Operations domain module: the cash operation engine and registers."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.operations.backend"
    label = "operations"
    verbose_name = _("Operations")

    def ready(self):
        """Publish the operation type registry (the extension SPI) and the catalog."""
        from modules.common.backend import permissions_catalog
        from modules.common.contracts import registry
        from modules.operations.backend.permission_codes import CATALOG
        from modules.operations.backend.registry import operation_type_registry
        from modules.operations.contracts import OPERATION_TYPES_REGISTRY

        permissions_catalog.register(CATALOG)
        registry.register(OPERATION_TYPES_REGISTRY, operation_type_registry)
