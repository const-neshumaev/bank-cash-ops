from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PrintingStandardConfig(AppConfig):
    """Baseline print forms declared as data for the printing engine.

    The module owns no tables: it declares document types and templates through
    the ``printing`` SPI, and the ``printing`` module persists them (see the
    ``sync_print_templates`` command).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.printing_standard.backend"
    label = "printing_standard"
    verbose_name = _("Standard print forms")

    def ready(self):
        """Declare the baseline document types and templates."""
        from modules.common.contracts import registry
        from modules.printing.contracts import PRINT_TEMPLATE_REGISTRY
        from modules.printing_standard.backend.declarations import DOCUMENT_TYPES, TEMPLATES
        from modules.printing_standard.backend.providers import CashReceiptProvider

        templates = registry.get(PRINT_TEMPLATE_REGISTRY)
        for spec in DOCUMENT_TYPES:
            if templates.has_document_type(spec.code):
                continue
            templates.register_document_type(spec)
        provider = CashReceiptProvider()
        for spec in TEMPLATES:
            if templates.has_template(spec.code):
                continue
            templates.register_template(spec, provider)
