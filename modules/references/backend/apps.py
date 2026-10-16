from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReferencesConfig(AppConfig):
    """System reference data module: currencies and rate types."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.references.backend"
    label = "references"
    verbose_name = _("Reference data")

    def ready(self):
        """Publish the module contract and permission catalog."""
        from modules.common.backend import permissions_catalog
        from modules.common.contracts import registry
        from modules.references.backend.permission_codes import CATALOG
        from modules.references.backend.services import ReferenceDirectoryService
        from modules.references.contracts import REFERENCE_DIRECTORY

        permissions_catalog.register(CATALOG)
        registry.register(REFERENCE_DIRECTORY, ReferenceDirectoryService())
