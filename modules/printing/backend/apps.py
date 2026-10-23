from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PrintingConfig(AppConfig):
    """Print forms, numbering and rendered documents."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.printing.backend"
    label = "printing"
    verbose_name = _("Printing")

    def ready(self):
        """Publish the template registry and the rendering service."""
        from modules.common.backend import permissions_catalog
        from modules.common.contracts import registry
        from modules.printing.backend.permission_codes import CATALOG
        from modules.printing.backend.registry import print_template_registry
        from modules.printing.backend.rendering import print_document_service
        from modules.printing.contracts import (
            PRINT_DOCUMENT_SERVICE,
            PRINT_TEMPLATE_REGISTRY,
        )

        permissions_catalog.register(CATALOG)
        registry.register(PRINT_TEMPLATE_REGISTRY, print_template_registry)
        registry.register(PRINT_DOCUMENT_SERVICE, print_document_service)
