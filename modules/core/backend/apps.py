from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Core domain module: users, authentication and roles."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.core.backend"
    label = "core"
    verbose_name = _("Core")

    def ready(self):
        """Publish the module contract to the in-process service registry."""
        from modules.common.contracts import registry
        from modules.core.backend.services import UserDirectoryService

        registry.register("core.users", UserDirectoryService())
