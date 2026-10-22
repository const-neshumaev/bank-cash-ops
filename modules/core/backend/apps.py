from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Core domain module: users, authentication and roles."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.core.backend"
    label = "core"
    verbose_name = _("Core")

    def ready(self):
        """Publish the module contracts to the in-process service registry."""
        from modules.common.backend import permissions_catalog
        from modules.common.contracts import registry
        from modules.core.backend.permission_codes import CATALOG
        from modules.core.backend.services import (
            BankSettingsService,
            CashDeskConfigService,
            OrgDirectoryService,
            RateTypeUsageGuardService,
            UserDirectoryService,
        )
        from modules.core.contracts import (
            BANK_SETTINGS,
            CASH_DESK_CONFIG,
            ORG_DIRECTORY,
            USER_DIRECTORY,
        )
        from modules.references.contracts import RATE_TYPE_USAGE_GUARD

        permissions_catalog.register(CATALOG)
        registry.register(USER_DIRECTORY, UserDirectoryService())
        registry.register(ORG_DIRECTORY, OrgDirectoryService())
        registry.register(CASH_DESK_CONFIG, CashDeskConfigService())
        registry.register(BANK_SETTINGS, BankSettingsService())
        registry.register(RATE_TYPE_USAGE_GUARD, RateTypeUsageGuardService())
