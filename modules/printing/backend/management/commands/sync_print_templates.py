"""Materialise the print forms declared by the installed modules."""

from django.core.management.base import BaseCommand

from modules.printing.backend.sync import sync_print_templates


class Command(BaseCommand):
    """Create or update the declared print document types and templates."""

    help = "Create or update the print forms declared by the installed modules."

    def handle(self, *args, **options):
        document_types, templates = sync_print_templates()
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {document_types} print document type(s) "
                f"and {templates} print template(s)."
            )
        )
