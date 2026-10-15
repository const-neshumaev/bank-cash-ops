from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommonConfig(AppConfig):
    """Shared helpers reused by every BankCashOps module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.common.backend"
    label = "common"
    verbose_name = _("Common")

    def ready(self):
        """Wire the shared infrastructure: schemas and system checks.

        Importing the modules below registers the pre-migrate hook that creates
        the module schemas and the check that every module model lives in its own
        schema.
        """
        from modules.common.backend import checks, schemas  # noqa: F401
