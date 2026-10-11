from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommonConfig(AppConfig):
    """Shared helpers reused by every BankCashOps module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.common.backend"
    label = "common"
    verbose_name = _("Common")
